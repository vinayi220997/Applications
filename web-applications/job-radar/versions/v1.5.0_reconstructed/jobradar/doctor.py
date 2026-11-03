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

    # 2. email settings
    e = s.get("email") or {}
    configured = bool(e.get("enabled") and e.get("username") and e.get("app_password"))
    if not e.get("enabled"):
        add("Email sending", False, "Email sending is turned off, so reports are only saved in the app.",
            "Open Settings, tick 'Send reports by email', enter your Gmail address and app password, then Save.")
    elif not (e.get("username") and e.get("app_password")):
        add("Email sending", False, "Email is turned on but the Gmail address or app password is missing.",
            "Open Settings and fill in both fields, then Save.")
    else:
        try:
            with smtplib.SMTP(e.get("smtp_host", "smtp.gmail.com"), int(e.get("smtp_port", 587)), timeout=20) as srv:
                srv.starttls(context=ssl.create_default_context())
                srv.login(e["username"], e["app_password"])
            add("Email sending", True, f"Signed in to Gmail as {e['username']}.")
        except smtplib.SMTPAuthenticationError:
            add("Email sending", False, "Gmail rejected the sign-in.",
                "Use a Gmail app password (16 letters from myaccount.google.com/apppasswords), not your normal password. 2-Step Verification must be on.")
        except Exception as ex:
            add("Email sending", False, f"Couldn't connect to Gmail ({ex.__class__.__name__}).",
                "Check the internet connection. Some office networks block outgoing email on port 587.")

    # 3. searches
    with dbm.session() as conn:
        profs = conn.execute("SELECT * FROM profiles").fetchall()
        active = [p for p in profs if p["active"]]
        mail = [p for p in active if p["email"] and p["email_on"]]
        if not profs:
            add("Saved searches", False, "There are no saved searches yet.", "Describe a job in Find jobs and press Save.")
        elif not active:
            add("Saved searches", False, "All searches are paused.", "Press Resume on a search.")
        elif not mail:
            off = [p for p in active if p["email"] and not p["email_on"]]
            if off:
                add("Saved searches", False, "Daily email is turned OFF for: " + ", ".join(f"{p['name']} ({p['email']})" for p in off) + ".",
                    "On that search card press 'Turn daily email on'.")
            else:
                add("Saved searches", False, f"{len(active)} active search(es), but none has an email address.",
                    "On the search card press 'Add email'.")
        else:
            add("Saved searches", True, f"{len(mail)} active search(es) will be emailed: " + ", ".join(f"{p['name']} → {p['email']}" for p in mail))

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
    sch = scheduler.status()
    add("Schedule", sch.get("enabled", False), sch.get("text", ""), "" if sch.get("enabled") else "Set a time in the Schedule card and press Save schedule.")
    return out


def cli():
    for c in check():
        print(("OK   " if c["ok"] else "FIX  ") + c["name"] + ": " + c["detail"])
        if not c["ok"] and c["fix"]:
            print("     -> " + c["fix"])
