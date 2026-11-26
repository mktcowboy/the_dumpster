#!/usr/bin/env python3
"""Build a dedicated CubCrafters aircraft pricer HTML report from saved/cubcrafters/.

Applies the airplane-pricer template and model-aware OLS pricing engine to every
CubCrafters aircraft on the market, organized into tailwheel-first and per-line tabs:
  - All Tailwheel (default tab; excludes NXCub nosewheel)
  - All CubCrafters (tailwheel + nosewheel)
  - Carbon Cub SS
  - Carbon Cub FX / EX (FX-3, EX-3, FX-2, EX-2, EX, FX, UL)
  - XCub
  - Sport & Top Cub
  - NXCub (Nosewheel)
  - README
"""
import argparse
import re
import sys
from pathlib import Path

from generate_report import render_tabs
from listings import FIELDS
from merge_listings import annotate_changes, merge_rows
from saved_store import (
    HERE,
    fresh_days as resolve_fresh_days,
    load_meta,
    read_csv,
    source_path,
    write_csv,
)

DEFAULT_OUTPUT = HERE / "output" / "cubcrafters.html"
SOURCE_KEYS = (
    "cubcrafters",
    "aso",
    "globalair",
    "aircraftdealer",
    "barnstormers",
    "controller",
    "tradeaplane",
    "aircraftcom",
    "aerotrader",
    "ebay",
)


def is_nosewheel(row):
    """True when the listing is an NXCub or explicitly states nosewheel/tricycle gear."""
    if (row.get("model") or "").strip() == "NXCub":
        return True
    stated = " ".join(str(row.get(k) or "") for k in ("model", "variant", "title"))
    return bool(re.search(r"\bnx-?\s*cub\b|\bnose\s*wheel\b|\btricycle\b", stated, re.I))


def is_tailwheel(row):
    return not is_nosewheel(row)


def is_carbon_ss(row):
    if (row.get("model") or "") != "Carbon Cub":
        return False
    variant = (row.get("variant") or "").upper()
    if variant == "SS":
        return True
    if not variant and re.search(r"\bCC11-160\b|\bSS\b", (row.get("title") or "") + " " + (row.get("description") or "")):
        return True
    return False


def is_carbon_fx_ex(row):
    if (row.get("model") or "") != "Carbon Cub":
        return False
    variant = (row.get("variant") or "").upper()
    return variant in {"FX-3", "FX-2", "FX", "EX-3", "EX-2", "EX", "UL"}


def remerge_saved(root=None):
    """Re-merge saved/cubcrafters per-source CSVs with current merge rules."""
    parts = []
    for key in SOURCE_KEYS:
        path = source_path("cubcrafters", key, root)
        if path.exists():
            parts.extend(read_csv(path))
    if not parts:
        merged_path = source_path("cubcrafters", "merged", root)
        return read_csv(merged_path) if merged_path.exists() else []
    merged_path = source_path("cubcrafters", "merged", root)
    previous = read_csv(merged_path) if merged_path.exists() else []
    merged = annotate_changes(merge_rows(parts), previous)
    # Preserve prior new/drop flags when re-merging the same snapshot
    by_id = {r.get("listing_id"): r for r in previous}
    for row in merged:
        old = by_id.get(row.get("listing_id"))
        if old:
            row["is_new"] = old.get("is_new") or ""
            row["prior_price"] = old.get("prior_price") or ""
            row["observed_drop"] = old.get("observed_drop") or ""
    write_csv(merged_path, merged, FIELDS)
    return merged


def cubcrafters_tabs(rows, meta):
    """Build ordered (rows, meta) tab pairs for all CubCrafters models."""
    base = dict(meta or {})
    base_meta = {
        "scraped_at": base.get("scraped_at") or "",
        "warnings": list(base.get("warnings") or []),
    }
    specs = [
        ("cubcrafters-tailwheel", "All Tailwheel", [r for r in rows if is_tailwheel(r)]),
        ("cubcrafters", "All CubCrafters", list(rows)),
        ("carbon-cub-ss", "Carbon Cub SS", [r for r in rows if is_carbon_ss(r)]),
        ("carbon-cub-fx-ex", "Carbon Cub FX / EX", [r for r in rows if is_carbon_fx_ex(r)]),
        ("xcub", "XCub", [r for r in rows if (r.get("model") or "") == "XCub"]),
        (
            "sport-top-cub",
            "Sport & Top Cub",
            [r for r in rows if (r.get("model") or "") in {"Sport Cub", "Top Cub", "Ranger Cub"}],
        ),
        ("nxcub", "NXCub (Nosewheel)", [r for r in rows if is_nosewheel(r)]),
    ]
    tabs = []
    for slug, title, subset in specs:
        if not subset:
            continue
        tabs.append((subset, {**base_meta, "slug": slug, "title": title}))
    return tabs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--no-remerge", action="store_true")
    parser.add_argument("--root", default="")
    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else None
    rows = read_csv(source_path("cubcrafters", "merged", root)) if args.no_remerge else remerge_saved(root)
    if not rows:
        print("no saved CubCrafters listings — run refresh_searches.py --slug cubcrafters first", file=sys.stderr)
        return 1
    meta = load_meta("cubcrafters", root) or {"slug": "cubcrafters", "title": "CubCrafters"}
    tabs = cubcrafters_tabs(rows, meta)
    render_tabs(
        tabs,
        args.output,
        fresh_days=resolve_fresh_days(None, root),
        search_api="",
        page_title="CubCrafters Tracker",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
