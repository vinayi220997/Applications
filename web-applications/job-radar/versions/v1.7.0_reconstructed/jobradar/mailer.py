"""Mail module (v1.7): several Gmail sending accounts, To/CC/BCC, templates, per-card email settings,
and an email history with one record per send attempt.

Sign-in uses Gmail app passwords over SMTP (Google's supported method for apps sending mail with 2-Step
Verification). OAuth isn't used: a self-made Google app in 'testing' mode loses its Gmail permission every
7 days, and avoiding that needs Google's verification of the app.

App passwords are kept apart from the settings, in config/secrets.json, encrypted with Windows DPAPI (only this
Windows user on this computer can decrypt them). They never appear in the browser, logs, history or exports.
"""
import base64
import html
import json
import os
import re
import smtplib
import socket
import ssl
import time
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid

from . import db as dbm
from .config import CONFIG_DIR, ensure_dirs
from .normalize import iso, now_utc, parse_date

SECRETS = CONFIG_DIR / "secrets.json"
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9-]{1,63})*\.[A-Za-z]{2,}$")
DEFAULT_MAIL = {"to": [], "cc": [], "bcc": [], "default_account": None,
                "sender": {"mode": "default", "accounts": [], "strategy": "copy"}, "fallback": "stop",
                "daily_limit": 450, "from_name": "Job Radar"}
SENDER_MODES = ("default", "specific", "multi")
STRATEGIES = ("copy", "rotate")
FALLBACKS = ("stop", "default", "other")

SCHEMA = """
CREATE TABLE IF NOT EXISTS mail_accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, from_name TEXT,
  status TEXT DEFAULT 'untested',            -- connected | failed | untested | disconnected | limited
  last_error TEXT, last_checked TEXT, limited_until TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS email_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT, subject TEXT NOT NULL, body TEXT NOT NULL,
  enabled INTEGER DEFAULT 1, is_default INTEGER DEFAULT 0, version INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS email_template_versions (
  template_id INTEGER, version INTEGER, subject TEXT, body TEXT, saved_at TEXT, PRIMARY KEY (template_id, version)
);
CREATE TABLE IF NOT EXISTS email_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, email_log_id INTEGER, account_id INTEGER, account_email TEXT,
  selected_email TEXT, fallback_reason TEXT,
  status TEXT,                                -- pending | sending | sent | failed | uncertain
  message_id TEXT, recipients_count INTEGER, retries INTEGER DEFAULT 0, error TEXT, at TEXT
);
CREATE INDEX IF NOT EXISTS email_attempts_log ON email_attempts(email_log_id);
CREATE TABLE IF NOT EXISTS email_messages (email_log_id INTEGER PRIMARY KEY, subject TEXT, html TEXT, text TEXT, to_json TEXT);
"""
LOG_COLUMNS = {"schedule_id": "INTEGER", "card_name": "TEXT", "trigger": "TEXT", "template_id": "INTEGER", "template_name": "TEXT",
               "template_version": "INTEGER", "sender_mode": "TEXT", "strategy": "TEXT", "selected_accounts": "TEXT",
               "recipients_count": "INTEGER", "idem_key": "TEXT", "note": "TEXT"}


class MailError(Exception):
    pass


def migrate(conn):
    conn.executescript(SCHEMA)
    have = {r[1] for r in conn.execute("PRAGMA table_info(email_log)")}
    for c, d in LOG_COLUMNS.items():
        if c not in have:
            conn.execute(f"ALTER TABLE email_log ADD COLUMN {c} {d}")
    conn.execute("CREATE INDEX IF NOT EXISTS email_log_idem ON email_log(idem_key)")
    if "email_json" not in {r[1] for r in conn.execute("PRAGMA table_info(profiles)")}:
        conn.execute("ALTER TABLE profiles ADD COLUMN email_json TEXT")
    if not conn.execute("SELECT COUNT(*) FROM email_templates").fetchone()[0]:
        for i, t in enumerate(DEFAULT_TEMPLATES):
            _insert_template(conn, t, is_default=(i == 0))


def audit(conn, detail):
    conn.execute("INSERT INTO activity(profile_id, at, kind, detail) VALUES (NULL,?,?,?)", (iso(now_utc()), "mail", detail))


# ------------------------------------------------------------------ secrets (DPAPI on Windows)
def _dpapi(data, protect):
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data))
    inp = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(inp), "JobRadar" if protect else None, None, None, None, 0x1, ctypes.byref(out))
    if not ok:
        raise MailError("Windows couldn't " + ("protect" if protect else "unlock") + " the saved app password. Enter it again.")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def protect(secret):
    raw = secret.encode("utf-8")
    if os.name == "nt":
        try:
            return "dpapi:" + base64.b64encode(_dpapi(raw, True)).decode()
        except Exception:
            import logging
            logging.getLogger("jobradar").warning("Windows data protection unavailable; app password stored locally without it")
    return "local:" + base64.b64encode(raw).decode()      # non-Windows: file is chmod 600


def unprotect(value):
    kind, _, b = (value or "").partition(":")
    raw = base64.b64decode(b)
    if kind == "dpapi":
        return _dpapi(raw, False).decode("utf-8")
    return raw.decode("utf-8")


def _load_secrets():
    try:
        return json.loads(SECRETS.read_text(encoding="utf-8")) if SECRETS.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_secrets(d):
    ensure_dirs()
    SECRETS.write_text(json.dumps(d, indent=1), encoding="utf-8")
    try:
        os.chmod(SECRETS, 0o600)
    except OSError:
        pass


def set_secret(aid, pw):
    d = _load_secrets()
    d[f"account:{aid}"] = protect(pw)
    _save_secrets(d)


def get_secret(aid):
    v = _load_secrets().get(f"account:{aid}")
    return unprotect(v) if v else None


def drop_secret(aid):
    d = _load_secrets()
    if d.pop(f"account:{aid}", None) is not None:
        _save_secrets(d)


# ------------------------------------------------------------------ addresses
def split_addresses(v):
    if isinstance(v, (list, tuple)):
        v = ",".join(str(x) for x in v)
    return [x.strip() for x in re.split(r"[,;\s]+", v or "") if x.strip()]


def check_addresses(lists):
    """lists: {'to': [...], 'cc': [...], 'bcc': [...]} -> (clean lists, problems). An address is kept once,
    in the first field it appears in (To before CC before BCC)."""
    seen, clean, problems = set(), {}, []
    for f in ("to", "cc", "bcc"):
        clean[f] = []
        for a in split_addresses(lists.get(f)):
            low = a.lower()
            if not EMAIL_RE.match(a):
                problems.append(f"“{a}” in {f.upper()} isn't a valid email address.")
            elif low in seen:
                problems.append(f"“{a}” is listed more than once; it will get one copy.")
            else:
                seen.add(low)
                clean[f].append(a)
    return clean, problems


# ------------------------------------------------------------------ settings / accounts
def mail_settings(settings):
    m = json.loads(json.dumps(DEFAULT_MAIL))
    m.update((settings or {}).get("mail") or {})
    m["sender"] = dict(DEFAULT_MAIL["sender"], **(m.get("sender") or {}))
    return m


def accounts(conn, with_usage=False):
    out = []
    for r in conn.execute("SELECT * FROM mail_accounts ORDER BY id"):
        a = dbm.row_to_dict(r)
        a["has_password"] = bool(_load_secrets().get(f"account:{a['id']}"))
        if a["status"] == "limited" and a["limited_until"] and a["limited_until"] < iso(now_utc()):
            a["status"] = "connected"
        a["sent_24h"] = sent_last_24h(conn, a["id"])
        out.append(a)
    if with_usage:
        cards = card_usage(conn)
        for a in out:
            a["used_by"] = cards.get(a["id"], [])
    return out


def card_usage(conn):
    from .config import load_settings
    use = {}
    for r in conn.execute("SELECT id, name, email_on, active, email_json FROM profiles"):
        cfg = card_cfg_raw(r)
        snd = cfg.get("sender")
        if snd:
            ids = snd.get("accounts") or []
            for i in ids:
                use.setdefault(int(i), []).append(r["name"])
    m = mail_settings(load_settings())
    dflt = m.get("default_account")
    for i in (m["sender"].get("accounts") or []) if m["sender"]["mode"] != "default" else []:
        use.setdefault(int(i), []).append("default sending rule")
    if dflt:
        use.setdefault(int(dflt), []).insert(0, "default account")
    return use


def sent_last_24h(conn, aid):
    since = iso(now_utc() - timedelta(hours=24))
    r = conn.execute("SELECT COALESCE(SUM(recipients_count),0) FROM email_attempts WHERE account_id=? AND status='sent' AND at>=?", (aid, since)).fetchone()
    return int(r[0] or 0)


def add_account(conn, email, password, from_name=None, test=True):
    email = (email or "").strip()
    if not EMAIL_RE.match(email):
        raise MailError("Enter a valid Gmail address.")
    pw = "".join((password or "").split())
    if len(pw) != 16 or not pw.isalpha():
        raise MailError("A Gmail app password is exactly 16 letters (Google shows it in 4 groups). Create one at myaccount.google.com/apppasswords.")
    if conn.execute("SELECT 1 FROM mail_accounts WHERE lower(email)=lower(?)", (email,)).fetchone():
        raise MailError(f"{email} is already added. Use Reconnect to change its app password.")
    ok, msg = (smtp_login(email, pw) if test else (None, "not tested"))
    if test and not ok:
        raise MailError(msg)
    now = iso(now_utc())
    aid = conn.execute("INSERT INTO mail_accounts(email, from_name, status, last_error, last_checked, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                       (email, from_name, "connected" if ok else "untested", None, now if test else None, now, now)).lastrowid
    set_secret(aid, pw)
    audit(conn, f"Gmail account {email} added" + (" and signed in" if ok else " (not tested)"))
    return aid


def reconnect(conn, aid, password):
    a = conn.execute("SELECT * FROM mail_accounts WHERE id=?", (aid,)).fetchone()
    if not a:
        raise MailError("That account no longer exists.")
    pw = "".join((password or "").split())
    if len(pw) != 16 or not pw.isalpha():
        raise MailError("A Gmail app password is exactly 16 letters.")
    ok, msg = smtp_login(a["email"], pw)
    if not ok:
        raise MailError(msg)
    set_secret(aid, pw)
    conn.execute("UPDATE mail_accounts SET status='connected', last_error=NULL, last_checked=?, updated_at=? WHERE id=?", (iso(now_utc()), iso(now_utc()), aid))
    audit(conn, f"Gmail account {a['email']} reconnected")


def test_account(conn, aid):
    a = conn.execute("SELECT * FROM mail_accounts WHERE id=?", (aid,)).fetchone()
    if not a:
        raise MailError("That account no longer exists.")
    try:
        pw = get_secret(aid)
    except MailError as e:
        pw, msg = None, str(e)
    if not pw:
        ok, msg = False, "No app password saved. Press Reconnect and enter it."
    else:
        ok, msg = smtp_login(a["email"], pw)
    conn.execute("UPDATE mail_accounts SET status=?, last_error=?, last_checked=? WHERE id=?",
                 ("connected" if ok else ("disconnected" if not pw else "failed"), None if ok else msg, iso(now_utc()), aid))
    return ok, (f"Signed in to Gmail as {a['email']}." if ok else msg)


def disconnect(conn, aid, remove=False):
    a = conn.execute("SELECT * FROM mail_accounts WHERE id=?", (aid,)).fetchone()
    if not a:
        return
    drop_secret(aid)
    if remove:
        conn.execute("DELETE FROM mail_accounts WHERE id=?", (aid,))
        audit(conn, f"Gmail account {a['email']} removed")
    else:
        conn.execute("UPDATE mail_accounts SET status='disconnected', last_error='Disconnected by you', updated_at=? WHERE id=?", (iso(now_utc()), aid))
        audit(conn, f"Gmail account {a['email']} disconnected (app password deleted from this computer)")


def smtp_login(user, pw, timeout=25):
    try:
        s = _open(user, pw, timeout)
        s.quit()
        return True, "ok"
    except smtplib.SMTPAuthenticationError:
        return False, (f"Gmail rejected the sign-in for {user}. Use a 16-letter app password created for this account at "
                       "myaccount.google.com/apppasswords (2-Step Verification must be on), not the normal Gmail password.")
    except (OSError, smtplib.SMTPException) as e:
        return False, (f"Couldn't reach Gmail's mail server ({e.__class__.__name__}). A firewall, antivirus or office "
                       "network may be blocking ports 587 and 465.")


def _open(user, pw, timeout=30):
    """Connect and sign in. Nothing is sent yet, so failures here are always safe to retry."""
    ctx = ssl.create_default_context()
    try:
        s = smtplib.SMTP("smtp.gmail.com", 587, timeout=timeout)
        s.starttls(context=ctx)
    except smtplib.SMTPAuthenticationError:
        raise
    except (OSError, smtplib.SMTPException):
        s = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=timeout, context=ctx)
    s.login(user, pw)
    return s


# ------------------------------------------------------------------ templates
CARD_FIELDS = {"job_search_name", "search_date", "total_jobs_found", "new_jobs_found", "cities", "work_modes", "job_list"}
JOB_FIELDS = {"job_title", "company_name", "job_location", "work_mode", "job_url", "job_description", "match_score", "salary"}
ALIASES = {"jobsearchname": "job_search_name", "totaljobsfound": "total_jobs_found", "searchdate": "search_date",
           "jobtitle": "job_title", "companyname": "company_name", "joblocation": "job_location", "workmode": "work_mode",
           "joburl": "job_url", "jobdescription": "job_description"}
TOKEN = re.compile(r"\{\{\s*([#/]?)\s*([a-zA-Z_]+)\s*\}\}")
DEFAULT_TEMPLATES = [
    {"name": "Daily Job Search Results", "description": "Daily summary with the full job cards (description, why it matches, apply links).",
     "subject": "Daily Job Opportunities — {{job_search_name}} — {{search_date}}",
     "body": "Hello,\n\nHere are the latest job opportunities identified by your job search configuration.\n\n"
             "Job Search: {{job_search_name}}\nSearch Date: {{search_date}}\nTotal Jobs Found: {{total_jobs_found}}\n\n"
             "The matching job details are included below.\n\n{{job_list}}\n\n"
             "Please review the opportunities and apply to the positions that match your profile.\n\nRegards,\nJob Search Notification System"},
    {"name": "New Job Opportunities", "description": "Short list: title, company, location, work mode and apply link for each job.",
     "subject": "{{total_jobs_found}} New Job Opportunities Found",
     "body": "Hello,\n\nYour latest job search has identified new opportunities.\n\nJob Search: {{job_search_name}}\nSearch Date: {{search_date}}\n\n"
             "{{#jobs}}• {{job_title}} — {{company_name}}\n  {{job_location}} · {{work_mode}}\n  Apply: {{job_url}}\n\n{{/jobs}}"
             "Regards,\nJob Search Notification System"},
]


def _norm(name):
    n = name.lower()
    return ALIASES.get(n, n)


def validate_template(subject, body):
    problems = []
    if not (subject or "").strip():
        problems.append("The subject is empty.")
    if not (body or "").strip():
        problems.append("The body is empty.")
    for t in TOKEN.finditer(subject or ""):
        n = _norm(t.group(2))
        if t.group(1) or n in JOB_FIELDS or n == "job_list":
            problems.append(f"{{{{{t.group(2)}}}}} can't be used in the subject (only job search placeholders can).")
        elif n not in CARD_FIELDS:
            problems.append(f"Unknown placeholder {{{{{t.group(2)}}}}} in the subject.")
    depth = 0
    for t in TOKEN.finditer(body or ""):
        n, mark = _norm(t.group(2)), t.group(1)
        if mark == "#":
            if n != "jobs" or depth:
                problems.append("Use one {{#jobs}} … {{/jobs}} block for the job list.")
            depth += 1
        elif mark == "/":
            if n != "jobs" or not depth:
                problems.append("{{/jobs}} has no matching {{#jobs}}.")
            depth = max(0, depth - 1)
        elif n in JOB_FIELDS and not depth:
            problems.append(f"{{{{{t.group(2)}}}}} is a job placeholder; put it inside {{{{#jobs}}}} … {{{{/jobs}}}}.")
        elif n not in JOB_FIELDS | CARD_FIELDS:
            problems.append(f"Unknown placeholder {{{{{t.group(2)}}}}}.")
    if depth:
        problems.append("{{#jobs}} is missing its closing {{/jobs}}.")
    leftovers = re.findall(r"\{\{[^}]*$|\{\{(?![^}]*\}\})", body or "")
    if leftovers:
        problems.append("A placeholder isn't closed with }}.")
    return list(dict.fromkeys(problems))


def _insert_template(conn, t, is_default=False):
    now = iso(now_utc())
    tid = conn.execute("""INSERT INTO email_templates(name, description, subject, body, enabled, is_default, version, created_at, updated_at)
                          VALUES (?,?,?,?,1,?,1,?,?)""", (t["name"], t.get("description"), t["subject"], t["body"], 1 if is_default else 0, now, now)).lastrowid
    conn.execute("INSERT INTO email_template_versions VALUES (?,?,?,?,?)", (tid, 1, t["subject"], t["body"], now))
    return tid


def templates(conn):
    use = {}
    for r in conn.execute("SELECT name, email_json FROM profiles"):
        tid = (dbm.jload(r["email_json"], {}) or {}).get("template_id")
        if tid:
            use.setdefault(int(tid), []).append(r["name"])
    out = []
    for r in conn.execute("SELECT * FROM email_templates ORDER BY is_default DESC, name"):
        t = dbm.row_to_dict(r)
        t["enabled"], t["is_default"] = bool(t["enabled"]), bool(t["is_default"])
        t["used_by"] = use.get(t["id"], [])
        out.append(t)
    return out


def get_template(conn, tid):
    r = conn.execute("SELECT * FROM email_templates WHERE id=?", (tid,)).fetchone()
    return dbm.row_to_dict(r) if r else None


def save_template(conn, body, tid=None):
    name = (body.get("name") or "").strip()[:80]
    if not name:
        raise MailError("Give the template a name.")
    subj, text = (body.get("subject") or "").strip()[:300], (body.get("body") or "")[:20000]
    probs = validate_template(subj, text)
    if probs:
        raise MailError(" ".join(probs))
    now = iso(now_utc())
    if tid:
        old = get_template(conn, tid)
        if not old:
            raise MailError("That template no longer exists.")
        ver = old["version"] + (1 if (old["subject"], old["body"]) != (subj, text) else 0)
        conn.execute("UPDATE email_templates SET name=?, description=?, subject=?, body=?, version=?, updated_at=? WHERE id=?",
                     (name, (body.get("description") or "").strip()[:300], subj, text, ver, now, tid))
        conn.execute("INSERT OR IGNORE INTO email_template_versions VALUES (?,?,?,?,?)", (tid, ver, subj, text, now))
        audit(conn, f"Email template “{name}” saved (version {ver})")
        return tid
    tid = _insert_template(conn, {"name": name, "description": body.get("description"), "subject": subj, "body": text})
    audit(conn, f"Email template “{name}” created")
    return tid


def set_template_flag(conn, tid, enabled=None, default=None):
    t = get_template(conn, tid)
    if not t:
        raise MailError("That template no longer exists.")
    if enabled is not None:
        if not enabled and t["is_default"]:
            raise MailError("The default template can't be turned off. Make another template the default first.")
        conn.execute("UPDATE email_templates SET enabled=? WHERE id=?", (1 if enabled else 0, tid))
        audit(conn, f"Email template “{t['name']}” {'enabled' if enabled else 'disabled'}")
    if default:
        if not t["enabled"]:
            raise MailError("Turn the template on before making it the default.")
        conn.execute("UPDATE email_templates SET is_default=CASE WHEN id=? THEN 1 ELSE 0 END", (tid,))
        audit(conn, f"Default email template set to “{t['name']}”")


def delete_template(conn, tid):
    t = get_template(conn, tid)
    if not t:
        return
    if t["is_default"]:
        raise MailError("The default template can't be deleted. Make another template the default first.")
    used = [x for x in templates(conn) if x["id"] == tid and x["used_by"]]
    if used:
        raise MailError("This template is used by: " + ", ".join(used[0]["used_by"]) + ". Pick another template for those cards first.")
    conn.execute("DELETE FROM email_templates WHERE id=?", (tid,))          # versions stay for the history
    audit(conn, f"Email template “{t['name']}” deleted (its versions stay in the email history)")


def duplicate_template(conn, tid):
    t = get_template(conn, tid)
    if not t:
        raise MailError("That template no longer exists.")
    return _insert_template(conn, {"name": (t["name"] + " (copy)")[:80], "description": t["description"], "subject": t["subject"], "body": t["body"]})


def default_template(conn):
    r = conn.execute("SELECT * FROM email_templates WHERE is_default=1 AND enabled=1").fetchone() or \
        conn.execute("SELECT * FROM email_templates WHERE enabled=1 ORDER BY id").fetchone()
    return dbm.row_to_dict(r) if r else dict(DEFAULT_TEMPLATES[0], id=None, version=0)


# ------------------------------------------------------------------ rendering
def _safe_url(u):
    return u if isinstance(u, str) and re.match(r"^https?://[^\s<>\"']+$", u) else ""


def job_values(j):
    modes = j.get("arrangement") or j.get("work_arrangement")
    desc = re.sub(r"\s+", " ", (j.get("description") or "")).strip()
    return {"job_title": j.get("title") or "Untitled role", "company_name": j.get("company") or "Company not stated",
            "job_location": j.get("location") or "Location not stated", "work_mode": (modes or "Not stated").replace("onsite", "on-site"),
            "job_url": _safe_url(j.get("apply_url")) or _safe_url(j.get("source_url")), "salary": j.get("salary_text") or "Not stated",
            "job_description": (desc[:600] + "…") if len(desc) > 600 else (desc or "No description in the listing."),
            "match_score": str(round(j.get("score") or 0))}


def render(template, ctx, jobs, standard_html=None, for_html=True):
    """ctx: card-level values. jobs: list of job dicts. standard_html: the full job cards, used for {{job_list}}
    (or appended when the template has no job list). Returns (subject, body)."""
    def val(n, jv=None):
        n = _norm(n)
        if jv is not None and n in JOB_FIELDS:
            v = jv.get(n, "")
        else:
            v = ctx.get(n, "")
        v = "" if v is None else str(v)
        if not for_html:
            return v
        if n == "job_url":
            return f'<a href="{html.escape(v)}" style="color:#2a4fd6">{html.escape(v)}</a>' if v else "(no link available)"
        return html.escape(v)

    subject = TOKEN.sub(lambda m: str(ctx.get(_norm(m.group(2)), "")), template["subject"])
    subject = re.sub(r"\s+", " ", subject).strip()
    body = template["body"]
    has_list = bool(re.search(r"\{\{\s*#\s*jobs\s*\}\}|\{\{\s*job_list\s*\}\}", body, re.I))
    out, pos = [], 0
    for m in re.finditer(r"\{\{\s*#\s*jobs\s*\}\}(.*?)\{\{\s*/\s*jobs\s*\}\}", body, re.S | re.I):
        out.append(_render_flat(body[pos:m.start()], val, for_html, standard_html, jobs))
        block = m.group(1)
        if not jobs:
            out.append(html.escape("(No jobs in this email.)\n") if for_html else "(No jobs in this email.)\n")
        for j in jobs:
            jv = job_values(j)
            seg = TOKEN.sub(lambda t: val(t.group(2), jv), html.escape(block) if for_html else block)
            out.append(seg)
        pos = m.end()
    out.append(_render_flat(body[pos:], val, for_html, standard_html, jobs))
    text = "".join(out)
    if for_html:
        text = text.replace("\n", "<br>\n").replace("[[JOBLIST]]", standard_html or "")
        if not has_list and standard_html:
            text += "<br>\n" + standard_html
    elif not has_list:
        text += "\n\n" + _plain_list(jobs)
    return subject, text


def _render_flat(s, val, for_html, standard_html, jobs):
    if for_html:
        s = html.escape(s)
    def rep(t):
        n = _norm(t.group(2))
        if n == "job_list":
            return "[[JOBLIST]]" if for_html else _plain_list(jobs)
        return val(t.group(2))
    return TOKEN.sub(rep, s)


def _plain_list(jobs):
    if not jobs:
        return "No new matching jobs this time."
    lines = []
    for j in jobs:
        v = job_values(j)
        lines.append(f"- {v['job_title']} | {v['company_name']} | {v['job_location']} | {v['work_mode']} | match {v['match_score']} | {v['job_url'] or 'no link'}")
    return "\n".join(lines)


def wrap_html(subject, body_html, footer_html=""):
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(subject)}</title></head>'
            f'<body style="font-family:Segoe UI,Arial,sans-serif;color:#171a24;max-width:760px;margin:0 auto;padding:16px;font-size:15px;line-height:1.5">'
            f'{body_html}{footer_html}</body></html>')


SAMPLE_JOBS = [
    {"title": "Product Designer", "company": "Example Fintech Pvt Ltd", "location": "Bengaluru, India", "arrangement": "hybrid",
     "apply_url": "https://careers.example.com/jobs/101", "description": "Design end-to-end flows for our payments app. 3-5 years of product design, strong Figma and user research.",
     "score": 86, "salary_text": "18-24 LPA"},
    {"title": "UX Designer", "company": "Sample SaaS Co", "location": "Remote - India", "arrangement": "remote",
     "apply_url": "https://jobs.example.org/ux-designer", "description": "Own usability testing and prototypes for a B2B SaaS product.", "score": 78},
    {"title": "UI Designer", "company": None, "location": None, "arrangement": None, "apply_url": "not-a-link", "description": "", "score": 64},
]


def preview(template, card_name="Example search"):
    from .report import job_html, _tz
    ctx = {"job_search_name": card_name, "search_date": now_utc().strftime("%d %b %Y"), "total_jobs_found": len(SAMPLE_JOBS),
           "new_jobs_found": 2, "cities": "Bengaluru, Hyderabad", "work_modes": "hybrid, remote"}
    tz = _tz({})
    std = "".join(job_html(dict(j, freshness="3d", status="appears_active", reasons=["Example reason"], gaps=[]), tz, i + 1) for i, j in enumerate(SAMPLE_JOBS[:2]))
    subj, body = render(template, ctx, SAMPLE_JOBS, std, True)
    _, text = render(template, ctx, SAMPLE_JOBS, None, False)
    return {"subject": subj, "html": wrap_html(subj, body), "text": text}


# ------------------------------------------------------------------ card email settings (precedence)
def card_cfg_raw(row):
    """Stored per-card settings. Legacy cards (before 1.7) have none: the card's email field = its To list."""
    cfg = dbm.jload(row["email_json"], None) if "email_json" in row.keys() else None
    if not isinstance(cfg, dict):
        cfg = {"recipients_mode": "custom" if row["email"] else "global"} if "email" in row.keys() else {"recipients_mode": "global"}
    cfg.setdefault("recipients_mode", "global")
    return cfg


def resolve(conn, row, settings):
    """Effective email settings for one card: card setting > global setting > built-in default."""
    m = mail_settings(settings)
    cfg = card_cfg_raw(row)
    out = {"enabled": bool(row["email_on"]), "issues": []}
    # recipients
    mode = cfg.get("recipients_mode")
    if mode == "none":
        rec = {"to": [], "cc": [], "bcc": []}
        out["recipients_source"] = "none"
    elif mode == "custom":
        rec = {"to": split_addresses(row["email"]), "cc": cfg.get("cc") or [], "bcc": cfg.get("bcc") or []}
        out["recipients_source"] = "card"
    else:
        rec = {"to": m["to"], "cc": m["cc"], "bcc": m["bcc"]}
        out["recipients_source"] = "global"
    out["recipients"], probs = check_addresses(rec)
    out["issues"] += probs
    out["recipient_count"] = sum(len(v) for v in out["recipients"].values())
    # template
    t = None
    if cfg.get("template_id"):
        t = get_template(conn, cfg["template_id"])
        if not t:
            out["issues"].append("The card's email template was deleted; the default template is used.")
        elif not t["enabled"]:
            out["issues"].append(f"The card's template “{t['name']}” is turned off; the default template is used.")
            t = None
    out["template"] = t or default_template(conn)
    out["template_source"] = "card" if t else "global"
    # sender
    snd = cfg.get("sender") or m["sender"]
    out["sender_source"] = "card" if cfg.get("sender") else "global"
    out["sender"] = {"mode": snd.get("mode") if snd.get("mode") in SENDER_MODES else "default",
                     "accounts": [int(x) for x in snd.get("accounts") or []],
                     "strategy": snd.get("strategy") if snd.get("strategy") in STRATEGIES else "copy"}
    out["fallback"] = cfg.get("fallback") if cfg.get("fallback") in FALLBACKS else m["fallback"]
    out["default_account"] = m.get("default_account")
    return out


def plan_senders(conn, res, settings, card_id):
    """Which accounts send, and why. Returns list of {account, selected, fallback_reason} plus blocking problems."""
    m = mail_settings(settings)
    accs = {a["id"]: a for a in accounts(conn)}
    limit = int(m.get("daily_limit") or 450)
    rcount = max(1, res["recipient_count"])

    def usable(a):
        if not a:
            return "it was removed"
        if not a["has_password"] or a["status"] == "disconnected":
            return "it is disconnected"
        if a["status"] == "failed":
            return "its last sign-in failed (" + (a.get("last_error") or "check the app password")[:120] + ")"
        if a["status"] == "limited":
            return "Gmail's daily sending limit was reached"
        if a["sent_24h"] + rcount > limit:
            return f"it already sent to {a['sent_24h']} recipients in 24 hours (limit {limit})"
        return None

    s = res["sender"]
    dflt = res["default_account"]
    if s["mode"] == "default":
        chosen = [dflt] if dflt else []
    elif s["mode"] == "specific":
        chosen = s["accounts"][:1]
    else:
        chosen = s["accounts"]
        if s["strategy"] == "rotate" and chosen:
            last = conn.execute("""SELECT a.account_id FROM email_attempts a JOIN email_log l ON l.id=a.email_log_id
                                   WHERE l.profile_id=? AND a.status='sent' ORDER BY a.id DESC LIMIT 1""", (card_id,)).fetchone()
            order = chosen[:]
            if last and last[0] in order:
                i = order.index(last[0])
                order = order[i + 1:] + order[:i + 1]
            chosen = order          # first usable one is used below
    if not chosen:
        return [], ["No sending Gmail account is set up. Add one in Mail → Sending Gmail accounts" +
                    (" and make it the default." if accs else ".")]
    plan, problems, used = [], [], set()
    targets = chosen if not (s["mode"] == "multi" and s["strategy"] == "rotate") else chosen[:1]
    rotate_pool = chosen[1:] if (s["mode"] == "multi" and s["strategy"] == "rotate") else []
    for aid in targets:
        a = accs.get(aid)
        why = usable(a)
        if not why:
            plan.append({"account": a, "selected": a, "fallback_reason": None})
            used.add(aid)
            continue
        label = a["email"] if a else f"account #{aid}"
        alt = None
        pool = []
        if rotate_pool:
            pool = rotate_pool
        elif res["fallback"] == "default":
            pool = [dflt]
        elif res["fallback"] == "other":
            pool = [x for x in (s["accounts"] if s["mode"] == "multi" else list(accs)) if x != aid]
        for cand in pool:
            if cand in used or cand in targets and s["strategy"] == "copy" and s["mode"] == "multi":
                continue                      # never send a second copy from an account already sending one
            if not usable(accs.get(cand)):
                alt = accs[cand]
                break
        if alt:
            plan.append({"account": alt, "selected": a, "fallback_reason": f"{label} couldn't be used because {why}; sent from {alt['email']} instead"})
            used.add(alt["id"])
        else:
            plan.append({"account": None, "selected": a, "fallback_reason": None,
                         "error": f"{label} couldn't be used because {why}." + (" Fallback policy is ‘Stop and notify’." if res["fallback"] == "stop" and not rotate_pool else " No other account was available.")})
    return plan, problems


# ------------------------------------------------------------------ sending
def _send_one(account, pw, rec, subject, html_body, text_body, from_name):
    """Returns (status, message_id, retries, error). status: sent | failed | uncertain."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name or "Job Radar", account["email"]))
    if rec["to"]:
        msg["To"] = ", ".join(rec["to"])
    if rec["cc"]:
        msg["Cc"] = ", ".join(rec["cc"])
    mid = make_msgid(domain="jobradar.local")
    msg["Message-ID"] = mid
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    rcpts = rec["to"] + rec["cc"] + rec["bcc"]
    retries, last = 0, ""
    for attempt in range(3):
        try:
            s = _open(account["email"], pw)
        except smtplib.SMTPAuthenticationError:
            return "failed", mid, retries, "auth"
        except (OSError, smtplib.SMTPException) as e:          # nothing sent yet: safe to retry
            last = f"Couldn't connect to Gmail ({e.__class__.__name__})."
            retries += 1
            time.sleep(2 * (attempt + 1) if attempt < 2 else 0)
            continue
        try:
            refused = s.sendmail(account["email"], rcpts, msg.as_string())
            try:
                s.quit()
            except Exception:
                pass
            if refused:
                return "sent", mid, retries, "Gmail refused some recipients: " + ", ".join(refused)
            return "sent", mid, retries, None
        except smtplib.SMTPRecipientsRefused as e:
            return "failed", mid, retries, "Gmail refused every recipient: " + ", ".join(e.recipients)
        except (smtplib.SMTPDataError, smtplib.SMTPSenderRefused) as e:
            code = getattr(e, "smtp_code", 0) or 0
            text = (getattr(e, "smtp_error", b"") or b"").decode("utf-8", "replace")
            if "5.4.5" in text or "limit" in text.lower():
                return "failed", mid, retries, "limit"
            if 400 <= code < 500 and attempt < 2:              # Gmail refused it for now; it wasn't accepted
                retries += 1
                last = f"Gmail asked to try later ({code})."
                time.sleep(3 * (attempt + 1))
                continue
            return "failed", mid, retries, f"Gmail rejected the message ({code}): {text[:200]}"
        except (OSError, smtplib.SMTPServerDisconnected, socket.timeout) as e:
            # The connection broke while the message was being handed over: Gmail may already have it.
            return "uncertain", mid, retries, (f"The connection to Gmail broke while sending ({e.__class__.__name__}). Gmail may or may not "
                                              "have accepted it, so it was not sent again automatically. Check the Sent folder of "
                                              f"{account['email']} before resending.")
    return "failed", mid, retries, last or "Couldn't connect to Gmail."


def send(conn, settings, *, card_row, execution_id, schedule_id=None, trigger="run", jobs, ctx, standard_html, footer_html="",
         idem_key=None, only_accounts=None, reuse_message=None):
    """Send one card email according to its settings. Records an execution (email_log) and one attempt per account.
    Returns {"status", "sent_any", "note", "log_id"}."""
    from .cards import log as alog
    pid, name = card_row["id"], card_row["name"]
    res = resolve(conn, card_row, settings)
    now = iso(now_utc())

    def skip(reason):
        lid = conn.execute("""INSERT INTO email_log(profile_id, execution_id, at, status, jobs_included, recipients, emails_sent, error,
                              schedule_id, card_name, trigger, idem_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (pid, execution_id, now, "skipped", 0, None, 0, reason, schedule_id, name, trigger, idem_key)).lastrowid
        alog(conn, pid, "email_skipped", f"Email skipped: {reason}")
        return {"status": "skipped", "sent_any": False, "note": reason, "log_id": lid}

    if not (settings.get("email") or {}).get("enabled", True):
        return skip("sending email is turned off in Mail settings")
    if not res["enabled"]:
        return skip("email is turned off for this card")
    if idem_key:
        prev = conn.execute("SELECT id, status FROM email_log WHERE idem_key=? AND status IN ('sent','partial','sending','uncertain','pending')", (idem_key,)).fetchone()
        if prev:
            return {"status": "duplicate", "sent_any": prev["status"] in ("sent", "partial"), "note": "this email was already sent for this run", "log_id": prev["id"]}
    if res["recipients_source"] == "none":
        return skip("this card is set to not email anyone (results stay in the app)")
    if not res["recipient_count"]:
        return skip("no recipients: add To addresses in Mail → Default recipients, or in the card's Email settings")
    plan, problems = plan_senders(conn, res, settings, pid)
    if problems:
        return skip(problems[0])
    if only_accounts:
        plan = [p for p in plan if (p["selected"] or {}).get("id") in only_accounts or (p["account"] or {}).get("id") in only_accounts]
    t = res["template"]
    if reuse_message:
        subject, body_html, text = reuse_message
    else:
        subject, body = render(t, ctx, jobs, standard_html, True)
        _, text = render(t, ctx, jobs, None, False)
        body_html = wrap_html(subject, body, footer_html)
    rec = res["recipients"]
    m = mail_settings(settings)
    lid = conn.execute("""INSERT INTO email_log(profile_id, execution_id, at, status, jobs_included, recipients, emails_sent, subject, error,
                          schedule_id, card_name, trigger, template_id, template_name, template_version, sender_mode, strategy,
                          selected_accounts, recipients_count, idem_key, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                       (pid, execution_id, now, "pending", len(jobs), ", ".join(rec["to"] + rec["cc"]) + (f" (+{len(rec['bcc'])} BCC)" if rec["bcc"] else ""),
                        0, subject, None, schedule_id, name, trigger, t.get("id"), t.get("name"), t.get("version"),
                        res["sender"]["mode"], res["sender"]["strategy"],
                        ", ".join(p["selected"]["email"] for p in plan if p.get("selected")), res["recipient_count"], idem_key,
                        "; ".join(res["issues"]) or None)).lastrowid
    conn.execute("INSERT OR REPLACE INTO email_messages VALUES (?,?,?,?,?)", (lid, subject, body_html, text, json.dumps(rec)))
    conn.execute("UPDATE email_log SET status='sending' WHERE id=?", (lid,))
    conn.commit()
    results = []
    for p in plan:
        a = p["account"]
        aid = conn.execute("""INSERT INTO email_attempts(email_log_id, account_id, account_email, selected_email, fallback_reason, status,
                              recipients_count, at) VALUES (?,?,?,?,?,?,?,?)""",
                           (lid, a["id"] if a else None, a["email"] if a else None, (p.get("selected") or {}).get("email"),
                            p.get("fallback_reason"), "pending" if a else "failed", res["recipient_count"], iso(now_utc()))).lastrowid
        if not a:
            conn.execute("UPDATE email_attempts SET error=? WHERE id=?", (p["error"], aid))
            results.append(("failed", p["error"]))
            continue
        conn.execute("UPDATE email_attempts SET status='sending' WHERE id=?", (aid,))
        conn.commit()
        try:
            pw = get_secret(a["id"])
        except MailError as e:
            pw, err = None, str(e)
        if not pw:
            st, mid, retries, err = "failed", None, 0, "No app password is saved for this account. Press Reconnect in Mail."
        else:
            st, mid, retries, err = _send_one(a, pw, rec, subject, body_html, text, m.get("from_name"))
        if err == "auth":
            err = f"Gmail rejected the sign-in for {a['email']} (app password wrong, revoked or 2-Step Verification turned off). Press Reconnect in Mail."
            conn.execute("UPDATE mail_accounts SET status='failed', last_error=?, last_checked=? WHERE id=?", (err, iso(now_utc()), a["id"]))
            audit(conn, f"Sign-in failed for {a['email']} while sending “{name}”")
        elif err == "limit":
            err = f"Gmail's daily sending limit was reached for {a['email']}. It can send again within 24 hours."
            conn.execute("UPDATE mail_accounts SET status='limited', limited_until=?, last_error=? WHERE id=?",
                         (iso(now_utc() + timedelta(hours=24)), err, a["id"]))
        elif st == "sent":
            conn.execute("UPDATE mail_accounts SET status='connected', last_error=NULL WHERE id=? AND status!='limited'", (a["id"],))
        conn.execute("UPDATE email_attempts SET status=?, message_id=?, retries=?, error=?, at=? WHERE id=?",
                     (st, mid, retries, err, iso(now_utc()), aid))
        conn.commit()
        results.append((st, err))
        if p.get("fallback_reason"):
            alog(conn, pid, "email", "Sender fallback: " + p["fallback_reason"])
    sent = sum(1 for s, _ in results if s == "sent")
    unc = sum(1 for s, _ in results if s == "uncertain")
    status = "sent" if sent == len(results) else ("partial" if sent else ("uncertain" if unc else "failed"))
    errs = [e for s, e in results if s != "sent" and e]
    note = "; ".join(errs) or None
    conn.execute("UPDATE email_log SET status=?, emails_sent=?, error=? WHERE id=?", (status, sent, note, lid))
    accts = ", ".join(p["account"]["email"] for p in plan if p["account"])
    msg = {"sent": f"Email sent from {accts} to {res['recipient_count']} recipient(s) ({len(jobs)} jobs, template “{t.get('name')}”)",
           "partial": f"Email partly sent: {sent} of {len(results)} accounts succeeded. {note}",
           "uncertain": f"Email outcome unconfirmed: {note}",
           "failed": f"Email failed: {note}"}[status]
    alog(conn, pid, "email_" + ("sent" if status == "sent" else "failed" if status == "failed" else "partial"), msg)
    conn.commit()
    return {"status": status, "sent_any": sent > 0, "note": msg, "log_id": lid}


def resend(conn, settings, log_id, confirm_uncertain=False):
    """Send a failed / unconfirmed / partly sent email again, only from the accounts that didn't succeed."""
    lg = conn.execute("SELECT * FROM email_log WHERE id=?", (log_id,)).fetchone()
    if not lg:
        raise MailError("That email record no longer exists.")
    if lg["status"] not in ("failed", "partial", "uncertain"):
        raise MailError("Only failed, unconfirmed or partly sent emails can be resent.")
    if lg["status"] == "uncertain" and not confirm_uncertain:
        raise MailError("uncertain")
    msg = conn.execute("SELECT * FROM email_messages WHERE email_log_id=?", (log_id,)).fetchone()
    row = conn.execute("SELECT * FROM profiles WHERE id=?", (lg["profile_id"],)).fetchone()
    if not row:
        raise MailError("The card for this email was deleted.")
    failed = [r["account_id"] or -1 for r in conn.execute("SELECT * FROM email_attempts WHERE email_log_id=? AND status!='sent'", (log_id,))]
    sel = {r["account_id"] for r in conn.execute("SELECT a.account_id FROM email_attempts a WHERE email_log_id=? AND status!='sent'", (log_id,))}
    n = conn.execute("SELECT COUNT(*) FROM email_log WHERE idem_key LIKE ?", (f"resend:{log_id}:%",)).fetchone()[0]
    reuse = (msg["subject"], msg["html"], msg["text"]) if msg else None
    r = send(conn, settings, card_row=row, execution_id=lg["execution_id"], schedule_id=lg["schedule_id"], trigger="resend",
             jobs=[None] * (lg["jobs_included"] or 0), ctx={}, standard_html="", idem_key=f"resend:{log_id}:{n + 1}",
             only_accounts=({x for x in sel if x} if lg["status"] == "partial" else None), reuse_message=reuse)
    if r["sent_any"] and lg["status"] in ("failed", "uncertain"):
        conn.execute("UPDATE email_log SET note=COALESCE(note || '; ', '') || ? WHERE id=?", (f"Resent as record #{r['log_id']}", log_id))
    return r, failed


def context(p, jobs, new_count, settings):
    from .report import _tz
    from .normalize import work_modes, modes_text
    d = now_utc().astimezone(_tz(settings))
    return {"job_search_name": p.get("name") or "Job search", "search_date": d.strftime("%d %b %Y"),
            "total_jobs_found": len(jobs), "new_jobs_found": new_count,
            "cities": ", ".join(p.get("locations") or ["India"]),
            "work_modes": modes_text(work_modes(p.get("work_modes") if p.get("work_modes") is not None else p.get("work_arrangement")))}


def history(conn, profile_id=None, limit=150):
    q = "SELECT * FROM email_log" + (" WHERE profile_id=?" if profile_id else "") + " ORDER BY id DESC LIMIT ?"
    rows = [dbm.row_to_dict(r) for r in conn.execute(q, ((profile_id, limit) if profile_id else (limit,)))]
    for r in rows:
        r["attempts"] = [dbm.row_to_dict(a) for a in conn.execute("SELECT * FROM email_attempts WHERE email_log_id=? ORDER BY id", (r["id"],))]
        r["has_message"] = bool(conn.execute("SELECT 1 FROM email_messages WHERE email_log_id=?", (r["id"],)).fetchone())
    return rows


def prune(conn, keep=300):
    """Keep stored message bodies for the last `keep` emails only (recipients/history rows stay)."""
    conn.execute("DELETE FROM email_messages WHERE email_log_id NOT IN (SELECT id FROM email_log ORDER BY id DESC LIMIT ?)", (keep,))


def migrate_legacy_settings(conn, settings):
    """1.6 → 1.7: the single Gmail address + app password in settings.json becomes account #1 (encrypted)."""
    from .config import save_settings
    em = settings.get("email") or {}
    changed = False
    if em.get("username") and em.get("app_password") and not conn.execute("SELECT 1 FROM mail_accounts").fetchone():
        now = iso(now_utc())
        enc = protect("".join(str(em["app_password"]).split()))
        aid = conn.execute("INSERT INTO mail_accounts(email, from_name, status, created_at, updated_at) VALUES (?,?,?,?,?)",
                           (em["username"].strip(), em.get("from_name"), "untested", now, now)).lastrowid
        d = _load_secrets(); d[f"account:{aid}"] = enc; _save_secrets(d)
        conn.commit()
        settings.setdefault("mail", {})["default_account"] = aid
        audit(conn, f"Gmail account {em['username']} moved to the new Mail settings (app password now encrypted)")
        changed = True
    if em.get("app_password"):
        em["app_password"] = ""          # never keep it in plain text any more
        changed = True
    if changed:
        settings["email"] = em
        save_settings(settings)
    return changed
