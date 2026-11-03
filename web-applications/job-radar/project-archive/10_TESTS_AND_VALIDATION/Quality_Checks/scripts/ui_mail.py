from playwright.sync_api import sync_playwright
OUT = "/tmp/claude-0/-home-claude/0c6309a8-b093-5fe6-8004-e79249b14a3e/scratchpad/"
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1100})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8765/"); pg.wait_for_timeout(800)
    pg.click("#modeQ"); pg.fill("#q_name", "DA mail"); pg.fill("#q_roles", "data analyst"); pg.press("#q_roles", "Enter"); pg.wait_for_timeout(300)
    pg.select_option("#q_experience", "3–5 years"); pg.click("#qForm .picker button:has-text('Pune')"); pg.click("#qForm button.primary"); pg.wait_for_timeout(900)
    pg.click("#tabMail"); pg.wait_for_timeout(600)
    for em in ["jobs.one@gmail.com", "jobs.two@gmail.com"]:
        pg.click("text=Add Gmail account"); pg.fill("#dlgBody input[type=email]", em); pg.fill("#dlgBody input[type=password]", "abcdefghijklmnop")
        pg.uncheck("#dlgBody input[type=checkbox]"); pg.click("#dlgActs button:has-text('Add account')"); pg.wait_for_timeout(600)
    sec = pg.locator("#mailBox section").nth(2)
    sec.locator("input[type=email]").nth(0).fill("vinay@gmail.com, a@b"); sec.locator("input[type=email]").nth(0).press("Enter"); pg.wait_for_timeout(150)
    pg.locator("#mailBox").screenshot(path=OUT + "m1.png")
    pg.click("#mailBox section >> nth=4 >> button:has-text('Edit') >> nth=1"); pg.wait_for_timeout(600)
    pg.locator("#dlg").screenshot(path=OUT + "m2_tmpl.png")
    pg.click("#dlgActs button:has-text('Preview')"); pg.wait_for_timeout(700); pg.locator("#dlg").screenshot(path=OUT + "m3_prev.png")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    pg.click("#tabCards"); pg.click(".jc >> nth=0 >> button:has-text('Email settings')"); pg.wait_for_timeout(500)
    pg.click("#dlgBody label:has-text('Only for this card')"); pg.wait_for_timeout(150)
    pg.locator("#dlg").screenshot(path=OUT + "m4_card.png")
    print("card email block:", pg.locator(".jc").first.locator(".blk").nth(2).inner_text().replace("\n", " | "))
    b.close()
print("ERRORS:", errs)
