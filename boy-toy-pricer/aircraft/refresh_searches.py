#!/usr/bin/env python3
"""Refresh the SR22, Vision Jet, and CubCrafters searches, reusing saved listings while they are still fresh.

The weekly script, the local server, and a manual run all come through here.
A search whose saved snapshot is within the freshness window (default 2 days)
is left alone unless --force is set. A source that fails keeps its previous
file and is reported as a warning. An empty result from a source that already
had listings is treated as a failure so a broken parser cannot wipe the last
good snapshot.

Saved files live in saved/<slug>/ (sr22, sf50, and cubcrafters):
  cirrus.csv or cubcrafters.csv, aso.csv, globalair.csv, aircraftdealer.csv, barnstormers.csv,
  controller.csv, tradeaplane.csv, aircraftcom.csv, aerotrader.csv, ebay.csv,
  merged.csv, meta.json

Usage:
    python3 refresh_searches.py
    python3 refresh_searches.py --force
    python3 refresh_searches.py --slug sf50
    python3 refresh_searches.py --slug cubcrafters
    python3 refresh_searches.py --fresh-days 3
"""
import argparse
import sys
from pathlib import Path

from fetch import Fetcher, ScrapeError
from listings import FIELDS
from merge_listings import annotate_changes, merge_rows
from saved_store import (
    fresh_days as resolve_fresh_days,
    is_fresh,
    load_meta,
    read_csv,
    save_meta,
    search_dir,
    source_path,
    stamp,
    utc_now,
    write_csv,
)
from scrape_sources import sources_for

HERE = Path(__file__).resolve().parent
REPORT = HERE / "output" / "report.html"
SEARCHES = (
    {"slug": "sr22", "title": "Cirrus SR22", "families": ("sr22", "sr20")},
    {"slug": "sf50", "title": "Cirrus Vision Jet", "families": ("sf50",)},
    {"slug": "cubcrafters", "title": "CubCrafters", "families": ("cubcrafters",)},
    {"slug": "pa28-180-181", "title": "Piper PA-28-180/181", "families": ("pa28-180-181",)},
)
SLUG = SEARCHES[0]["slug"]
TITLE = SEARCHES[0]["title"]
# A source that previously saved at least this many rows is not replaced by
# an empty scrape. Fewer than this can legitimately be a small site.
EMPTY_GUARD = 5


def _log(message):
    print(message, flush=True)


def _source_state(meta, name):
    sources = meta.get("sources") if isinstance(meta.get("sources"), dict) else {}
    state = sources.get(name) if isinstance(sources.get(name), dict) else {}
    return dict(state)


def refresh_search(search=None, *, force=False, fresh_days=None, now=None, root=None, scrapers=None, fetch=None):
    """Refresh one search. Returns a status dict and writes saved/<slug>/.

    Scrapers are injectable so tests can avoid the network. A failure keeps
    that source's previous file. The default search is the SR22.
    """
    if search is None:
        search = SEARCHES[0]
    slug = search["slug"]
    title = search["title"]
    days = resolve_fresh_days(fresh_days, root)
    moment = utc_now(now)
    folder = search_dir(slug, root)
    folder.mkdir(parents=True, exist_ok=True)
    meta = load_meta(slug, root) or {}
    merged_path = source_path(slug, "merged", root)
    previous_warnings = list(meta.get("warnings") or [])
    previous_stamp = meta.get("scraped_at") or ""
    previous_merged = read_csv(merged_path) if merged_path.exists() else []

    if not force and is_fresh(meta, days, moment, merged_path.exists()):
        _log(f"[skip] {title}: saved data as of {previous_stamp} is within {days:g} days")
        return {
            "slug": slug,
            "title": title,
            "ok": True,
            "skipped": True,
            "changed": False,
            "scraped_at": previous_stamp,
            "warnings": previous_warnings,
        }

    specs = list(scrapers) if scrapers is not None else sources_for(search["families"])
    own_fetch = False
    if fetch is None and scrapers is None:
        fetch = Fetcher()
        fetch.__enter__()
        own_fetch = True
    when = stamp(moment)
    warnings = []
    sources = {name: _source_state(meta, name) for name, _label, _fn in specs}
    new_source = False
    _log(f"[{moment.strftime('%Y-%m-%d %H:%M:%S')}] scraping: {title}")
    try:
        for name, label, fn in specs:
            try:
                rows = fn(fetch)
                if not rows and len(read_csv(source_path(slug, name, root))) >= EMPTY_GUARD:
                    raise ScrapeError(f"{label} returned no listings")
                write_csv(source_path(slug, name, root), rows, FIELDS)
                sources[name] = {"scraped_at": when, "ok": True, "rows": len(rows), "warning": ""}
                new_source = True
                _log(f"[ok] {label}: {len(rows)} listings")
            except (ScrapeError, OSError) as exc:
                saved = source_path(slug, name, root)
                saved_when = sources[name].get("scraped_at") or ""
                if saved.exists() and read_csv(saved):
                    shown = f" from {saved_when}" if saved_when else ""
                    warnings.append(f"{label} failed ({exc}); showing saved {label} listings{shown}")
                else:
                    warnings.append(f"{label} failed ({exc}); no saved {label} listings")
                sources[name]["ok"] = False
                sources[name]["warning"] = str(exc)
                _log(f"[warn] {title}: {warnings[-1]}")
    finally:
        if own_fetch:
            fetch.close()

    parts = []
    for name, _label, _fn in specs:
        path = source_path(slug, name, root)
        if path.exists():
            parts.extend(read_csv(path))
    if not parts:
        meta = {
            **meta,
            "slug": slug,
            "title": title,
            "warnings": warnings,
            "last_attempt_at": when,
            "sources": sources,
        }
        save_meta(slug, meta, root)
        return {
            "slug": slug,
            "title": title,
            "ok": False,
            "skipped": False,
            "changed": warnings != previous_warnings,
            "scraped_at": previous_stamp,
            "warnings": warnings,
        }

    merged_rows = annotate_changes(merge_rows(parts), previous_merged)
    write_csv(merged_path, merged_rows, FIELDS)
    sources["merged"] = {
        "scraped_at": when if new_source else (sources.get("merged", {}).get("scraped_at") or previous_stamp),
        "ok": True,
        "rows": len(merged_rows),
        "warning": "",
    }
    scraped_at = when if new_source else previous_stamp
    meta = {
        "slug": slug,
        "title": title,
        "scraped_at": scraped_at,
        "warnings": warnings,
        "last_attempt_at": when,
        "sources": sources,
    }
    save_meta(slug, meta, root)
    _log(f"[done] {title}: {len(merged_rows)} airplanes, data as of {scraped_at}")
    return {
        "slug": slug,
        "title": title,
        "ok": True,
        "skipped": False,
        "changed": scraped_at != previous_stamp or warnings != previous_warnings or len(merged_rows) != len(previous_merged),
        "scraped_at": scraped_at,
        "warnings": warnings,
    }


def write_report(output=None, days=None, root=None, search_api="http://127.0.0.1:8766"):
    from generate_report import render_tabs

    output = Path(output or REPORT)
    tabs = []
    for search in SEARCHES:
        merged = source_path(search["slug"], "merged", root)
        if not merged.exists():
            _log(f"[warn] {search['title']}: no saved merged listings, tab omitted")
            continue
        meta = load_meta(search["slug"], root) or {}
        meta.setdefault("slug", search["slug"])
        meta.setdefault("title", search["title"])
        tabs.append((read_csv(merged), meta))
    if not tabs:
        raise ScrapeError("no saved listings to put in the report")
    _log("[building report]")
    render_tabs(tabs, output, fresh_days=resolve_fresh_days(days, root), search_api=search_api)
    return output


def refresh_all(*, force=False, fresh_days=None, now=None, root=None, output=None, write=True,
                search_api="http://127.0.0.1:8766", scrapers=None, fetch=None, slug=None):
    selected = [item for item in SEARCHES if slug in (None, "", item["slug"])]
    if slug and not selected:
        raise ScrapeError(f"unknown search {slug!r}")
    own_fetch = False
    results = []
    try:
        for search in selected:
            meta = load_meta(search["slug"], root)
            merged = source_path(search["slug"], "merged", root)
            days = resolve_fresh_days(fresh_days, root)
            stale = force or not is_fresh(meta, days, utc_now(now), merged.exists())
            if stale and fetch is None and scrapers is None and not own_fetch:
                fetch = Fetcher()
                fetch.__enter__()
                own_fetch = True
            results.append(refresh_search(
                search, force=force, fresh_days=fresh_days, now=now, root=root,
                scrapers=scrapers, fetch=fetch,
            ))
    finally:
        if own_fetch:
            fetch.close()
    report = Path(output or REPORT)
    if write and (any(item.get("changed") for item in results) or not report.exists()):
        if any(source_path(item["slug"], "merged", root).exists() for item in SEARCHES):
            write_report(output=report, days=fresh_days, root=root, search_api=search_api)
    elif write:
        _log(f"[skip] report unchanged at {report}")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="Scrape even when saved data is still fresh")
    parser.add_argument("--fresh-days", default=None, help="Freshness window in days (default 2)")
    parser.add_argument("--slug", default="", help="Refresh one search (sr22, sf50, cubcrafters, or pa28-180-181)")
    parser.add_argument("--no-report", action="store_true", help="Update saved files without rewriting the report")
    args = parser.parse_args(argv)
    try:
        results = refresh_all(
            force=args.force, fresh_days=args.fresh_days, slug=args.slug or None, write=not args.no_report,
        )
    except ScrapeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    failed = [item for item in results if not item.get("ok")]
    return 1 if failed and all(not item.get("ok") for item in results) else 0


if __name__ == "__main__":
    sys.exit(main())
