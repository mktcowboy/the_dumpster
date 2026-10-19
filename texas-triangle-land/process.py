#!/usr/bin/env python3
"""Step 2: newest raw snapshot -> data/listings.json.

Dedupes (Realtor returns some listings twice), drops pending/contingent and anything under
5 acres, fills the few missing coordinates by geocoding (OpenStreetMap Nominatim, cached in
data/geocode_cache.json), classifies inside-triangle / 50-mile ring / outside, and records
when each listing first appeared across all snapshots.

    python process.py                    # newest snapshot in data/raw/
    python process.py --date 2026-10-18  # a specific one
    python process.py --no-geocode       # skip network lookups for missing coordinates
"""
import argparse, glob, gzip, json, os, time, urllib.parse, urllib.request

from geo import zone_of
from privacy_filter import blocked

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(HERE, "data", "raw")
OUT = os.path.join(HERE, "data", "listings.json")
GEOCODE_CACHE = os.path.join(HERE, "data", "geocode_cache.json")

MIN_ACRES = 5.0
MIN_PRICE = 1_000  # below this is a placeholder ($1, "call for price") or a lease
SQFT_PER_ACRE = 43_560
KEEP_STATUS = {"FOR_SALE"}  # add "PENDING" / "CONTINGENT" to keep under-contract listings
# condo/townhome units report the whole complex's lot size, so "5+ acres" is meaningless for them
DROP_STYLES = {"CONDOS", "CONDO", "CONDOP", "COOP", "TOWNHOMES", "CONDO_TOWNHOME",
               "CONDO_TOWNHOME_ROWHOME_COOP"}


def snapshots():
    return sorted(d for d in os.listdir(RAW_DIR)
                  if os.path.isdir(os.path.join(RAW_DIR, d)) and not d.startswith("."))


def load_snapshot(date):
    rows = []
    for f in sorted(glob.glob(os.path.join(RAW_DIR, date, "*.json.gz"))):
        with gzip.open(f, "rt") as fh:
            data = json.load(fh)
        for r in data:
            r["_search_county"] = os.path.basename(f)[:-len(".json.gz")]
            rows.append(r)
    return rows


def key_of(r):
    return str(r.get("property_id") or r.get("property_url"))


def dedupe(rows):
    """One row per property. Realtor sometimes returns a property twice (e.g. relisted under a
    new listing id at a new price); keep the newest listing so every run picks the same row."""
    best = {}
    for r in rows:
        k = key_of(r)
        rank = (r.get("list_date") or "", str(r.get("listing_id") or ""))
        if k not in best or rank > best[k][0]:
            best[k] = (rank, r)
    return [r for _, r in best.values()]


def history(dates):
    """property key -> (first snapshot date it appeared in, price in the previous snapshot)."""
    first, prev_price = {}, {}
    for i, d in enumerate(dates):
        for r in dedupe(load_snapshot(d)):
            k = key_of(r)
            first.setdefault(k, d)
            if i == len(dates) - 2:
                prev_price[k] = r.get("list_price")
    return first, prev_price


def nominatim(q):
    url = ("https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=us&q="
           + urllib.parse.quote(q))
    req = urllib.request.Request(url, headers={"User-Agent": "texas-triangle-land/2.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        d = json.load(resp)
    return [float(d[0]["lat"]), float(d[0]["lon"])] if d else None


def geocode(r, cache, online):
    """Cascade street+city -> zip -> city. Returns (lat, lon, precision) or None."""
    city, street, zipc = r.get("city") or "", r.get("street") or "", r.get("zip_code") or ""
    cands = []
    if street and city:
        cands.append((f"{street}, {city}, Texas {zipc}".strip(), "street"))
    if zipc:
        cands.append((f"{zipc}, Texas", "zip"))
    if city:
        cands.append((f"{city}, Texas", "city"))
    for q, prec in cands:
        if q not in cache:
            if not online:
                continue
            try:
                cache[q] = nominatim(q)
            except Exception as e:
                print(f"    geocode error for {q!r}: {e}")
                continue  # don't cache transient failures
            time.sleep(1.1)  # Nominatim usage policy: max 1 request/second
        if cache[q]:
            return cache[q][0], cache[q][1], prec
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="snapshot folder (default: newest)")
    ap.add_argument("--no-geocode", action="store_true")
    args = ap.parse_args()

    dates = snapshots()
    if not dates:
        raise SystemExit("no snapshots in data/raw -- run scrape.py first")
    date = args.date or dates[-1]
    dates = [d for d in dates if d <= date]
    raw = load_snapshot(date)
    print(f"snapshot {date}: {len(raw)} raw rows")
    first_seen, prev_price = history(dates)

    rows = [r for r in dedupe(raw) if not blocked(r)]
    print(f"unique: {len(rows)}")
    rows = [r for r in rows if (r.get("status") or "FOR_SALE") in KEEP_STATUS]
    print(f"status in {sorted(KEEP_STATUS)}: {len(rows)}")
    rows = [r for r in rows if (r.get("style") or "").upper() not in DROP_STYLES]
    print(f"minus condos/townhomes: {len(rows)}")
    rows = [r for r in rows if r.get("lot_sqft") and r["lot_sqft"] / SQFT_PER_ACRE >= MIN_ACRES]
    print(f">= {MIN_ACRES} acres: {len(rows)}")
    rows = [r for r in rows if (r.get("list_price") or 0) >= MIN_PRICE]
    print(f"price >= ${MIN_PRICE:,}: {len(rows)}")

    cache = json.load(open(GEOCODE_CACHE)) if os.path.exists(GEOCODE_CACHE) else {}
    missing = [r for r in rows if r.get("latitude") is None or r.get("longitude") is None]
    print(f"missing coordinates: {len(missing)} -> geocoding"
          + (" (cache only)" if args.no_geocode else ""), flush=True)
    for i, r in enumerate(missing, 1):
        hit = geocode(r, cache, not args.no_geocode)
        if hit:
            r["latitude"], r["longitude"], r["_loc"] = hit
        if i % 25 == 0:
            json.dump(cache, open(GEOCODE_CACHE, "w"), indent=0, sort_keys=True)
            print(f"  geocoded {i}/{len(missing)}", flush=True)
    json.dump(cache, open(GEOCODE_CACHE, "w"), indent=0, sort_keys=True)

    out, counts = [], {"inside": 0, "buffer": 0, "outside": 0, "no_coords": 0}
    for r in rows:
        if r.get("latitude") is None:
            counts["no_coords"] += 1
            continue
        zone, d = zone_of(r["latitude"], r["longitude"])
        counts[zone] += 1
        if zone == "outside":
            continue
        k = key_of(r)
        prev = prev_price.get(k)
        out.append({
            "id": k,
            "title": r.get("formatted_address") or r.get("street"),
            "price": r.get("list_price"),
            "acres": round(r["lot_sqft"] / SQFT_PER_ACRE, 2),
            "lat": round(r["latitude"], 5), "lon": round(r["longitude"], 5),
            "city": r.get("city"),
            "county": r.get("county") or r["_search_county"],
            "url": r.get("property_url"),
            "zone": zone, "dist_tri_mi": round(d, 1),
            "loc": r.get("_loc", "parcel"),
            "type": (r.get("style") or "LAND").replace("_", " ").title(),
            "list_date": r.get("list_date"),
            "first_seen": first_seen.get(k, date),
            "prev_price": prev if prev != r.get("list_price") else None,
        })
    out.sort(key=lambda x: (x["county"] or "", -(x["price"] or 0)))
    print("zones:", counts)
    json.dump({"snapshot": date, "listings": out}, open(OUT, "w"), indent=1)
    print(f"wrote {os.path.relpath(OUT, HERE)}: {len(out)} listings")


if __name__ == "__main__":
    main()
