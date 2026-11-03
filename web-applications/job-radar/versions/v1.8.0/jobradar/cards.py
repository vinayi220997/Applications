"""Job search cards: listing with status, activity history, create/update/duplicate, export/import.

The card is the saved search (table `profiles`). Its history lives in `activity`, `executions` and `email_log`
and is kept when the card is edited or turned off.
"""
import json
from datetime import timedelta

from . import db as dbm
from .intake import LABELS, QUESTIONS, finalize, show, summary as profile_summary
from .normalize import iso, now_utc, parse_date, work_modes

EXPORT_FORMAT = "jobradar.card"
EXPORT_VERSION = 1
APP_VERSION = "1.8.0"
PORTABLE_KEYS = ["name", "description", "roles", "skills", "nice_to_have", "industries", "experience", "locations",
                 "remote_international", "work_modes", "work_arrangement", "min_salary", "exclude", "employment_type"]
LIST_FIELDS = {"roles", "skills", "nice_to_have", "industries", "locations", "work_modes", "exclude"}
MODES = {"chart": "Chart mode", "questionnaire": "Questionnaire mode"}
SOURCES = {"manual", "file", "screenshot", "voice", "ai", "import"}


class CardError(Exception):
    pass


def log(conn, pid, kind, detail):
    conn.execute("INSERT INTO activity(profile_id, at, kind, detail) VALUES (?,?,?,?)", (pid, iso(now_utc()), kind, detail))


def _sources(v):
    if isinstance(v, str):
        v = dbm.jload(v, None) if v.startswith("[") else [x.strip() for x in v.split(",")]
    return [s for s in (v or []) if s in SOURCES] or ["manual"]


def _duration(a, b):
    da, db_ = parse_date(a), parse_date(b)
    return int((db_ - da).total_seconds()) if da and db_ else None


def _fix_stale(conn):
    """A run that was killed (PC shut down mid-scan) leaves 'running' rows behind; close them."""
    from .pipeline import LOCK
    if LOCK.exists():
        return
    rows = conn.execute("SELECT id, profile_id FROM executions WHERE status='running'").fetchall()
    for r in rows:
        conn.execute("UPDATE executions SET status='failed', finished_at=?, error=? WHERE id=?",
                     (iso(now_utc()), "Interrupted: the scan stopped unexpectedly (computer shut down or app closed).", r["id"]))
        log(conn, r["profile_id"], "search_failed", "Search interrupted (the scan stopped unexpectedly)")
    conn.execute("UPDATE email_log SET status='failed', error='Interrupted before the email finished' WHERE status='sending'")


def trigger_label(conn, trig, sid):
    if sid:
        r = conn.execute("SELECT name FROM schedules WHERE id=?", (sid,)).fetchone()
        return "Schedule: " + (r["name"] if r else f"#{sid} (deleted)")
    return {"manual": "Run manually", "scheduled": "Scheduled (old schedule)", "retry": "Retry"}.get(trig or "", trig or "Manual")


def card_list(conn):
    from . import schedules as S
    _fix_stale(conn)
    from . import mailer
    from .config import load_settings
    settings = load_settings()
    master = (settings.get("email") or {}).get("enabled", True)
    have_accounts = bool(conn.execute("SELECT 1 FROM mail_accounts WHERE status!='disconnected'").fetchone())
    out = []
    for r in conn.execute("SELECT * FROM profiles ORDER BY id DESC"):
        p = dbm.jload(r["profile_json"], {})
        c = {"id": r["id"], "name": r["name"], "email": r["email"], "email_on": bool(r["email_on"]), "active": bool(r["active"]),
             "input_mode": r["input_mode"] or "chart", "answer_source": _sources(r["answer_source"]),
             "created_at": r["created_at"], "updated_at": r["updated_at"], "profile": p, "summary": profile_summary(p),
             "cities": p.get("locations") or ["India"],
             "work_modes": work_modes(p.get("work_modes") if p.get("work_modes") is not None else p.get("work_arrangement"))}
        e = conn.execute("SELECT * FROM executions WHERE profile_id=? AND status!='skipped' ORDER BY id DESC LIMIT 1", (r["id"],)).fetchone()
        c["last_exec"] = None
        if e:
            e = dbm.row_to_dict(e)
            e["duration_s"] = _duration(e["started_at"], e["finished_at"])
            e["trigger_label"] = trigger_label(conn, e["trigger"], e["schedule_id"])
            c["last_exec"] = e
        m = conn.execute("SELECT * FROM email_log WHERE profile_id=? ORDER BY id DESC LIMIT 1", (r["id"],)).fetchone()
        c["last_email"] = dbm.row_to_dict(m) if m else None
        if m:
            c["last_email"]["attempts"] = [dbm.row_to_dict(a) for a in conn.execute("SELECT account_email, selected_email, fallback_reason, status, error FROM email_attempts WHERE email_log_id=?", (m["id"],))]
        res = mailer.resolve(conn, r, settings)
        c["email_cfg"] = {"enabled": res["enabled"], "recipients_source": res["recipients_source"], "recipients": res["recipients"],
                          "recipient_count": res["recipient_count"], "template": res["template"].get("name"), "template_id": res["template"].get("id"),
                          "template_source": res["template_source"], "sender": res["sender"], "sender_source": res["sender_source"],
                          "fallback": res["fallback"], "issues": res["issues"], "raw": mailer.card_cfg_raw(r)}
        c["total_jobs"] = conn.execute("""SELECT COUNT(*) n FROM matches m JOIN jobs j ON j.id=m.job_id
                                          WHERE m.profile_id=? AND j.status!='closed'""", (r["id"],)).fetchone()["n"]
        sch = S.for_card(conn, r["id"])
        c["schedules"] = [{"id": s["id"], "name": s["name"], "enabled": s["enabled"], "kind": s["kind"], "text": s["text"],
                           "next_run": s["next_run"], "next_run_text": s["next_run_text"]} for s in sch]
        active_sch = [s for s in sch if s["enabled"]]
        c["schedule_status"] = "Scheduled" if active_sch else ("Paused" if sch else "Not Scheduled")
        nxt = sorted([s for s in active_sch if s["next_run"]], key=lambda s: s["next_run"])
        c["next_run"], c["next_run_text"] = (nxt[0]["next_run"], nxt[0]["next_run_text"]) if nxt else (None, None)
        c["duplicate_schedules"] = len(active_sch) > 1
        # search status
        if not c["active"]:
            st = "Disabled"
        elif e and e["status"] == "running":
            st = "Running"
        elif not e:
            st = "Ready" if active_sch else "Not Started"
        else:
            st = {"completed": "Completed", "failed": "Failed", "stopped": "Stopped"}.get(e["status"], e["status"].title())
        c["status"] = st
        # email status (separate from the search)
        LBL = {"pending": "Pending", "sending": "Sending", "sent": "Sent", "partial": "Partly sent", "uncertain": "Unconfirmed",
               "failed": "Failed", "skipped": "Skipped"}
        es = LBL.get(m["status"], m["status"].title()) if m else None
        wants = c["active"] and res["enabled"] and res["recipient_count"] and master
        c["email_status"] = es or ("Scheduled" if wants and active_sch else "Not Scheduled")
        c["email_next"] = ("Scheduled" if active_sch else "Sent when you run the search") if wants else (
            "Email off for this card" if not res["enabled"] else
            ("Nobody (set on this card)" if res["recipients_source"] == "none" else "No recipients yet (Mail tab or Email settings)") if not res["recipient_count"] else
            "Email sending is turned off in Mail" if not master else "Not scheduled")
        if wants and not have_accounts:
            c["email_next"] = "No sending Gmail account set up (Mail tab)"
        out.append(c)
    return out


def _email_ready():
    from .config import load_settings
    e = load_settings().get("email") or {}
    return bool(e.get("enabled") and e.get("username") and e.get("app_password"))


def history(conn, pid):
    acts = [dbm.row_to_dict(r) for r in conn.execute("SELECT * FROM activity WHERE profile_id=? ORDER BY id DESC LIMIT 400", (pid,))]
    exs = []
    for r in conn.execute("SELECT * FROM executions WHERE profile_id=? ORDER BY id DESC LIMIT 200", (pid,)):
        e = dbm.row_to_dict(r)
        e["duration_s"] = _duration(e["started_at"], e["finished_at"])
        e["trigger_label"] = trigger_label(conn, e["trigger"], e["schedule_id"])
        exs.append(e)
    from . import mailer
    ems = mailer.history(conn, pid, 200)
    return {"activity": acts, "executions": exs, "emails": ems}


# ------------------------------------------------------------------ create / update
def _portable(p):
    out = {}
    for k in PORTABLE_KEYS:
        v = p.get(k)
        if v in (None, "", []):
            continue
        if k in LIST_FIELDS:
            if not isinstance(v, list):
                v = [v]
            v = [str(x).strip()[:80] for x in v if str(x).strip()][:20]
        elif k == "remote_international":
            v = bool(v)
        else:
            v = str(v).strip()[:2000 if k == "description" else 120]
        out[k] = v
    return out


def create(conn, profile, input_mode="chart", answer_source=None, email=None, email_on=True, active=True,
           link_default=True, note="Card created"):
    p = finalize(profile or {})
    if not (p.get("roles") and any(r.strip() for r in p["roles"])):
        raise CardError("Add at least one job title.")
    now = iso(now_utc())
    from . import mailer
    email = (email if email is not None else p.get("email")) or None
    if email:
        addrs = mailer.split_addresses(email)
        bad = [a for a in addrs if not mailer.EMAIL_RE.match(a)]
        if bad:
            raise CardError(f"“{bad[0]}” isn't a valid email address.")
        email = ", ".join(dict.fromkeys(addrs)) or None
    pid = conn.execute("""INSERT INTO profiles(name, email, email_on, active, description, profile_json, created_at, updated_at, input_mode, answer_source)
                          VALUES (?,?,?,?,?,?,?,?,?,?)""",
                       (p["name"], email, 1 if email_on else 0, 1 if active else 0, p.get("description"), dbm.jdump(p), now, now,
                        input_mode if input_mode in MODES else "chart", json.dumps(_sources(answer_source)))).lastrowid
    log(conn, pid, "created", f"{note} ({MODES.get(input_mode, 'Chart mode')}; answers from {', '.join(_sources(answer_source))})")
    linked = None
    if link_default:
        from . import schedules as S
        d = S.default_schedule(conn)
        if d and d["enabled"]:
            S.set_cards(conn, d["id"], [x["id"] for x in (S.get(conn, d["id"])["cards"])] + [pid])
            linked = d["name"]
    return pid, linked


def update(conn, pid, profile, input_mode=None, answer_source=None, note="Configuration updated"):
    r = conn.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
    if not r:
        raise CardError("That card no longer exists.")
    old = dbm.jload(r["profile_json"], {})
    p = finalize(profile or {})
    if not (p.get("roles") and any(x.strip() for x in p["roles"])):
        raise CardError("Add at least one job title.")
    changed = [LABELS[q["key"]] for q in QUESTIONS if show(old, q["key"]) != show(p, q["key"])]
    if (old.get("industries") or []) != (p.get("industries") or []):
        changed.append("Industries")
    mode_changed = input_mode and input_mode != (r["input_mode"] or "chart")
    email = r["email"]
    conn.execute("""UPDATE profiles SET name=?, email=?, description=?, profile_json=?, updated_at=?, input_mode=COALESCE(?, input_mode),
                    answer_source=COALESCE(?, answer_source) WHERE id=?""",
                 (p["name"], email or None, p.get("description"), dbm.jdump(p), iso(now_utc()),
                  input_mode if input_mode in MODES else None, json.dumps(_sources(answer_source)) if answer_source else None, pid))
    if "email" in (profile or {}) and (profile.get("email") or "") != (r["email"] or ""):
        apply_form_email(conn, pid, profile.get("email") or "")
        changed.append("Report email")
    bits = []
    if changed:
        bits.append("changed " + ", ".join(changed))
    if mode_changed:
        bits.append(f"input mode changed to {MODES[input_mode]}")
    log(conn, pid, "updated", note + (": " + "; ".join(bits) if bits else " (no changes to the answers)"))
    return changed


def apply_form_email(conn, pid, value):
    """The 'Report email' field in Chart / Questionnaire mode is the card's To list."""
    from . import mailer
    row = conn.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
    cfg = mailer.card_cfg_raw(row)
    addrs = mailer.split_addresses(value)
    bad = [a for a in addrs if not mailer.EMAIL_RE.match(a)]
    if bad:
        raise CardError(f"“{bad[0]}” isn't a valid email address.")
    if addrs:
        cfg["recipients_mode"] = "custom"
    elif cfg.get("recipients_mode") == "custom":
        cfg["recipients_mode"] = "global"
    conn.execute("UPDATE profiles SET email=?, email_json=? WHERE id=?", (", ".join(dict.fromkeys(addrs)) or None, json.dumps(cfg), pid))


def set_email_cfg(conn, pid, body):
    """Save a card's Email settings (only the card is changed; global Mail settings stay)."""
    from . import mailer
    row = conn.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
    if not row:
        raise CardError("That card no longer exists.")
    old = mailer.card_cfg_raw(row)
    cfg = {}
    mode = body.get("recipients_mode") or "global"
    if mode not in ("global", "custom", "none"):
        raise CardError("Choose who gets this card's email.")
    cfg["recipients_mode"] = mode
    to = None
    if mode == "custom":
        clean, probs = mailer.check_addresses({"to": body.get("to"), "cc": body.get("cc"), "bcc": body.get("bcc")})
        bad = [x for x in probs if "isn't a valid" in x]
        if bad:
            raise CardError(" ".join(bad))
        if not clean["to"] and not clean["cc"] and not clean["bcc"]:
            raise CardError("Add at least one recipient, or choose ‘Don't email anyone’.")
        to, cfg["cc"], cfg["bcc"] = ", ".join(clean["to"]) or None, clean["cc"], clean["bcc"]
    tid = body.get("template_id")
    if tid:
        t = mailer.get_template(conn, int(tid))
        if not t:
            raise CardError("That template no longer exists.")
        if not t["enabled"]:
            raise CardError(f"The template “{t['name']}” is turned off. Turn it on in Mail → Templates, or pick another.")
        cfg["template_id"] = int(tid)
    snd = body.get("sender")
    if snd:
        if snd.get("mode") not in mailer.SENDER_MODES:
            raise CardError("Choose how this card's email is sent.")
        ids = [int(x) for x in snd.get("accounts") or []]
        known = {r[0] for r in conn.execute("SELECT id FROM mail_accounts")}
        if any(i not in known for i in ids):
            raise CardError("One of the chosen Gmail accounts no longer exists.")
        if snd["mode"] == "specific" and len(ids) != 1:
            raise CardError("Pick the Gmail account to send from.")
        if snd["mode"] == "multi" and len(ids) < 2:
            raise CardError("Pick at least two Gmail accounts, or choose a single account.")
        if snd["mode"] == "all":
            ids = []
        strategy = snd.get("strategy") if snd.get("strategy") in mailer.STRATEGIES else "rotate"
        if snd["mode"] in ("multi", "all") and strategy == "copy" and not body.get("confirm_copies"):
            raise CardError("confirm_copies")
        cfg["sender"] = {"mode": snd["mode"], "accounts": ids, "strategy": strategy}
    if body.get("fallback") in mailer.FALLBACKS:
        cfg["fallback"] = body["fallback"]
    enabled = bool(body.get("enabled", True))
    conn.execute("UPDATE profiles SET email=?, email_on=?, email_json=?, updated_at=? WHERE id=?",
                 (to if mode == "custom" else None, 1 if enabled else 0, json.dumps(cfg), iso(now_utc()), pid))
    bits = []
    if enabled != bool(row["email_on"]):
        bits.append("email " + ("on" if enabled else "off"))
    if mode != old.get("recipients_mode") or mode == "custom":
        bits.append({"global": "recipients: default list", "custom": "recipients: " + (to or "") + (f" +{len(cfg['cc'])} CC" if cfg.get("cc") else "") + (f" +{len(cfg['bcc'])} BCC" if cfg.get("bcc") else ""), "none": "recipients: nobody (results stay in the app)"}[mode])
    if cfg.get("template_id") != old.get("template_id"):
        bits.append("template changed")
    if cfg.get("sender") != old.get("sender"):
        bits.append("sending account changed")
    if cfg.get("fallback") != old.get("fallback"):
        bits.append("fallback policy changed")
    log(conn, pid, "email", "Email settings changed: " + (", ".join(bits) or "no changes"))


def set_flag(conn, pid, field, on):
    conn.execute(f"UPDATE profiles SET {field}=?, updated_at=? WHERE id=?", (1 if on else 0, iso(now_utc()), pid))
    if field == "active":
        log(conn, pid, "enabled" if on else "disabled", "Card turned on" if on else "Card turned off (no automatic searches or emails)")
    else:
        log(conn, pid, "email", "Daily email turned on" if on else "Daily email turned off")


def duplicate(conn, pid):
    r = conn.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
    if not r:
        raise CardError("That card no longer exists.")
    p = dbm.jload(r["profile_json"], {})
    p["name"] = (r["name"] + " (copy)")[:80]
    new, _ = create(conn, p, r["input_mode"] or "chart", _sources(r["answer_source"]), r["email"], bool(r["email_on"]), False,
                    link_default=False, note=f"Duplicated from “{r['name']}” (starts turned off)")
    log(conn, pid, "duplicated", f"Duplicated as “{p['name']}”")
    return new


def delete(conn, pid):
    from . import attachments
    attachments.delete_for_profile(conn, pid)
    for t in ("profiles WHERE id=?", "matches WHERE profile_id=?", "notifications WHERE profile_id=?", "user_state WHERE profile_id=?",
              "schedule_cards WHERE profile_id=?", "executions WHERE profile_id=?", "email_log WHERE profile_id=?", "activity WHERE profile_id=?"):
        conn.execute("DELETE FROM " + t, (pid,))


# ------------------------------------------------------------------ export / import
def export(conn, pid, include_email=False):
    from . import schedules as S
    r = conn.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
    if not r:
        raise CardError("That card no longer exists.")
    p = dbm.jload(r["profile_json"], {})
    card = {"name": r["name"], "input_mode": r["input_mode"] or "chart", "answer_source": _sources(r["answer_source"]),
            "email_on": bool(r["email_on"]), "answers": _portable(p)}
    from . import mailer
    cfg = mailer.card_cfg_raw(r)
    es = {"recipients_mode": cfg.get("recipients_mode", "global"), "fallback": cfg.get("fallback")}
    if es["recipients_mode"] == "custom" and not include_email:
        es["recipients_mode"] = "global"
    if include_email and cfg.get("recipients_mode") == "custom":
        es.update(cc=cfg.get("cc") or [], bcc=cfg.get("bcc") or [])
    if cfg.get("template_id"):
        t = mailer.get_template(conn, cfg["template_id"])
        if t:
            es["template_name"] = t["name"]
    card["email_settings"] = es
    if include_email and r["email"]:
        card["email"] = r["email"]
    data = {"format": EXPORT_FORMAT, "version": EXPORT_VERSION, "app": f"Job Radar {APP_VERSION}",
            "exported_at": iso(now_utc()),
            "note": "Job Radar search card. Contains the search settings and answers only: no passwords, API keys, results or history.",
            "card": card,
            "questions": [{"key": q["key"], "question": q["ask"], "label": LABELS[q["key"]], "answer": show(p, q["key"])} for q in QUESTIONS
                          if q["key"] != "email" or include_email],
            "schedules": [{"name": s["name"], "kind": s["kind"], "frequency": s["frequency"], "time": s["time"], "days": s["days"],
                           "every_hours": s["every_hours"], "timezone": s["timezone"]} for s in S.for_card(conn, pid)]}
    log(conn, pid, "exported", "Card exported" + (" (with email address)" if card.get("email") else ""))
    return data


SECRET_HINTS = ("password", "app_password", "api_key", "apikey", "token", "secret")


def check_import(data):
    """Validate an exported card file. Returns (card, warnings). Raises CardError with a clear message."""
    if not isinstance(data, dict):
        raise CardError("This isn't a Job Radar card file (expected a JSON object).")
    if data.get("format") != EXPORT_FORMAT:
        raise CardError("This file isn't a Job Radar card export (the 'format' field is missing or different).")
    try:
        ver = int(data.get("version"))
    except (TypeError, ValueError):
        raise CardError("The card file has no valid version number.")
    if ver > EXPORT_VERSION:
        raise CardError(f"This card was exported by a newer Job Radar (file version {ver}). Update Job Radar, then import it.")
    if ver < 1:
        raise CardError(f"Unsupported card file version {ver}.")
    c = data.get("card")
    if not isinstance(c, dict) or not isinstance(c.get("answers"), dict):
        raise CardError("The card file has no saved answers.")
    warnings = []
    blob = json.dumps(data).lower()
    if any(f'"{h}"' in blob for h in SECRET_HINTS):
        warnings.append("The file contained fields that look like credentials; they were ignored.")
    ans = _portable(c["answers"])
    if not ans.get("roles"):
        raise CardError("The card file has no job titles, so it can't be imported.")
    mode = c.get("input_mode") if c.get("input_mode") in MODES else "chart"
    if c.get("input_mode") not in MODES:
        warnings.append("Unknown input mode in the file; it will open in Chart mode.")
    email = c.get("email") if isinstance(c.get("email"), str) and "@" in c.get("email", "") else None
    sch = []
    for s in data.get("schedules") or []:
        if isinstance(s, dict):
            sch.append({k: s.get(k) for k in ("name", "kind", "frequency", "time", "days", "every_hours", "timezone")})
    card = {"name": str(c.get("name") or ans.get("name") or "Imported search")[:80], "input_mode": mode,
            "answer_source": _sources(c.get("answer_source")), "email": email, "email_on": bool(c.get("email_on", True)),
            "answers": ans, "schedules": sch, "exported_at": data.get("exported_at"), "app": data.get("app"),
            "email_settings": c.get("email_settings") if isinstance(c.get("email_settings"), dict) else {}}
    card["answers"]["name"] = card["name"]
    card["preview"] = [{"label": LABELS[q["key"]], "answer": show(dict(ans, email=email), q["key"])} for q in QUESTIONS]
    return card, warnings


def do_import(conn, data, mode="new", target_id=None, answers=None, with_schedules=False):
    from . import schedules as S
    card, warnings = check_import(data)
    ans = _portable(answers) if answers else card["answers"]
    if answers and not ans.get("roles"):
        raise CardError("Add at least one job title.")
    src = list(dict.fromkeys(card["answer_source"] + ["import"]))
    if mode == "update":
        if not target_id or not conn.execute("SELECT 1 FROM profiles WHERE id=?", (target_id,)).fetchone():
            raise CardError("Choose the card to update.")
        prof = dict(ans)
        if card["email"]:
            prof["email"] = card["email"]
        update(conn, target_id, prof, card["input_mode"], src, note="Updated from an imported card file")
        log(conn, target_id, "imported", f"Imported settings from a card file ({card.get('app') or 'Job Radar'})")
        pid = target_id
    else:
        pid, _ = create(conn, ans, card["input_mode"], src, card["email"], card["email_on"], True, link_default=True,
                        note="Card imported from a file")
        log(conn, pid, "imported", f"Imported from a card file ({card.get('app') or 'Job Radar'})")
    es = card.get("email_settings") or {}
    if es and mode != "update":
        from . import mailer
        row = conn.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
        cfg = mailer.card_cfg_raw(row)
        if es.get("recipients_mode") == "none":
            cfg["recipients_mode"] = "none"
        if es.get("recipients_mode") == "custom" and card["email"]:
            clean, _ = mailer.check_addresses({"to": card["email"], "cc": es.get("cc"), "bcc": es.get("bcc")})
            cfg.update(recipients_mode="custom", cc=clean["cc"], bcc=clean["bcc"])
        if es.get("fallback") in mailer.FALLBACKS:
            cfg["fallback"] = es["fallback"]
        if es.get("template_name"):
            t = conn.execute("SELECT id FROM email_templates WHERE name=? AND enabled=1", (es["template_name"],)).fetchone()
            if t:
                cfg["template_id"] = t["id"]
            else:
                warnings.append(f"Email template “{es['template_name']}” doesn't exist here; the default template is used.")
        conn.execute("UPDATE profiles SET email_json=? WHERE id=?", (json.dumps(cfg), pid))
    made = []
    if with_schedules:
        for s in card["schedules"]:
            if s.get("kind") != "card":
                continue
            try:
                sid, _ = S.save(conn, dict(s, kind="card", name=s.get("name") or f"{card['name']} schedule", card_ids=[pid],
                                           confirm_duplicates=True, enabled=True))
                made.append(sid)
            except S.ScheduleError as e:
                warnings.append(f"Schedule not imported: {e}")
    return pid, warnings, made
