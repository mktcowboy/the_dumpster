#!/usr/bin/env python3
"""
refresh.py — pull fresh Utah land listings from Realtor.com and rebuild the page.

No LLM needed. Opens a visible Google Chrome window (its own profile, kept in
.browser-profile/), pages through the search slowly, and saves each page to
disk the moment it loads. When every page is in, it swaps the new capture
into raw/ (the old one is archived), runs build.py, shows a Mac notification
with what changed, and opens the page.

If Realtor.com shows a bot check, the script stops, notifies you, and waits:
solve it in the Chrome window, then press Enter in the terminal to go on.
Nothing here tries to get around a bot check.

Run:  python3 refresh.py            (or double-click refresh.command)
      python3 refresh.py --pages 2  (quick test: first 2 pages, no swap/build)
"""

import argparse
import datetime
import glob
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
CAPTURES = os.path.join(HERE, "raw-captures")
PROFILE = os.path.join(HERE, ".browser-profile")
SEARCH = "https://www.realtor.com/realestateandhomes-search/Utah/type-land/lot-sqft-435600/sby-1"
PER_PAGE = 42
PAUSE = (7, 11)  # seconds between pages
FIELDS = ["id", "slug", "price", "lot_sqft", "line", "city", "zip", "lat", "lon", "fips", "broker", "pending", "list_date"]

# Same extraction used for the first capture: read the page's own search data, not the lazy-loaded cards.
EXTRACT = """async () => {
  let S = null;
  for (let i = 0; i < 40; i++) {
    S = window.__reactRouterDataRouter?.state?.loaderData?.srp?.search?.value;
    if (S && S.properties && S.properties.length) break;
    await new Promise(r => setTimeout(r, 500));
  }
  if (!S || !S.properties) return {error: 'no data', title: document.title, body: document.body.innerText.slice(0, 300)};
  const rows = S.properties.map(p => {
    const a = (p.location && p.location.address) || {}, c = a.coordinate || {};
    return [p.property_id, p.ldpSlug, p.list_price, p.description && p.description.lot_sqft,
      a.line || p.addressLine1 || null, a.city || null, a.postal_code || null,
      c.lat ?? p.lat ?? null, c.lon ?? p.lng ?? null,
      (p.location && p.location.county && p.location.county.fips_code) || null,
      p.brokerageName || null, !!(p.flags && (p.flags.is_pending || p.flags.is_contingent)),
      p.list_date ? p.list_date.slice(0, 10) : null];
  });
  return {total: S.total, rows};
}"""


def notify(title, msg):
    print(f"\n== {title}: {msg}")
    subprocess.run(["osascript", "-e", f'display notification {json.dumps(msg)} with title {json.dumps(title)} sound name "Glass"'],
                   check=False)


def grab(page, url, pg):
    """Load one results page; on a bot check or empty page, wait for the user and retry."""
    for attempt in range(3):
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        got = page.evaluate(EXTRACT)
        if "rows" in got:
            return got
        notify("Realtor.com needs you", f"Page {pg} did not load listings (title: {got.get('title')}). "
               "Check the Chrome window, solve any check there, then press Enter in the terminal.")
        input("Press Enter to retry this page (Ctrl+C to stop)... ")
    raise SystemExit(f"Page {pg} failed 3 times; stopping. Pages already saved are in {CAPTURES}.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, help="only fetch this many pages (test run; no swap or build)")
    args = ap.parse_args()

    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    out = os.path.join(CAPTURES, stamp)
    os.makedirs(out, exist_ok=True)
    started = time.time()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, channel="chrome", headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        first = grab(page, SEARCH, 1)
        total = first["total"]
        pages = math.ceil(total / PER_PAGE)
        if args.pages:
            pages = min(pages, args.pages)
        print(f"Realtor.com reports {total} listings over {math.ceil(total / PER_PAGE)} pages; fetching {pages}.")
        got = first
        for pg in range(1, pages + 1):
            if pg > 1:
                time.sleep(random.uniform(*PAUSE))
                got = grab(page, f"{SEARCH}/pg-{pg}", pg)
            rows = got["rows"]
            check = [len(rows), sum(r[2] or 0 for r in rows), sum(r[3] or 0 for r in rows),
                     sum(len(v) for r in rows for v in r if isinstance(v, str))]
            path = os.path.join(out, f"realtor-ut-sby1-pg-{pg:02d}.json")
            with open(path, "w") as fh:  # saved immediately, one file per page
                json.dump({"page": pg, "captured": stamp[:10], "site_total": total, "fields": FIELDS,
                           "check": check, "rows": rows}, fh, separators=(",", ":"), ensure_ascii=False)
            print(f"  page {pg}/{pages}: {len(rows)} listings saved")
        ctx.close()

    new = [r for f in sorted(glob.glob(os.path.join(out, "*.json"))) for r in json.load(open(f))["rows"]]
    ids = {r[0] for r in new}
    print(f"Captured {len(new)} rows, {len(ids)} unique, in {round((time.time() - started) / 60, 1)} min -> {out}")
    if args.pages:
        notify("Utah land test run done", f"{args.pages} pages, {len(new)} listings saved to raw-captures/{stamp}")
        return
    if len(ids) < total * 0.98:
        notify("Utah land refresh incomplete", f"Got {len(ids)} of {total}; raw/ left unchanged. Capture kept in raw-captures/{stamp}.")
        sys.exit(1)

    # What changed versus the capture now in raw/
    old = {r[0]: r for f in glob.glob(os.path.join(RAW, "realtor-ut-*.json")) for r in json.load(open(f))["rows"]}
    added = [i for i in ids if i not in old]
    gone = [i for i in old if i not in ids]
    repriced = [r for r in new if r[0] in old and old[r[0]][2] != r[2]]

    # Swap: archive the old pages, move the new ones in, rebuild.
    archive = os.path.join(CAPTURES, "replaced-" + stamp)
    os.makedirs(archive, exist_ok=True)
    for f in glob.glob(os.path.join(RAW, "realtor-ut-*.json")) + glob.glob(os.path.join(RAW, "page-checksums.json")):
        shutil.move(f, archive)
    for f in glob.glob(os.path.join(out, "*.json")):
        shutil.copy(f, RAW)
    subprocess.run([sys.executable, os.path.join(HERE, "build.py")], check=True, cwd=HERE)

    msg = f"{len(ids)} listings: {len(added)} new, {len(gone)} gone, {len(repriced)} price changes"
    with open(os.path.join(out, "changes.json"), "w") as fh:
        json.dump({"added": added, "gone": gone, "repriced": [[r[0], old[r[0]][2], r[2]] for r in repriced]}, fh, indent=1)
    notify("Utah land refresh done", msg)
    subprocess.run(["open", os.path.join(HERE, "utah-land-10ac.html")], check=False)


if __name__ == "__main__":
    main()
