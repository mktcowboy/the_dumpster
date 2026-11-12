"""Screenshot the report (overview + one market) in dark and light themes; prints any JS errors."""
import sys, os
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "shots"); os.makedirs(OUT, exist_ok=True)
sym = sys.argv[1] if len(sys.argv) > 1 else "CL"; grp = sys.argv[2] if len(sys.argv) > 2 else "Energy"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    errs = []
    for theme in ["dark", "light"]:
        pg = b.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("request", lambda r: errs.append("EXT " + r.url) if not r.url.startswith(("file:", "data:")) else None)
        pg.add_init_script(f"localStorage.setItem('fc-theme','{theme}')")
        pg.goto("file://" + os.path.join(HERE, "futures-curves.html")); pg.wait_for_timeout(700)
        pg.screenshot(path=f"{OUT}/overview_{theme}.png")
        pg.screenshot(path=f"{OUT}/overview_{theme}_full.png", full_page=True)
        pg.goto("file://" + os.path.join(HERE, f"futures-curves.html#{grp}/{sym}")); pg.wait_for_timeout(900)
        pg.locator(f"#m-{sym}").screenshot(path=f"{OUT}/{sym}_{theme}.png")
        pg.close()
    pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    pg.goto("file://" + os.path.join(HERE, f"futures-curves.html#{grp}/{sym}")); pg.wait_for_timeout(900)
    pg.screenshot(path=f"{OUT}/{sym}_mobile.png")
    print("errors:", errs)
    b.close()
