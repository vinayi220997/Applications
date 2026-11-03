"""Schedule the scan with the operating system's own scheduler, so it runs even when the app is closed.

Windows: Task Scheduler (task 'JobRadar\\DailyScan'), set to run as soon as possible if the PC was off.
macOS / Linux: a line in the user's crontab.
"""
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime

from .config import ROOT, DATA_DIR, ensure_dirs

TASK_NAME = r"JobRadar\DailyScan"
CRON_TAG = "# jobradar-scan"
STATE = DATA_DIR / "schedule.json"
DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
WIN_DAYS = {"MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday", "FRI": "Friday",
            "SAT": "Saturday", "SUN": "Sunday"}


def _python():
    exe = sys.executable
    if os.name == "nt":
        pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")   # no console window
        if os.path.exists(pyw):
            return pyw
    return exe


def _runner():
    """A launcher script inside the project, so the task always runs from the right folder."""
    ensure_dirs()
    if os.name == "nt":
        path = ROOT / "run_scan.bat"
        log_ = DATA_DIR / "scheduled.log"
        path.write_text(f'@echo off\r\ncd /d "{ROOT}"\r\nif "%~1"=="" goto all\r\n'
                        f'"{_python()}" -m jobradar run --schedule %~1 >> "{log_}" 2>&1\r\ngoto :eof\r\n'
                        f':all\r\n"{_python()}" -m jobradar run --trigger scheduled >> "{log_}" 2>&1\r\n', encoding="utf-8")
    else:
        path = ROOT / "run_scan.sh"
        path.write_text(f'#!/bin/sh\ncd "{ROOT}"\nif [ -z "$1" ]; then "{_python()}" -m jobradar run --trigger scheduled; else "{_python()}" -m jobradar run --schedule "$1"; fi >> "{DATA_DIR / "scheduled.log"}" 2>&1\n',
                        encoding="utf-8")
        os.chmod(path, 0o755)
    return path


def _validate(time_str, days, every_hours):
    hh, mm = [int(x) for x in time_str.split(":")]
    assert 0 <= hh < 24 and 0 <= mm < 60, "time must be HH:MM"
    days = [d.upper()[:3] for d in (days or DAYS)]
    assert all(d in DAYS for d in days) and days, "days must be MON..SUN"
    if every_hours:
        assert int(every_hours) in (1, 2, 3, 4, 6, 8, 12), "repeat every 1, 2, 3, 4, 6, 8 or 12 hours"
    return hh, mm, days


def _windows_xml(hh, mm, days, every_hours, runner):
    start = datetime.now().strftime("%Y-%m-%d") + f"T{hh:02d}:{mm:02d}:00"
    if len(days) == 7:
        trig = "<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>"
    else:
        d = "".join(f"<{WIN_DAYS[x]} />" for x in days)
        trig = f"<ScheduleByWeek><DaysOfWeek>{d}</DaysOfWeek><WeeksInterval>1</WeeksInterval></ScheduleByWeek>"
    rep = ""
    if every_hours:
        rep = f"<Repetition><Interval>PT{int(every_hours)}H</Interval><Duration>P1D</Duration><StopAtDurationEnd>true</StopAtDurationEnd></Repetition>"
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Job Radar: scan job sources and send the daily report</Description></RegistrationInfo>
  <Triggers><CalendarTrigger>{rep}<StartBoundary>{start}</StartBoundary><Enabled>true</Enabled>{trig}</CalendarTrigger></Triggers>
  <Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <Enabled>true</Enabled>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author"><Exec><Command>"{runner}"</Command><WorkingDirectory>{ROOT}</WorkingDirectory></Exec></Actions>
</Task>"""


def install(time_str="08:00", days=None, every_hours=None):
    """Create or replace the schedule. Returns (ok, message)."""
    try:
        hh, mm, days = _validate(time_str, days, every_hours)
    except (AssertionError, ValueError) as e:
        return False, f"Invalid schedule: {e}"
    runner = _runner()
    system = platform.system()
    try:
        if system == "Windows":
            xml = _windows_xml(hh, mm, days, every_hours, runner)
            with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-16") as f:
                f.write(xml)
                tmp = f.name
            r = subprocess.run(["schtasks", "/Create", "/TN", TASK_NAME, "/XML", tmp, "/F"],
                               capture_output=True, text=True)
            os.unlink(tmp)
            if r.returncode != 0:
                return False, (r.stderr or r.stdout).strip()
        else:
            dow = "*" if len(days) == 7 else ",".join(str((DAYS.index(d) + 1) % 7) for d in days)
            hour = f"{hh}" if not every_hours else f"{hh}-23/{int(every_hours)}"
            line = f"{mm} {hour} * * {dow} {runner} {CRON_TAG}"
            cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
            lines = [l for l in cur.splitlines() if CRON_TAG not in l] + [line]
            subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True, check=True)
    except FileNotFoundError as e:
        return False, f"System scheduler not available: {e}"
    except subprocess.CalledProcessError as e:
        return False, f"Could not update the schedule: {e}"
    state = {"enabled": True, "time": f"{hh:02d}:{mm:02d}", "days": days, "every_hours": every_hours,
             "installed_at": datetime.now().isoformat(timespec="seconds"), "system": system}
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return True, describe(state)


def remove():
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], capture_output=True, text=True)
        else:
            cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
            lines = [l for l in cur.splitlines() if CRON_TAG not in l]
            subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True)
    except FileNotFoundError:
        pass
    if STATE.exists():
        STATE.unlink()
    return True, "Schedule removed. Scans now run only when you start them."


def status():
    if not STATE.exists():
        return {"enabled": False, "text": "Not scheduled. Scans run only when you start them."}
    s = json.loads(STATE.read_text(encoding="utf-8"))
    s["text"] = describe(s)
    if platform.system() == "Windows":
        r = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"], capture_output=True, text=True)
        if r.returncode != 0:
            s["enabled"] = False
            s["text"] = "The saved schedule is missing from Windows Task Scheduler. Save it again."
        else:
            nxt = [l.split(":", 1)[1].strip() for l in r.stdout.splitlines() if l.lower().startswith("next run time")]
            if nxt:
                s["next_run"] = nxt[0]
    return s


def describe(s):
    days = s.get("days") or DAYS
    dtxt = "every day" if len(days) == 7 else ("weekdays" if days == DAYS[:5] else ", ".join(d.title() for d in days))
    rep = f", then every {s['every_hours']} hours until midnight" if s.get("every_hours") else ""
    return f"Runs {dtxt} at {s.get('time')}{rep} (your computer's local time). If the computer was off or asleep at that time, the scan runs as soon as it's back on."


# ------------------------------------------------------------------ one OS task per schedule (v1.6)
TASK_PREFIX = "JobRadar\\Schedule-"
CRON_SCHED_TAG = "# jobradar-schedule-"


def _task_xml(hh, mm, days, every_hours, runner, sid, offset_min, desc):
    sign = "+" if offset_min >= 0 else "-"
    o = abs(int(offset_min))
    start = datetime.now().strftime("%Y-%m-%d") + f"T{hh:02d}:{mm:02d}:00{sign}{o // 60:02d}:{o % 60:02d}"
    if len(days) == 7:
        trig = "<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>"
    else:
        d = "".join(f"<{WIN_DAYS[x]} />" for x in days)
        trig = f"<ScheduleByWeek><DaysOfWeek>{d}</DaysOfWeek><WeeksInterval>1</WeeksInterval></ScheduleByWeek>"
    rep = ""
    if every_hours:
        until_midnight = 24 * 60 - (hh * 60 + mm)
        rep = (f"<Repetition><Interval>PT{int(every_hours)}H</Interval><Duration>PT{until_midnight}M</Duration>"
               f"<StopAtDurationEnd>false</StopAtDurationEnd></Repetition>")
    desc = (desc or "").replace("&", "and").replace("<", "").replace(">", "")
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Job Radar schedule: {desc}</Description></RegistrationInfo>
  <Triggers><CalendarTrigger>{rep}<StartBoundary>{start}</StartBoundary><Enabled>true</Enabled>{trig}</CalendarTrigger></Triggers>
  <Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <Enabled>true</Enabled>
    <ExecutionTimeLimit>PT3H</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author"><Exec><Command>"{runner}"</Command><Arguments>{int(sid)}</Arguments><WorkingDirectory>{ROOT}</WorkingDirectory></Exec></Actions>
</Task>"""


def install_task(sid, time_str, days, every_hours, offset_min, desc=""):
    """Create/replace the OS task for one schedule. offset_min: the schedule time zone's UTC offset."""
    try:
        hh, mm, days = _validate(time_str, days, every_hours)
    except (AssertionError, ValueError) as e:
        return False, f"Invalid schedule: {e}"
    runner = _runner()
    try:
        if platform.system() == "Windows":
            xml = _task_xml(hh, mm, days, every_hours, runner, sid, offset_min, desc)
            with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-16") as f:
                f.write(xml)
                tmp = f.name
            r = subprocess.run(["schtasks", "/Create", "/TN", f"{TASK_PREFIX}{int(sid)}", "/XML", tmp, "/F"],
                               capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            os.unlink(tmp)
            if r.returncode != 0:
                return False, (r.stderr or r.stdout).strip()
        else:
            local_off = int((datetime.now().astimezone().utcoffset().total_seconds()) // 60)
            t = (hh * 60 + mm - offset_min + local_off) % (24 * 60)
            lh, lm = divmod(t, 60)
            dow = "*" if len(days) == 7 else ",".join(str((DAYS.index(d) + 1) % 7) for d in days)
            hour = f"{lh}" if not every_hours else f"{lh}-23/{int(every_hours)}"
            line = f"{lm} {hour} * * {dow} {runner} {int(sid)} {CRON_SCHED_TAG}{int(sid)}"
            cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
            lines = [l for l in cur.splitlines() if not l.endswith(f"{CRON_SCHED_TAG}{int(sid)}")] + [line]
            subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True, check=True)
    except FileNotFoundError as e:
        return False, f"System scheduler not available: {e}"
    except subprocess.CalledProcessError as e:
        return False, f"Could not update the schedule: {e}"
    return True, "ok"


def remove_task(sid):
    try:
        if platform.system() == "Windows":
            subprocess.run(["schtasks", "/Delete", "/TN", f"{TASK_PREFIX}{int(sid)}", "/F"], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
            lines = [l for l in cur.splitlines() if not l.endswith(f"{CRON_SCHED_TAG}{int(sid)}")]
            subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True)
    except FileNotFoundError:
        pass


def installed_ids():
    """Schedule ids that have an OS task, or None if the system scheduler can't be read."""
    try:
        if platform.system() == "Windows":
            r = subprocess.run(["schtasks", "/Query", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode != 0:
                return None
            out = set()
            for line in r.stdout.splitlines():
                name = line.split(",")[0].strip('"')
                if name.lower().startswith("\\jobradar\\schedule-"):
                    try:
                        out.add(int(name.rsplit("-", 1)[1]))
                    except ValueError:
                        pass
            return out
        cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if cur.returncode not in (0, 1):
            return None
        return {int(l.rsplit(CRON_SCHED_TAG, 1)[1]) for l in cur.stdout.splitlines() if CRON_SCHED_TAG in l}
    except (FileNotFoundError, ValueError):
        return None


def legacy_state():
    """The pre-1.6 single global schedule, if one was saved."""
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
    return None
