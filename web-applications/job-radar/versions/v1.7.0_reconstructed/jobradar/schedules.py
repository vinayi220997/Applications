"""Schedules (v1.6): any number of named schedules, each linked to one or more job search cards.

* A 'card' schedule belongs to one card (made from the card's Schedule button).
* A 'shared' schedule is made in the Schedule section and can trigger several cards.
Each enabled schedule with at least one card gets its own OS task (Windows Task Scheduler / cron) that runs
`python -m jobradar run --schedule <id>`. Disabled cards never run automatically; disabled schedules trigger nothing.
"""
import json
from datetime import datetime, timedelta, timezone

from . import db as dbm
from . import scheduler
from .normalize import iso, now_utc, parse_date

DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
DAY_NAMES = {"MON": "Mon", "TUE": "Tue", "WED": "Wed", "THU": "Thu", "FRI": "Fri", "SAT": "Sat", "SUN": "Sun"}
TIMEZONES = [("Asia/Kolkata", "India (IST)"), ("UTC", "UTC"), ("Asia/Dubai", "Dubai (GST)"), ("Asia/Singapore", "Singapore (SGT)"),
             ("Europe/London", "London"), ("Europe/Berlin", "Berlin / Paris"), ("America/New_York", "New York"),
             ("America/Los_Angeles", "Los Angeles"), ("Australia/Sydney", "Sydney")]
FIXED = {"Asia/Kolkata": 330, "Asia/Calcutta": 330, "UTC": 0, "Asia/Dubai": 240, "Asia/Singapore": 480, "Europe/London": 0,
         "Europe/Berlin": 60, "America/New_York": -300, "America/Los_Angeles": -480, "Australia/Sydney": 600}
DUPLICATE_WINDOW_MIN = 15


class ScheduleError(Exception):
    pass


class Conflict(Exception):
    def __init__(self, conflicts):
        super().__init__("duplicate schedules")
        self.conflicts = conflicts


def tz(name):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name or "Asia/Kolkata")
    except Exception:
        return timezone(timedelta(minutes=FIXED.get(name, 330)), name)


def tz_offset_min(name, when=None):
    d = (when or datetime.now(timezone.utc)).astimezone(tz(name))
    return int(d.utcoffset().total_seconds() // 60)


def _row(r, conn=None):
    s = dbm.row_to_dict(r)
    s["days"] = dbm.jload(s.pop("days_json"), DAYS) or DAYS
    s["enabled"] = bool(s["enabled"])
    s["is_default"] = bool(s["is_default"])
    if conn is not None:
        s["cards"] = [dbm.row_to_dict(x) for x in conn.execute(
            """SELECT p.id, p.name, p.active, sc.allow_duplicate FROM schedule_cards sc JOIN profiles p ON p.id=sc.profile_id
               WHERE sc.schedule_id=? ORDER BY p.name""", (s["id"],))]
    return s


def get(conn, sid):
    r = conn.execute("SELECT * FROM schedules WHERE id=?", (sid,)).fetchone()
    return _row(r, conn) if r else None


# ------------------------------------------------------------------ timing
def occurrences(s, start, end):
    """All run times (aware, in the schedule's zone) between start and end."""
    z = tz(s.get("timezone"))
    hh, mm = [int(x) for x in (s.get("time") or "09:00").split(":")]
    days = s.get("days") or DAYS
    every = s.get("every_hours") if s.get("frequency") == "hourly" else None
    out = []
    d0 = start.astimezone(z).date()
    for i in range(0, 9):
        day = d0 + timedelta(days=i)
        if DAYS[day.weekday()] not in days:
            continue
        t = datetime(day.year, day.month, day.day, hh, mm, tzinfo=z)
        times = [t]
        if every:
            k = 1
            while (t + timedelta(hours=every * k)).date() == day:
                times.append(t + timedelta(hours=every * k))
                k += 1
        out += [x for x in times if start < x <= end]
    return out


def next_run(s, now=None):
    if not s.get("enabled"):
        return None
    now = now or datetime.now(timezone.utc)
    occ = occurrences(s, now, now + timedelta(days=8))
    return min(occ) if occ else None


def describe(s):
    days = s.get("days") or DAYS
    hh, mm = [int(x) for x in (s.get("time") or "09:00").split(":")]
    t = datetime(2000, 1, 1, hh, mm).strftime("%I:%M %p").lstrip("0")
    dtxt = "Daily" if len(days) == 7 else ("Weekdays" if days == DAYS[:5] else ("Weekends" if days == ["SAT", "SUN"] else ", ".join(DAY_NAMES[d] for d in days)))
    zone = dict(TIMEZONES).get(s.get("timezone"), s.get("timezone"))
    if s.get("frequency") == "hourly" and s.get("every_hours"):
        return f"{dtxt}, every {s['every_hours']} h from {t} until midnight ({zone})"
    return f"{dtxt} at {t} ({zone})"


def fmt_local(d, zone_name):
    if not d:
        return None
    x = d.astimezone(tz(zone_name))
    return x.strftime("%a %d %b, %I:%M %p").replace(" 0", " ")


# ------------------------------------------------------------------ listing
_OS_CACHE = {"at": 0, "ids": None}


def _os_ids():
    import time
    if time.time() - _OS_CACHE["at"] > 20:
        _OS_CACHE.update(at=time.time(), ids=scheduler.installed_ids())
    return _OS_CACHE["ids"]


def list_all(conn, with_os=True):
    os_ids = _os_ids() if with_os else None
    out = []
    for r in conn.execute("SELECT * FROM schedules ORDER BY kind DESC, name"):
        s = _row(r, conn)
        nr = next_run(s) if s["cards"] else None
        s["next_run"] = iso(nr) if nr else None
        s["next_run_text"] = fmt_local(nr, s["timezone"]) if nr else None
        s["text"] = describe(s)
        last = conn.execute("""SELECT e.*, p.name AS card FROM executions e LEFT JOIN profiles p ON p.id=e.profile_id
                               WHERE e.schedule_id=? ORDER BY e.id DESC LIMIT 1""", (s["id"],)).fetchone()
        s["last"] = dbm.row_to_dict(last) if last else None
        s["history"] = [dbm.row_to_dict(x) for x in conn.execute(
            """SELECT e.id, e.started_at, e.finished_at, e.status, e.jobs_found, e.new_jobs, e.error, p.name AS card
               FROM executions e LEFT JOIN profiles p ON p.id=e.profile_id WHERE e.schedule_id=? ORDER BY e.id DESC LIMIT 30""", (s["id"],))]
        needs_task = s["enabled"] and bool(s["cards"])
        s["os_ok"] = None if os_ids is None else ((s["id"] in os_ids) == needs_task)
        out.append(s)
    return out


def for_card(conn, pid):
    rows = conn.execute("""SELECT s.* FROM schedules s JOIN schedule_cards sc ON sc.schedule_id=s.id
                           WHERE sc.profile_id=? ORDER BY s.name""", (pid,)).fetchall()
    out = []
    for r in rows:
        s = _row(r)
        nr = next_run(s)
        s.update(next_run=iso(nr) if nr else None, next_run_text=fmt_local(nr, s["timezone"]) if nr else None, text=describe(s))
        out.append(s)
    return out


# ------------------------------------------------------------------ saving
def clean(body):
    name = (body.get("name") or "").strip()[:80]
    if not name:
        raise ScheduleError("Give the schedule a name, for example 'Morning search'.")
    freq = body.get("frequency") or "daily"
    if freq not in ("daily", "weekly", "hourly"):
        raise ScheduleError("Frequency must be daily, weekly or every few hours.")
    t = (body.get("time") or "09:00").strip()
    try:
        hh, mm = [int(x) for x in t.split(":")]
        assert 0 <= hh < 24 and 0 <= mm < 60
    except (ValueError, AssertionError):
        raise ScheduleError("Time must be like 09:00.")
    days = [d.upper()[:3] for d in (body.get("days") or DAYS)]
    if freq == "daily":
        days = DAYS[:]
    if not days or any(d not in DAYS for d in days):
        raise ScheduleError("Pick at least one day.")
    days = [d for d in DAYS if d in days]
    every = None
    if freq == "hourly":
        try:
            every = int(body.get("every_hours") or 0)
        except ValueError:
            every = 0
        if every not in (1, 2, 3, 4, 6, 8, 12):
            raise ScheduleError("Repeat every 1, 2, 3, 4, 6, 8 or 12 hours.")
    zone = body.get("timezone") or "Asia/Kolkata"
    if zone not in dict(TIMEZONES) and zone not in FIXED:
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(zone)
        except Exception:
            raise ScheduleError(f"Unknown time zone '{zone}'.")
    return {"name": name, "frequency": freq, "time": f"{hh:02d}:{mm:02d}", "days": days, "every_hours": every,
            "timezone": zone, "enabled": bool(body.get("enabled", True)), "kind": body.get("kind") if body.get("kind") in ("card", "shared") else "shared"}


def conflicts(conn, card_ids, exclude_sid=None, candidate=None):
    """Cards that would also be triggered by another enabled schedule."""
    out = []
    for pid in card_ids:
        others = [dbm.row_to_dict(r) for r in conn.execute(
            """SELECT s.id, s.name FROM schedules s JOIN schedule_cards sc ON sc.schedule_id=s.id
               WHERE sc.profile_id=? AND s.enabled=1 AND s.id IS NOT ?""", (pid, exclude_sid))]
        if others and (candidate is None or candidate.get("enabled", True)):
            name = conn.execute("SELECT name FROM profiles WHERE id=?", (pid,)).fetchone()
            out.append({"card_id": pid, "card": name["name"] if name else f"#{pid}", "schedules": [o["name"] for o in others]})
    return out


def save(conn, body, sid=None):
    s = clean(body)
    card_ids = [int(x) for x in (body.get("card_ids") or [])]
    valid = {r["id"] for r in conn.execute("SELECT id FROM profiles")}
    card_ids = [c for c in dict.fromkeys(card_ids) if c in valid]
    if s["kind"] == "card" and len(card_ids) != 1:
        raise ScheduleError("A card schedule belongs to exactly one card.")
    confl = conflicts(conn, card_ids, sid, s)
    if confl and not body.get("confirm_duplicates"):
        raise Conflict(confl)
    now = iso(now_utc())
    if sid:
        if not get(conn, sid):
            raise ScheduleError("That schedule no longer exists.")
        conn.execute("""UPDATE schedules SET name=?, kind=?, frequency=?, time=?, days_json=?, every_hours=?, timezone=?, enabled=?, updated_at=?
                        WHERE id=?""", (s["name"], s["kind"], s["frequency"], s["time"], json.dumps(s["days"]), s["every_hours"],
                                        s["timezone"], int(s["enabled"]), now, sid))
    else:
        sid = conn.execute("""INSERT INTO schedules(name, kind, frequency, time, days_json, every_hours, timezone, enabled, created_at, updated_at)
                              VALUES (?,?,?,?,?,?,?,?,?,?)""", (s["name"], s["kind"], s["frequency"], s["time"], json.dumps(s["days"]),
                                                                s["every_hours"], s["timezone"], int(s["enabled"]), now, now)).lastrowid
    if "card_ids" in body:
        set_cards(conn, sid, card_ids, {c["card_id"] for c in confl} if body.get("confirm_duplicates") else set())
    if "is_default" in body:
        set_default(conn, sid if body.get("is_default") else None, only_if=sid)
    return sid, confl


def set_cards(conn, sid, card_ids, allow_dup=()):
    from .cards import log
    old = {r["profile_id"] for r in conn.execute("SELECT profile_id FROM schedule_cards WHERE schedule_id=?", (sid,))}
    name = conn.execute("SELECT name FROM schedules WHERE id=?", (sid,)).fetchone()["name"]
    for pid in old - set(card_ids):
        conn.execute("DELETE FROM schedule_cards WHERE schedule_id=? AND profile_id=?", (sid, pid))
        log(conn, pid, "schedule", f"Removed from schedule “{name}”")
    for pid in card_ids:
        conn.execute("INSERT OR IGNORE INTO schedule_cards(schedule_id, profile_id) VALUES (?,?)", (sid, pid))
        conn.execute("UPDATE schedule_cards SET allow_duplicate=? WHERE schedule_id=? AND profile_id=?", (1 if pid in allow_dup else 0, sid, pid))
        if pid not in old:
            log(conn, pid, "schedule", f"Added to schedule “{name}”")


def set_default(conn, sid, only_if=None):
    if sid:
        conn.execute("UPDATE schedules SET is_default=CASE WHEN id=? THEN 1 ELSE 0 END", (sid,))
    elif only_if:
        conn.execute("UPDATE schedules SET is_default=0 WHERE id=?", (only_if,))


def set_enabled(conn, sid, on):
    from .cards import log
    s = get(conn, sid)
    if not s:
        raise ScheduleError("That schedule no longer exists.")
    if on:
        confl = conflicts(conn, [c["id"] for c in s["cards"] if not c["allow_duplicate"]], sid)
        if confl:
            raise Conflict(confl)
    conn.execute("UPDATE schedules SET enabled=?, updated_at=? WHERE id=?", (1 if on else 0, iso(now_utc()), sid))
    for c in s["cards"]:
        log(conn, c["id"], "schedule", f"Schedule “{s['name']}” {'enabled' if on else 'paused'}")


def delete(conn, sid):
    from .cards import log
    s = get(conn, sid)
    if not s:
        return
    for c in s["cards"]:
        log(conn, c["id"], "schedule", f"Schedule “{s['name']}” deleted")
    conn.execute("DELETE FROM schedule_cards WHERE schedule_id=?", (sid,))
    conn.execute("DELETE FROM schedules WHERE id=?", (sid,))
    scheduler.remove_task(sid)
    _OS_CACHE["at"] = 0


def default_schedule(conn):
    r = conn.execute("SELECT * FROM schedules WHERE is_default=1 LIMIT 1").fetchone()
    return _row(r) if r else None


# ------------------------------------------------------------------ OS tasks
def sync_os(conn):
    """Make the OS tasks match the schedules. Returns a list of problems (empty when all is well)."""
    problems = []
    for r in conn.execute("SELECT * FROM schedules"):
        s = _row(r, conn)
        if s["enabled"] and s["cards"]:
            ok, msg = scheduler.install_task(s["id"], s["time"], s["days"], s["every_hours"] if s["frequency"] == "hourly" else None,
                                             tz_offset_min(s["timezone"]), f"{s['name']} - {describe(s)}")
            if not ok:
                problems.append(f"{s['name']}: {msg}")
        else:
            scheduler.remove_task(s["id"])
    ids = {r["id"] for r in conn.execute("SELECT id FROM schedules")}
    for orphan in (scheduler.installed_ids() or set()) - ids:
        scheduler.remove_task(orphan)
    _OS_CACHE["at"] = 0
    return problems


def migrate_legacy(conn):
    """Turn the pre-1.6 single global schedule into a 'Default schedule' linked to every card."""
    st = scheduler.legacy_state()
    if not st or not st.get("enabled"):
        return None
    if conn.execute("SELECT COUNT(*) n FROM schedules").fetchone()["n"]:
        scheduler.remove()
        return None
    body = {"name": "Default schedule", "frequency": "hourly" if st.get("every_hours") else ("daily" if len(st.get("days") or DAYS) == 7 else "weekly"),
            "time": st.get("time") or "08:00", "days": st.get("days") or DAYS, "every_hours": st.get("every_hours"),
            "timezone": "Asia/Kolkata", "kind": "shared", "enabled": True,
            "card_ids": [r["id"] for r in conn.execute("SELECT id FROM profiles")], "confirm_duplicates": True, "is_default": True}
    sid, _ = save(conn, body)
    conn.commit()
    scheduler.remove()           # old JobRadar\DailyScan task and schedule.json
    sync_os(conn)
    return sid


# ------------------------------------------------------------------ running
def cards_to_run(conn, sid):
    """For a schedule firing now: (schedule, [card ids to run], [(card id, reason skipped)])."""
    s = get(conn, sid)
    if not s:
        return None, [], []
    if not s["enabled"]:
        return s, [], [(c["id"], "the schedule is paused") for c in s["cards"]]
    run, skipped = [], []
    cutoff = iso(now_utc() - timedelta(minutes=DUPLICATE_WINDOW_MIN))
    for c in s["cards"]:
        if not c["active"]:
            skipped.append((c["id"], "the card is turned off"))
            continue
        recent = conn.execute("""SELECT e.started_at, s.name FROM executions e LEFT JOIN schedules s ON s.id=e.schedule_id
                                 WHERE e.profile_id=? AND e.started_at>=? AND e.status IN ('running','completed')
                                 ORDER BY e.id DESC LIMIT 1""", (c["id"], cutoff)).fetchone()
        if recent and not c["allow_duplicate"]:
            skipped.append((c["id"], f"it already ran at {recent['started_at'][11:16]} UTC" + (f" (schedule “{recent['name']}”)" if recent["name"] else "")))
            continue
        run.append(c["id"])
    return s, run, skipped
