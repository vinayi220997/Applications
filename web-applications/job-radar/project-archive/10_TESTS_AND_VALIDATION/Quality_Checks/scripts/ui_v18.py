import json, urllib.request
from playwright.sync_api import sync_playwright
OUT = "/tmp/claude-0/-home-claude/0c6309a8-b093-5fe6-8004-e79249b14a3e/scratchpad/"
errs = []
def state(): return json.load(urllib.request.urlopen("http://127.0.0.1:8765/api/state"))
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1100})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8765/"); pg.wait_for_timeout(800)
    pg.click("#tabMail"); pg.wait_for_timeout(500)
    for em in ["jobs.one@gmail.com", "jobs.two@gmail.com"]:
        pg.click("text=Add Gmail account"); pg.fill("#dlgBody input[type=email]", em); pg.fill("#dlgBody input[type=password]", "abcdefghijklmnop")
        pg.uncheck("#dlgBody input[type=checkbox]"); pg.click("#dlgActs button:has-text('Add account')"); pg.wait_for_timeout(500)
    print("advanced open?", pg.locator("details.adv").get_attribute("open"))
    pg.locator("#mailBox").screenshot(path=OUT + "v1_mail.png")
    # questionnaire with emails + all accounts copy
    pg.click("#modeQ"); pg.wait_for_timeout(200)
    pg.fill("#q_name", "DA email"); pg.fill("#q_roles", "data analyst"); pg.press("#q_roles", "Enter"); pg.wait_for_timeout(300)
    pg.select_option("#q_experience", "3–5 years"); pg.click("#qForm .picker button:has-text('Pune')")
    blk = pg.locator("#qForm .emailblk")
    blk.locator("input[type=email]").first.fill("vinay@gmail.com, dilip@blive.co.in"); blk.locator("input[type=email]").first.press("Enter"); pg.wait_for_timeout(150)
    blk.locator("text=+ Add CC / BCC").click(); pg.wait_for_timeout(100)
    blk.locator("input[type=email]").nth(1).fill("boss@x.com"); blk.locator("input[type=email]").nth(1).press("Enter")
    blk.locator("button:has-text('All accounts')").click(); pg.wait_for_timeout(100)
    blk.locator("button:has-text('A copy from each')").click(); pg.wait_for_timeout(100)
    blk.screenshot(path=OUT + "v2_block.png")
    pg.click("#qForm button.primary"); pg.wait_for_timeout(900)
    c = [x for x in state()["profiles"] if x["name"] == "DA email"][0]
    print("saved:", c["email"], c["email_cfg"]["recipients"], c["email_cfg"]["sender"], c["email_cfg"]["recipients_source"])
    # edit in chart mode: switch mode, check block keeps values
    pg.locator(".jc").first.locator("button:has-text('Edit card')").click(); pg.wait_for_timeout(500)
    pg.click("#editBar button:has-text('Change input mode')"); pg.wait_for_timeout(700)
    blk2 = pg.locator(".summary .emailblk")
    print("chart block:", blk2.inner_text().replace("\n", " | ")[:300])
    blk2.locator("button:has-text('Choose accounts')").click(); pg.wait_for_timeout(100)
    blk2.locator(".checklist input").nth(1).check(); pg.wait_for_timeout(100)
    pg.click(".summary button:has-text('Save changes')"); pg.wait_for_timeout(900)
    c = [x for x in state()["profiles"] if x["name"] == "DA email"][0]
    print("after chart edit:", c["input_mode"], c["email_cfg"]["sender"], c["email_cfg"]["recipients"])
    # pause account
    pg.click("#tabMail"); pg.wait_for_timeout(500)
    pg.locator("#mailBox .tbl tbody tr").nth(1).locator(".switch").click(); pg.wait_for_timeout(500)
    print("pause dialog:", pg.inner_text("#dlg")[:160].replace("\n", " ") if pg.locator("#dlg[open]").count() else "none")
    if pg.locator("#dlg[open]").count(): pg.click("#dlgActs button:has-text('Pause')"); pg.wait_for_timeout(600)
    print("row:", pg.locator("#mailBox .tbl tbody tr").nth(1).inner_text().replace("\n", " | ")[:200])
    # theme
    pg.click("#themeTop button[aria-label='Dark theme']"); pg.wait_for_timeout(200)
    pg.screenshot(path=OUT + "v3_dark.png")
    print("theme attr:", pg.evaluate("document.documentElement.dataset.theme"), pg.evaluate("getComputedStyle(document.body).backgroundColor"))
    pg.reload(); pg.wait_for_timeout(600); print("after reload:", pg.evaluate("document.documentElement.dataset.theme"))
    pg.click("#themeTop button[aria-label='Light theme']"); print("light bg:", pg.evaluate("getComputedStyle(document.body).backgroundColor"))
    b.close()
print("ERRORS:", errs)
