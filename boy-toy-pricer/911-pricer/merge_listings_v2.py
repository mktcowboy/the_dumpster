#!/usr/bin/env python3
"""Merge v2 AutoTempest and Autotrader CSVs into one (v2).

Collapses rows that share a VIN.

The same car is often listed on more than one site, at different prices.
Rows that carry a VIN collapse to one car: the asking price kept for the
report is the lowest, and every site's price is stored on the row. Rows
with no VIN fall back to the old listing-id (then link) dedupe, then join
the one car with the same model year, mileage and city at a price within 3%.

Usage:
    python3 merge_listings_v2.py out.csv part1.csv part2.csv ...
"""
import csv
import json
import re
import sys

# 17-character VIN, excluding I, O and Q, which the standard never uses.
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
PRICE_RE = re.compile(r"[\d,]+")
EXTRA_RE = re.compile(r"\+(\d+)")
YEAR_RE = re.compile(r"\b(?:19|20)\d\d\b")
DEAL_RANK = {"": 0, "fair": 1, "good": 2, "great": 3}
# A row with no VIN joins a car only when the asking prices are this close.
NO_VIN_PRICE_GAP = 0.03

FIELDS = [
    "listing_id", "site_code", "title", "price", "price_with_fees", "deal_rating", "is_hot",
    "mileage", "posted_date", "city", "distance", "dealer", "description",
    "extra_sites", "link", "image_url", "msrp", "msrp_source", "vin", "sources",
]


def clean_vin(value):
    vin = re.sub(r"\s+", "", str(value or "")).upper()
    return vin if VIN_RE.match(vin) else ""


def price_value(value):
    match = PRICE_RE.search(str(value or ""))
    return int(match.group(0).replace(",", "")) if match else None


def car_key(row):
    """Model year, mileage and city of a listing, or None when one is missing."""
    year = YEAR_RE.search(str(row.get("title") or ""))
    miles = price_value(row.get("mileage"))  # same digit parse as a price
    city = str(row.get("city") or "").split(",")[0].strip().lower()
    if not year or miles is None or not city:
        return None
    return year.group(0), miles, city


def _close_price(a, b):
    a, b = price_value(a), price_value(b)
    return a is not None and b is not None and abs(a - b) <= NO_VIN_PRICE_GAP * max(a, b)


def _truthy(value):
    return value is True or str(value).strip().lower() == "true"


def _extra_count(value):
    match = EXTRA_RE.search(str(value or ""))
    return int(match.group(1)) if match else 0


def _source_entry(row):
    entry = {
        "site_code": row.get("site_code") or "",
        "price": row.get("price") or "",
        "link": row.get("link") or "",
        "listing_id": row.get("listing_id") or "",
    }
    if row.get("price_with_fees"):
        entry["price_with_fees"] = row["price_with_fees"]
    return entry


def iter_sources(row):
    """Sources already merged onto a row, or this row itself."""
    raw = row.get("sources") or ""
    if raw:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = None
        if isinstance(data, list) and data:
            for item in data:
                if isinstance(item, dict):
                    yield item
            return
    yield _source_entry(row)


def _merge_group(rows):
    """Collapse every listing of one VIN into a single row."""
    sources, seen = [], set()
    for row in rows:
        for source in iter_sources(row):
            key = (source.get("site_code") or "", source.get("listing_id") or source.get("link") or "")
            if key in seen:
                continue
            seen.add(key)
            sources.append(source)

    def cost(pair):
        index, row = pair
        price = price_value(row.get("price"))
        return (price is None, price or 0, index)

    primary = min(enumerate(rows), key=cost)[1]
    out = dict(primary)
    # The cheapest listing may be one with no VIN that joined this car.
    out["vin"] = clean_vin(primary.get("vin")) or next((v for v in (clean_vin(r.get("vin")) for r in rows) if v), "")
    if price_value(primary.get("price")) is None:
        priced = [r for r in rows if price_value(r.get("price")) is not None]
        if priced:
            primary = min(priced, key=lambda r: price_value(r.get("price")))
            out["price"] = primary.get("price") or ""
            out["link"] = primary.get("link") or out.get("link") or ""
            out["listing_id"] = primary.get("listing_id") or out.get("listing_id") or ""
    else:
        out["price"] = primary.get("price") or ""
        out["link"] = primary.get("link") or ""
        out["listing_id"] = primary.get("listing_id") or ""

    for field in ("mileage", "city", "dealer", "posted_date", "distance", "image_url", "title", "msrp", "msrp_source", "price_with_fees"):
        if not str(out.get(field) or "").strip():
            for row in rows:
                if str(row.get(field) or "").strip():
                    out[field] = row[field]
                    break
    out["description"] = max((r.get("description") or "" for r in rows), key=len)
    out["deal_rating"] = max((r.get("deal_rating") or "" for r in rows), key=lambda d: DEAL_RANK.get(d, 0))
    out["is_hot"] = any(_truthy(r.get("is_hot")) for r in rows)
    extra = max(rows, key=lambda r: _extra_count(r.get("extra_sites")))
    out["extra_sites"] = extra.get("extra_sites") or ""

    # Cheapest source first, so the price column and the first chip agree.
    sources.sort(key=lambda s: (price_value(s.get("price")) is None, price_value(s.get("price")) or 0))
    codes = []
    for source in sources:
        code = source.get("site_code") or ""
        if code and code not in codes:
            codes.append(code)
    if codes:
        out["site_code"] = ",".join(codes)
    out["sources"] = json.dumps(sources, ensure_ascii=False)
    return out


def merge_rows(rows):
    """Return one row per car.

    VIN decides first: rows that share one are the same car, and two different
    VINs never merge. A row with no VIN is deduped by listing id (then link),
    then joins the car whose year, mileage and city match and whose price is
    within NO_VIN_PRICE_GAP. With no match, or more than one car matching, it
    stays its own car.
    """
    groups = {}
    order = []
    pending = []
    seen_ids = set()
    for row in rows:
        vin = clean_vin(row.get("vin"))
        if vin:
            row = dict(row)
            row["vin"] = vin
            if vin not in groups:
                groups[vin] = []
                order.append(vin)
            groups[vin].append(row)
            continue
        key = (row.get("listing_id") or "").strip() or (row.get("link") or "").strip()
        if key:
            if key in seen_ids:
                continue
            seen_ids.add(key)
        slot = ("row", len(order))
        order.append(slot)
        pending.append((slot, dict(row)))

    # VIN cars are all known before any row without one looks for its match,
    # so input order does not decide whether a row finds its car.
    by_key = {}
    for gid, members in groups.items():
        for member in members:
            key = car_key(member)
            if key:
                by_key.setdefault(key, []).append((gid, member))
    for slot, row in pending:
        key = car_key(row)
        hits = {gid for gid, other in by_key.get(key, ())
                if _close_price(row.get("price"), other.get("price"))} if key else set()
        if len(hits) == 1:
            groups[hits.pop()].append(row)
            continue
        groups[slot] = [row]
        if key:
            by_key.setdefault(key, []).append((slot, row))

    merged = []
    for gid in order:
        members = groups.get(gid)
        if not members:
            continue  # a row with no VIN that joined another car
        if len(members) > 1 or clean_vin(members[0].get("vin")):
            merged.append(_merge_group(members))
        else:
            value = members[0]
            value["sources"] = json.dumps(list(iter_sources(value)), ensure_ascii=False)
            value["vin"] = ""
            merged.append(value)
    return merged


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    out, parts = sys.argv[1], sys.argv[2:]
    rows = []
    for path in parts:
        with open(path, newline="", encoding="utf-8") as f:
            rows.extend(csv.DictReader(f))
    before = len(rows)
    merged = merge_rows(rows)
    with_vin = sum(1 for r in merged if r.get("vin"))
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)
    print(f"[done] merged {len(parts)} files, {before} rows -> {len(merged)} cars "
          f"({with_vin} with a VIN) in {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
