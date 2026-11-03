import sys, time
from playwright.sync_api import sync_playwright
OUT = "/tmp/claude-0/-home-claude/0c6309a8-b093-5fe6-8004-e79249b14a3e/scratchpad/"
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1300, "height": 1000})
    pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8765/"); pg.wait_for_timeout(1200)
    def say(t):
        pg.fill("#chatText", t); pg.click("#send"); pg.wait_for_timeout(500)
    def thread(): return pg.inner_text("#thread")
    say("UI designer with figma and user research, 4 years, Bengaluru")
    pg.locator("section[aria-labelledby=chatH]").screenshot(path=OUT + "s1_confirm.png")
    assert pg.is_visible("#confirmBtn"), thread()
    print("PROG before confirm:", pg.inner_text("#prog").splitlines()[0])
    pg.click("#confirmBtn"); pg.wait_for_timeout(300)
    print("PROG after:", pg.inner_text("#prog").splitlines()[0])
    print("LAST:", thread().splitlines()[-3:])
    # answer loop
    answers = {"search for": "yes", "where do you want": "add bengular", "international": "Yes", "Work arrangement": "Hybrid", "skills": "yes",
               "salary": "12", "Avoid": "skip", "email": "skip", "call this search": "Dilip design"}
    for i in range(14):
        if pg.is_visible("text=Here's the search I'll run"): break
        last = pg.evaluate("[...S.chat].reverse().find(m=>m.role==='bot').text")
        ans = next((v for k, v in answers.items() if k.lower() in last.lower()), "yes")
        say(ans)
        if pg.is_visible("#confirmBtn"):
            print("CONFIRM:", pg.inner_text(".card").replace("\n", " | ")[:200])
            if i == 1:
                # test Edit: restores text
                pg.click(".card button:has-text('Edit')"); pg.wait_for_timeout(200); print("EDIT restored:", pg.input_value("#chatText")); say(pg.input_value("#chatText"))
            pg.click("#confirmBtn"); pg.wait_for_timeout(250)
        else:
            print("NO CONFIRM (reask):", thread().splitlines()[-1][:120])
    pg.locator("section[aria-labelledby=chatH]").screenshot(path=OUT + "s2_summary.png")
    # click a done segment -> editor
    pg.click("text=Edit >> nth=-1") if False else None
    pg.click(".summary.card button:has-text('Edit')"); pg.wait_for_timeout(300)
    pg.locator("section[aria-labelledby=chatH]").screenshot(path=OUT + "s3_pick.png")
    pg.check("text=Locations >> xpath=preceding-sibling::input") if False else None
    labels = pg.locator(".picks label")
    labels.nth(2).locator("input").check(); labels.nth(5).locator("input").check()
    pg.click("text=Edit selected (2)"); pg.wait_for_timeout(300)
    pg.locator("section[aria-labelledby=chatH]").screenshot(path=OUT + "s4_edit.png")
    pg.click("button[role=radio]:has-text('Add to existing')"); pg.fill("#edText", "Chennai"); pg.click("text=Review change"); pg.wait_for_timeout(300)
    print("REVIEW:", pg.inner_text(".card").replace("\n", " | "))
    pg.click("#edConfirm"); pg.wait_for_timeout(300)
    # skills: edit existing remove first chip
    pg.locator(".tag button").first.click(); pg.fill("#edText", "prototyping"); pg.click("text=Review change"); pg.wait_for_timeout(300)
    print("REVIEW2:", pg.inner_text(".card").replace("\n", " | "))
    pg.locator("section[aria-labelledby=chatH]").screenshot(path=OUT + "s5_review.png")
    pg.click("#edConfirm"); pg.wait_for_timeout(400)
    print("TOASTS:", pg.inner_text("#toasts"))
    pg.locator("section[aria-labelledby=chatH]").screenshot(path=OUT + "s6_after.png")
    # status panel
    pg.click("#statusBtn"); pg.wait_for_timeout(200); print("STATUS:", pg.inner_text("#svcBody")[:500])
    pg.locator("section[aria-labelledby=chatH]").screenshot(path=OUT + "s7_status.png")
    pg.click("#svcClose")
    # attach panel + brief upload
    pg.click("text=Start over"); pg.click("text=Start over") if pg.is_visible("text=Press again") else None
    pg.click("#restart"); pg.wait_for_timeout(200); pg.click("#restart"); pg.wait_for_timeout(300)
    pg.click("#attachBtn"); pg.wait_for_timeout(200); pg.locator("section[aria-labelledby=chatH]").screenshot(path=OUT + "s8_attach.png")
    pg.set_input_files("#fileInput", "/home/claude/jobradar-agent/jobradar/static/samples/sample-job-post.png"); pg.wait_for_timeout(3500)
    pg.locator("section[aria-labelledby=chatH]").screenshot(path=OUT + "s9_review.png")
    print("REVIEW PANEL:", pg.inner_text("#review")[:400])
    pg.click("text=Use these details"); pg.wait_for_timeout(800)
    print("AFTER USE:", pg.inner_text(".card")[:300] if pg.is_visible(".card") else thread()[-300:])
    pg.locator("section[aria-labelledby=chatH]").screenshot(path=OUT + "s10.png")
    # voice panel
    pg.click("#micBtn"); pg.wait_for_timeout(200); pg.locator("section[aria-labelledby=chatH]").screenshot(path=OUT + "s11_voice.png")
    # settings
    pg.click("text=Settings: email"); pg.wait_for_timeout(200); pg.locator("#aiForm").scroll_into_view_if_needed(); pg.locator("#aiForm").screenshot(path=OUT + "s12_settings.png")
    pg.click("#ocrTest"); pg.wait_for_timeout(3000); print("OCR TEST TOAST:", pg.inner_text("#toasts")[-300:]); print("OCR STATE:", pg.inner_text("#ocrState"))
    pg.check("#aiOn"); pg.click("#aiForm button[type=submit]"); pg.wait_for_timeout(300); print("AI VALID:", pg.inner_text("#aiMsg"))
    b.close()
print("ERRORS:", errs)
