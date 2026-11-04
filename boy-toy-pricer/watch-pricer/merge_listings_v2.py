#!/usr/bin/env python3
"""Merge every source's 5711 CSV into one list, one row per watch (v2).

Watches have no VIN, so the car scanner's VIN merge becomes:

1. Same source + same listing id (or link): the same listing, kept once.
2. Same serial / stock number on two sources (when a site shows one): same watch.
3. Otherwise a row from one source joins a watch from a *different* source when
   the variant matches, the price is within PRICE_GAP (2%), the year does not
   conflict (equal, or missing on one side) and box/papers does not conflict.
   If more than one watch matches, the row stays its own watch.

Chrono24 is the primary source: its rows are placed first, so a dealer's own
site listing folds into the Chrono24 row for the same watch and the dealer
price shows on that row's per-source chips. Two Chrono24 listings never merge
with each other (a dealer can have two of the same reference).

Usage:
    python3 merge_listings_v2.py out.csv chrono24.csv bobs.csv ...
"""
import csv
import json
import sys

from watch_common_v2 import FIELDS, price_int

PRICE_GAP = 0.02
PRIMARY = "chrono24"
SOLD = ("Sold", "Sold (auction)", "Sold / out of stock")


def _source_entry(row):
    return {
        "site_code": row.get("site_code") or "",
        "price": row.get("price") or "",
        "status": row.get("status") or "",
        "seller": row.get("seller") or "",
        "link": row.get("link") or "",
        "listing_id": row.get("listing_id") or "",
    }


def _close(a, b):
    a, b = price_int(a), price_int(b)
    return a is not None and b is not None and abs(a - b) <= PRICE_GAP * max(a, b)


def _compatible(row, group):
    head = group[0]
    if row.get("variant") != head.get("variant") or not row.get("variant"):
        return False
    if row.get("site_code") in {g.get("site_code") for g in group}:
        return False
    if (row.get("status") in SOLD) != (head.get("status") in SOLD):
        return False
    y1, y2 = row.get("year"), next((g.get("year") for g in group if g.get("year")), "")
    if y1 and y2 and y1 != y2:
        return False
    b1, b2 = row.get("box_papers"), head.get("box_papers")
    if b1 and b2 and ("Watch only" in (b1, b2)) and b1 != b2:
        return False
    # Chrono24 names the dealer, and a dealer's own listing shows up there under
    # its own name. A price match with a different seller is a coincidence.
    if any(g.get("site_code") == PRIMARY and g.get("seller") for g in group) and not _same_seller(row, group):
        return False
    return any(_close(row.get("price"), g.get("price")) for g in group)


# Words that say nothing about who the seller is ("Grailzee (private seller)"
# vs "Chrono24 Private Office UK" must not count as the same seller).
GENERIC_SELLER_WORDS = {
    "the", "watches", "watch", "co", "company", "inc", "llc", "and", "ltd", "limited", "gmbh", "sa",
    "srl", "private", "seller", "pro", "office", "uk", "us", "usa", "group", "trading", "trade",
    "international", "luxury", "time", "timepieces", "grailzee", "chrono24", "dealer", "store", "shop",
    "hk", "hong", "kong", "new", "york", "london", "of", "de", "&",
}


def _norm_seller(name):
    words = "".join(c if c.isalnum() else " " for c in str(name or "").lower()).split()
    return {w for w in words if w not in GENERIC_SELLER_WORDS}


def _same_seller(row, group):
    a = _norm_seller(row.get("seller"))
    return bool(a) and any(a & _norm_seller(g.get("seller")) for g in group)


def _merge(group):
    def cost(r):
        p = price_int(r.get("price"))
        return (p is None, p or 0)
    primary = next((g for g in group if g.get("site_code") == PRIMARY), group[0])
    out = dict(primary)
    for field in ("year", "box_papers", "condition", "dial", "seller", "location", "image_url", "serial"):
        if not str(out.get(field) or "").strip():
            for g in group:
                if str(g.get(field) or "").strip():
                    out[field] = g[field]
                    break
    # Longest reference wins (5711/1A-010 over 5711/1A).
    out["reference"] = max((g.get("reference") or "" for g in group), key=len)
    cheapest = min(group, key=cost)
    out["price"] = cheapest.get("price") or ""
    sources = sorted((_source_entry(g) for g in group), key=lambda s: (price_int(s["price"]) is None, price_int(s["price"]) or 0))
    out["site_code"] = ",".join(dict.fromkeys(s["site_code"] for s in sources))
    out["sources"] = json.dumps(sources, ensure_ascii=False)
    return out


def merge_rows(rows):
    seen, unique = set(), []
    for row in rows:
        key = (row.get("site_code"), (row.get("listing_id") or "").strip() or (row.get("link") or "").strip())
        if key in seen:
            continue
        seen.add(key)
        unique.append(dict(row))
    unique.sort(key=lambda r: 0 if r.get("site_code") == PRIMARY else 1)  # stable

    groups, by_serial = [], {}
    for row in unique:
        serial = (row.get("serial") or "").strip().upper()
        if serial and serial in by_serial:
            groups[by_serial[serial]].append(row)
            continue
        hits = [i for i, g in enumerate(groups) if row.get("site_code") != PRIMARY and _compatible(row, g)]
        if len(hits) > 1:
            # Tie-break: the dealer's own name on the Chrono24 listing.
            same = [i for i in hits if _same_seller(row, groups[i])]
            hits = same if len(same) == 1 else hits
        if len(hits) == 1:
            groups[hits[0]].append(row)
        else:
            groups.append([row])
            if serial:
                by_serial[serial] = len(groups) - 1
    merged = []
    for g in groups:
        if len(g) == 1:
            r = g[0]
            r["sources"] = json.dumps([_source_entry(r)], ensure_ascii=False)
            merged.append(r)
        else:
            merged.append(_merge(g))
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
    merged = merge_rows(rows)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(merged)
    multi = sum(1 for r in merged if "," in (r.get("site_code") or ""))
    print(f"[done] {len(rows)} rows from {len(parts)} files -> {len(merged)} watches "
          f"({multi} seen on more than one site) in {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
