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
    pg.goto(URL + "#11/35.5500/-97.4100", wait_until="networkidle", timeout=90000)
    pg.click("#modal-ok")
    pg.wait_for_timeout(3000)
    n_paths = pg.eval_on_selector_all("path.leaflet-interactive, svg path", "els => els.length")
    tiles = pg.eval_on_selector_all("img.leaflet-tile-loaded", "els => els.length")
    pg.screenshot(path="docs/screenshot-overview.jpg", type="jpeg", quality=78)
    # identify a downtown OKC parcel (400 W California Ave)
    pg.evaluate("ccmap.map.setView([35.46499,-97.52034],17)"); pg.wait_for_timeout(5000)
    parcels = pg.evaluate("ccmap.OVERLAYS.find(o=>o.id==='parcels').layer.getLayers().length")
    pg.evaluate("ccmap.identify(L.latLng(35.46499,-97.52034))"); pg.wait_for_timeout(6000)
    info = pg.inner_text("#panel-body")
    pg.screenshot(path="docs/screenshot-parcel.jpg", type="jpeg", quality=78)
    pg.evaluate("ccmap.map.setView([35.6285,-97.374],14)"); pg.wait_for_timeout(2500)
    pg.evaluate("ccmap.identify(L.latLng(35.6285,-97.374))"); pg.wait_for_timeout(5000)
    wma_info = pg.inner_text("#panel-body")
    pg.screenshot(path="docs/screenshot-wma.jpg", type="jpeg", quality=78)
    pg.fill("#q", "T12N R3W S33"); pg.press("#q", "Enter"); pg.wait_for_timeout(4000)
    res = pg.inner_text("#results")
    pg.fill("#q", "SMITH JOHN"); pg.press("#q", "Enter"); pg.wait_for_timeout(6000)
    owner_res = pg.inner_text("#results")
    pg.fill("#q", "Lake Hefner"); pg.press("#q", "Enter"); pg.wait_for_timeout(6000)
    place_res = pg.inner_text("#results")
    b.close()

report = {"svg_paths": n_paths, "tiles_loaded": tiles, "parcels_drawn_z17": parcels,
          "identify_parcel_owner": [l for l in info.splitlines() if l.startswith("Owner")][:2],
          "identify_has_parcel": "Account #" in info and "CITY OF OKLA CITY" in info,
          "identify_plss": [l for l in info.splitlines() if "Sec " in l][:2],
          "identify_wma": "Arcadia" in wma_info, "plss_search": res.splitlines()[:2],
          "owner_search": owner_res.splitlines()[:4], "place_search": place_res.splitlines()[:6],
          "js_errors": errors, "failed_requests": failed[:10]}
print(json.dumps(report, indent=1))
ok = n_paths > 50 and tiles > 4 and parcels > 0 and report["identify_has_parcel"] and report["identify_wma"] and not errors
sys.exit(0 if ok else 1)
