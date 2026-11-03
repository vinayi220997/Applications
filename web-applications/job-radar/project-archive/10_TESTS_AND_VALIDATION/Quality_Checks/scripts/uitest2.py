import os, sys, threading, time, shutil
from unittest import mock
ROOT = "/tmp/jrui2"
shutil.rmtree(ROOT, ignore_errors=True); shutil.copytree("/home/claude/jobradar-agent", ROOT, ignore=shutil.ignore_patterns("data", "reports"))
sys.path.insert(0, ROOT); os.chdir(ROOT)
from jobradar import pipeline as pl, web
from jobradar.sources import boards
from jobradar.normalize import iso, now_utc

def slow_get_json(url, timeout=20, retries=2, headers=None):
    time.sleep(0.6)
    if "/jobs" in url:
        return {"jobs": [{"id": 1, "title": "Product Designer", "first_published": iso(now_utc()), "location": {"name": "Bengaluru, India"},
                          "absolute_url": "https://example.com/1", "content": "Figma, CSS. 3-5 years of experience."}]}
    return {"name": "Acme"}
cands = [{"ats": "greenhouse", "token": f"co{i}"} for i in range(40)]
for p in [mock.patch("jobradar.sources.ats.get_json", slow_get_json), mock.patch.object(pl, "online", return_value=True),
          mock.patch.object(pl, "load_company_candidates", return_value=cands), mock.patch.dict(boards.BOARDS, {}, clear=True),
          mock.patch("jobradar.scheduler.subprocess.run")]:
    p.start()
srv = web.ThreadingHTTPServer(("127.0.0.1", 8765), web.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()

from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1300, "height": 950}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8765/"); pg.wait_for_timeout(700)
    say = lambda t: (pg.fill("#chatText", t), pg.click("#send"), pg.wait_for_timeout(450))
    say("UI/UX designer with Figma and CSS, Visakhapatnam")
    for t in ["also add location", "Bengaluru and Hyderabad", "yes", "3-5 years", "Yes", "Remote", "yes", "6 LPA", "skip", "vinayi220997@gmail.com", "Test 2 @uiux Vinay"]:
        if pg.locator(".summary").count(): break
        say(t)
    say("add Pune"); say("make it hybrid")
    print("SUMMARY:", pg.inner_text(".summary").replace("\n", " | ")[:420])
    print("LAST BOT:", pg.locator(".msg.bot .b").last.inner_text()[:140])
    pg.click("text=Save and scan now"); pg.wait_for_timeout(1800)
    print("BUTTON while scanning:", pg.inner_text("#runAll"), "| spinner visible:", pg.is_visible("#scanning"), "|", pg.inner_text("#runH"))
    pg.screenshot(path="/tmp/ui_scanning.png", clip={"x": 420, "y": 0, "width": 880, "height": 420})
    pg.click("#runAll"); pg.wait_for_timeout(5000)
    print("AFTER STOP:", pg.inner_text("#runAll"), "| status:", pg.inner_text("#runBody").splitlines()[0:2], "| spinner:", pg.is_visible("#scanning"))
    print("LOG:", pg.inner_text("#log").splitlines()[-2:])
    pg.screenshot(path="/tmp/ui_stopped.png", clip={"x": 420, "y": 0, "width": 880, "height": 420})
    print("errors:", errs); b.close()
srv.shutdown()
