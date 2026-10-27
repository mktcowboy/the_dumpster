"""Headless smoke test: loads the app, checks layers render, identify + search work, no JS errors.
Usage: python3 -m http.server 8080 &  then  python3 scripts/smoke_test.py [url]
Requires: pip install playwright && playwright install chromium
"""
import sys, json
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080/"
errors, failed = [], []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 860})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
    pg.on("requestfailed", lambda r: failed.append(r.url[:120]))
    pg.goto(URL + "#11/35.2050/-97.4100", wait_until="networkidle", timeout=90000)
    pg.click("#modal-ok")
    pg.wait_for_timeout(3000)
    n_paths = pg.eval_on_selector_all("path.leaflet-interactive, svg path", "els => els.length")
    tiles = pg.eval_on_selector_all("img.leaflet-tile-loaded", "els => els.length")
    pg.screenshot(path="docs/screenshot-overview.jpg", type="jpeg", quality=78)
    # identify inside Lake Thunderbird State Park / Norman
    pg.evaluate("ccmap.map.setView([35.2205,-97.4440],17)"); pg.wait_for_timeout(4000)
    parcels = pg.evaluate("ccmap.OVERLAYS.find(o=>o.id==='parcels').layer.getLayers().length")
    pg.evaluate("ccmap.identify(L.latLng(35.2205,-97.4440))"); pg.wait_for_timeout(5000)
    info = pg.inner_text("#panel-body")
    pg.screenshot(path="docs/screenshot-parcel.jpg", type="jpeg", quality=78)
    pg.evaluate("ccmap.map.setView([35.06,-97.21],13)"); pg.wait_for_timeout(2500)
    pg.evaluate("ccmap.identify(L.latLng(35.06,-97.21))"); pg.wait_for_timeout(4000)
    wma_info = pg.inner_text("#panel-body")
    pg.screenshot(path="docs/screenshot-wma.jpg", type="jpeg", quality=78)
    pg.fill("#q", "T9N R2W S15"); pg.press("#q", "Enter"); pg.wait_for_timeout(4000)
    res = pg.inner_text("#results")
    b.close()

report = {"svg_paths": n_paths, "tiles_loaded": tiles, "parcels_drawn_z17": parcels,
          "identify_norman_has_parcel": "Parcel" in info and "Situs" in info,
          "identify_norman_plss": [l for l in info.splitlines() if "Sec " in l][:1],
          "identify_wma": "Lexington" in wma_info, "plss_search": res.splitlines()[:2],
          "js_errors": errors, "failed_requests": failed[:10]}
print(json.dumps(report, indent=1))
ok = n_paths > 50 and tiles > 4 and parcels > 0 and report["identify_norman_has_parcel"] and report["identify_wma"] and not errors
sys.exit(0 if ok else 1)
