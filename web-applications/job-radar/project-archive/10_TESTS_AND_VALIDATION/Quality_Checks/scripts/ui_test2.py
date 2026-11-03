from playwright.sync_api import sync_playwright
OUT = "/tmp/claude-0/-home-claude/0c6309a8-b093-5fe6-8004-e79249b14a3e/scratchpad/"
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
    ctx = b.new_context(viewport={"width": 1300, "height": 1000}, permissions=["microphone"])
    pg = ctx.new_page()
    pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8765/"); pg.wait_for_timeout(1000)
    chat = pg.locator("section[aria-labelledby=chatH]")
    def say(t): pg.fill("#chatText", t); pg.press("#chatText", "Enter"); pg.wait_for_timeout(500)
    def last_bot(): return pg.evaluate("[...S.chat].reverse().find(m=>m.role==='bot').text")
    say("Data analyst, SQL and Tableau")
    pg.click("#confirmBtn"); pg.wait_for_timeout(200)
    print("Q:", last_bot()[:80]); say("yes"); pg.press("#chatText", "Enter"); pg.wait_for_timeout(300)   # Enter on empty confirms
    print("Q2:", last_bot()[:80], "| prog:", pg.inner_text("#prog").splitlines()[0])
    say("4 years")
    # Change: clears and re-asks
    pg.click(".card button:has-text('Change')"); pg.wait_for_timeout(200)
    print("after Change, box:", repr(pg.input_value("#chatText")), "| last:", last_bot()[:60])
    say("3-5 years"); print("confirm shows:", pg.inner_text(".card").replace("\n"," | ")[:120])
    # type a different answer while confirm pending -> replaces
    say("5 years"); print("replaced:", pg.inner_text(".card").replace("\n"," | ")[:120]); pg.click("#confirmBtn"); pg.wait_for_timeout(200)
    print("Q3:", last_bot()[:80])
    # mid-flow: click done segment 1 (job titles) and edit it
    pg.locator(".seg.done").first.click(); pg.wait_for_timeout(200)
    pg.click("button[role=radio]:has-text('Add to existing')"); pg.fill("#edText", "business analyst"); pg.press("#edText", "Enter"); pg.wait_for_timeout(300)
    print("mid review:", pg.inner_text(".card").replace("\n"," | ")[:140]); pg.click("#edConfirm"); pg.wait_for_timeout(300)
    print("back to:", last_bot()[:80], "| opts visible:", pg.locator(".opts button").count())
    chat.screenshot(path=OUT + "t1_mid.png")
    # voice: record with fake mic
    pg.click("#micBtn"); pg.click("text=● Start recording"); pg.wait_for_timeout(1800)
    chat.screenshot(path=OUT + "t2_rec.png")
    pg.click("text=■ Stop recording"); pg.wait_for_timeout(600)
    chat.screenshot(path=OUT + "t3_voicereview.png")
    pg.fill("#vTx", "Hyderabad and Pune, hybrid"); pg.click("text=Use this recording"); pg.wait_for_timeout(1500)
    print("voice ->", pg.inner_text(".card").replace("\n"," | ")[:200] if pg.locator(".card").count() else last_bot())
    print("toasts:", pg.inner_text("#toasts").replace("\n"," "))
    # unsupported file
    pg.set_input_files("#fileInput", files=[{"name": "x.zip", "mimeType": "application/zip", "buffer": b"PK\x03\x04"}]); pg.wait_for_timeout(300)
    print("zip toast:", pg.inner_text("#toasts").replace("\n"," ")[-160:])
    b.close()
print("ERRORS:", errs)
