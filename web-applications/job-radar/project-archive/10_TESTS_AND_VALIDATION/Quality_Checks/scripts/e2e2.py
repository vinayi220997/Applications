from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1300,"height":900}); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
    pg.goto("http://127.0.0.1:8765/"); pg.wait_for_timeout(1000)
    pg.click("#docBtn"); pg.wait_for_timeout(9000)
    pg.click("text=Email results now"); pg.wait_for_timeout(800)
    print("toast:", pg.inner_text("#topMsg"))
    pg.screenshot(path="/tmp/ui3.png")
    pg.click("text=Change email"); pg.wait_for_timeout(300); print("inputs in card:", pg.locator(".search input").count())
    print("errors:", errs); b.close()
