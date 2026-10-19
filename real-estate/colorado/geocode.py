#!/usr/bin/env python3
"""
geocode.py — place each listing on the map.

Sends every listing title (an address as shown on the Realtor.com card) to the
State of Colorado's public address locator (OIT, gis.colorado.gov, built on the
statewide address-point data) and writes colorado-land-geocodes.json:

  { "<url or title>": {"lat": .., "lon": .., "kind": "address" | "road",
                       "score": .., "matched": "<locator's matched address>"}, ... }

kind = "address"  the locator hit an address point or address range
kind = "road"     only the road was found (e.g. "County Road 502, Bayfield");
                  the point sits somewhere on that road in that ZIP

Listings with no usable match (score < 80, or > 60 km from their city) are left
out; the HTML page falls back to the city position and marks them approximate.

Run: python3 geocode.py   (needs colorado-land-over-10ac.json reassembled; see README)
"""

import json
import math
import os
import re
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "colorado-land-over-10ac.json")
HTML = os.path.join(HERE, "colorado-land-10ac.html")
OUT = os.path.join(HERE, "colorado-land-geocodes.json")
LOCATOR = "https://gis.colorado.gov/gp/rest/services/Geocoders/PA_Composite_Pro/GeocodeServer"
BATCH = 200
MIN_SCORE = 80
MAX_KM_FROM_CITY = 60
KIND = {"PointAddress": "address", "Subaddress": "address", "StreetAddress": "address",
        "StreetAddressExt": "address", "StreetName": "road", "StreetInt": "road"}


def split_title(title):
    """'3448 County Road 352A, Canon City, CO 81212' -> (street, city, state, zip).
    The batch endpoint ignores SingleLine, so the parts go in separate fields."""
    parts = [p.strip() for p in (title or "").split(",")]
    if len(parts) < 3:
        return None
    m = re.match(r"([A-Z]{2})\s*(\d{5})?", parts[-1])
    if not m:
        return None
    return ", ".join(parts[:-2]), parts[-2], m.group(1), m.group(2) or ""


def clean_street(street):
    """Drop lot/tract/TBD/unit tokens the locator can't use: 'Rockcliff Cir Lot 16' -> 'Rockcliff Cir'."""
    s = re.sub(r"\b(lot|tract|tr|parcel|par|unit|l)\s*#?\s*[\w-]+", "", street, flags=re.I)
    s = re.sub(r"\btbd\b", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip(" ,")


def find_one(single_line):
    """Single-address lookup; unlike the batch endpoint it accepts SingleLine."""
    q = urllib.parse.urlencode({"SingleLine": single_line, "outSR": 4326, "maxLocations": 1,
                                "outFields": "Addr_type,Score,Match_addr", "f": "json"})
    with urllib.request.urlopen(LOCATOR + "/findAddressCandidates?" + q, timeout=60) as r:
        c = json.load(r).get("candidates") or []
    return c[0] if c else None


def city_centroids():
    """City positions already embedded in the page (MARKERS), used as a sanity check."""
    with open(HTML) as fh:
        m = re.search(r"const MARKERS = (\[.*?\]);", fh.read())
    return {c["c"]: (c["la"], c["lo"]) for c in json.loads(m.group(1))}


def km(a, b):
    dy = math.radians(a[0] - b[0])
    dx = math.radians(a[1] - b[1]) * math.cos(math.radians(a[0]))
    return 6371 * math.hypot(dx, dy)


def geocode_batch(records):
    body = urllib.parse.urlencode({
        "addresses": json.dumps({"records": records}),
        "outSR": 4326, "f": "json",
    }).encode()
    for attempt in range(3):
        with urllib.request.urlopen(LOCATOR + "/geocodeAddresses", data=body, timeout=300) as r:
            resp = json.load(r)
        if "locations" in resp:
            return resp["locations"]
        time.sleep(5 * (attempt + 1))  # the state server returns an error body under load
    raise RuntimeError(f"geocodeAddresses failed: {resp}")


def main():
    with open(SRC) as fh:
        listings = json.load(fh)
    cities = city_centroids()
    records = []
    for i, rec in enumerate(listings):
        parts = split_title(rec["title"])
        if parts:
            street, city, state, zip5 = parts
            records.append({"attributes": {"OBJECTID": i + 1, "Address": street,
                                           "City": city, "Region": state, "Postal": zip5}})

    out, tally = {}, {"address": 0, "road": 0, "low score": 0, "too far": 0, "no match": 0}
    for start in range(0, len(records), BATCH):
        for loc in geocode_batch(records[start:start + BATCH]):
            a = loc["attributes"]
            rec = listings[a["ResultID"] - 1]
            kind = KIND.get(a.get("Addr_type"))
            if not kind or not loc.get("location"):
                tally["no match"] += 1
                continue
            if a["Score"] < MIN_SCORE:
                tally["low score"] += 1
                continue
            pt = (loc["location"]["y"], loc["location"]["x"])
            home = cities.get(rec["city"])
            if home and km(pt, home) > MAX_KM_FROM_CITY:
                tally["too far"] += 1
                continue
            out[rec["url"] or rec["title"]] = {
                "lat": round(pt[0], 5), "lon": round(pt[1], 5), "kind": kind,
                "score": round(a["Score"], 1), "matched": a.get("Match_addr"),
            }
            tally[kind] += 1
        print(f"  {min(start + BATCH, len(records))}/{len(records)} sent")

    # Second pass: retry misses one at a time with a cleaned street and a single-line query.
    tally["retry placed"] = 0
    for rec in listings:
        key = rec["url"] or rec["title"]
        parts = split_title(rec["title"])
        if key in out or not parts:
            continue
        street = clean_street(parts[0])
        if not street:
            continue
        c = find_one(f"{street}, {parts[1]}, {parts[2]} {parts[3]}".strip())
        kind = c and KIND.get(c["attributes"].get("Addr_type"))
        if not kind or c["score"] < MIN_SCORE:
            continue
        pt = (c["location"]["y"], c["location"]["x"])
        home = cities.get(rec["city"])
        if home and km(pt, home) > MAX_KM_FROM_CITY:
            continue
        out[key] = {"lat": round(pt[0], 5), "lon": round(pt[1], 5), "kind": kind,
                    "score": round(c["score"], 1), "matched": c["attributes"].get("Match_addr")}
        tally[kind] += 1
        tally["retry placed"] += 1

    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    tally["unparseable title"] = len(listings) - len(records)
    print(f"placed {len(out)} of {len(listings)}: {tally}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
