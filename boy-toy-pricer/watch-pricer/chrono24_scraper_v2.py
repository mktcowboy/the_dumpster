#!/usr/bin/env python3
"""Chrono24 scraper (v2) for each model in models_v2.py. Chrono24 is the primary source.

Reads every page of the Chrono24 search (120 per page), then each listing's
detail page for reference, year, condition, box/papers, location and seller.
Detail pages are cached by listing id in saved/<slug>/chrono24_details.json so
a weekly run only opens listings it has not seen.

Usage:
    python3 chrono24_scraper_v2.py -o chrono24.csv [--cache details.json] [--max-pages 10]
"""
import argparse
import csv
import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from watch_common_v2 import AUCTION_HOUSES, FIELDS, ScrapeError, get, keep_row, price_int, session, year_from

SEARCH = ("https://www.chrono24.com/search/index.htm?query=patek+philippe+5711"
          "&dosearch=true&pageSize=120&showpage={page}")
ID_RE = re.compile(r"--id(\d+)\.htm")
TOTAL_RE = re.compile(r"<strong>([\d,]+) listings</strong>")


def _ld_offers(text):
    out = []
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for node in data.get("@graph", []) if isinstance(data, dict) else []:
            if node.get("@type") == "AggregateOffer":
                out.extend(node.get("offers") or [])
    return out


TILE_SPLIT = 'js-listing-item-container listing-item-container'


def _tiles(text):
    """Every listing tile on a search page (the JSON-LD block lists only some)."""
    out = []
    for chunk in text.split(TILE_SPLIT)[1:]:
        m = re.search(r'href="(/[^"]+--id(\d+)\.htm)"', chunk)
        if not m:
            continue
        names = re.findall(r'<p class="[^"]*text-ellipsis[^"]*"[^>]*>\s*(.*?)\s*</p>', chunk, re.S)
        price = re.search(r'wt-listing-item-price[^>]*>\s*<strong>\s*([^<]+?)\s*</strong>', chunk, re.S)
        img = re.search(r"data-lazy-sweet-spot-master-src='([^']+)'", chunk)
        loc = re.search(r'data-content="This (?:dealer|seller) is from ([^"]+?)\."', chunk)
        out.append({
            "url": "https://www.chrono24.com" + m.group(1),
            "name": " ".join(html.unescape(re.sub(r"<[^>]+>", "", n)).strip() for n in names[:2]),
            "price": price.group(1) if price else "",
            "priceCurrency": "USD",
            "image": [{"contentUrl": img.group(1).replace("_SIZE_", "280")}] if img else [],
            "location": html.unescape(loc.group(1)) if loc else "",
        })
    return out


def search_pages(sess, max_pages, pause, urls=None):
    """Every listing tile on every page of each search URL. Returns (rows, site total)."""
    rows, total = {}, 0
    for template, dial_hint in (urls or [(SEARCH, "")]):
        url_total = None
        for page in range(1, max_pages + 1):
            text = get(sess, template.format(page=page)).text
            if url_total is None:
                m = TOTAL_RE.search(text)
                url_total = int(m.group(1).replace(",", "")) if m else 0
                total += url_total
            offers = _tiles(text) or _ld_offers(text)
            new = 0
            for offer in offers:
                m = ID_RE.search(offer.get("url") or "")
                if not m or m.group(1) in rows:
                    continue
                images = offer.get("image") or []
                rows[m.group(1)] = {
                    "listing_id": m.group(1),
                    "title": html.unescape(offer.get("name") or "").strip(),
                    "price": offer.get("price") or "",
                    "currency": offer.get("priceCurrency") or "USD",
                    "link": offer.get("url"),
                    "image_url": images[0].get("contentUrl", "") if images and isinstance(images[0], dict) else "",
                    "tile_location": offer.get("location", ""),
                    "dial_hint": dial_hint,
                }
                new += 1
            print(f"[chrono24] {dial_hint or 'search'} page {page}: {len(offers)} tiles, {new} new "
                  f"(site says {url_total})", file=sys.stderr)
            # Past the last page Chrono24 repeats earlier tiles, so few or no new ones means done.
            if not offers or new <= 2:
                break
            time.sleep(pause)
    if not rows:
        raise ScrapeError("Chrono24 search returned no listings")
    return list(rows.values()), total


def parse_detail(text):
    soup = BeautifulSoup(text, "lxml")
    spec = {}
    for tr in soup.select("table tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) == 2 and cells[0] and len(cells[0]) < 40:
            spec.setdefault(cells[0], cells[1])
    seller = ""
    node = soup.select_one(".js-link-merchant-name")
    if node:
        seller = node.get_text(" ", strip=True)
    kind = "Private seller" if "Private seller" in text[:400000] and "Professional dealer" not in text else ""
    return {
        "reference": spec.get("Reference number", ""),
        "year": year_from(spec.get("Year of production", "")),
        "condition": re.split(r"\s+The item\b", spec.get("Condition", ""), maxsplit=1)[0].strip(),
        "scope": spec.get("Scope of delivery", ""),
        "location": spec.get("Location", ""),
        "dial": spec.get("Dial", ""),
        "detail_price": spec.get("Price", ""),
        "seller": seller or kind,
        "listing_code": spec.get("Listing code", ""),
    }


def scope_to_bp(scope):
    """Chrono24 "Scope of delivery" -> Box & papers / Papers / Box / Watch only.

    The field reads like "Original box, original papers" or
    "No original box, no original papers", so each part is checked for a "no".
    """
    low = scope.lower()
    if not low:
        return ""
    parts = [p.strip() for p in low.split(",")]
    box = any("original box" in p and not p.startswith("no ") for p in parts)
    papers = any("original papers" in p and not p.startswith("no ") for p in parts)
    if box and papers:
        return "Box & papers"
    if papers:
        return "Papers"
    if box:
        return "Box"
    if "original box" in low or "original papers" in low or "watch only" in low:
        return "Watch only"
    return scope


def scrape(out, cache_path=None, max_pages=10, pause=1.0, detail_limit=None, model="5711"):
    from models_v2 import MODELS
    M = MODELS[model]
    sess = session()
    when = datetime.now(timezone.utc).isoformat()
    base, total = search_pages(sess, max_pages, pause, M.chrono24_urls)
    cache = {}
    if cache_path and Path(cache_path).exists():
        try:
            cache = json.loads(Path(cache_path).read_text(encoding="utf-8"))
        except ValueError:
            cache = {}
    fetched = failed = 0
    rows = []
    for row in base:
        lid = row["listing_id"]
        det = cache.get(lid)
        if det is None and (detail_limit is None or fetched < detail_limit):
            try:
                det = parse_detail(get(sess, row["link"]).text)
                cache[lid] = det
                fetched += 1
                if cache_path and fetched % 25 == 0:  # keep progress if the run is cut short
                    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(cache_path).write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
                time.sleep(pause)
            except ScrapeError as exc:
                failed += 1
                print(f"[chrono24] detail failed {lid}: {exc}", file=sys.stderr)
                det = None
        det = det or {}
        title = row["title"]
        if not M.match(det.get("reference"), title):
            continue  # Chrono24's text search also returns 5712, 5726, 5980...
        loc = det.get("location", "") or row.pop("tile_location", "")
        row.pop("tile_location", None)
        out_row = {
            **row,
            "site_code": "chrono24",
            "reference": det.get("reference") or title,
            "year": det.get("year", ""),
            "condition": re.split(r"\s+The item\b", det.get("condition", ""), maxsplit=1)[0].strip(),
            "box_papers": scope_to_bp(det.get("scope", "")),
            "dial": det.get("dial", ""),
            "seller": det.get("seller", ""),
            "location": loc,
            "status": ("Auction house lot (estimate, not an asking price)"
                       if any(h in det.get("seller", "").lower() for h in AUCTION_HOUSES) else "For sale"),
            "description": title,
        }
        if not price_int(out_row.get("price")) and det.get("detail_price"):
            out_row["price"] = det["detail_price"]
        done = M.finish(out_row, when)
        if done and keep_row(done):
            rows.append(done)
    if cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        Path(cache_path).write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"[chrono24] {len(base)} search results (site says {total}), {len(rows)} kept as {M.noun}; "
          f"{fetched} detail pages opened, {failed} failed", file=sys.stderr)
    return {"rows": len(rows), "search_results": len(base), "site_total": total,
            "details_fetched": fetched, "details_failed": failed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--cache", default="")
    ap.add_argument("--max-pages", type=int, default=10)
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--detail-limit", type=int, default=None)
    ap.add_argument("--model", default="5711")
    a = ap.parse_args()
    try:
        scrape(a.out, a.cache or None, a.max_pages, a.pause, a.detail_limit, a.model)
    except ScrapeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
