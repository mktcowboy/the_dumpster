#!/usr/bin/env python3
"""Merge per-source SR22 listings into one row per airplane.

The same airplane is often listed on more than one site, at different prices.
Rows that share an N-number collapse to one airplane. The asking price kept
for the report is the lowest USD ask, and every site's price is stored on the
row. Rows with no N-number fall back to the serial number (c/n). Two different
N-numbers never merge. A row with neither identifier stays its own row.

Usage:
    python3 merge_listings.py out.csv part1.csv part2.csv ...
"""
import csv
import json
import sys

from listings import (
    FIELDS,
    apply_listing,
    blank_row,
    clean_registration,
    format_usd,
    price_number,
    row_key,
    serial_key,
)


def _source_entry(row):
    return {
        "source": row.get("source") or "",
        "price": row.get("price") or "",
        "link": row.get("link") or "",
        "listing_id": row.get("listing_id") or "",
    }


def iter_sources(row):
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
    sources, seen = [], set()
    for row in rows:
        for source in iter_sources(row):
            key = (
                source.get("source") or "",
                source.get("listing_id") or source.get("link") or "",
            )
            if key in seen:
                continue
            seen.add(key)
            sources.append(source)

    def cost(pair):
        index, row = pair
        price = price_number(row.get("price"))
        return (price is None, price or 0, index)

    primary = min(enumerate(rows), key=cost)[1]
    out = blank_row()
    out.update(primary)
    registration = ""
    for row in rows:
        registration = clean_registration(row.get("n_number"))
        if registration:
            break
    out["n_number"] = registration
    if price_number(primary.get("price")) is None:
        priced = [row for row in rows if price_number(row.get("price")) is not None]
        if priced:
            primary = min(priced, key=lambda row: price_number(row.get("price")))
    out["price"] = primary.get("price") or ""
    out["link"] = primary.get("link") or out.get("link") or ""
    out["listing_id"] = primary.get("listing_id") or ""
    out["source"] = primary.get("source") or ""

    for field in FIELDS:
        if field in {"sources", "price", "link", "listing_id", "source", "n_number"}:
            continue
        if not str(out.get(field) or "").strip():
            for row in rows:
                if str(row.get(field) or "").strip():
                    out[field] = row[field]
                    break
    # A turbo or more specific model stated by any source is kept.
    for row in rows:
        if row.get("model") in {"SR22T", "SR22 TN"} and out.get("model") == "SR22":
            out["model"] = row["model"]
        if row.get("model") in {"PA-28-180", "PA-28-181"} and out.get("model") not in {"PA-28-180", "PA-28-181"}:
            stated = out.get("model") or ""
            out["model"] = row["model"]
            if stated and not (out.get("variant") or ""):
                out["variant"] = stated
        current_serial = out.get("serial_number") or ""
        other_serial = row.get("serial_number") or ""
        if other_serial.startswith(current_serial) and len(other_serial) > len(current_serial):
            out["serial_number"] = other_serial
        if row.get("turbo") == "yes":
            out["turbo"] = "yes"
        if row.get("generation", "").endswith("+") and out.get("generation") == row["generation"].rstrip("+"):
            out["generation"] = row["generation"]
        if row.get("fiki") == "yes":
            out["fiki"] = "yes"
        elif row.get("fiki") == "no" and not out.get("fiki"):
            out["fiki"] = "no"
    descriptions = [row.get("description") or "" for row in rows]
    out["description"] = max(descriptions, key=len)
    sources.sort(key=lambda source: (price_number(source.get("price")) is None, price_number(source.get("price")) or 0))
    names = []
    for source in sources:
        name = source.get("source") or ""
        if name and name not in names:
            names.append(name)
    if names:
        out["source"] = ",".join(names)
    out["sources"] = json.dumps(sources, ensure_ascii=False)
    return out


def merge_rows(rows):
    """Return one row per airplane.

    N-number decides first. A row with no N-number joins the single airplane
    whose serial matches, or groups with other serial-only rows for that
    airframe. With no identifier it stays its own row.
    """
    groups = {}
    order = []
    serial_index = {}
    pending_serial = []
    loose = []

    for row in rows:
        item = dict(row)
        item["n_number"] = clean_registration(item.get("n_number"))
        registration = item["n_number"]
        if registration:
            key = "n:" + registration
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(item)
            serial = serial_key(item.get("serial_number"))
            if serial:
                serial_index.setdefault(serial, set()).add(key)
            continue
        serial = serial_key(item.get("serial_number"))
        if serial:
            pending_serial.append((serial, item))
            continue
        loose.append(item)

    for serial, item in pending_serial:
        hits = serial_index.get(serial) or set()
        if len(hits) == 1:
            groups[next(iter(hits))].append(item)
            continue
        key = "s:" + serial
        if key not in groups:
            groups[key] = []
            order.append(key)
            serial_index.setdefault(serial, set()).add(key)
        groups[key].append(item)

    for item in loose:
        key = "id:" + (item.get("listing_id") or item.get("link") or str(len(order)))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)

    merged = []
    for key in order:
        members = groups.get(key) or []
        if not members:
            continue
        if len(members) == 1 and not clean_registration(members[0].get("n_number")) and not serial_key(members[0].get("serial_number")):
            value = members[0]
            value["sources"] = json.dumps(list(iter_sources(value)), ensure_ascii=False)
            merged.append(value)
        else:
            merged.append(_merge_group(members))
    return merged


def annotate_changes(rows, previous):
    """Mark airplanes that are new, or cheaper, since the previous snapshot.

    The first snapshot has no previous rows, so nothing is marked new.
    """
    prior = {}
    for row in previous or []:
        key = row_key(row)
        if key:
            prior[key] = row
    have_prior = bool(prior)
    for row in rows:
        key = row_key(row)
        old = prior.get(key) if have_prior and key else None
        row["is_new"] = "yes" if have_prior and key and old is None else ""
        row["prior_price"] = ""
        row["observed_drop"] = ""
        if not old:
            continue
        old_price = price_number(old.get("price"))
        new_price = price_number(row.get("price"))
        if old_price is not None and new_price is not None and new_price < old_price:
            row["prior_price"] = old.get("price") or ""
            row["observed_drop"] = format_usd(old_price - new_price)
    return rows


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    out, parts = sys.argv[1], sys.argv[2:]
    rows = []
    for path in parts:
        with open(path, newline="", encoding="utf-8") as handle:
            rows.extend(apply_listing(row) for row in csv.DictReader(handle))
    merged = merge_rows(rows)
    with open(out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)
    with_n = sum(1 for row in merged if row.get("n_number"))
    print(
        f"[done] merged {len(parts)} files, {len(rows)} rows -> {len(merged)} airplanes "
        f"({with_n} with an N-number) in {out}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
