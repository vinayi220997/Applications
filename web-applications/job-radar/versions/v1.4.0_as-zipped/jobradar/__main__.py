"""Command line:

  python -m jobradar                 open the app in your browser (same as `ui`)
  python -m jobradar ask             add a search by answering questions in the terminal
  python -m jobradar run             scan now for every active search (emails reports if set up)
  python -m jobradar schedule 08:00 [--days MON,TUE,...] [--every-hours 4]
  python -m jobradar unschedule      stop scheduled scans
  python -m jobradar status          show searches, schedule and the last scan
  python -m jobradar doctor          explain why reports might not be arriving
  python -m jobradar email-now ID    email all open matches for search ID right now
"""
import argparse
import json
import sys

from . import db as dbm
from . import intake, pipeline, scheduler
from .normalize import iso, now_utc


def _utf8_console():
    """Windows consoles and redirected logs default to cp1252; names like '₹' or '→' would crash print()."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main(argv=None):
    _utf8_console()
    ap = argparse.ArgumentParser(prog="jobradar", description="Local job discovery agent")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("ui")
    sub.add_parser("ask")
    r = sub.add_parser("run")
    r.add_argument("--trigger", default="manual")
    r.add_argument("--no-email", action="store_true")
    r.add_argument("--profile", type=int, action="append")
    s = sub.add_parser("schedule")
    s.add_argument("time", nargs="?", default="08:00")
    s.add_argument("--days", default="MON,TUE,WED,THU,FRI,SAT,SUN")
    s.add_argument("--every-hours", type=int)
    sub.add_parser("unschedule")
    sub.add_parser("status")
    sub.add_parser("doctor")
    e = sub.add_parser("email-now")
    e.add_argument("profile", type=int)
    a = ap.parse_args(argv)

    if a.cmd in (None, "ui"):
        from .web import serve
        serve()
    elif a.cmd == "ask":
        p = intake.cli()
        now = iso(now_utc())
        with dbm.session() as conn:
            conn.execute("""INSERT INTO profiles(name, email, email_on, active, description, profile_json, created_at, updated_at)
                            VALUES (?,?,1,1,?,?,?,?)""", (p["name"], p.get("email"), p.get("description"), dbm.jdump(p), now, now))
        print(f"\nSaved search '{p['name']}': {intake.summary(p)}")
        if input("Run a scan now? [y/N] ").strip().lower().startswith("y"):
            pipeline.run("manual")
    elif a.cmd == "run":
        rid = pipeline.run(a.trigger, a.profile, send=not a.no_email)
        sys.exit(0 if rid else 1)
    elif a.cmd == "schedule":
        ok, msg = scheduler.install(a.time, a.days.split(","), a.every_hours)
        print(msg)
        sys.exit(0 if ok else 1)
    elif a.cmd == "unschedule":
        print(scheduler.remove()[1])
    elif a.cmd == "doctor":
        from .doctor import cli
        cli()
    elif a.cmd == "email-now":
        print(pipeline.email_current(a.profile)[1])
    elif a.cmd == "status":
        with dbm.session() as conn:
            for r in conn.execute("SELECT id, name, email, active FROM profiles"):
                print(f"[{r['id']}] {r['name']}  email={r['email'] or '-'}  {'active' if r['active'] else 'paused'}")
            last = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
            if last:
                print(f"Last scan: {last['started_at']} {last['status']} – {last['sources_scanned']}/{last['sources_configured']} sources")
        print(scheduler.status()["text"])


if __name__ == "__main__":
    main()
