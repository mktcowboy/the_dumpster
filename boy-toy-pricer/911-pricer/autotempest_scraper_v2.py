#!/usr/bin/env python3
"""Scrape AutoTempest search results into CSV/JSON (v2).

Loads every
result page and keeps each listing's VIN.

AutoTempest streams results in from multiple source sites after the page
loads, about 50 at a time, and hides the rest behind "More ... Results"
buttons. This drives a real browser, clicks those buttons until each source
is exhausted, and reads the queue-results payload (which carries a VIN and
the "+N sites" duplicate count) rather than the result cards alone.

    python3 autotempest_scraper_v2.py "https://www.autotempest.com/results?localization=country&make_model=audi_rs6&zip=73102" -o rs6.csv

Install (one-time):
    pip3 install playwright
    python3 -m playwright install chromium
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from merge_listings_v2 import FIELDS, clean_vin

# Only MSRPs a listing actually states are recorded: CarGurus embeds the dealer-reported
# sticker price in new-car listing pages, and some descriptions quote it. Nothing is estimated.
# On used CarGurus listings the "msrp" field is just the dealer's asking price, so it is ignored.
MSRP_TEXT_RE = re.compile(r"(?:msrp|window sticker|sticker price)\W{0,12}(?:of\W{0,3})?\$\s?(\d{2,3}(?:,\d{3})+|\d{5,7})", re.I)
CARGURUS_MSRP_RE = re.compile(r'"msrp":(\d{4,7})[,}]')
CARGURUS_NEW_RE = re.compile(r'"isNew":(true|false)')
DEAL_RE = re.compile(r"(good|great|fair)-deal")
DEAL_WORD_RE = re.compile(r"\b(good|great|fair)\b", re.I)
ISO_DAY_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

DETAIL_KEYS = ("detailsShort", "detailsMid", "detailsLong", "detailsExtraLong")

CHROME_CANDIDATES = (
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def cargurus_new_car_msrp(html):
    m = CARGURUS_MSRP_RE.search(html)
    if not m:
        return None
    near = CARGURUS_NEW_RE.search(html[max(0, m.start() - 5000):m.end() + 5000])
    return int(m.group(1)) if near and near.group(1) == "true" else None


EXTRACT_JS = r"""
() => {
  function text(el) { return el ? el.textContent.replace(/\s+/g, ' ').trim() : ""; }

  return Array.from(document.querySelectorAll('section.search-result')).map(el => {
    const linkEl = el.querySelector('a.listing-link.source-link') || el.querySelector('a.listing-link');
    const priceEl = el.querySelector('.badge__label.label--price, .badge__label.label--bid');
    const dealEl = el.querySelector('.deal-gauge-notice');
    const dealClassMatch = dealEl ? dealEl.className.match(/(good|great|fair)-deal/) : null;
    const detailParts = el.querySelectorAll('.details > .short, .details > .mid, .details > .long, .details > .extra-long');
    const extraSitesEl = el.querySelector('.result-wrap--has-duplicates') ? el.textContent.match(/\+\d+\s+sites?/) : null;
    const imgEl = el.querySelector('[data-img]');

    return {
      listing_id: el.getAttribute('data-listing-id') || "",
      site_code: el.getAttribute('data-backend-sitecode') || "",
      title: text(linkEl),
      price: text(priceEl),
      deal_rating: dealClassMatch ? dealClassMatch[1] : "",
      is_hot: !!el.querySelector('.hot-deal-badge'),
      mileage: text(el.querySelector('.mileage')),
      posted_date: text(el.querySelector('.info.mileageDate .date')),
      city: text(el.querySelector('.location .city')),
      distance: text(el.querySelector('.location .distance')),
      dealer: text(el.querySelector('.dealerName')),
      description: Array.from(detailParts).map(text).join(''),
      extra_sites: extraSitesEl ? extraSitesEl[0] : "",
      link: linkEl ? linkEl.href : "",
      image_url: imgEl ? imgEl.getAttribute('data-img') : "",
      vin: "",
    };
  });
}
"""


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

SITE_COUNT_JS = "els => els.map(el => el.getAttribute('data-backend-sitecode') || '')"


def find_chrome():
    for path in CHROME_CANDIDATES:
        if os.path.exists(path):
            return path
    return ""


def launch_browser(playwright, headless=True):
    """Playwright's Chromium when it is installed, otherwise the system Chrome."""
    override = os.environ.get("AUTOTMPEST_CHROME", "")
    if override:
        return playwright.chromium.launch(headless=headless, executable_path=override)
    try:
        return playwright.chromium.launch(headless=headless)
    except Exception as exc:
        chrome = find_chrome()
        if chrome and "Executable doesn't exist" in str(exc):
            print(f"[info] Playwright browser missing; using {chrome}", file=sys.stderr)
            return playwright.chromium.launch(headless=headless, executable_path=chrome)
        raise


def wait_for_results_to_settle(page, timeout_s=45, quiet_s=3):
    """AutoTempest fires off async requests per source site; wait until the
    number of rendered result cards stops changing for `quiet_s` seconds."""
    start = time.time()
    last_count = -1
    last_change = time.time()
    while time.time() - start < timeout_s:
        count = page.eval_on_selector_all("section.search-result", "els => els.length")
        if count != last_count:
            last_count = count
            last_change = time.time()
        if time.time() - last_change >= quiet_s:
            break
        page.wait_for_timeout(500)
    return last_count


def _log_sites(label, counts):
    detail = ", ".join(f"{code}={n}" for code, n in counts.most_common()) or "none"
    print(f"[info] {label}: {sum(counts.values())} ({detail})", file=sys.stderr)


def load_more_results(page, timeout_s=45, max_rounds=40):
    """Click every visible "More ... Results" button until none remain.

    Each click asks AutoTempest for the next page of one source (Cars.com,
    the Other group that holds CarGurus, and so on). A round that adds no
    cards is retried once, then the loop stops so a stuck button cannot spin.
    """
    stalled = 0
    for _ in range(max_rounds):
        buttons = [b for b in page.query_selector_all("button.more-results:not(.hide)") if b.is_visible()]
        if not buttons:
            return
        button = buttons[0]
        try:
            label = button.inner_text().strip() or "More Results"
        except Exception:
            label = "More Results"
        before = page.eval_on_selector_all("section.search-result", "els => els.length")
        print(f"[info] {label} ({before} cards so far)", file=sys.stderr)
        try:
            button.scroll_into_view_if_needed(timeout=5000)
            button.click(timeout=8000)
        except Exception as exc:
            print(f"[warn] could not click {label!r}: {exc}", file=sys.stderr)
            stalled += 1
            if stalled >= 2:
                return
            continue
        after = wait_for_results_to_settle(page, timeout_s=min(timeout_s, 25), quiet_s=2)
        if after <= before:
            stalled += 1
            if stalled >= 2:
                print("[warn] More Results stopped adding cards", file=sys.stderr)
                return
        else:
            stalled = 0


def as_price(value):
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"${int(round(value)):,}"
    text = str(value).strip()
    if not text:
        return ""
    if text.startswith("$"):
        return text
    digits = re.sub(r"[^\d.]", "", text)
    if digits and re.fullmatch(r"\d+(?:\.\d+)?", digits):
        return f"${int(round(float(digits))):,}"
    return text


def format_mileage(value):
    text = str(value or "").strip()
    if not text or text.lower() in {"n/a", "na", "none"}:
        return ""
    if re.search(r"\b(mi|km)\b", text, re.I):
        return text
    return f"{text} mi."


def format_distance(value):
    if value is None or value == "":
        return ""
    try:
        miles = int(round(float(value)))
    except (TypeError, ValueError):
        return str(value)
    return f"({miles:,} mi.)"


def relative_day(value):
    match = ISO_DAY_RE.match(str(value or ""))
    if not match:
        return ""
    day = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date()
    delta = (datetime.now().astimezone().date() - day).days
    if delta <= 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    if delta < 30:
        return f"{delta} days ago"
    return day.isoformat()


def deal_rating(item):
    match = DEAL_RE.search(str(item.get("dealGaugeClass") or ""))
    if match:
        return match.group(1)
    word = DEAL_WORD_RE.search(str(item.get("dealGauge") or ""))
    return word.group(1).lower() if word else ""


def extra_sites(item):
    try:
        count = int(item.get("duplicateCount") or 0)
    except (TypeError, ValueError):
        return ""
    if count <= 0:
        return ""
    return f"+{count} site" if count == 1 else f"+{count} sites"


def blank_row():
    return {field: "" for field in FIELDS}


def row_from_api(item):
    """Map one queue-results listing onto the report's columns, including VIN."""
    if not isinstance(item, dict):
        return None
    title = str(item.get("title") or "").strip()
    year = str(item.get("year") or "").strip()
    if year and year not in title:
        title = f"{year} {title}".strip()
    description = re.sub(r"\s+", " ", "".join(str(item.get(key) or "") for key in DETAIL_KEYS)).strip()
    row = blank_row()
    row.update({
        "listing_id": str(item.get("id") or ""),
        "site_code": str(item.get("backendSitecode") or item.get("sitecode") or ""),
        "title": title,
        "price": as_price(item.get("price")) or as_price(item.get("currentBid")),
        "deal_rating": deal_rating(item),
        "is_hot": bool(item.get("hotCar")),
        "mileage": format_mileage(item.get("mileage")),
        "posted_date": relative_day(item.get("date")),
        "city": str(item.get("location") or ""),
        "distance": format_distance(item.get("distance")),
        "dealer": str(item.get("dealerName") or ""),
        "description": description,
        "extra_sites": extra_sites(item),
        "link": str(item.get("url") or ""),
        "image_url": str(item.get("img") or item.get("imgSource") or ""),
        "vin": clean_vin(item.get("vin")),
    })
    return row if row["listing_id"] or row["link"] or row["vin"] else None


def rows_from_api(items):
    rows, seen = [], set()
    for item in items:
        row = row_from_api(item)
        if not row:
            continue
        key = row["listing_id"] or row["link"]
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        rows.append(row)
    return rows


def _dom_rows(page):
    rows = []
    for item in page.evaluate(EXTRACT_JS):
        row = blank_row()
        row.update(item)
        row["vin"] = clean_vin(item.get("vin"))
        row["is_hot"] = bool(item.get("is_hot"))
        rows.append(row)
    return rows


def scrape(url, headless=True, timeout_s=45, max_more_rounds=40):
    captured = []

    def on_response(response):
        if "queue-results" not in response.url:
            return
        try:
            payload = response.json()
        except Exception:
            return
        if isinstance(payload, dict):
            captured.extend(payload.get("results") or [])

    with sync_playwright() as p:
        browser = launch_browser(p, headless=headless)
        page = browser.new_page(user_agent=USER_AGENT)
        page.on("response", on_response)
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        initial = wait_for_results_to_settle(page, timeout_s=timeout_s)
        initial_sites = Counter(page.eval_on_selector_all("section.search-result", SITE_COUNT_JS))
        _log_sites("before More Results", initial_sites)
        load_more_results(page, timeout_s=timeout_s, max_rounds=max_more_rounds)
        final_sites = Counter(page.eval_on_selector_all("section.search-result", SITE_COUNT_JS))
        _log_sites("after More Results", final_sites)
        rows = rows_from_api(captured)
        if rows:
            print(f"[info] {len(rows)} listings from results data "
                  f"({sum(1 for r in rows if r['vin'])} with a VIN); {initial} cards before paging",
                  file=sys.stderr)
        else:
            print("[warn] results payload was empty; falling back to the cards on the page", file=sys.stderr)
            rows = _dom_rows(page)
            print(f"[info] {len(rows)} result cards parsed from the page", file=sys.stderr)
        browser.close()
        return rows


def msrp_from_text(text):
    m = MSRP_TEXT_RE.search(text or "")
    return int(m.group(1).replace(",", "")) if m else None


def load_cache(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def add_msrp(rows, cache_path, headless=True, fetch=True):
    """Fill msrp/msrp_source per row. CarGurus pages are fetched once per listing and cached
    (including "not listed"), so weekly runs only visit new listings."""
    cache = load_cache(cache_path) if cache_path else {}
    todo = [r for r in rows if fetch and r["site_code"] == "cgu" and r["link"] and r["listing_id"] not in cache]
    if todo:
        print(f"[info] checking {len(todo)} new CarGurus listings for MSRP", file=sys.stderr)
        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            page = browser.new_page(user_agent=USER_AGENT)
            for r in todo:
                try:
                    page.goto(r["link"], wait_until="domcontentloaded", timeout=30_000)
                    cache[r["listing_id"]] = cargurus_new_car_msrp(page.content())
                except Exception as e:  # leave uncached so the next run retries it
                    print(f"[warn] MSRP lookup failed for {r['listing_id']}: {e}", file=sys.stderr)
                page.wait_for_timeout(300)
            browser.close()
        if cache_path:
            os.makedirs(os.path.dirname(os.path.abspath(cache_path)), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=0, sort_keys=True)

    for r in rows:
        r["msrp"], r["msrp_source"] = "", ""
        if cache.get(r["listing_id"]):
            r["msrp"], r["msrp_source"] = cache[r["listing_id"]], "cargurus"
        else:
            stated = msrp_from_text(r["title"] + " " + r["description"])
            if stated:
                r["msrp"], r["msrp_source"] = stated, "description"
    found = sum(1 for r in rows if r["msrp"])
    print(f"[info] MSRP stated on {found} of {len(rows)} listings", file=sys.stderr)
    return rows


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def write_json(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", help="Full AutoTempest /results?... search URL")
    ap.add_argument("-o", "--output", default="autotempest_results.csv", help="Output file (.csv or .json)")
    ap.add_argument("--show-browser", action="store_true", help="Run with a visible browser window (debugging)")
    ap.add_argument("--timeout", type=int, default=45, help="Max seconds to wait for results to finish loading")
    ap.add_argument("--max-more", type=int, default=40, help="Max More Results clicks per search")
    ap.add_argument("--msrp-cache", default="", help="JSON file caching MSRPs looked up from CarGurus listing pages")
    ap.add_argument("--no-msrp", action="store_true", help="Skip MSRP lookups on listing pages (descriptions are still checked)")
    args = ap.parse_args()

    if "autotempest.com" not in urlparse(args.url).netloc:
        print("error: URL does not look like an autotempest.com results URL", file=sys.stderr)
        sys.exit(1)

    rows = scrape(args.url, headless=not args.show_browser, timeout_s=args.timeout, max_more_rounds=args.max_more)
    add_msrp(rows, args.msrp_cache, headless=not args.show_browser, fetch=not args.no_msrp)

    if args.output.lower().endswith(".json"):
        write_json(rows, args.output)
    else:
        write_csv(rows, args.output)

    counts = Counter(r["site_code"] for r in rows)
    detail = ", ".join(f"{code}={n}" for code, n in counts.most_common())
    print(f"[done] wrote {len(rows)} listings ({detail}) to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
