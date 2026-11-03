from playwright.sync_api import sync_playwright
OUT = "/tmp/claude-0/-home-claude/0c6309a8-b093-5fe6-8004-e79249b14a3e/scratchpad/"
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1400, "height": 1000}, accept_downloads=True)
    pg = ctx.new_page()
    pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8765/"); pg.wait_for_timeout(1000)
    def say(t): pg.fill("#chatText", t); pg.press("#chatText", "Enter"); pg.wait_for_timeout(450)
    def last_bot(): return pg.evaluate("[...S.chat].reverse().find(m=>m.role==='bot').text")
    # ---- chart mode card with multi cities & modes
    say("Data analyst, SQL and Tableau, 3-5 years, Bengaluru, Hyderabad and Pune")
    pg.click("#confirmBtn"); pg.wait_for_timeout(200)
    for i in range(14):
        if pg.locator(".summary.card").count(): break
        q = last_bot().lower()
        if "work modes" in q:
            pg.click(".picker button:has-text('Hybrid')"); pg.click(".picker button:has-text('Remote')"); pg.click("text=Use Hybrid + Remote"); pg.wait_for_timeout(400)
        else:
            say({"email": "skip", "call this search": "DA chart"}.get(next((k for k in ["email", "call this search"] if k in q), ""), ("skip" if ("salary" in q or "avoid" in q) else ("yes" if "international" not in q else "No"))))
        if pg.locator("#confirmBtn").count(): pg.click("#confirmBtn"); pg.wait_for_timeout(200)
    print("SUMMARY:", pg.inner_text(".summary.card").replace("\n", " | ")[:300])
    pg.click(".summary.card button:has-text('Save and scan')") if False else pg.click(".summary.card button:has-text('Save'):not(:has-text('scan'))")
    pg.wait_for_timeout(1200)
    pg.locator("#paneCards").screenshot(path=OUT + "c1_cards.png")
    print("CARD:", pg.inner_text(".jc").replace("\n", " | ")[:500])
    # ---- questionnaire mode
    pg.click("#modeQ"); pg.wait_for_timeout(300)
    pg.fill("#q_name", "PD questionnaire")
    pg.fill("#q_roles", "product designer, ux designer"); pg.press("#q_roles", "Enter"); pg.wait_for_timeout(300)
    pg.select_option("#q_experience", "3–5 years")
    pg.click("#qForm .picker button:has-text('Chennai')")
    pg.fill("#q_locations", "bengular"); pg.press("#q_locations", "Enter"); pg.wait_for_timeout(300)
    pg.click("#qForm .picker button:has-text('Remote')"); pg.click("#qForm .picker button:has-text('On-site')")
    pg.set_input_files("#qFile", "/home/claude/jobradar-agent/jobradar/static/samples/job-search-brief.txt"); pg.wait_for_timeout(1500)
    print("FILE NOTE:", pg.inner_text("#qForm .upbox .note"))
    pg.locator("[aria-labelledby=chatH]").screenshot(path=OUT + "c2_q.png")
    pg.click("#qForm button.primary"); pg.wait_for_timeout(1000)
    print("TOASTS:", pg.inner_text("#toasts").replace("\n", " ")[-300:])
    # ---- toggle off first card, edit second
    cards = pg.locator(".jc")
    print("NCARDS:", cards.count())
    pg.locator(".jc").nth(1).locator(".switch").click(); pg.wait_for_timeout(700)
    print("OFF CARD STATUS:", pg.locator(".jc").nth(1).locator(".jc-head").inner_text().replace("\n", " "))
    pg.locator(".jc").nth(0).locator("button:has-text('Edit card')").click(); pg.wait_for_timeout(600)
    print("EDITBAR:", pg.inner_text("#editBar").replace("\n", " "), "| mode q visible:", pg.is_visible("#qForm"))
    pg.click("#editBar button:has-text('Change input mode')"); pg.wait_for_timeout(700)
    print("AFTER SWITCH:", pg.inner_text("#editBar").replace("\n"," "), "| summary:", pg.locator(".summary.card").count())
    pg.click(".summary.card button:has-text('Save changes')"); pg.wait_for_timeout(1000)
    print("AFTER SAVE NCARDS:", pg.locator(".jc").count(), "| mode line:", pg.locator(".jc").nth(0).locator(".kv").inner_text().replace("\n"," ")[:200])
    # ---- schedule: own schedule for card 0
    pg.locator(".jc").nth(0).locator("button:has-text('Schedule')").click(); pg.wait_for_timeout(300)
    pg.click("#dlgActs button:has-text('own schedule')"); pg.wait_for_timeout(300)
    pg.click("#dlgBody .seg2 button:has-text('Weekly')"); pg.wait_for_timeout(100)
    pg.click("#dlgBody .picker button:has-text('Sat')"); pg.click("#dlgBody .picker button:has-text('Sun')")
    pg.locator("#dlg").screenshot(path=OUT + "c3_sched.png")
    pg.click("#dlgActs button:has-text('Save schedule')"); pg.wait_for_timeout(900)
    # shared schedule with both cards -> conflict
    pg.click("#tabSched"); pg.click("#newSchedBtn"); pg.wait_for_timeout(300)
    pg.fill("#dlgBody input >> nth=0", "Morning search")
    for lab in pg.locator("#dlgBody .checklist label").all(): lab.locator("input").check()
    pg.click("#dlgActs button:has-text('Save schedule')"); pg.wait_for_timeout(700)
    print("CONFLICT DLG:", pg.inner_text("#dlg").replace("\n"," ")[:250])
    pg.click("#dlgActs button:has-text('Allow duplicate runs')"); pg.wait_for_timeout(1000)
    pg.locator("#paneSchedules").screenshot(path=OUT + "c4_schedlist.png")
    print("SCHEDULES:", pg.inner_text("#schedList").replace("\n"," | ")[:600])
    # ---- export / import
    pg.click("#tabCards"); pg.wait_for_timeout(200)
    pg.locator(".jc").nth(0).locator("summary").click(); pg.click(".jc >> nth=0 >> text=Export card")
    with pg.expect_download() as dl:
        pg.click("#dlgActs button:has-text('Download .json')")
    path = dl.value.path(); print("EXPORT:", dl.value.suggested_filename, open(path).read()[:200].replace("\n"," "))
    pg.set_input_files("#importFile", path); pg.wait_for_timeout(700)
    pg.locator("#dlg").screenshot(path=OUT + "c5_import.png")
    pg.click("#dlgActs button:has-text('Import')"); pg.wait_for_timeout(1000)
    print("AFTER IMPORT NCARDS:", pg.locator(".jc").count())
    # ---- history
    pg.locator(".jc").nth(1).locator("button:has-text('History')").click(); pg.wait_for_timeout(600)
    print("HISTORY:", pg.inner_text("#dlgBody").replace("\n"," | ")[:500])
    pg.locator("#dlg").screenshot(path=OUT + "c6_hist.png")
    pg.click("#dlgActs button:has-text('Close')")
    # ---- delete confirm
    pg.locator(".jc").nth(0).locator("summary").click(); pg.click(".jc >> nth=0 >> text=Delete card"); pg.wait_for_timeout(300)
    print("DELETE DLG:", pg.inner_text("#dlg").replace("\n"," ")[:200]); pg.click("#dlgActs button:has-text('Cancel')")
    pg.screenshot(path=OUT + "c7_full.png", full_page=False)
    b.close()
print("ERRORS:", errs)
