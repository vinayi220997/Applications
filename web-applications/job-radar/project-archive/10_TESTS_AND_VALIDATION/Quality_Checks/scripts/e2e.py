from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                                "--auto-select-desktop-capture-source=Entire screen", "--enable-usermedia-screen-capturing"])
    ctx = b.new_context(viewport={"width": 1300, "height": 1100}, permissions=["microphone"])
    pg = ctx.new_page(); errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8765/"); pg.wait_for_timeout(800)
    pg.set_input_files("#fileInput", "/tmp/fx/resume.pdf"); pg.wait_for_timeout(1500)
    print("chip:", pg.inner_text("#files"))
    pg.click("#shotBtn"); pg.wait_for_timeout(3000)
    print("chip2:", pg.inner_text("#files"))
    pg.click("#micBtn"); pg.wait_for_timeout(2200); print("mic label:", pg.inner_text("#micLabel"))
    pg.click("#micBtn"); pg.wait_for_timeout(1500)
    print("chip3:", pg.inner_text("#files"))
    pg.fill("#chatText", "Looking for a backend role, remote or Bengaluru")
    pg.click("#send"); pg.wait_for_timeout(1500)
    pg.screenshot(path="/tmp/ui2.png", clip={"x": 0, "y": 0, "width": 460, "height": 1100})
    print("last bot:", pg.locator(".msg.bot .b").last.inner_text()[:500])
    print("errors:", errs)
    b.close()
