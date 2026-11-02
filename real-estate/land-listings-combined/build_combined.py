#!/usr/bin/env python3
"""
build_combined.py — merge the state land-listing drops into one grouped file.

Reads the state projects in place (they stay separate) and writes:
  land-listings-combined.csv
  land-listings-combined.json

Sources (siblings under real-estate/):
  ../colorado          (10+ acres, land)
  ../utah              (10+ acres, land)
  ../texas-triangle    (5+ acres, several property types)

Run from anywhere: python3 real-estate/land-listings-combined/build_combined.py
"""

import csv
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CO_DIR = os.path.join(ROOT, "colorado")
UT_DIR = os.path.join(ROOT, "utah")
TX_DIR = os.path.join(ROOT, "texas-triangle")

FIELDS = [
    "state",
    "snapshot_date",
    "dataset",
    "title",
    "price_usd",
    "acres",
    "price_per_acre",
    "county",
    "city",
    "zip",
    "broker",
    "pending",
    "list_date",
    "property_type",
    "lat",
    "lon",
    "location_precision",
    "zone",
    "distance_to_triangle_mi",
    "first_seen",
    "prev_price",
    "realtor_id",
    "url",
]

PRECISION = {
    "realtor": "parcel",
    "address": "address",
    "road": "street",
    "street": "street",
    "zip": "zip",
    "city": "city",
    "none": "none",
}


def blank_row(state, snapshot_date, dataset):
    return {f: None for f in FIELDS} | {
        "state": state,
        "snapshot_date": snapshot_date,
        "dataset": dataset,
    }


def per_acre(price, acres):
    if price is None or acres is None or acres <= 0:
        return None
    return round(price / acres, 2)


def date_only(value):
    if not value:
        return None
    return str(value).split(" ")[0]


def load_colorado():
    direct = os.path.join(CO_DIR, "colorado-land-over-10ac.json")
    if os.path.exists(direct):
        with open(direct) as fh:
            listings = json.load(fh)
    else:
        parts = sorted(glob.glob(os.path.join(CO_DIR, "colorado-land-over-10ac.json.part*")))
        if not parts:
            raise SystemExit("No Colorado JSON (full file or parts) found")
        merged = ""
        for part in parts:
            with open(part) as fh:
                merged += fh.read()
        listings = json.loads(merged)

    with open(os.path.join(CO_DIR, "colorado-land-geocodes.json")) as fh:
        geocodes = json.load(fh)

    rows = []
    for rec in listings:
        row = blank_row("CO", "2026-10-13", "colorado-land-listings")
        row.update(
            title=rec.get("title"),
            price_usd=rec.get("price_usd"),
            acres=rec.get("acres"),
            price_per_acre=per_acre(rec.get("price_usd"), rec.get("acres")),
            county=rec.get("county"),
            city=rec.get("city"),
            broker=rec.get("broker"),
            url=rec.get("url"),
        )
        geo = None
        if rec.get("url") and rec["url"] in geocodes:
            geo = geocodes[rec["url"]]
        elif rec.get("title") in geocodes:
            geo = geocodes[rec["title"]]
        if geo:
            row["lat"] = geo.get("lat")
            row["lon"] = geo.get("lon")
            row["location_precision"] = PRECISION.get(geo.get("kind"), geo.get("kind"))
        else:
            row["location_precision"] = "city" if rec.get("city") else "none"
        rows.append(row)
    return rows


def load_utah():
    with open(os.path.join(UT_DIR, "utah-land-over-10ac.json")) as fh:
        listings = json.load(fh)
    rows = []
    for rec in listings:
        row = blank_row("UT", "2026-10-16", "utah-land-listings")
        row.update(
            title=rec.get("title"),
            price_usd=rec.get("price"),
            acres=rec.get("acres"),
            price_per_acre=per_acre(rec.get("price"), rec.get("acres")),
            county=rec.get("county"),
            city=rec.get("city"),
            zip=rec.get("zip"),
            broker=rec.get("broker"),
            pending=rec.get("pending"),
            list_date=date_only(rec.get("list_date")),
            lat=rec.get("lat"),
            lon=rec.get("lon"),
            location_precision=PRECISION.get(rec.get("gk"), rec.get("gk")),
            url=rec.get("url"),
        )
        rows.append(row)
    return rows


def load_texas():
    with open(os.path.join(TX_DIR, "data", "listings.json")) as fh:
        payload = json.load(fh)
    rows = []
    for rec in payload["listings"]:
        row = blank_row("TX", payload.get("snapshot"), "texas-triangle-land")
        row.update(
            title=rec.get("title"),
            price_usd=rec.get("price"),
            acres=rec.get("acres"),
            price_per_acre=per_acre(rec.get("price"), rec.get("acres")),
            county=rec.get("county"),
            city=rec.get("city"),
            list_date=date_only(rec.get("list_date")),
            property_type=rec.get("type"),
            lat=rec.get("lat"),
            lon=rec.get("lon"),
            location_precision=PRECISION.get(rec.get("loc"), rec.get("loc")),
            zone=rec.get("zone"),
            distance_to_triangle_mi=rec.get("dist_tri_mi"),
            first_seen=rec.get("first_seen"),
            prev_price=rec.get("prev_price"),
            realtor_id=rec.get("id"),
            url=rec.get("url"),
        )
        rows.append(row)
    return rows


def main():
    rows = load_colorado() + load_texas() + load_utah()

    csv_path = os.path.join(HERE, "land-listings-combined.csv")
    json_path = os.path.join(HERE, "land-listings-combined.json")

    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    with open(json_path, "w") as fh:
        json.dump(rows, fh, indent=1)

    counts = {}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    print(f"wrote {len(rows)} listings: " + ", ".join(f"{k} {v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
