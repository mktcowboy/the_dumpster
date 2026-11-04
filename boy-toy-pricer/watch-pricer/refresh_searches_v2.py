#!/usr/bin/env python3
"""Refresh the saved Patek searches (Nautilus 5711, blue/green Aquanaut) and rebuild the report (v2).

Same flow as Cars_autotempest_scan/refresh_searches_v2.py:
  SEARCHES config -> scrape each source -> saved/<slug>/<source>.csv
  -> merge/dedupe -> merged.csv + meta.json (freshness window) -> one HTML report.

Chrono24 is the primary source. Every other source is tried each run; one that
fails or blocks the scraper keeps its last good file and gets a warning in
meta.json instead of failing the run. Each run also appends price stats to
saved/<slug>/price_history.csv so week-over-week changes show in the report.

    python3 refresh_searches_v2.py              # skip if saved data is still fresh
    python3 refresh_searches_v2.py --force      # scrape again
    python3 refresh_searches_v2.py --only chrono24,bobs --force
"""
import argparse
import statistics
import sys
import tempfile
from pathlib import Path

from dealer_scrapers_v2 import SOURCES, Browser, run_source
from merge_listings_v2 import merge_rows
from saved_store_v2 import (append_csv, format_as_of, is_fresh, load_meta, read_csv, save_meta,
                            search_dir, source_path, stamp, utc_now, write_csv)
from saved_store_v2 import fresh_days as resolve_fresh_days
from models_v2 import MODELS
from watch_common_v2 import FIELDS, ScrapeError, price_int, session

HERE = Path(__file__).resolve().parent
REPORT = HERE / "output" / "report.html"

SEARCHES = [
    {
        "slug": "patek5711",
        "title": "Patek Philippe Nautilus 5711",
        "model": "5711",
        # Order matters: Chrono24 first (primary), then dealers, then the
        # sites that blocked or had no 5711s when this was built. Those are
        # still tried every week so the report says if one starts working.
        "sources": [
            "chrono24", "bobs", "the1916", "swe", "davidsw", "analogshift", "hodinkee",
            "watchfinder", "jomashop", "grailzee",
            "ebay", "watchcharts", "crown", "bezel", "wristcheck", "luxurybazaar", "europeanwatch",
        ],
    },
    {
        "slug": "aquanaut_bluegreen",
        "title": "Patek Philippe Aquanaut, blue and green dials",
        "model": "aquanaut",
        "sources": [
            "chrono24", "bobs", "the1916", "swe", "davidsw", "analogshift", "hodinkee",
            "watchfinder", "jomashop", "grailzee",
            "ebay", "watchcharts", "crown", "bezel", "wristcheck", "luxurybazaar", "europeanwatch",
        ],
    },
]

LABELS = {"chrono24": "Chrono24", **{k: v[0] for k, v in SOURCES.items()}}
ASKING = ("For sale", "Auction live", "Buy-now (auction ended unsold)")
HISTORY_FIELDS = ["run_at", "variant", "source", "count", "low", "median", "high"]


def searches(slug=None):
    return [s for s in SEARCHES if not slug or s["slug"] == slug]


def _log(message):
    print(message, flush=True)


def price_stats(rows):
    prices = sorted(p for p in (price_int(r.get("price")) for r in rows
                                if r.get("status", "For sale") in ASKING) if p)
    if not prices:
        return None
    return {"count": len(prices), "low": prices[0], "median": int(statistics.median(prices)), "high": prices[-1]}


def history_rows(when, merged, per_source, model="5711"):
    M = MODELS[model]
    out = []
    for variant in sorted({r.get("variant") for r in merged if r.get("variant")}, key=M.variant_key):
        rows = [r for r in merged if r.get("variant") == variant]
        st = price_stats(rows)
        if st:
            out.append({"run_at": when, "variant": variant, "source": "all (merged)", **st})
        for name, srows in per_source.items():
            st = price_stats([r for r in srows if r.get("variant") == variant])
            if st:
                out.append({"run_at": when, "variant": variant, "source": name, **st})
    return out


def _scrape_one(name, dest, slug, root, browser_box, sess, model="5711"):
    if name == "chrono24":
        from chrono24_scraper_v2 import scrape
        info = scrape(dest, cache_path=search_dir(slug, root) / "chrono24_details.json", model=model)
        return read_csv(dest), info
    kind = SOURCES[name][1]
    browser = None
    if kind == "browser":
        if browser_box.get("b") is None:
            browser_box["b"] = Browser().__enter__()
        browser = browser_box["b"]
    rows = run_source(name, dest, browser=browser, sess=sess, model=model)
    return rows, {}


def refresh_search(search, *, force=False, fresh_days=None, now=None, root=None, only=None):
    days = resolve_fresh_days(fresh_days, root)
    moment = utc_now(now)
    slug, title = search["slug"], search["title"]
    folder = search_dir(slug, root)
    folder.mkdir(parents=True, exist_ok=True)
    meta = load_meta(slug, root) or {}
    merged_path = source_path(slug, "merged", root)
    previous_stamp = meta.get("scraped_at") or ""

    if not force and is_fresh(meta, days, moment, merged_path.exists()):
        _log(f"[skip] {title}: saved data as of {previous_stamp} is within {days:g} days")
        return {"slug": slug, "ok": True, "skipped": True, "changed": False}

    when = stamp(moment)
    warnings, sources = [], dict(meta.get("sources") or {})
    new_source = False
    sess = session()
    browser_box = {}
    _log(f"[{moment.strftime('%Y-%m-%d %H:%M:%S')}] scraping: {title}")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for name in search["sources"]:
                if only and name not in only:
                    continue
                label = LABELS.get(name, name)
                dest = Path(tmp) / f"{name}.csv"
                prev = dict(sources.get(name) or {})
                try:
                    rows, info = _scrape_one(name, dest, slug, root, browser_box, sess, search.get("model", "5711"))
                    dest.replace(source_path(slug, name, root)) if dest.exists() else None
                    note = "" if rows else f"{label} answered but listed no {MODELS[search.get('model', '5711')].noun}"
                    sources[name] = {"label": label, "scraped_at": when, "ok": True, "rows": len(rows),
                                     "warning": note, **({"detail": info} if info else {})}
                    new_source = True
                    _log(f"[ok] {label}: {len(rows)} rows" + (f" ({note})" if note else ""))
                except (ScrapeError, OSError, RuntimeError) as exc:
                    saved = source_path(slug, name, root)
                    keep = saved.exists() and bool(read_csv(saved))
                    msg = f"{label} failed ({exc})" + ("; showing saved rows from " + prev.get("scraped_at", "") if keep else "")
                    warnings.append(msg)
                    sources[name] = {**prev, "label": label, "ok": False, "warning": str(exc),
                                     "last_attempt_at": when}
                    _log(f"[warn] {msg}")
                except Exception as exc:  # a parser bug in one source must not stop the others
                    warnings.append(f"{label} crashed ({type(exc).__name__}: {exc})")
                    sources[name] = {**prev, "label": label, "ok": False,
                                     "warning": f"{type(exc).__name__}: {exc}", "last_attempt_at": when}
                    _log(f"[warn] {label} crashed: {exc!r}")
    finally:
        if browser_box.get("b") is not None:
            browser_box["b"].__exit__(None, None, None)

    per_source, parts = {}, []
    for name in search["sources"]:
        path = source_path(slug, name, root)
        if path.exists():
            rows = read_csv(path)
            per_source[name] = rows
            parts.extend(rows)
    if not parts:
        warnings.append("No rows from any source to merge")
        meta.update(slug=slug, title=title, warnings=warnings, last_attempt_at=when, sources=sources)
        save_meta(slug, meta, root)
        return {"slug": slug, "ok": False, "skipped": False, "changed": True}
    merged = merge_rows(parts)
    write_csv(merged_path, merged, FIELDS)
    scraped_at = when if new_source else previous_stamp
    if new_source:
        append_csv(folder / "price_history.csv", history_rows(when, merged, per_source, search.get("model", "5711")), HISTORY_FIELDS)
    meta = {"slug": slug, "title": title, "model": search.get("model", "5711"), "scraped_at": scraped_at, "data_as_of": format_as_of(scraped_at),
            "warnings": warnings, "last_attempt_at": when, "merged_rows": len(merged), "sources": sources}
    save_meta(slug, meta, root)
    _log(f"[done] {title}: {len(parts)} rows -> {len(merged)} watches, data as of {format_as_of(scraped_at)}")
    return {"slug": slug, "ok": True, "skipped": False, "changed": True}


def write_report(output=None, root=None):
    from generate_report_v2 import build
    output = Path(output or REPORT)
    output.parent.mkdir(parents=True, exist_ok=True)
    build([s["slug"] for s in SEARCHES], output, root=root)
    _log(f"[report] {output}")
    return output


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--fresh-days", default=None)
    ap.add_argument("--slug", default="")
    ap.add_argument("--only", default="", help="comma list of sources to scrape this run")
    ap.add_argument("--no-report", action="store_true")
    a = ap.parse_args(argv)
    only = set(x.strip() for x in a.only.split(",") if x.strip()) or None
    results = [refresh_search(s, force=a.force, fresh_days=a.fresh_days, only=only) for s in searches(a.slug or None)]
    if not a.no_report and (any(r.get("changed") for r in results) or not REPORT.exists()):
        write_report()
    return 0 if any(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
