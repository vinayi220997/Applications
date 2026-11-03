from playwright.sync_api import sync_playwright
import glob
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1300,"height":1500})
    errs=[]; pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
    pg.goto("http://127.0.0.1:8765/"); pg.wait_for_timeout(1200)
    pg.fill("#chatText","Data analyst, SQL and Power BI, Pune"); pg.click("#send"); pg.wait_for_timeout(800)
    pg.screenshot(path="/tmp/ui.png", full_page=True)
    m = b.new_page(viewport={"width":400,"height":900}); m.goto("http://127.0.0.1:8765/"); m.wait_for_timeout(1000)
    print("mobile overflow:", m.evaluate("document.documentElement.scrollWidth > innerWidth"))
    r = b.new_page(viewport={"width":800,"height":1400}); r.goto("file://"+glob.glob("/tmp/jr3/reports/*.html")[0]); r.screenshot(path="/tmp/report.png", full_page=False)
    print("errors:", errs)
    b.close()
