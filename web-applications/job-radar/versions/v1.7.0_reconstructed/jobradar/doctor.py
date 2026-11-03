"""'Check setup': explains in plain words why reports might not be arriving."""
import smtplib
import ssl

from . import db as dbm
from . import scheduler
from .config import load_settings
from .pipeline import online


def check():
    s = load_settings()
    out = []
    def add(name, ok, detail, fix=""):
        out.append({"name": name, "ok": ok, "detail": detail, "fix": fix})

    # 1. internet / job sites
    try:
        net = online(10)
    except Exception:
        net = False
    add("Job sites reachable", net,
        "This computer can reach the job-board APIs." if net else "Couldn't reach job sites from this computer.",
        "" if net else "Check the internet connection. On an office network, a firewall or proxy may block job sites.")

    # 2. email: sending accounts
    from . import mailer
    with dbm.session() as conn:
        mailer.migrate_legacy_settings(conn, s)
        accs = [x for x in mailer.accounts(conn) if x["status"] != "disconnected"]
        if not (s.get("email") or {}).get("enabled", True):
            add("Email sending", False, "Sending email is turned off in Mail, so results are only saved in the app.", "Open the Mail tab and turn on ‘Send emails’.")
        elif not accs:
            add("Email sending", False, "No sending Gmail account is set up.", "Open the Mail tab → Add Gmail account (needs a 16-letter app password).")
        else:
            bad = []
            for a_ in accs:
                ok, msg = mailer.test_account(conn, a_["id"])
                if not ok:
                    bad.append(f"{a_['email']}: {msg}")
            dflt = mailer.mail_settings(s).get("default_account")
            if bad:
                add("Email sending", False, "Sign-in failed for " + "; ".join(bad), "Open Mail → Sending Gmail accounts and press Reconnect.")
            elif not dflt:
                add("Email sending", False, f"{len(accs)} Gmail account(s) work, but none is the default sender.", "Open Mail and press ‘Make default’ on one account.")
            else:
                add("Email sending", True, f"Signed in to Gmail: {', '.join(a_['email'] for a_ in accs)}.")

    # 3. searches
    with dbm.session() as conn:
        profs = conn.execute("SELECT * FROM profiles").fetchall()
        active = [p for p in profs if p["active"]]
        res = {p["id"]: mailer.resolve(conn, p, s) for p in active}
        mail = [p for p in active if res[p["id"]]["enabled"] and res[p["id"]]["recipient_count"]]
        if not profs:
            add("Saved searches", False, "There are no saved searches yet.", "Describe a job in Find jobs and press Save.")
        elif not active:
            add("Saved searches", False, "All cards are turned off.", "Turn a card on in Job search cards.")
        elif not mail:
            add("Saved searches", False, f"{len(active)} card(s) are on, but none will be emailed (email off or no recipients).",
                "Add default recipients in the Mail tab, or open a card's Email settings.")
        else:
            add("Saved searches", True, f"{len(mail)} card(s) will be emailed: " + ", ".join(
                f"{p['name']} → {res[p['id']]['recipient_count']} recipient(s)" for p in mail))

        # 4. last scan
        r = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        if not r:
            add("Last scan", False, "No scan has run yet.", "Press Scan now.")
        else:
            summ = dbm.jload(r["summary_json"], {}) or {}
            notes = [f"{v.get('reported', 0)} new for one search; email: {'sent' if v.get('email_sent') else v.get('email_note')}" for v in summ.values() if isinstance(v, dict)]
            ok = r["status"] in ("completed", "partial")
            add("Last scan", ok, f"{r['started_at']} – {r['status']}, {r['sources_scanned'] or 0}/{r['sources_configured'] or 0} sources. " + " | ".join(notes),
                "" if ok else "Press Scan now and watch the progress log. 'No internet connection' means job sites are blocked.")
            if ok:
                total = conn.execute("SELECT COUNT(*) FROM matches m JOIN jobs j ON j.id=m.job_id WHERE j.status!='closed'").fetchone()[0]
                new = sum(v.get("reported", 0) for v in summ.values() if isinstance(v, dict))
                adz = (s.get("sources", {}).get("adzuna") or {}).get("enabled")
                if total == 0:
                    add("Matches", False, "No jobs match your searches yet.",
                        "Widen the search: allow 'Anywhere in India' or more cities, choose 'Any' work arrangement, add similar job titles, "
                        "or lower the minimum salary." + ("" if adz else " Most important for India: turn on Adzuna in Settings (free key from developer.adzuna.com); it covers Indian job boards."))
                elif new == 0:
                    add("Matches", True, f"No new jobs since the last report; {total} open match(es) are stored. Press 'Email results now' to send them.")
                else:
                    add("Matches", True, f"{new} new match(es) in the last scan; {total} open in total.")
                if not adz:
                    add("India coverage", False, "Adzuna is off, so Indian job boards (Naukri-style listings) aren't searched. Results come mostly from company career pages and remote boards.",
                        "Get a free app ID and key at developer.adzuna.com, then tick 'Use Adzuna' in Settings and save.")

    # 5. schedule
    from . import db as _db, schedules as _S
    with _db.session() as conn:
        _S.migrate_legacy(conn)
        sl = _S.list_all(conn)
        cards_on = {r["id"] for r in conn.execute("SELECT id FROM profiles WHERE active=1")}
    live = [s for s in sl if s["enabled"] and any(c["active"] for c in s["cards"])]
    covered = {c["id"] for s in live for c in s["cards"]}
    missing_os = [s["name"] for s in live if s.get("os_ok") is False]
    if missing_os:
        add("Schedule", False, "These schedules are missing from the system scheduler: " + ", ".join(missing_os) + ".",
            "Open the Schedules tab and press Save on each one (or turn it off and on again).")
    elif not live:
        add("Schedule", False, "No active schedule. Scans run only when you start them.", "Open Schedules → Create schedule, or use Schedule on a card.")
    else:
        unsched = len(cards_on - covered)
        add("Schedule", True, f"{len(live)} active schedule(s): " + "; ".join(f"{s['name']} – next {s['next_run_text'] or '—'}" for s in live[:4])
            + (f". {unsched} turned-on card(s) have no schedule." if unsched else "."))
    return out


def cli():
    for c in check():
        print(("OK   " if c["ok"] else "FIX  ") + c["name"] + ": " + c["detail"])
        if not c["ok"] and c["fix"]:
            print("     -> " + c["fix"])
