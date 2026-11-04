#!/usr/bin/env python3
"""Every non-Chrono24 source for the Patek scanner (v2): Nautilus 5711 and blue/green Aquanaut.

Each scraper returns rows with watch_common_v2.FIELDS or raises ScrapeError
with a short reason ("HTTP 403", "Cloudflare challenge", "no 5711 results").
refresh_searches_v2.py records that reason in meta.json and keeps the last
good file for that source.

Plain HTTP (curl_cffi with a Chrome fingerprint) is used where it works.
Watchfinder, Jomashop and Grailzee only render listings in a real browser,
so those open the page in Playwright Chromium and read what the page shows
(or the JSON the page itself loads). No site credentials are used.

Usage (one source, for testing):
    python3 dealer_scrapers_v2.py bobs -o bobs.csv
"""
import argparse
import csv
import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

from models_v2 import MODELS
from watch_common_v2 import (FIELDS, UA, ScrapeError, box_papers_from, get, keep_row,
                             price_int, session, year_from)

CHALLENGE_MARKERS = ("Just a moment...", "cf-chl", "px-captcha", "Access Denied",
                     "Pardon Our Interruption", "_Incapsula_Resource")


def _challenge(text):
    head = text[:20000]
    return next((m for m in CHALLENGE_MARKERS if m in head), "")


def _ld_products(text):
    out = []
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', text, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                t = node.get("@type")
                if t == "Product" or (isinstance(t, list) and "Product" in t):
                    out.append(node)
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
    return out


def _offer(product):
    offers = product.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = offers.get("price")
    if price in (None, "") and offers.get("priceSpecification"):
        spec = offers["priceSpecification"]
        spec = spec[0] if isinstance(spec, list) and spec else spec
        price = spec.get("price") if isinstance(spec, dict) else None
    avail = str(offers.get("availability") or "")
    status = "Sold / out of stock" if ("OutOfStock" in avail or "SoldOut" in avail) else ("For sale" if avail else "")
    return price, offers.get("priceCurrency") or "USD", status


def _props(product):
    props = {}
    for p in product.get("additionalProperty") or []:
        if isinstance(p, dict):
            props[str(p.get("name"))] = str(p.get("value"))
    return props


def _row_from_product(product, site, link, extra_text=""):
    price, cur, status = _offer(product)
    props = _props(product)
    desc = html.unescape(str(product.get("description") or ""))
    title = html.unescape(str(product.get("name") or ""))
    text = " ".join([title, desc, extra_text, " ".join(props.values())])
    cond = props.get("Condition Grade") or str(product.get("itemCondition") or "").split("/")[-1].replace("Condition", "")
    return {
        "listing_id": str(product.get("sku") or product.get("productID") or link),
        "site_code": site,
        "title": title,
        "reference": " ".join([str(product.get("mpn") or ""), props.get("Reference Number", ""), title]),
        "dial": props.get("Dial Color", "") or str(product.get("color") or ""),
        "year": year_from(props.get("Year", ""), props.get("Year of Production", ""), title, desc[:400]),
        "box_papers": box_papers_from(props.get("Box and Papers", "") + " " + text),
        "condition": cond,
        "price": price,
        "currency": cur,
        "status": status,
        "link": link,
        "description": text,
    }


# --------------------------------------------------------------- plain HTTP

def scrape_bobs(sess, when, M=None):
    """Bob's Watches: the model page, then each product page's JSON-LD."""
    M = M or MODELS["5711"]
    base = "https://www.bobswatches.com"
    rows, links = [], []
    paths = {"5711": ("/patek-philippe/nautilus-5711", "/patek-philippe/nautilus-5711-blue"),
             "aquanaut": ("/patek-philippe/aquanaut-1.html",)}[M.key]
    for path in paths:
        text = get(sess, base + path).text
        for href in re.findall(r'<div class="seocart_ProductWrapper".*?<a href="(/patek-philippe/[^"]+\.html)"', text, re.S):
            if href not in links:
                links.append(href)
    for href in links:
        text = get(sess, base + href).text
        for prod in _ld_products(text)[:1]:
            row = _row_from_product(prod, "bobs", base + href)
            row["seller"] = "Bob's Watches"
            row["location"] = "Newport Beach, CA, US"
            if M.match(row["reference"]) and price_int(row["price"]):
                rows.append(M.finish(row, when))
        time.sleep(0.5)
    if not links:
        raise ScrapeError(f"no {M.noun} on the Bob's model page")
    return rows


def scrape_swe(sess, when, M=None):
    """Swiss Watch Expo search tiles: title, stock number, price or a Sold ribbon."""
    M = M or MODELS["5711"]
    base = "https://www.swisswatchexpo.com"
    text = get(sess, base + f"/search/?q={M.term}").text
    rows = []
    for m in re.finditer(r'<a href="(/watches/[^"]+)"[^>]*>\s*<div class="product_box catalog">(.*?)</a>', text, re.S):
        href, tile = m.group(1), m.group(2)
        title = html.unescape(re.sub(r"<[^>]+>", "", (re.search(r"<h5>(.*?)</h5>", tile, re.S) or [None, ""])[1])).strip()
        alt = html.unescape((re.search(r'alt="([^"]*)"', tile) or [None, ""])[1])
        if not M.match(title, href):
            continue
        sold = 'ribbon sold' in tile
        price = (re.search(r'class="price"[^>]*>.*?\$([\d,]+(?:\.\d\d)?)', tile, re.S) or [None, ""])[1]
        stock = (re.search(r"Stock Number:\s*(\d+)", tile) or [None, ""])[1]
        img = (re.search(r'src="([^"]+)"', tile) or [None, ""])[1]
        rows.append(M.finish({
            "listing_id": stock or href, "site_code": "swe", "title": title,
            "reference": title + " | " + alt, "price": "" if sold else price,
            "status": "Sold" if sold else "For sale", "seller": "Swiss Watch Expo",
            "location": "Atlanta, GA, US", "link": base + href, "image_url": img,
            "description": title + " " + alt,
        }, when))
    if not rows:
        raise ScrapeError(f"no {M.noun} tiles in the Swiss Watch Expo search")
    return rows


def scrape_davidsw(sess, when, M=None):
    """DavidSW (WooCommerce): search page links, then product JSON-LD."""
    M = M or MODELS["5711"]
    text = get(sess, f"https://www.davidsw.com/?s={M.term}").text
    links = []
    for href in re.findall(r'href="(https://(?:www\.)?davidsw\.com/shop/watch/patek-philippe/[^"]+)"', text):
        if M.term in href.lower() and href not in links:
            links.append(href)
    rows = []
    for href in links:
        page = get(sess, href).text
        for prod in _ld_products(page)[:1]:
            row = _row_from_product(prod, "davidsw", href, re.sub(r"<[^>]+>", " ", page[:0]))
            row["seller"] = "DavidSW"
            row["location"] = "Austin, TX, US"
            if M.match(row["reference"]):
                rows.append(M.finish(row, when))
        time.sleep(0.5)
    if not links:
        raise ScrapeError(f"no {M.noun} product links in the DavidSW search")
    return rows


def scrape_analogshift(sess, when, M=None):
    """Analog Shift (Shopify): search results, then /products/<handle>.js for each."""
    M = M or MODELS["5711"]
    base = "https://www.analogshift.com"
    handles = []
    for page in (1, 2, 3):
        text = get(sess, f"{base}/search?q={M.term}&type=product&page={page}").text
        found = [h for h in re.findall(r'href="/products/([^"?#/]+)', text) if "patek" in h]
        new = [h for h in found if h not in handles]
        handles.extend(new)
        if not new:
            break
    rows = []
    for h in handles:
        try:
            data = get(sess, f"{base}/products/{h}.js").json()
        except (ScrapeError, ValueError):
            continue
        body = re.sub(r"<[^>]+>", " ", html.unescape(data.get("description") or "")).replace("\xa0", " ")
        tags = " ".join(data.get("tags") or [])
        # Descriptions often mention "the 5711" in passing; only the stated reference counts.
        stated = re.findall(r"\bRef(?:erence|\.)?\s*(?:No\.?|Number)?\s*:?\s*(\d{4}[A-Z0-9/\-]*)", body)
        ref_text = stated[0] if stated else ""
        # A bare "Reference 5711" is usually a comparison ("like the reference 5711").
        if M.key == "5711":
            if not re.match(r"5711\s*[/A-Z]", ref_text) and not re.search(r"5711\s*[/A-Z]", (data.get("title") or "") + " " + tags):
                continue
        elif M.term not in (h + " " + (data.get("title") or "")).lower():
            continue
        avail = data.get("available")
        price = (data.get("price") or 0) / 100 if data.get("price") else ""
        imgs = data.get("images") or []
        rows.append(M.finish({
            "listing_id": str(data.get("id") or h), "site_code": "analogshift",
            "title": data.get("title") or "", "reference": ref_text or data.get("title") or "",
            "year": year_from(tags, body[:600]), "price": price if avail else "",
            "status": "For sale" if avail else "Sold", "seller": "Analog Shift",
            "location": "New York, NY, US", "link": f"{base}/products/{h}",
            "image_url": ("https:" + imgs[0]) if imgs and str(imgs[0]).startswith("//") else (imgs[0] if imgs else ""),
            "description": " ".join([data.get("title") or "", ref_text, tags]),
        }, when))
        time.sleep(0.3)
    if not handles:
        raise ScrapeError("no Patek results in the Analog Shift search")
    return rows


def scrape_the1916(sess, when, M=None):
    """The 1916 Company (formerly WatchBox / Govberg / Radcliffe): search page JSON-LD."""
    M = M or MODELS["5711"]
    rows = []
    for url in (f"https://www.the1916company.com/search/pre-owned/?q={M.term}",
                f"https://www.the1916company.com/search/?q=patek%20{M.term}"):
        text = get(sess, url).text
        for prod in _ld_products(text):
            link = prod.get("url") or ""
            row = _row_from_product(prod, "the1916", link)
            row["listing_id"] = str(prod.get("sku") or link)
            row["seller"] = "The 1916 Company (WatchBox)"
            if M.match(row["reference"]) and not any(r and r["listing_id"] == row["listing_id"] for r in rows):
                rows.append(M.finish(row, when))
    return rows


def scrape_hodinkee(sess, when, M=None):
    M = M or MODELS["5711"]
    text = get(sess, f"https://shop.hodinkee.com/search?q={M.term}&type=product").text
    if re.search(r"0 results found", text):
        return []  # works, just nothing listed
    rows = []
    for h in sorted(set(re.findall(r'href="/products/([^"?#/]+)', text))):
        try:
            data = get(sess, f"https://shop.hodinkee.com/products/{h}.js").json()
        except (ScrapeError, ValueError):
            continue
        if M.match(data.get("title"), " ".join(data.get("tags") or [])) and data.get("available"):
            rows.append(M.finish({
                "listing_id": str(data.get("id")), "site_code": "hodinkee", "title": data.get("title"),
                "reference": data.get("title"), "price": (data.get("price") or 0) / 100, "status": "For sale",
                "seller": "Hodinkee Shop", "link": f"https://shop.hodinkee.com/products/{h}",
                "description": data.get("title"),
            }, when))
    return rows


def _blocked_check(sess, url, name, need="5711"):
    """For sites known to block scripts: try once, raise with the reason."""
    try:
        resp = sess.get(url, timeout=40)
    except Exception as exc:
        raise ScrapeError(f"{name}: {type(exc).__name__}")
    mark = _challenge(resp.text)
    if resp.status_code in (401, 403, 429, 503) or resp.status_code == 202 or mark:
        raise ScrapeError(f"{name} blocked the scraper (HTTP {resp.status_code}{', ' + mark if mark else ''})")
    if resp.status_code == 404:
        raise ScrapeError(f"{name}: page not found (HTTP 404); site search may have moved")
    raise ScrapeError(f"{name}: page loaded (HTTP {resp.status_code}) but listings are rendered by "
                      f"JavaScript from an API this scanner does not call")


def scrape_ebay(sess, when, M=None):
    M = M or MODELS["5711"]
    _blocked_check(sess, f"https://www.ebay.com/sch/i.html?_nkw=patek+philippe+{M.term}&_sacat=31387&LH_Sold=1&LH_Complete=1", "eBay")


def scrape_watchcharts(sess, when, M=None):
    M = M or MODELS["5711"]
    _blocked_check(sess, f"https://watchcharts.com/watches?search={M.term}", "WatchCharts")


def scrape_crown(sess, when, M=None):
    M = M or MODELS["5711"]
    _blocked_check(sess, f"https://www.crownandcaliber.com/search?q={M.term}", "Crown & Caliber")


def scrape_bezel(sess, when, M=None):
    M = M or MODELS["5711"]
    _blocked_check(sess, "https://shop.getbezel.com/explore/patek-philippe/" + ("nautilus" if M.key == "5711" else "aquanaut"), "Bezel")


def scrape_wristcheck(sess, when, M=None):
    M = M or MODELS["5711"]
    _blocked_check(sess, f"https://wristcheck.com/us/buy?q={M.term}", "Wristcheck")


def scrape_luxurybazaar(sess, when, M=None):
    M = M or MODELS["5711"]
    text = get(sess, f"https://www.luxurybazaar.com/search-results/?q={M.term}").text
    if not (re.search(r"5711/|5711[A-Z]", text) if M.key == "5711" else re.search(r"5\d{3}/?\d*[AGR]-0\d\d", text)):
        raise ScrapeError(f"Luxury Bazaar: search page loads but shows no {M.noun} to a script "
                          "(results are rendered by JavaScript)")
    raise ScrapeError("Luxury Bazaar: listing text found but no parser for this layout yet")


def scrape_europeanwatch(sess, when, M=None):
    M = M or MODELS["5711"]
    _blocked_check(sess, f"https://www.europeanwatch.com/search?q={M.term}", "European Watch Co.")


# --------------------------------------------------------------- browser

class Browser:
    """One shared headless Chromium for the browser-only sources."""

    def __init__(self):
        self.pw = self.browser = None

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ScrapeError("playwright is not installed") from exc
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=True)
        return self

    def __exit__(self, *exc):
        try:
            if self.browser:
                self.browser.close()
        finally:
            if self.pw:
                self.pw.stop()

    def open(self, url, wait_ms=9000, capture=None):
        ctx = self.browser.new_context(user_agent=UA, locale="en-US", viewport={"width": 1400, "height": 1000})
        page = ctx.new_page()
        bodies = []
        if capture:
            def on_resp(resp):
                try:
                    if capture in resp.url and "json" in (resp.headers.get("content-type") or ""):
                        bodies.append(resp.text())
                except Exception:
                    pass
            page.on("response", on_resp)
        try:
            resp = page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            status = resp.status if resp else 0
            content = page.content()
            title = page.title()
        except Exception as exc:
            ctx.close()
            raise ScrapeError(f"browser could not open {url}: {str(exc)[:120]}")
        ctx.close()
        if status in (401, 403, 429) or title.startswith("Just a moment") or _challenge(content):
            raise ScrapeError(f"blocked in a browser too (HTTP {status}, title {title[:40]!r})")
        return content, bodies


def scrape_watchfinder(browser, when, M=None):
    M = M or MODELS["5711"]
    rows = []
    for url in (f"https://www.watchfinder.com/search?q={M.term}",
                "https://www.watchfinder.com/watches/patek-philippe/" + ("nautilus" if M.key == "5711" else "aquanaut")):
        content, _ = browser.open(url)
        for m in re.finditer(r'<a href="(https://www\.watchfinder\.com/watches/patek-philippe/[^"]+)" class="product-card"(.*?)</a>', content, re.S):
            href, card = m.group(1), m.group(2)
            model = (re.search(r'data-product-model="([^"]+)"', card) or [None, ""])[1]
            if not M.match(model):
                continue
            sku = (re.search(r'data-product-sku="([^"]+)"', card) or [None, ""])[1]
            if any(r and r["listing_id"] == sku for r in rows):
                continue
            price = (re.search(r'data-price-amount="([\d.]+)"', card) or [None, ""])[1]
            year = (re.search(r'Year <span[^>]*>\s*(\d{4})', card) or [None, ""])[1]
            box = 'Box <span class="icon icon-yes"' in card
            papers = 'Papers <span class="icon icon-yes"' in card
            bp = "Box & papers" if box and papers else "Papers" if papers else "Box" if box else "Watch only"
            img = (re.search(r'data-product-image="([^"]+)"', card) or [None, ""])[1]
            rows.append(M.finish({
                "listing_id": sku, "site_code": "watchfinder", "title": f"Patek Philippe Nautilus {model}",
                "reference": model, "year": year, "box_papers": bp, "price": price, "status": "For sale",
                "seller": "Watchfinder & Co.", "link": href, "image_url": html.unescape(img),
                "description": model,
            }, when))
    return rows


def scrape_jomashop(browser, when, M=None):
    M = M or MODELS["5711"]
    _content, bodies = browser.open(f"https://www.jomashop.com/search?q=patek%20philippe%20{M.term}",
                                    capture="jomashop_production/search")
    if not bodies:
        raise ScrapeError("Jomashop page loaded but its product search did not answer")
    rows = []
    for body in bodies:
        try:
            hits = json.loads(body).get("hits") or []
        except ValueError:
            continue
        for h in hits:
            title = h.get("variantTitle") or h.get("name") or ""
            if not M.match(title, h.get("sku")) or not h.get("in_stock"):
                continue
            rows.append(M.finish({
                "listing_id": str(h.get("product_id") or h.get("sku")), "site_code": "jomashop",
                "title": title, "reference": f"{h.get('sku', '')} {title}", "price": h.get("price"),
                "condition": "Pre-owned" if h.get("is_preowned") else (h.get("item_condition") or ""),
                "status": "For sale", "seller": "Jomashop", "location": "Brooklyn, NY, US",
                "link": "https://www.jomashop.com/" + str(h.get("url_key") or ""),
                "image_url": h.get("small_image") or "", "description": title + " " + (h.get("description") or ""),
            }, when))
    return rows


def scrape_grailzee(browser, when, M=None):
    M = M or MODELS["5711"]
    _content, bodies = browser.open(f"https://grailzee.com/search?q={M.term}", capture="prod-auctions/_search")
    if not bodies:
        raise ScrapeError("Grailzee page loaded but its auction search did not answer")
    rows, seen = [], set()
    for body in bodies:
        try:
            hits = json.loads(body).get("hits", {}).get("hits", [])
        except (ValueError, AttributeError):
            continue
        for hit in hits:
            s = hit.get("_source") or {}
            ref = (s.get("referenceNumber") or {}).get("referenceNumber") or ""
            if not M.match(ref) or str(s.get("id")) in seen:
                continue
            seen.add(str(s.get("id")))
            sold = bool(s.get("hasAuctionSold"))
            ended = bool(s.get("hasAuctionEnded"))
            price = s.get("finalPriceUsd") if sold else (s.get("askingPrice") or s.get("currentBid"))
            status = ("Sold (auction)" if sold else
                      "Buy-now (auction ended unsold)" if ended and s.get("askingPrice") else
                      "Auction live")
            rows.append(M.finish({
                "listing_id": str(s.get("id")), "site_code": "grailzee", "title": s.get("title") or "",
                "reference": ref, "year": year_from(s.get("title")), "price": price, "status": status,
                "seller": "Grailzee" + (" (pro seller)" if (s.get("customer") or {}).get("isProSeller") else " (private seller)"),
                "location": (s.get("customer") or {}).get("country") or "",
                "link": "https://grailzee.com/products/" + str(s.get("handle") or ""),
                "image_url": ((s.get("media") or [{}])[0] or {}).get("src", ""),
                "description": (s.get("title") or "") + " " + (s.get("bodyText") or ""),
            }, when))
    return rows


# name -> (label, kind, function). kind "http" gets a curl session, "browser" a Browser.
SOURCES = {
    "bobs": ("Bob's Watches", "http", scrape_bobs),
    "the1916": ("The 1916 Company (WatchBox)", "http", scrape_the1916),
    "swe": ("Swiss Watch Expo", "http", scrape_swe),
    "davidsw": ("DavidSW", "http", scrape_davidsw),
    "analogshift": ("Analog Shift", "http", scrape_analogshift),
    "hodinkee": ("Hodinkee Shop", "http", scrape_hodinkee),
    "watchfinder": ("Watchfinder & Co.", "browser", scrape_watchfinder),
    "jomashop": ("Jomashop", "browser", scrape_jomashop),
    "grailzee": ("Grailzee", "browser", scrape_grailzee),
    "ebay": ("eBay", "http", scrape_ebay),
    "watchcharts": ("WatchCharts", "http", scrape_watchcharts),
    "crown": ("Crown & Caliber", "http", scrape_crown),
    "bezel": ("Bezel", "http", scrape_bezel),
    "wristcheck": ("Wristcheck", "http", scrape_wristcheck),
    "luxurybazaar": ("Luxury Bazaar", "http", scrape_luxurybazaar),
    "europeanwatch": ("European Watch Co.", "http", scrape_europeanwatch),
}


def write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def run_source(name, dest, browser=None, sess=None, model="5711"):
    M = MODELS[model]
    label, kind, fn = SOURCES[name]
    when = datetime.now(timezone.utc).isoformat()
    if kind == "browser":
        if browser is None:
            with Browser() as b:
                rows = fn(b, when, M)
        else:
            rows = fn(browser, when, M)
    else:
        rows = fn(sess or session(), when, M)
    rows = [r for r in (rows or []) if r and keep_row(r)]
    write_rows(dest, rows)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", choices=sorted(SOURCES))
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--model", default="5711", choices=sorted(MODELS))
    a = ap.parse_args()
    try:
        rows = run_source(a.source, a.out, model=a.model)
    except ScrapeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(2)
    print(f"[{a.source}] {len(rows)} rows -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
