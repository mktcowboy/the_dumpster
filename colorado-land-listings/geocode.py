#!/usr/bin/env python3
"""
geocode.py — place each listing on the map.

Sends every listing title (an address as shown on the Realtor.com card) to the
free US Census batch geocoder and writes colorado-land-geocodes.json:

  { "<url or title>": {"lat": .., "lon": .., "match": "Exact" | "Non_Exact"}, ... }

Listings the Census geocoder can't place (road-only addresses like
"County Road 502, Bayfield") are left out; the HTML page falls back to the
city centroid for those and marks them as approximate.

Run: python3 geocode.py   (needs the JSON reassembled; see README)
"""

import csv
import io
import json
import os
import re
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "colorado-land-over-10ac.json")
OUT = os.path.join(HERE, "colorado-land-geocodes.json")
ENDPOINT = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"


def split_title(title):
    """'3448 County Road 352A, Canon City, CO 81212' -> (street, city, state, zip)."""
    parts = [p.strip() for p in (title or "").split(",")]
    if len(parts) < 3:
        return None
    m = re.match(r"([A-Z]{2})\s*(\d{5})?", parts[-1])
    if not m:
        return None
    return ", ".join(parts[:-2]), parts[-2], m.group(1), m.group(2) or ""


def post_batch(rows):
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"benchmark\"\r\n\r\nPublic_AR_Current\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"addressFile\"; filename=\"a.csv\"\r\n"
        f"Content-Type: text/csv\r\n\r\n{buf.getvalue()}\r\n--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(ENDPOINT, data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read().decode("utf-8", "replace")


def main():
    with open(SRC) as fh:
        listings = json.load(fh)
    rows, keys = [], {}
    for i, rec in enumerate(listings):
        parts = split_title(rec["title"])
        if parts:
            rows.append([i, *parts])
            keys[str(i)] = rec["url"] or rec["title"]
    print(f"sending {len(rows)} of {len(listings)} addresses")

    out = {}
    for row in csv.reader(io.StringIO(post_batch(rows))):
        if len(row) < 6 or row[2] != "Match":
            continue
        lon, lat = (float(v) for v in row[5].split(","))
        out[keys[row[0]]] = {"lat": round(lat, 5), "lon": round(lon, 5), "match": row[3]}

    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    exact = sum(1 for v in out.values() if v["match"] == "Exact")
    print(f"matched {len(out)} ({exact} exact, {len(out) - exact} non-exact); wrote {OUT}")


if __name__ == "__main__":
    main()
