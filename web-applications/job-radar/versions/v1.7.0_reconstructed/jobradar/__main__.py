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
    u = sub.add_parser("ui")
    u.add_argument("--no-browser", action="store_true")
    u.add_argument("--wait-port", action="store_true")
    sub.add_parser("ask")
    r = sub.add_parser("run")
    r.add_argument("--trigger", default="manual")
    r.add_argument("--no-email", action="store_true")
    r.add_argument("--profile", type=int, action="append")
    r.add_argument("--schedule", type=int, help="run the cards linked to this schedule (used by the system scheduler)")
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
        serve(open_browser=not getattr(a, "no_browser", False), wait_port=getattr(a, "wait_port", False))
    elif a.cmd == "ask":
        p = intake.cli()
        now = iso(now_utc())
        with dbm.session() as conn:
            from . import cards
            cards.create(conn, p, "chart", ["manual"])
        print(f"\nSaved search '{p['name']}': {intake.summary(p)}")
        if input("Run a scan now? [y/N] ").strip().lower().startswith("y"):
            pipeline.run("manual")
    elif a.cmd == "run":
        rid = pipeline.run(a.trigger, a.profile, send=not a.no_email, schedule_id=a.schedule)
        sys.exit(0 if (rid or a.schedule) else 1)
    elif a.cmd == "schedule":
        from . import schedules
        with dbm.session() as conn:
            schedules.migrate_legacy(conn)
            d = schedules.default_schedule(conn)
            body = {"name": "Default schedule", "frequency": "hourly" if a.every_hours else "weekly", "time": a.time,
                    "days": a.days.split(","), "every_hours": a.every_hours, "kind": "shared", "is_default": True,
                    "card_ids": [r["id"] for r in conn.execute("SELECT id FROM profiles")], "confirm_duplicates": True}
            try:
                sid, _ = schedules.save(conn, body, d["id"] if d else None)
            except schedules.ScheduleError as e:
                print(e); sys.exit(1)
            conn.commit()
            probs = schedules.sync_os(conn)
            print("; ".join(probs) or schedules.describe(schedules.get(conn, sid)))
            sys.exit(1 if probs else 0)
    elif a.cmd == "unschedule":
        from . import schedules
        with dbm.session() as conn:
            for r in conn.execute("SELECT id FROM schedules").fetchall():
                schedules.set_enabled(conn, r["id"], False)
            conn.commit()
            schedules.sync_os(conn)
        scheduler.remove()
        print("All schedules paused. Scans now run only when you start them.")
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
            from . import schedules
            for sc in schedules.list_all(conn, with_os=False):
                print(f"Schedule '{sc['name']}': {sc['text']} – {'on' if sc['enabled'] else 'paused'}; cards: "
                      + (", ".join(c["name"] for c in sc["cards"]) or "none") + f"; next: {sc['next_run_text'] or '—'}")


if __name__ == "__main__":
    main()
