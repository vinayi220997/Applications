"""Daily report: HTML (email + saved file) and plain text, plus SMTP delivery."""
import html
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

from .freshness import CATEGORIES
from .normalize import parse_date

STATUS_LABEL = {"verified_active": "Verified active", "appears_active": "Appears active",
                "closed": "Closed or expired", "unable_to_verify": "Unable to verify"}
STATUS_COLOR = {"verified_active": "#137a4b", "appears_active": "#2a4fd6", "closed": "#b42318", "unable_to_verify": "#8a6100"}


FIXED_OFFSETS = {"Asia/Kolkata": (5, 30), "Asia/Calcutta": (5, 30), "UTC": (0, 0), "Asia/Dubai": (4, 0),
                 "Asia/Singapore": (8, 0), "Europe/London": (0, 0), "America/New_York": (-5, 0)}


def _tz(settings):
    """Windows Python has no timezone database unless 'tzdata' is installed, so fall back to a fixed offset."""
    name = settings.get("timezone") or "Asia/Kolkata"
    try:
        return ZoneInfo(name)
    except Exception:
        from datetime import timedelta, timezone
        h, m = FIXED_OFFSETS.get(name, (5, 30))
        return timezone(timedelta(hours=h, minutes=m if h >= 0 else -m), name)


def fmt(ts, tz, with_time=False):
    d = parse_date(ts)
    if not d:
        return None
    return d.astimezone(tz).strftime("%d %b %Y, %I:%M %p" if with_time else "%d %b %Y")


def e(s):
    return html.escape("" if s is None else str(s))


def job_html(j, tz, n):
    pub = fmt(j.get("published_at"), tz)
    pub_txt = (pub + (" (from another listing of this job)" if j.get("published_from") else "")) if pub else "Unknown (source gives no date)"
    link = lambda url, label: f'<a href="{e(url)}" style="color:#2a4fd6">{e(label)}</a>' if url else "—"
    apply_label = "Apply" + ("" if j.get("apply_url_verified", True) else " (link unverified)")
    also = "".join(f" · {link(u, s)}" for s, u in (j.get("also_seen_on") or [])[:4])
    desc = (j.get("description") or "").strip()
    desc = desc[:900] + ("… (full description on the job page)" if len(desc) > 900 else "")
    rows = [
        ("Location", j.get("location")), ("Work arrangement", j.get("arrangement") or j.get("work_arrangement") or "Not stated"),
        ("Employment type", j.get("employment_type") or "Not stated"), ("Published", pub_txt),
        ("First discovered", fmt(j.get("first_seen_at"), tz)), ("Salary", j.get("salary_text") or "Not stated"),
        ("Experience required", j.get("experience_text") or "Not stated"),
        ("Status", f'<b style="color:{STATUS_COLOR.get(j.get("status"), "#444")}">{e(STATUS_LABEL.get(j.get("status"), "Unable to verify"))}</b>'
                   + (f' – {e(j.get("verify_note"))}' if j.get("verify_note") else "")),
        ("Last verified", (fmt(j.get("verified_at"), tz, True) or "—") + " IST"),
    ]
    tr = "".join(f'<tr><td style="color:#5b6173;padding:2px 12px 2px 0;vertical-align:top;white-space:nowrap">{k}</td>'
                 f'<td style="padding:2px 0">{v if k == "Status" else e(v)}</td></tr>' for k, v in rows)
    reasons = "".join(f"<li>{e(r)}</li>" for r in j.get("reasons") or []) or "<li>—</li>"
    gaps = "".join(f"<li>{e(g)}</li>" for g in j.get("gaps") or []) or "<li>Nothing flagged</li>"
    change = {"updated": " · <b>Updated since last report</b>", "reopened": " · <b>Reposted / reopened</b>"}.get(j.get("change"), "")
    return f"""
<div style="border:1px solid #d8dbe4;border-radius:10px;padding:14px 16px;margin:0 0 14px">
  <div style="font-size:12px;color:#5b6173">#{n} · {e(CATEGORIES.get(j.get('freshness'), ''))}{change}</div>
  <div style="font-size:18px;font-weight:700;margin:4px 0">{e(j.get('title'))}</div>
  <div style="font-size:15px"><b>{e(j.get('company'))}</b> &nbsp;·&nbsp; Match <b>{round(j.get('score') or 0)}/100</b></div>
  <table style="font-size:14px;margin:8px 0;border-collapse:collapse">{tr}</table>
  <div style="font-size:14px"><b>Why it matches</b><ul style="margin:4px 0 8px">{reasons}</ul>
  <b>Missing or uncertain</b><ul style="margin:4px 0 8px">{gaps}</ul></div>
  <div style="font-weight:600;font-size:14px;margin-top:4px">Job description</div>
  <div style="white-space:pre-wrap;font-size:13px;color:#2b2f3a;background:#f3f4f7;border-radius:8px;padding:10px;margin-top:6px">{e(desc) or 'The source did not include a description.'}</div>
  <div style="margin-top:10px;font-size:14px">
    <a href="{e(j.get('apply_url'))}" style="background:#2a4fd6;color:#fff;padding:7px 14px;border-radius:7px;text-decoration:none;font-weight:600">{apply_label}</a>
    {('&nbsp; ' + link(j.get('careers_url'), 'Company careers page') + ' &nbsp;·') if j.get('careers_url') else ''} &nbsp;Source: {link(j.get('source_url'), j.get('source_name'))}{also}
  </div>
</div>"""


def section(title, jobs, tz, start=1, note=""):
    if not jobs:
        return ""
    body = "".join(job_html(j, tz, start + i) for i, j in enumerate(jobs))
    return f'<h2 style="font-size:18px;margin:26px 0 10px">{e(title)} ({len(jobs)})</h2>{note}{body}'


def jobs_html(sections, settings):
    """The standard job cards (all sections), used in the saved report and for {{job_list}} in email templates."""
    tz = _tz(settings)
    n, parts = 1, []
    for title, key, note in SECTIONS:
        jobs = sections.get(key) or []
        parts.append(section(title, jobs, tz, n, note))
        n += len(jobs)
    if not any(sections.get(k) for k in ("top24", "week", "changed", "unknown", "older")):
        parts.append('<p style="font-size:15px;margin:20px 0"><b>No new jobs that meet every one of your criteria today.</b> '
                     + ('The jobs below are still open or come close, so you still have something to act on.' if (sections.get("still_open") or sections.get("close")) else
                        'Every source was checked. Try widening the search (more cities, any work mode, similar job titles).') + '</p>')
    still = sections.get("still_open") or []
    parts.append(section("Reported earlier and still open", still[:10], tz, n,
                         '<p style="font-size:13px;color:#5b6173">Sent before; listed again so you have them in one place.</p>'))
    n += len(still[:10])
    parts.append(section("Close matches (don't meet every criterion)", sections.get("close") or [], tz, n,
                         '<p style="font-size:13px;color:#5b6173">Strongly related jobs that miss one of your settings, such as the city or work mode. '
                         'The reason is shown under "Missing or uncertain".</p>'))
    return "".join(parts)


def footer_html(failures, manual_links):
    fail_html = "".join(f"<li>{e(f)}</li>" for f in failures) or "<li>None. All configured sources responded.</li>"
    links = "".join(f'<li><a href="{e(u)}">{e(n_)}</a></li>' for n_, u in manual_links)
    return (f'<h2 style="font-size:16px;margin:26px 0 8px">Source failures or incomplete coverage</h2><ul style="font-size:13px">{fail_html}</ul>'
            f'<h2 style="font-size:16px;margin:20px 0 8px">Not scanned automatically – search these yourself</h2>'
            f'<p style="font-size:13px;color:#5b6173">LinkedIn, Naukri, Indeed, Glassdoor, Foundit, Wellfound and Dice don\'t offer an open API, so the agent doesn\'t scrape them. These links open a pre-filled search.</p>'
            f'<ul style="font-size:13px">{links}</ul>'
            f'<p style="font-size:12px;color:#5b6173;margin-top:24px">Sent by Job Radar. Job Radar never applies on your behalf.</p>')


SECTIONS = [
    ("Top opportunities published in the last 24 hours", "top24", ""),
    ("Other strong matches published in the last 7 days", "week", ""),
    ("Previously reported jobs that have changed", "changed", ""),
    ("Jobs with an unknown publication date", "unknown", '<p style="font-size:13px;color:#5b6173">These sources do not publish a date. "First discovered" is when this agent first saw the job, not when it was posted.</p>'),
    ("Older but still open", "older", ""),
]


def build(profile, sections, stats, failures, manual_links, settings):
    tz = _tz(settings)
    now = datetime.now(tz)
    head = [
        ("Scan date and time", now.strftime("%d %b %Y, %I:%M %p")), ("Timezone", str(tz)),
        ("Sources configured", stats["sources_configured"]), ("Sources scanned successfully", stats["sources_scanned"]),
        ("Jobs retrieved", stats["retrieved"]), ("Unique jobs after deduplication", stats["unique"]),
        ("Newly discovered matches", stats["new"]), ("Recently published (≤7 days)", stats["recent"]),
        ("Verified active", stats["verified"]), ("High-match opportunities", stats["high"]),
    ]
    hdr = "".join(f'<tr><td style="color:#5b6173;padding:2px 14px 2px 0">{k}</td><td><b>{e(v)}</b></td></tr>' for k, v in head)
    n = 1
    parts = []
    for title, key, note in [
        ("Top opportunities published in the last 24 hours", "top24", ""),
        ("Other strong matches published in the last 7 days", "week", ""),
        ("Previously reported jobs that have changed", "changed", ""),
        ("Jobs with an unknown publication date", "unknown", '<p style="font-size:13px;color:#5b6173">These sources do not publish a date. "First discovered" is when this agent first saw the job, not when it was posted.</p>'),
        ("Older but still open", "older", ""),
    ]:
        jobs = sections.get(key) or []
        parts.append(section(title, jobs, tz, n, note))
        n += len(jobs)
    if not any(sections.get(k) for k in ("top24", "week", "changed", "unknown", "older")):
        parts.append('<p style="font-size:15px;margin:20px 0"><b>No new jobs that meet every one of your criteria today.</b> '
                     + ('The jobs below are still open or come close, so you still have something to act on.' if (sections.get("still_open") or sections.get("close")) else
                        'Every source below was checked. Try widening the search (more cities, any work arrangement, similar job titles).') + '</p>')
    still = sections.get("still_open") or []
    parts.append(section("Reported earlier and still open", still[:10], tz, n,
                         '<p style="font-size:13px;color:#5b6173">Sent before; listed again so you have them in one place.</p>'))
    n += len(still[:10])
    close = sections.get("close") or []
    parts.append(section("Close matches (don't meet every criterion)", close, tz, n,
                         '<p style="font-size:13px;color:#5b6173">Strongly related jobs that miss one of your settings, such as the city or work arrangement. '
                         'The reason is shown under "Missing or uncertain". Widen the search in Job Radar to include jobs like these as full matches.</p>'))
    fail_html = "".join(f"<li>{e(f)}</li>" for f in failures) or "<li>None. All configured sources responded.</li>"
    links = "".join(f'<li><a href="{e(u)}">{e(n_)}</a></li>' for n_, u in manual_links)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Job Radar – {e(profile.get('name'))}</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;color:#171a24;max-width:760px;margin:0 auto;padding:16px">
<div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#5b6173">Daily Job Discovery Report</div>
<h1 style="font-size:24px;margin:4px 0 6px">{e(profile.get('name'))}</h1>
<div style="font-size:14px;color:#5b6173;margin-bottom:12px">{e(profile.get('summary'))}</div>
<table style="font-size:14px;border-collapse:collapse">{hdr}</table>
{''.join(parts)}
<h2 style="font-size:16px;margin:26px 0 8px">Source failures or incomplete coverage</h2><ul style="font-size:13px">{fail_html}</ul>
<h2 style="font-size:16px;margin:20px 0 8px">Not scanned automatically – search these yourself</h2>
<p style="font-size:13px;color:#5b6173">LinkedIn, Naukri, Indeed, Glassdoor, Foundit, Wellfound and Dice don't offer an open API, so the agent doesn't scrape them. These links open a pre-filled search.</p>
<ul style="font-size:13px">{links}</ul>
<p style="font-size:12px;color:#5b6173;margin-top:24px">Remote listings include data from Remotive, Remote OK (remoteok.com), Jobicy and We Work Remotely. Employer listings come from the companies' own Greenhouse, Lever, Ashby, SmartRecruiters, Workable and Recruitee job boards. Job Radar never applies on your behalf.</p>
</body></html>"""


def plain_text(profile, sections):
    lines = [f"Job Radar – {profile.get('name')}", ""]
    for key in ("top24", "week", "changed", "unknown", "older", "still_open", "close"):
        for j in sections.get(key) or []:
            lines.append(f"- {j.get('title')} | {j.get('company')} | {j.get('location')} | match {round(j.get('score') or 0)} | {j.get('apply_url')}")
    if len(lines) == 2:
        lines.append("No new matching jobs today.")
    return "\n".join(lines)


def send_email(settings, to, subject, html_body, text_body):
    cfg = settings.get("email") or {}
    if not cfg.get("enabled"):
        return False, "email sending is not configured (Settings → Email: tick 'Send reports by email')"
    if not cfg.get("username"):
        return False, "email sending is not configured (Settings → Email: the sending Gmail address is empty)"
    if not cfg.get("app_password"):
        return False, "email sending is not configured (Settings → Email: the Gmail app password is empty)"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f'{cfg.get("from_name", "Job Radar")} <{cfg["username"]}>'
    msg["To"] = to
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    user = cfg["username"].strip()
    pw = "".join(str(cfg["app_password"]).split())          # Gmail shows app passwords with spaces
    host = cfg.get("smtp_host", "smtp.gmail.com")
    recipients = [x.strip() for x in str(to).replace(";", ",").split(",") if x.strip()]
    try:
        try:
            with smtplib.SMTP(host, int(cfg.get("smtp_port", 587)), timeout=30) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(user, pw)
                s.sendmail(user, recipients, msg.as_string())
        except (OSError, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as first:
            if isinstance(first, smtplib.SMTPAuthenticationError):
                raise
            # Some networks block port 587; Gmail also accepts SSL on 465.
            with smtplib.SMTP_SSL(host, 465, timeout=30, context=ssl.create_default_context()) as s:
                s.login(user, pw)
                s.sendmail(user, recipients, msg.as_string())
        return True, "sent"
    except smtplib.SMTPAuthenticationError:
        return False, ("email failed: Gmail rejected the sign-in. Use a 16-letter app password from "
                       "myaccount.google.com/apppasswords for the sending address, not your normal password.")
    except smtplib.SMTPRecipientsRefused:
        return False, f"email failed: Gmail refused the recipient address {to}. Check it for typos."
    except (OSError, smtplib.SMTPException) as ex:
        return False, (f"email failed: couldn't connect to Gmail's mail server ({ex.__class__.__name__}: {ex}). "
                       "A firewall, antivirus or office network may be blocking outgoing email (ports 587 and 465).")
    except Exception as ex:   # report, never crash the run
        return False, f"email failed: {ex.__class__.__name__}: {ex}"
