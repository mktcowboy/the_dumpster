#!/usr/bin/env python3
"""Step 1: pull every for-sale listing on 5+ acres from Realtor.com, one county at a time.

All property types: land, farm/ranch, houses on acreage, mobile, multi-family, etc.
(condos/townhomes are dropped later in process.py; they report the shared complex lot).

Uses HomeHarvest (pip install homeharvest), which queries Realtor.com's own search API,
so every listing comes back with Realtor's coordinates, lot size, price and URL.

Writes one file per county to data/raw/<YYYY-MM-DD>/<County>.json.gz plus _meta.json.
Re-running on the same day skips counties already saved (resume after a failure);
use --force to re-pull them.

    python scrape.py                       # all counties in data/counties_target.json
    python scrape.py --counties Bexar Hays # just these
    python scrape.py --force               # re-pull today's counties
"""
import argparse, datetime, gzip, json, math, os, random, sys, time

from homeharvest import scrape_property

from privacy_filter import blocked

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTIES = os.path.join(HERE, "data", "counties_target.json")
RAW_DIR = os.path.join(HERE, "data", "raw")

MIN_LOT_SQFT = 217_800  # 5 acres
# Only property facts are kept; agent/office contact fields are dropped on purpose.
KEEP = ["property_id", "listing_id", "property_url", "status", "style", "formatted_address", "street",
        "city", "zip_code", "county", "list_price", "lot_sqft", "latitude", "longitude",
        "list_date", "days_on_mls", "mls"]


def clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    if hasattr(v, "item"):  # numpy scalar
        return v.item()
    return v


def pull(county, tries=4):
    for attempt in range(1, tries + 1):
        try:
            df = scrape_property(
                location=f"{county} County, TX",
                listing_type="for_sale",
                lot_sqft_min=MIN_LOT_SQFT,
                extra_property_data=False,
            )
            cols = [c for c in KEEP if c in df.columns]
            rows = [{c: clean(v) for c, v in row.items()} for row in df[cols].to_dict("records")]
            return [r for r in rows if not blocked(r)]
        except Exception as e:
            wait = 10 * attempt ** 2
            print(f"    attempt {attempt} failed: {type(e).__name__}: {e} -- waiting {wait}s",
                  flush=True)
            if attempt == tries:
                raise
            time.sleep(wait)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--counties", nargs="*", help="subset of county names (default: all)")
    ap.add_argument("--force", action="store_true", help="re-pull counties already saved today")
    ap.add_argument("--date", default=datetime.date.today().isoformat(),
                    help="snapshot folder name (default: today)")
    args = ap.parse_args()

    counties = json.load(open(COUNTIES))
    if args.counties:
        want = {c.lower() for c in args.counties}
        counties = [c for c in counties if c.lower() in want]
    out_dir = os.path.join(RAW_DIR, args.date)
    os.makedirs(out_dir, exist_ok=True)
    meta_path = os.path.join(out_dir, "_meta.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {"counties": {}}

    failed = []
    for i, county in enumerate(counties, 1):
        path = os.path.join(out_dir, f"{county}.json.gz")
        if os.path.exists(path) and not args.force:
            print(f"[{i}/{len(counties)}] {county}: already saved, skipping")
            continue
        print(f"[{i}/{len(counties)}] {county} ...", flush=True)
        try:
            rows = pull(county)
        except Exception:
            failed.append(county)
            meta["counties"][county] = {"error": True}
            continue
        with gzip.open(path, "wt") as f:
            json.dump(rows, f, separators=(",", ":"))
        meta["counties"][county] = {"rows": len(rows),
                                    "at": datetime.datetime.now().isoformat(timespec="seconds")}
        print(f"    {len(rows)} rows", flush=True)
        json.dump(meta, open(meta_path, "w"), indent=1)
        time.sleep(random.uniform(2, 5))  # be polite

    json.dump(meta, open(meta_path, "w"), indent=1)
    total = sum(v.get("rows", 0) for v in meta["counties"].values())
    print(f"snapshot {args.date}: {total} rows across {len(meta['counties'])} counties")
    if failed:
        print(f"FAILED ({len(failed)}): {', '.join(failed)} -- re-run to retry just these",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
