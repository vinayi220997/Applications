"""End-to-end check of the whole flow, simulating Windows (no timezone database) with fake job sites and a fake Gmail."""
import json, os, sys, threading, time, shutil
from unittest import mock
from datetime import timedelta
ROOT = "/tmp/jrflow"
shutil.rmtree(ROOT, ignore_errors=True); shutil.copytree("/home/claude/jobradar-agent", ROOT, ignore=shutil.ignore_patterns("data", "reports", "secrets.json", "settings.json"))
sys.path.insert(0, ROOT); os.chdir(ROOT)

import zoneinfo
def no_tz(*a, **k): raise zoneinfo.ZoneInfoNotFoundError("No time zone found (simulated Windows)")
import jobradar.report as report
report.ZoneInfo = no_tz

from jobradar import pipeline as pl, web
from jobradar.normalize import iso, now_utc
from jobradar.sources import boards
h = lambda n: iso(now_utc() - timedelta(hours=n))
GH = {"jobs": [
  {"id": 1, "title": "Backend Engineer", "first_published": h(3), "updated_at": h(3), "location": {"name": "Bengaluru, India"},
   "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/1", "content": "&lt;p&gt;Python, Django, AWS. 3-5 years of experience. Build payment APIs.&lt;/p&gt;"},
  {"id": 2, "title": "Software Developer", "first_published": h(70), "updated_at": h(70), "location": {"name": "Remote - India"},
   "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/2", "content": "&lt;p&gt;Python and AWS. 4+ years of experience.&lt;/p&gt;"}]}
def fake_get_json(url, timeout=20, retries=2, headers=None):
    if "boards/acme/jobs" in url: return GH
    if "boards/acme" in url: return {"name": "Acme Pay"}
    from jobradar.http import FetchError; raise FetchError("HTTP 404", 404)

SENT = []
class FakeSMTP:
    def __init__(self, host, port, timeout=None, context=None): self.port = port
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def starttls(self, context=None): pass
    def login(self, u, p):
        import smtplib
        if p != "abcdefghijklmnop": raise smtplib.SMTPAuthenticationError(535, b"bad credentials")
    def sendmail(self, frm, to, msg): SENT.append({"from": frm, "to": to, "msg": msg}); return {}
    def quit(self): pass

patches = [mock.patch("jobradar.sources.ats.get_json", fake_get_json), mock.patch.object(pl, "online", return_value=True),
           mock.patch.object(pl, "load_company_candidates", return_value=[{"ats": "greenhouse", "token": "acme"}, {"ats": "lever", "token": "gone"}]),
           mock.patch.dict(boards.BOARDS, {}, clear=True), mock.patch("smtplib.SMTP", FakeSMTP), mock.patch("smtplib.SMTP_SSL", FakeSMTP),
           mock.patch("jobradar.doctor.online", return_value=True), mock.patch("jobradar.scheduler.subprocess.run")]
for p in patches: p.start()

srv = web.ThreadingHTTPServer(("127.0.0.1", 8765), web.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()

from playwright.sync_api import sync_playwright
problems = []
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1300, "height": 1000}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("response", lambda r: errs.append(f"{r.status} {r.url}") if r.status >= 500 else None)
    pg.goto("http://127.0.0.1:8765/"); pg.wait_for_timeout(800)
    # 1. intake
    pg.fill("#chatText", "Backend developer, Python Django AWS, 4 years, Bengaluru"); pg.click("#send"); pg.wait_for_timeout(500)
    if pg.locator("#confirmBtn").count(): pg.click("#confirmBtn"); pg.wait_for_timeout(200)
    asked = []
    for _ in range(12):
        if pg.locator(".summary").count(): break
        q = pg.locator(".msg.bot .b").last.inner_text()
        asked.append(q.split("\n")[-1][:60])
        ans = "vinayi220997@gmail.com" if "email" in q.lower() else ("Vinay – backend" if "call this search" in q else ("Yes" if "remote jobs at international" in q or "Is that right" in q or "Reply yes" in q else ("Any" if "arrangement" in q else "skip")))
        pg.fill("#chatText", ans); pg.click("#send"); pg.wait_for_timeout(400)
        if pg.locator("#confirmBtn").count(): pg.click("#confirmBtn"); pg.wait_for_timeout(200)
    print("Questions asked:", asked)
    if not pg.locator(".summary").count(): problems.append("intake never finished")
    print("Summary:", pg.inner_text(".summary").replace("\n", " | ")[:400])
    # 2. save + scan (email not set up yet)
    pg.click("text=Save and scan"); pg.wait_for_timeout(5000)
    print("Scan log end:", pg.inner_text("#log").splitlines()[-2:])
    print("Card after scan:", pg.locator(".jc").first.inner_text().replace("\n", " | ")[:400])
    pg.click(".jc >> nth=0 >> button:has-text('View results')"); pg.wait_for_timeout(800)
    print("Jobs shown:", pg.locator(".job").count(), "| banner:", pg.inner_text("#banner")[:60])
    if pg.locator(".job").count() != 2: problems.append("expected 2 jobs")
    # 3. Mail tab: add accounts (wrong then right password), recipients, test
    pg.click("#tabMail"); pg.wait_for_timeout(600)
    pg.click("text=Add Gmail account"); pg.fill("#dlgBody input[type=email]", "sender@gmail.com"); pg.fill("#dlgBody input[type=password]", "zzzz zzzz zzzz zzzz")
    pg.click("#dlgActs button:has-text('Add account')"); pg.wait_for_timeout(800); print("Wrong password:", pg.inner_text("#toasts")[-160:].replace("\n", " "))
    pg.fill("#dlgBody input[type=password]", "abcd efgh ijkl mnop"); pg.click("#dlgActs button:has-text('Add account')"); pg.wait_for_timeout(900)
    pg.click("text=Add Gmail account"); pg.fill("#dlgBody input[type=email]", "second@gmail.com"); pg.fill("#dlgBody input[type=password]", "abcdefghijklmnop")
    pg.click("#dlgActs button:has-text('Add account')"); pg.wait_for_timeout(900)
    print("Accounts:", pg.inner_text("#mailBox section >> nth=1").replace("\n", " | ")[:400])
    pg.click("details.adv summary"); pg.wait_for_timeout(200)
    to = pg.locator("#mailBox section >> nth=2").locator("input[type=email]")
    to.nth(0).fill("vinayi220997@gmail.com, bad@, vinayi220997@gmail.com"); to.nth(0).press("Enter"); pg.wait_for_timeout(200)
    print("Recipient validation:", pg.inner_text("#mailBox section >> nth=2").replace("\n", " | ")[-260:])
    pg.click("#mailBox section >> nth=3 >> button:has-text('Save recipients and rules')"); pg.wait_for_timeout(500); print("Save with bad:", pg.inner_text("#toasts")[-120:].replace("\n", " "))
    sec = pg.locator("#mailBox section >> nth=2")
    for t in sec.locator(".tag").all()[::-1]:
        txt = t.inner_text()
        if "bad@" in txt or (txt.startswith("vinay") and sec.locator(".tag").count() > 1 and t != sec.locator(".tag").first): t.locator("button").click(); pg.wait_for_timeout(100)
    sec.locator("input[type=email]").nth(1).fill("dilip@blive.co.in"); sec.locator("input[type=email]").nth(1).press("Enter")
    pg.click("#mailBox section >> nth=3 >> button:has-text('Save recipients and rules')"); pg.wait_for_timeout(700)
    print("Saved:", pg.inner_text("#toasts")[-80:].replace("\n", " "))
    pg.click("#mailBox section >> nth=1 >> button:has-text('Send test') >> nth=0"); pg.wait_for_timeout(200); pg.click("#dlgActs button:has-text('Send test')"); pg.wait_for_timeout(800)
    print("Test email:", pg.inner_text("#toasts")[-120:].replace("\n", " "))
    # 4. email results now
    pg.click("#tabCards"); pg.click(".jc >> nth=0 >> summary"); pg.click(".jc >> nth=0 >> text=Email results now"); pg.wait_for_timeout(1500); print("Email now:", pg.inner_text("#toasts")[-160:].replace("\n"," "))
    # 4b. card email settings: template B + both accounts, copy from each (confirm)
    pg.click(".jc >> nth=0 >> button:has-text('Email settings')"); pg.wait_for_timeout(400)
    pg.select_option("#dlgBody select", label="New Job Opportunities")
    pg.click("#dlgBody label:has-text('Several accounts')"); pg.wait_for_timeout(100)
    pg.click("#dlgBody label:has-text('Several accounts')"); pg.wait_for_timeout(100)
    for c in pg.locator("#dlgBody .checklist input").all(): c.check()
    pg.click("#dlgBody label:has-text('Send a copy from each account')")
    pg.click("#dlgActs button:has-text('Save')"); pg.wait_for_timeout(500)
    print("Copy confirm:", pg.inner_text("#dlgBody")[:120].replace("\n", " ")); pg.click("#dlgActs button:has-text('Yes, send copies')"); pg.wait_for_timeout(800)
    print("Card email block:", pg.locator(".jc").first.locator(".blk").nth(2).inner_text().replace("\n", " | ")[:300])
    # 5. setup check
    pg.click("#docBtn"); pg.wait_for_timeout(1500); print("Checks:", [c.replace("\n", " ")[:70] for c in pg.locator(".checks li").all_inner_texts()])
    # 6. schedule
    pg.keyboard.press("Escape"); pg.click(".jc >> nth=0 >> button:has-text('Schedule')"); pg.click("#dlgActs button:has-text('own schedule')"); pg.wait_for_timeout(300)
    pg.click("#dlgActs button:has-text('Save schedule')"); pg.wait_for_timeout(800); print("Card schedule:", pg.locator(".jc").first.locator(".blk").first.inner_text().replace("\n"," "))
    # 7. scan again -> nothing new, but the 'no new matches' email should still go out
    n0 = len(SENT); pg.click("#runAll"); pg.wait_for_timeout(5000)
    print("Second scan emails:", [(s["from"], s["to"], s["msg"].split("Subject: ")[1].split("\n")[0][:80]) for s in SENT[n0:]])
    print("Card after 2nd scan:", pg.locator(".jc").first.inner_text().replace("\n", " | ")[:600])
    pg.click(".jc >> nth=0 >> button:has-text('History')"); pg.wait_for_timeout(500)
    print("History:", pg.inner_text("#dlgBody").replace("\n", " | ")[:700]); pg.click("#dlgBody .seg2 button >> nth=2"); print("Emails:", pg.inner_text("#dlgBody").replace("\n", " | ")[:500])
    print("Browser errors:", errs)
    b.close()

print("\nEMAILS SENT:")
import email
for s in SENT:
    m = email.message_from_string(s["msg"])
    html = next((p.get_payload(decode=True).decode() for p in m.walk() if p.get_content_type() == "text/html"), "")
    print(" -", s["to"], "|", email.header.make_header(email.header.decode_header(m["Subject"])), "| has description:", "Job description" in html, "| apply link:", "jobs/1" in html)
print("PROBLEMS:", problems)
srv.shutdown()
