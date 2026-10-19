#!/usr/bin/env python3
"""
build.py — assemble the Colorado land-listings drop.

Reads every raw page-chunk JSON in raw/ (as scraped from Realtor.com),
normalizes fields, drops superseded partial captures, dedupes by detail URL,
and writes:
  colorado-land-over-10ac.csv
  colorado-land-over-10ac.json

Run: python3 build.py
"""

import csv
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(HERE, "raw")
FIELDS = ["title", "price_usd", "acres", "county", "city", "url", "broker"]

# Partial captures that were later fully re-captured. Records in these files
# whose title also appears in the corresponding full capture are dropped,
# because the full capture has complete fields (esp. the detail URL).
SUPERSEDED = {
    "realtor-page-49-partial.json": "realtor-pages-49-57.json",
    "realtor-page-62-partial.json": "realtor-pages-62-74.json",
}


def load_chunks():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "realtor-*.json")))
    chunks = {}
    for f in files:
        with open(f) as fh:
            chunks[os.path.basename(f)] = json.load(fh)
    return chunks


def normalize(rec):
    """Coerce types; keep nulls as None. Never invent values."""
    out = {}
    out["title"] = rec.get("title") or None
    p = rec.get("price_usd")
    out["price_usd"] = int(p) if p is not None else None
    a = rec.get("acres")
    out["acres"] = float(a) if a is not None else None
    out["county"] = rec.get("county")  # null on Realtor.com cards
    out["city"] = rec.get("city") or None
    out["url"] = rec.get("url") or None
    out["broker"] = rec.get("broker") or None
    return out


def main():
    chunks = load_chunks()
    per_file = {name: len(rows) for name, rows in chunks.items()}
    raw_total = sum(per_file.values())

    # Drop partial-file records superseded by a full re-capture (match by title).
    dropped_partial = 0
    for partial, full in SUPERSEDED.items():
        if partial not in chunks or full not in chunks:
            continue
        full_titles = {r.get("title") for r in chunks[full]}
        kept = []
        for r in chunks[partial]:
            if r.get("title") in full_titles:
                dropped_partial += 1
            else:
                kept.append(r)
        chunks[partial] = kept

    # Dedupe: primary key = detail URL; fallback (title, price_usd) when URL is null.
    seen = set()
    unique = []
    dupes = 0
    order = sorted(chunks.keys())
    for name in order:
        for r in chunks[name]:
            rec = normalize(r)
            key = ("url", rec["url"]) if rec["url"] else ("t", rec["title"], rec["price_usd"])
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            unique.append(rec)

    csv_path = os.path.join(HERE, "colorado-land-over-10ac.csv")
    json_path = os.path.join(HERE, "colorado-land-over-10ac.json")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for rec in unique:
            w.writerow(rec)
    with open(json_path, "w") as fh:
        json.dump(unique, fh, indent=1)

    # Audit report
    print("per-file record counts:")
    for name in order:
        print(f"  {name}: {per_file[name]}")
    print(f"raw records loaded: {raw_total}")
    print(f"superseded partial records dropped: {dropped_partial}")
    print(f"duplicate records removed: {dupes}")
    print(f"FINAL UNIQUE RECORDS: {len(unique)}")
    print("missing-field counts:")
    for f in FIELDS:
        n = sum(1 for r in unique if r[f] is None)
        print(f"  {f}: {n}")
    exact10 = sum(1 for r in unique if r["acres"] == 10)
    under10 = sum(1 for r in unique if r["acres"] is not None and r["acres"] < 10)
    no_acres = sum(1 for r in unique if r["acres"] is None)
    print(f"records at exactly 10.0 acres: {exact10}")
    print(f"records under 10 acres: {under10}")
    print(f"records with no acreage shown: {no_acres}")


if __name__ == "__main__":
    main()
