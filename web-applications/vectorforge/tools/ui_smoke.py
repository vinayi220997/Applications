"""Headless UI smoke test: upload, wait for the result, switch views, edit palette, download.
Usage: python tools/ui_smoke.py http://localhost:8077 image.png out_dir"""
import sys, pathlib
from playwright.sync_api import sync_playwright
base, img, out = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    errors = []
    for name, vp in (("desktop", {"width": 1360, "height": 820}), ("mobile", {"width": 390, "height": 844})):
        pg = b.new_page(viewport=vp)
        pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base)
        pg.screenshot(path=str(out / f"{name}-empty.png"))
        pg.set_input_files("#fileInput", img)
        pg.wait_for_selector("#vecLayer svg", timeout=60000)
        pg.wait_for_selector("#busy", state="hidden", timeout=60000)
        pg.screenshot(path=str(out / f"{name}-compare.png"), full_page=(name == "mobile"))
        if name == "desktop":
            for v in ("vector", "outlines"):
                pg.click(f'.view-tools [data-view="{v}"]')
                pg.screenshot(path=str(out / f"{name}-{v}.png"))
            pg.click('.view-tools [data-view="compare"]')
            n0 = pg.locator("#swatches li").count()
            pg.locator("#swatches li button").first.click()  # make first color transparent
            pg.wait_for_timeout(500)
            pg.wait_for_selector("#busy", state="hidden", timeout=60000)
            pg.wait_for_timeout(300)
            off = pg.locator("#swatches li.off").count()
            pg.screenshot(path=str(out / f"{name}-palette-edit.png"))
            pg.click('#formats [data-fmt="pdf"]')
            with pg.expect_download() as dl:
                pg.click("#downloadBtn")
            d = dl.value
            d.save_as(str(out / d.suggested_filename))
            print("swatches", n0, "transparent after edit", off, "download", d.suggested_filename)
        pg.close()
    print("console errors:", errors)
    b.close()
