#!/usr/bin/env python3
"""Pull Bring a Trailer completed auctions for a model page into a CSV that
generate_report.py can load as a "BaT sold" overlay.

BaT model pages (e.g. https://bringatrailer.com/mercedes-benz/e-class-amg/)
embed the first page of completed auctions as JSON, including the keyword
filter that defines the page. Later pages come from BaT's public
listings-filter endpoint using that same filter. Only auctions that actually
sold are kept ("Bid to" results where the reserve was not met are dropped).
Mileage is not a structured field, so it is parsed from the listing excerpt.

Usage:
    python3 bat_sold_scraper.py https://bringatrailer.com/mercedes-benz/e-class-amg/ --match e63 --match wagon -o e63-wagon-bat.csv
    python3 bat_sold_scraper.py PAGE1 PAGE2 --match "f-?250" --match "platinum;limited;king ranch" -o f250-bat.csv
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
API = "https://bringatrailer.com/wp-json/bringatrailer/1.0/data/listings-filter"
INITIAL_RE = re.compile(r"auctionsCompletedInitialData\s*=\s*(\{.*?\});\s*\n", re.S)

# Same columns as autotempest_scraper.py so generate_report.load_rows() reads it as-is.
FIELDS = [
    "listing_id", "site_code", "title", "price", "deal_rating", "is_hot",
    "mileage", "posted_date", "city", "distance", "dealer", "description",
    "extra_sites", "link", "image_url",
]

MILES_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k)?(?:\s+(?:actual\s+|indicated\s+)?miles|-miles?)\b", re.I)
KM_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k)?(?:\s+(?:kilometers|km)|-kilometers?)\b", re.I)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
# Listing pages carry mileage as an essentials bullet, e.g. <li>65k Miles</li>
ESSENTIALS_MILES_RE = re.compile(r"<li>([^<]{0,60}(?:Miles|Kilometers)[^<]{0,40})</li>", re.I)


def fetch(url, tries=3):
    """GET with a few retries, since one slow page shouldn't sink a 75-page run."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except (OSError, urllib.error.URLError) as e:
            if attempt == tries:
                raise
            print(f"[warn] {e}; retrying ({attempt}/{tries - 1})", file=sys.stderr)
            time.sleep(5 * attempt)


def parse_miles(text):
    """'now has 14k miles' -> 14000, '32,100 miles' -> 32100, km converted."""
    for regex, factor in ((MILES_RE, 1.0), (KM_RE, 0.621371)):
        m = regex.search(text or "")
        if m:
            n = float(m.group(1).replace(",", ""))
            if m.group(2):
                n *= 1000
            return int(round(n * factor))
    return None


def listing_page_miles(url, cache, cache_path, delay_s=1.0):
    """Mileage from the listing page itself, for auctions whose excerpt and
    title don't state it. Results are cached by URL so weekly runs only fetch
    newly sold auctions."""
    if url in cache:
        return cache[url]
    miles = None
    try:
        m = ESSENTIALS_MILES_RE.search(fetch(url))
        miles = parse_miles(m.group(1)) if m else None
    except Exception as e:  # one bad page shouldn't sink the run
        print(f"[warn] {url}: {e}", file=sys.stderr)
        return None
    cache[url] = miles
    if cache_path:
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    time.sleep(delay_s)
    return miles


def filter_params(base_filter, page, per_page):
    params = [("page", page), ("per_page", per_page), ("get_items", 1), ("get_stats", 0), ("sort", "td")]
    for key, val in base_filter.items():
        if isinstance(val, list):
            params += [(f"base_filter[{key}][]", v) for v in val]
        else:
            params.append((f"base_filter[{key}]", val))
    return urllib.parse.urlencode(params)


def ended_at(item):
    try:
        return int(item.get("sold_text_timestamp") or item.get("timestamp_end") or 0)
    except (TypeError, ValueError):
        return 0


def completed_auctions(model_url, per_page=60, delay_s=1.0, since=None):
    """Yield a model page's completed auctions, newest first. Paging stops once a
    whole page ended before `since` (a Unix time)."""
    initial = INITIAL_RE.search(fetch(model_url))
    if not initial:
        raise RuntimeError(f"no completed-auctions data found on {model_url}")
    base_filter = json.loads(initial.group(1))["base_filter"]

    page, pages_total = 1, 1
    while page <= pages_total:
        data = json.loads(fetch(f"{API}?{filter_params(base_filter, page, per_page)}"))
        pages_total = data.get("pages_total", 1)
        print(f"[info] page {page}/{pages_total}: {len(data.get('items', []))} auctions", file=sys.stderr)
        items = data.get("items", [])
        yield from items
        if since and items and all(ended_at(item) < since for item in items):
            break
        page += 1
        time.sleep(delay_s)


def to_row(item, miles_cache, cache_path, fetch_page_miles=True):
    ts = item.get("sold_text_timestamp") or item.get("timestamp_end")
    title = re.sub(r"^no reserve:\s*", "", item.get("title", ""), flags=re.I)
    miles = parse_miles(title)
    if miles is None:
        miles = parse_miles(item.get("excerpt", ""))
    if miles is None and fetch_page_miles and item.get("url"):
        miles = listing_page_miles(item["url"], miles_cache, cache_path)
    return {
        "listing_id": item.get("id", ""),
        "site_code": "BaT",
        "title": title,
        "price": f"${item['current_bid']:,}" if item.get("current_bid") else "",
        "deal_rating": "",
        "is_hot": False,
        "mileage": f"{miles:,} mi." if miles is not None else "",
        "posted_date": datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d") if ts else "",
        "city": item.get("country_code") or "",
        "distance": "",
        "dealer": "Bring a Trailer (sold)",
        "description": item.get("excerpt", ""),
        "extra_sites": "",
        "link": item.get("url", ""),
        "image_url": item.get("thumbnail_url", ""),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model_urls", nargs="+", metavar="model_url",
                    help="BaT model page(s), e.g. https://bringatrailer.com/mercedes-benz/e-class-amg/")
    ap.add_argument("--match", action="append", default=[], metavar="REGEX",
                    help='Case-insensitive regex the auction title must match. Repeatable; all must match. '
                         'Within one --match, ";" separates alternatives ("platinum;limited").')
    ap.add_argument("-o", "--output", default="bat_sold.csv", help="Output CSV path")
    ap.add_argument("--miles-cache", default="data/bat_mileage_cache.json",
                    help='JSON cache of listing URL -> mileage from listing pages; "" disables it')
    ap.add_argument("--since-days", type=int, default=0,
                    help="Only keep auctions sold in the last N days (the API is newest first, so paging stops early)")
    ap.add_argument("--no-page-miles", action="store_true",
                    help="Do not fetch individual listing pages for missing mileage (faster, but drops some sales)")
    args = ap.parse_args()

    cutoff = int(time.time()) - args.since_days * 86400 if args.since_days else None

    miles_cache = {}
    if args.miles_cache:
        try:
            with open(args.miles_cache, encoding="utf-8") as f:
                miles_cache = json.load(f)
        except FileNotFoundError:
            pass

    for url in args.model_urls:
        if "bringatrailer.com" not in urllib.parse.urlparse(url).netloc:
            print(f"error: {url} does not look like a bringatrailer.com model page", file=sys.stderr)
            sys.exit(1)

    patterns = [[re.compile(alt, re.I) for alt in m.split(";")] for m in args.match]
    seen, rows, unsold = set(), [], 0
    items = (item for url in args.model_urls for item in completed_auctions(url, since=cutoff))
    for item in items:
        if cutoff and ended_at(item) < cutoff:
            continue
        title = item.get("title", "")
        if item.get("id") in seen or not all(any(p.search(title) for p in alts) for alts in patterns):
            continue
        # Cars carry a model year in the title; wheels, seats and signs on the same model page don't.
        if not YEAR_RE.search(item.get("title", "")):
            continue
        seen.add(item.get("id"))
        if not (item.get("sold_text") or "").lower().startswith("sold for"):
            unsold += 1
            continue
        rows.append(to_row(item, miles_cache, args.miles_cache, fetch_page_miles=not args.no_page_miles))

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    no_miles = sum(1 for r in rows if not r["mileage"])
    print(f"[done] wrote {len(rows)} sold auctions to {args.output} "
          f"(skipped {unsold} unsold; {no_miles} without parsable mileage)", file=sys.stderr)


if __name__ == "__main__":
    main()
