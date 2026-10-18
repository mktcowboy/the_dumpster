#!/usr/bin/env python3
"""v1 pipeline: chunks -> dedupe -> Census batch geocode -> classify -> listings.json

Reads ~/workspace/texas-triangle-land/chunks/texas-*.json, dedupes by URL,
geocodes addresses via the Census batch geocoder (TIGER/Line), falls back to
city-center for unmatched rural addresses (marked loc='city'), classifies
inside-triangle vs 50mi buffer, writes listings.json for build_tx_page.py.
"""
import json, glob, math, os, re, csv, io, time

HERE = os.path.dirname(os.path.abspath(__file__))
CHUNKS = os.path.join(HERE, "chunks")
OUT = os.path.join(HERE, "listings.json")

V = [(32.7767, -96.7970), (29.4241, -98.4936), (29.7604, -95.3698)]
BUFFER_MI = 50.0
MIN_ACRES = 5.0


def point_in_poly(pt, poly):
    x, y = pt[1], pt[0]
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i][1], poly[i][0]
        x2, y2 = poly[(i + 1) % n][1], poly[(i + 1) % n][0]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
            inside = not inside
    return inside


def dist_to_triangle_mi(p):
    if point_in_poly(p, V):
        return 0.0
    lat0 = math.radians(p[0])
    kx = math.cos(lat0) * 69.0
    best = float("inf")
    for i in range(3):
        a, b = V[i], V[(i + 1) % 3]
        ax, ay = (a[1] - p[1]) * kx, (a[0] - p[0]) * 69.0
        bx, by = (b[1] - p[1]) * kx, (b[0] - p[0]) * 69.0
        dx, dy = bx - ax, by - ay
        t = 0 if dx == 0 and dy == 0 else max(0, min(1, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def parse_addr(title, city):
    """Split '123 Main St, Hockley, TX 77447' -> (street, zip)."""
    title = (title or "").strip()
    m = re.search(r"(\b\d{5}(?:-\d{4})?\b)\s*$", title)
    zipc = m.group(1)[:5] if m else ""
    # street = text before the first ", <city>" or before ", TX"
    street = title
    for pat in [f", {city},", ", TX", ", Texas"]:
        if pat in street:
            street = street.split(pat)[0]
            break
    street = street.strip(" ,")
    return street, zipc


GEOCODE_CACHE = os.path.join(HERE, "geocode_cache.json")


def nominatim(q):
    import urllib.request, urllib.parse
    url = ("https://nominatim.openstreetmap.org/search?q=" + urllib.parse.quote(q) +
           "&format=json&limit=1&countrycodes=us")
    req = urllib.request.Request(url, headers={"User-Agent": "tx-land-pull/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        d = json.load(resp)
    return d


def geocode_all(unique):
    """Cascade: full address -> street+city -> city. Returns dict idx -> (lat,lon,loc)."""
    cache = {}
    if os.path.exists(GEOCODE_CACHE):
        cache = json.load(open(GEOCODE_CACHE))
    out = {}
    for i, r in enumerate(unique):
        title = (r.get("t") or "").strip()
        city = (r.get("c") or "").strip()
        street, _zipc = parse_addr(title, city)
        cands = []
        if title:
            cands.append((title, "parcel"))
        if street and city and street.lower() != city.lower():
            cands.append((f"{street}, {city}, Texas", "street"))
        if city:
            cands.append((f"{city}, Texas", "city"))
        hit = None
        for q, loc in cands:
            if q in cache:
                if cache[q] is not None:
                    hit = (cache[q], loc)
                    break
                continue  # this query failed before; try the next, less-specific one
            try:
                d = nominatim(q)
            except Exception:
                d = None
            time.sleep(1.1)
            if d:
                cache[q] = [float(d[0]["lat"]), float(d[0]["lon"])]
                hit = (cache[q], loc)
                break
            cache[q] = None
        if hit and hit[0]:
            out[i] = (hit[0][0], hit[0][1], hit[1])
        else:
            out[i] = (None, None, "none")
        if i % 25 == 0:
            json.dump(cache, open(GEOCODE_CACHE, "w"))
            print(f"  geocoded {i}/{len(unique)}", flush=True)
    json.dump(cache, open(GEOCODE_CACHE, "w"))
    return out


def main():
    files = sorted(glob.glob(os.path.join(CHUNKS, "texas-*.json")))
    raw = []
    for f in files:
        county = os.path.basename(f)[len("texas-"):-len(".json")]
        for r in json.load(open(f)):
            r["county"] = county
            raw.append(r)
    print(f"raw: {len(raw)} from {len(files)} files")
    seen, unique = set(), []
    for r in raw:
        key = r.get("u") or (r.get("t"), r.get("p"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    print(f"unique: {len(unique)}")
    unique = [r for r in unique
              if r.get("a") is None or float(r["a"]) >= MIN_ACRES]
    print(f">= {MIN_ACRES}ac (or unknown): {len(unique)}")

    # geocode via Nominatim cascade (full addr -> street -> city)
    print(f"geocoding {len(unique)} via Nominatim cascade...", flush=True)
    res = geocode_all(unique)
    n_parcel = sum(1 for v in res.values() if v[2] == "parcel")
    n_street = sum(1 for v in res.values() if v[2] == "street")
    n_city = sum(1 for v in res.values() if v[2] == "city")
    n_none = sum(1 for v in res.values() if v[2] == "none")
    print(f"parcel: {n_parcel}, street: {n_street}, city: {n_city}, failed: {n_none}")

    final = []
    for i, r in enumerate(unique):
        lat, lon, loc = res.get(i, (None, None, "none"))
        if lat is None:
            continue
        d = dist_to_triangle_mi((lat, lon))
        zone = "inside" if d == 0.0 else ("buffer" if d <= BUFFER_MI else "outside")
        url = r.get("u") or ""
        if url.startswith("/"):
            url = "https://www.realtor.com" + url
        final.append({
            "title": r.get("t"), "price": r.get("p"), "acres": r.get("a"),
            "lat": round(lat, 5), "lon": round(lon, 5),
            "city": r.get("c"), "county": r.get("county"), "url": url,
            "zone": zone, "dist_tri_mi": round(d, 1), "loc": loc,
        })
    inside = sum(1 for r in final if r["zone"] == "inside")
    buffer = sum(1 for r in final if r["zone"] == "buffer")
    outside = sum(1 for r in final if r["zone"] == "outside")
    approx = sum(1 for r in final if r["loc"] == "city")
    print(f"inside: {inside}, buffer: {buffer}, outside(dropped): {outside}, city-approx: {approx}")
    kept = [r for r in final if r["zone"] in ("inside", "buffer")]
    json.dump(kept, open(OUT, "w"), indent=1)
    print(f"wrote {OUT}: {len(kept)} records")


if __name__ == "__main__":
    main()
