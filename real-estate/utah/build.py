#!/usr/bin/env python3
"""
build.py — assemble the Utah land-listings drop and its map page.

Reads every raw capture in raw/ (Realtor.com search: Utah, Land, 10+ acre lot,
"Lowest price" sort), dedupes by Realtor property id, places each listing on
the map, and writes:
  utah-land-over-10ac.csv
  utah-land-over-10ac.json
  utah-land-10ac.html          (from page-template.html)

Placement, best first:
  realtor  Realtor.com's own map pin for the listing (in the search data)
  address  matched to a UGRC statewide address point (street-numbered listings)
  city     the city's position from OpenStreetMap Nominatim (approximate)
Lookups are cached in utah-geocache.json so reruns don't hit the services again.

Run: python3 build.py
"""

import csv
import glob
import html
import json
import math
import os
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
CACHE = os.path.join(HERE, "utah-geocache.json")
COUNTIES = os.path.join(HERE, "utah-counties.json")
TEMPLATE = os.path.join(HERE, "page-template.html")
OUT_CSV = os.path.join(HERE, "utah-land-over-10ac.csv")
OUT_JSON = os.path.join(HERE, "utah-land-over-10ac.json")
OUT_HTML = os.path.join(HERE, "utah-land-10ac.html")
UGRC = ("https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services/"
        "UtahAddressPoints/FeatureServer/0/query")
NOMINATIM = "https://nominatim.openstreetmap.org/search"
UA = "land-listings-build/1.0"
FIELDS = ["id", "slug", "price", "lot_sqft", "line", "city", "zip", "lat", "lon",
          "fips", "broker", "pending", "list_date"]
CSV_FIELDS = ["title", "price_usd", "acres", "price_per_acre", "county", "city", "zip",
              "broker", "pending", "list_date", "lat", "lon", "placement", "url"]


# ---------- load ----------

def load_raw():
    """Raw files come in two shapes: one page per file ({fields, rows}), or the
    whole tab export ([{page, rows: [ {...}, ... ]}, ...])."""
    recs, site_total, files = [], None, sorted(glob.glob(os.path.join(RAW, "*.json")))
    for f in files:
        with open(f) as fh:
            d = json.load(fh)
        if isinstance(d, dict) and "rows" in d:
            site_total = d.get("site_total", site_total)
            recs += [dict(zip(d["fields"], r)) for r in d["rows"]]
        elif isinstance(d, list):
            for page in d:
                for r in page["rows"]:
                    recs.append({"id": r["id"], "slug": r["slug"], "price": r["price"], "lot_sqft": r["lot"],
                                 "line": r["line"], "city": r["city"], "zip": r["zip"], "lat": r["lat"],
                                 "lon": r["lon"], "fips": r["fips"], "broker": r["broker"],
                                 "pending": r.get("pend", False), "list_date": (r.get("ld") or "")[:10] or None})
    return recs, site_total, files


# ---------- geocoding ----------

def load_cache():
    if os.path.exists(CACHE):
        with open(CACHE) as fh:
            return json.load(fh)
    return {"address": {}, "city": {}}


class LookupFailed(Exception):
    """The service kept failing; the listing is skipped this run and not cached, so a rerun retries it."""


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(3 * (attempt + 1))  # UGRC and Nominatim both return 5xx under load
    raise LookupFailed(f"{url[:80]}: {last}")


def save_cache(cache):
    with open(CACHE, "w") as fh:
        json.dump(cache, fh, indent=1, sort_keys=True)


def norm_addr(s):
    s = re.sub(r"[#.,]", " ", (s or "").upper())
    s = re.sub(r"\b(UNIT|LOT|APT)\b\s*\S+", " ", s)
    for a, b in [("NORTH", "N"), ("SOUTH", "S"), ("EAST", "E"), ("WEST", "W"), ("ROAD", "RD"), ("DRIVE", "DR"),
                 ("STREET", "ST"), ("LANE", "LN"), ("AVENUE", "AVE"), ("CIRCLE", "CIR"), ("HIGHWAY", "HWY")]:
        s = re.sub(r"\b" + a + r"\b", b, s)
    return re.sub(r"\s+", " ", s).strip()


def ugrc_address(line, zip5, city):
    """Exact match against UGRC address points by house number + ZIP (or city)."""
    m = re.match(r"(\d+)\s+(.+)", line or "")
    if not m:
        return None
    want = norm_addr(line)
    for where in [f"AddNum='{m.group(1)}' AND ZipCode='{zip5}'",
                  f"AddNum='{m.group(1)}' AND City='{(city or '').upper().replace(chr(39), '')}'"]:
        q = urllib.parse.urlencode({"where": where, "outFields": "FullAdd", "outSR": 4326,
                                    "f": "json", "resultRecordCount": 50})
        for f in get_json(UGRC + "?" + q).get("features", []):
            if norm_addr(f["attributes"]["FullAdd"]) == want:
                return [round(f["geometry"]["y"], 5), round(f["geometry"]["x"], 5)]
    return None


def city_point(city, zip5):
    d = []
    if city:
        q = urllib.parse.urlencode({"city": city, "state": "Utah", "country": "USA", "format": "jsonv2",
                                    "limit": 1, "addressdetails": 1})
        d = get_json(NOMINATIM + "?" + q, {"User-Agent": UA})
        time.sleep(1.1)  # Nominatim usage policy: at most one request per second
    if not d and zip5:
        q = urllib.parse.urlencode({"postalcode": zip5, "country": "USA", "format": "jsonv2", "limit": 1,
                                    "addressdetails": 1})
        d = get_json(NOMINATIM + "?" + q, {"User-Agent": UA})
        time.sleep(1.1)
    d = [x for x in d if x.get("address", {}).get("state") == "Utah"]
    return [round(float(d[0]["lat"]), 5), round(float(d[0]["lon"]), 5)] if d else None


def place_all(rows):
    cache = load_cache()
    tally = {"realtor": 0, "address": 0, "city": 0, "none": 0, "lookup failed": 0}
    for n, r in enumerate(rows):
        if n % 25 == 0:
            save_cache(cache)  # keep finished lookups if a later one dies
        if r["lat"] is not None and r["lon"] is not None:
            r["gk"] = "realtor"
        else:
            hit = None
            if r["line"] and re.match(r"\d", r["line"]):
                key = f'{r["line"]}|{r["zip"]}|{r["city"]}'
                if key not in cache["address"]:
                    try:
                        cache["address"][key] = ugrc_address(r["line"], r["zip"], r["city"])
                    except LookupFailed:
                        tally["lookup failed"] += 1
                hit = cache["address"].get(key)
            if hit:
                r["lat"], r["lon"], r["gk"] = hit[0], hit[1], "address"
            else:
                key = f'{r["city"]}|{r["zip"]}'
                if key not in cache["city"]:
                    try:
                        cache["city"][key] = city_point(r["city"], r["zip"]) if r["city"] or r["zip"] else None
                    except LookupFailed:
                        tally["lookup failed"] += 1
                hit = cache["city"].get(key)
                if hit:
                    r["lat"], r["lon"], r["gk"] = hit[0], hit[1], "city"
                else:
                    r["gk"] = None
        tally[r["gk"] or "none"] += 1
    save_cache(cache)
    return tally


# ---------- page pieces ----------

def money(n):
    return "$" + format(round(n), ",")


def hist_svg(ppas):
    edges = [0, 250, 500, 1e3, 2e3, 4e3, 8e3, 16e3, 32e3, 64e3, 128e3, 256e3, 512e3, math.inf]
    def lab(v):
        return f"{int(v // 1000)}k" if v >= 1000 else str(int(v))
    labels = ["<$250"] + [f"${lab(edges[i])}–{lab(edges[i + 1])}" for i in range(1, 12)] + [">$512k"]
    counts = [sum(1 for v in ppas if edges[i] <= v < edges[i + 1]) for i in range(13)]
    top, slot = max(counts) or 1, 690 / 13
    out = ['<svg viewBox="0 0 760 190" width="100%" role="img" aria-label="Price per acre distribution">',
           '<line x1="34" y1="164" x2="726" y2="164" stroke="#999"/>']
    for i, (n, l) in enumerate(zip(counts, labels)):
        h = 150 * n / top
        x = 36 + i * slot
        cx = x + (slot - 4) / 2
        out.append(f'<rect x="{x:.1f}" y="{164 - h:.1f}" width="{slot - 4:.1f}" height="{h:.1f}" fill="#23406b" '
                   f'opacity="0.85"><title>{html.escape(l)}: {n} listings</title></rect>')
        out.append(f'<text x="{cx:.1f}" y="178" font-size="8.5" text-anchor="middle" fill="#666">{html.escape(l)}</text>')
        if n:
            out.append(f'<text x="{cx:.1f}" y="{160 - h:.1f}" font-size="8.5" text-anchor="middle" fill="#333">{n}</text>')
    return "".join(out) + "</svg>"


def stats_html(rows):
    prices = [r["price"] for r in rows if r["price"] is not None]
    ppas = [r["ppa"] for r in rows if r["ppa"] is not None]
    acres = [r["acres"] for r in rows if r["acres"] is not None]
    def stat(k, v, d):
        return f'    <div class="stat"><div class="k">{k}</div><div class="v">{v}</div><div class="d">{d}</div></div>'
    return "\n".join([
        stat("Listings", format(len(rows), ","), "unique, deduped by Realtor property id"),
        stat("Median price", money(statistics.median(prices)),
             f"mean {money(statistics.mean(prices))} &middot; range {money(min(prices))}&ndash;{money(max(prices))}"),
        stat("Median $/acre", money(statistics.median(ppas)), f"mean {money(statistics.mean(ppas))}"),
        stat("Median acres", f"{statistics.median(acres):,.1f}", f"range {min(acres):,.1f}&ndash;{max(acres):,.1f}"),
    ])


def main():
    raw, site_total, files = load_raw()
    with open(COUNTIES) as fh:
        counties = json.load(fh)
    county_name = {f["properties"]["fips"]: f["properties"]["n"] for f in counties["features"]}

    seen, rows = set(), []
    for r in raw:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        acres = round(r["lot_sqft"] / 43560, 2) if r["lot_sqft"] else None
        place = ", ".join(x for x in [r["line"], r["city"]] if x)
        r.update({
            "title": (f"{place}, " if place else "") + f"UT {r['zip'] or ''}".strip(),
            "acres": acres,
            "ppa": round(r["price"] / acres) if r["price"] and acres else None,
            "county": county_name.get(r["fips"]),
            "url": "https://www.realtor.com/realestateandhomes-detail/" + r["slug"] if r["slug"] else None,
        })
        rows.append(r)
    tally = place_all(rows)

    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(CSV_FIELDS)
        for r in rows:
            w.writerow([r["title"], r["price"], r["acres"], r["ppa"], r["county"], r["city"], r["zip"], r["broker"],
                        r["pending"], r["list_date"], r["lat"], r["lon"], r["gk"], r["url"]])
    with open(OUT_JSON, "w") as fh:
        json.dump([{k: r.get(k) for k in ["title", "price", "acres", "ppa", "county", "city", "zip", "broker",
                                          "pending", "list_date", "lat", "lon", "gk", "url"]} for r in rows], fh, indent=1)

    data = [{"title": r["title"], "price": r["price"], "acres": r["acres"], "ppa": r["ppa"], "city": r["city"],
             "broker": r["broker"], "url": r["url"], "region": r["county"] or "Unknown", "county": r["county"],
             "la": r["lat"], "lo": r["lon"], "gk": r["gk"]} for r in rows]
    n, total = len(rows), site_total or len(rows)
    partial = n < total
    at10 = sum(1 for r in rows if r["acres"] == 10)
    placed = tally["realtor"] + tally["address"]
    counties_present = sorted({r["county"] for r in rows if r["county"]})
    fill = {
        "TITLE": f"Utah Land — 10+ Acres · {n:,} Listings",
        "H1": "Utah Land &mdash; 10+ Acres",
        "SUB": f"{n:,} for-sale listings &middot; Realtor.com snapshot, October 16, 2026",
        "CAVEAT": (f"<b>Partial build: {n:,} of the {total:,} listings Realtor.com reports.</b> The rest were collected "
                   "but are not on disk yet; rerun <code>build.py</code> once they are. " if partial else
                   f"Coverage: all {n:,} listings Realtor.com reported for this search. ") +
                  f"The site&rsquo;s acreage filter is inclusive (10+), so {at10} listings sit at exactly 10.0 acres. "
                  "A few listings carry the site&rsquo;s own oddities (a $1 price, a water right listed as 100,000 acres); "
                  "values are reproduced as listed, not corrected.",
        "STATS": stats_html(rows),
        "HIST": hist_svg([r["ppa"] for r in rows if r["ppa"] is not None]),
        "REGION_OPTIONS": "".join(f'<option value="{html.escape(c)}">{html.escape(c)}</option>' for c in counties_present),
        "MAPNOTE": ("One dot per listing: color is price per acre, size is acreage. Hover a dot for its $/acre and key "
                    "numbers (tap on a phone); click for details and the Realtor.com link. From zoom level 12 each dot "
                    "becomes a circle with the parcel&rsquo;s real area; the true boundary isn&rsquo;t known. Filters "
                    f"above update the map and the table. {placed:,} listings use Realtor.com&rsquo;s own map pin or a "
                    f"UGRC address point; {tally['city']:,} sit at their city and are drawn hollow. Click "
                    "&ldquo;Map&rdquo; on any table row to jump to that listing."),
        "FOOT": ("Source: Realtor.com search (Utah statewide, Land, 10+ acre lot filter, for sale), "
                 "&ldquo;Lowest price&rdquo; sort. County from Realtor.com&rsquo;s county code. Positions: "
                 "Realtor.com map pins, UGRC Utah address points, or OpenStreetMap city positions. County outlines: "
                 "US Census 2010 cartographic boundaries. Built October 2026."),
        "COUNTY_SOURCE": "Utah county outlines (US Census 2010 cartographic boundaries via plotly/datasets), 4-decimal coords",
        "CSV_NAME": "utah-land-filtered.csv",
        "DATA": json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/"),
        "COUNTIES": json.dumps(counties, separators=(",", ":")),
    }
    with open(TEMPLATE) as fh:
        page = fh.read()
    for k, v in fill.items():
        page = page.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{[A-Z0-9_]+\}\}", page)
    assert not left, f"unfilled placeholders: {left}"
    with open(OUT_HTML, "w") as fh:
        fh.write(page)

    print(f"raw files: {len(files)}  raw records: {len(raw)}  unique: {n}  (site total {total})")
    print(f"placement: {tally}")
    print(f"wrote {OUT_CSV}\nwrote {OUT_JSON}\nwrote {OUT_HTML}")


if __name__ == "__main__":
    main()
