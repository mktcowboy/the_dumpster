#!/usr/bin/env python3
"""Refresh the Porsche 911 searches and rebuild report.html.

One search per generation tab, from porsche_911.search_lines(). A search whose
saved snapshot is within the freshness window (default 2 days) is left alone
unless --force is set. A Bring a Trailer failure keeps the previous file and
is reported as a warning. No browser window opens: AutoTempest runs headless
and Bring a Trailer is plain HTTP.

Saved files live in saved/<generation>/:
  autotempest.csv, bat.csv, merged.csv, meta.json

Usage:
    python3 refresh_911.py                 # skip fresh searches
    python3 refresh_911.py --force         # scrape every generation
    python3 refresh_911.py --slug 992      # one generation
    python3 refresh_911.py --fresh-days 3
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import porsche_911
from bat_sold_scraper import FIELDS as BAT_FIELDS
from merge_listings_v2 import FIELDS, merge_rows
from saved_store_v2 import (
    SAVED_DIR,
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

HERE = Path(__file__).resolve().parent
REPORT = HERE / "report.html"
DATA = HERE / "data"
SCRAPER = HERE / "autotempest_scraper_v2.py"
AUTOTRADER = HERE / "autotrader_scraper_v2.py"
BAT = HERE / "bat_sold_scraper.py"
FILTER = HERE / "filter_listings.py"
REPORT_PY = HERE / "generate_report_v2.py"

# One line per generation tab. Fields:
# URL|Title|slug|BAT_URL|BAT_MATCH|AT_MATCH|AUTOTRADER_URL|MATCH_ON|CLASSIFY
# URL and BAT_URL hold several space-separated links. BAT_MATCH is a
# comma-separated list of regexes; within one, ";" means "or". CLASSIFY is
# "911:<generation>": after the VIN merge, only the cars porsche_911.classify()
# puts in that generation are kept. The 911 lines have no Autotrader URLs:
# Autotrader only answers a visible Chrome window.
SEARCHES = porsche_911.search_lines()


class ScrapeError(RuntimeError):
    pass


def parse_search(entry):
    parts = entry.split("|")
    if len(parts) < 3 or not parts[2]:
        raise ValueError(f"search line needs URL|Title|slug, got {entry!r}")
    while len(parts) < 9:
        parts.append("")
    url, title, slug, bat_url, bat_match, at_match, atr_url, match_on, classify = parts[:9]
    classifier, _, generation = classify.partition(":")
    return {
        "autotempest_urls": url.split(),
        "title": title,
        "slug": slug,
        "bat_urls": bat_url.split(),
        "bat_match": [item for item in bat_match.split(",") if item],
        "at_match": [item for item in at_match.split(",") if item],
        "autotrader_urls": atr_url.split(),
        # "text" searches the title and the description. Anything else is title only.
        "match_on": "text" if match_on == "text" else "title",
        # "911:992" keeps only the cars porsche_911.classify() puts in the 992 generation.
        "classifier": classifier,
        "generation": generation,
    }


def searches(slug=None):
    parsed = [parse_search(entry) for entry in SEARCHES]
    if slug:
        parsed = [item for item in parsed if item["slug"] == slug]
        if not parsed:
            raise ScrapeError(f"unknown search {slug!r}")
    return parsed


def _run(argv):
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        lines = (proc.stderr or proc.stdout or "").strip().splitlines()
        detail = lines[-1] if lines else f"exit {proc.returncode}"
        raise ScrapeError(detail)
    return proc


def _match_regex(pattern):
    """Turn a search-line match into one regex. ";" separates alternatives."""
    alternatives = [part for part in pattern.split(";") if part]
    if len(alternatives) > 1:
        return "(?:" + "|".join(alternatives) + ")"
    return pattern


def autotrader_cap_notes(stderr):
    """Pull 'stopped at N of M' lines out of the Autotrader scraper's stderr."""
    notes = []
    marker = "[warn] stopped at "
    for line in (stderr or "").splitlines():
        if marker in line:
            notes.append(line.split(marker, 1)[1].strip())
    return notes


def _filter(path, patterns, match_on="title"):
    if not patterns or not Path(path).exists():
        return
    argv = [sys.executable, str(FILTER), str(path)]
    for pattern in patterns:
        argv.extend(["--match", _match_regex(pattern)])
    if match_on == "text":
        argv.extend(["--field", "title", "--field", "description"])
    _run(argv)


def _concat(parts, dest):
    rows = []
    for part in parts:
        rows.extend(read_csv(part))
    write_csv(dest, rows, FIELDS)


def default_scrape_autotempest(urls, dest, msrp_cache):
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        parts = []
        for index, url in enumerate(urls):
            part = folder / f"part{index}.csv"
            _run([
                sys.executable, str(SCRAPER), url,
                "-o", str(part), "--timeout", "60", "--msrp-cache", str(msrp_cache),
                # CarGurus answers most listing-page lookups with a verification
                # page, so MSRP comes only from what the listing text states.
                "--no-msrp",
            ])
            parts.append(part)
        _concat(parts, dest)


def default_scrape_autotrader(urls, dest):
    proc = subprocess.run(
        [sys.executable, str(AUTOTRADER), *urls, "-o", str(dest)],
        capture_output=True, text=True,
    )
    if proc.stderr:
        print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n", file=sys.stderr)
    if proc.returncode != 0:
        lines = (proc.stderr or proc.stdout or "").strip().splitlines()
        detail = lines[-1] if lines else f"exit {proc.returncode}"
        raise ScrapeError(detail)
    default_scrape_autotrader.cap_notes = autotrader_cap_notes(proc.stderr)


def default_scrape_bat(urls, matches, dest, miles_cache, since_days=0):
    argv = [sys.executable, str(BAT), *urls, "-o", str(dest), "--miles-cache", str(miles_cache)]
    if since_days:
        argv.extend(["--since-days", str(since_days)])
    for pattern in matches:
        argv.extend(["--match", pattern])
    _run(argv)


def _source_state(meta, name):
    sources = meta.get("sources") if isinstance(meta.get("sources"), dict) else {}
    state = sources.get(name) if isinstance(sources.get(name), dict) else {}
    return dict(state)


def _log(message):
    print(message, flush=True)


def refresh_search(search, *, force=False, fresh_days=None, now=None, root=None,
                   scrape_autotempest=None, scrape_autotrader=None, scrape_bat=None, progress=None):
    """Refresh one search. Returns a status dict and writes saved/<slug>/.

    progress(stage) is called with a short label as each site is scraped.

    Scrapers are injectable so tests can avoid the network. A failure of
    Autotrader or BaT keeps that source's previous file.
    """
    days = resolve_fresh_days(fresh_days, root)
    moment = utc_now(now)
    slug = search["slug"]
    title = search["title"]
    folder = search_dir(slug, root)
    folder.mkdir(parents=True, exist_ok=True)
    meta = load_meta(slug, root) or {}
    merged = source_path(slug, "merged", root)
    previous_warnings = list(meta.get("warnings") or [])
    previous_stamp = meta.get("scraped_at") or ""

    if not force and is_fresh(meta, days, moment, merged.exists()):
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

    scrape_autotempest = scrape_autotempest or default_scrape_autotempest
    scrape_autotrader = scrape_autotrader or default_scrape_autotrader
    scrape_bat = scrape_bat or default_scrape_bat
    DATA.mkdir(parents=True, exist_ok=True)
    msrp_cache = DATA / "msrp_cache.json"
    miles_cache = DATA / "bat_mileage_cache.json"
    when = stamp(moment)
    warnings = []
    sources = {
        "autotempest": _source_state(meta, "autotempest"),
        "autotrader": _source_state(meta, "autotrader"),
        "bat": _source_state(meta, "bat"),
        "merged": _source_state(meta, "merged"),
    }
    new_source = False

    _log(f"[{moment.strftime('%Y-%m-%d %H:%M:%S')}] scraping: {title}")
    progress = progress or (lambda stage: None)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        at_dest = work / "autotempest.csv"
        try:
            progress("Searching AutoTempest")
            scrape_autotempest(search["autotempest_urls"], at_dest, msrp_cache)
            _filter(at_dest, search["at_match"], search.get("match_on", "title"))
            shutil.copyfile(at_dest, source_path(slug, "autotempest", root))
            rows = read_csv(source_path(slug, "autotempest", root))
            sources["autotempest"] = {"scraped_at": when, "ok": True, "rows": len(rows), "warning": ""}
            new_source = True
        except (ScrapeError, OSError) as exc:
            saved = source_path(slug, "autotempest", root)
            if saved.exists():
                warnings.append(f"AutoTempest failed ({exc}); showing saved AutoTempest listings")
                sources["autotempest"]["ok"] = False
                sources["autotempest"]["warning"] = str(exc)
            else:
                warnings.append(f"AutoTempest failed ({exc}); no saved listings to show")
                meta = {
                    **meta,
                    "slug": slug,
                    "title": title,
                    "warnings": warnings,
                    "last_attempt_at": when,
                    "sources": sources,
                }
                save_meta(slug, meta, root)
                _log(f"[warn] {title}: {warnings[-1]}")
                return {
                    "slug": slug, "title": title, "ok": False, "skipped": False,
                    "changed": warnings != previous_warnings, "scraped_at": previous_stamp,
                    "warnings": warnings,
                }

        if search["autotrader_urls"]:
            atr_dest = work / "autotrader.csv"
            try:
                progress("Searching Autotrader")
                scrape_autotrader(search["autotrader_urls"], atr_dest)
                notes = list(getattr(scrape_autotrader, "cap_notes", None) or [])
                if hasattr(scrape_autotrader, "cap_notes"):
                    scrape_autotrader.cap_notes = []
                _filter(atr_dest, search["at_match"], search.get("match_on", "title"))
                shutil.copyfile(atr_dest, source_path(slug, "autotrader", root))
                rows = read_csv(source_path(slug, "autotrader", root))
                cap_warning = "; ".join(f"Autotrader stopped at {note}" for note in notes)
                if cap_warning:
                    warnings.append(cap_warning)
                    _log(f"[warn] {title}: {cap_warning}")
                sources["autotrader"] = {
                    "scraped_at": when, "ok": True, "rows": len(rows), "warning": cap_warning,
                }
                new_source = True
            except (ScrapeError, OSError) as exc:
                saved = source_path(slug, "autotrader", root)
                saved_when = sources["autotrader"].get("scraped_at") or ""
                if saved.exists():
                    shown = f" from {saved_when}" if saved_when else ""
                    warnings.append(f"Autotrader failed ({exc}); showing saved Autotrader listings{shown}")
                else:
                    warnings.append(f"Autotrader failed ({exc}); no saved Autotrader listings")
                sources["autotrader"]["ok"] = False
                sources["autotrader"]["warning"] = str(exc)
                _log(f"[warn] {title}: {warnings[-1]}")

        parts = []
        for name in ("autotempest", "autotrader"):
            if name == "autotrader" and not search["autotrader_urls"]:
                continue
            path = source_path(slug, name, root)
            if path.exists():
                parts.extend(read_csv(path))
        if not parts:
            warnings.append("No AutoTempest or Autotrader rows to merge")
            meta.update(slug=slug, title=title, warnings=warnings, last_attempt_at=when, sources=sources)
            save_meta(slug, meta, root)
            return {
                "slug": slug, "title": title, "ok": False, "skipped": False,
                "changed": True, "scraped_at": previous_stamp, "warnings": warnings,
            }
        progress("Merging listings by VIN")
        merged_rows = merge_rows(parts)
        if search.get("generation"):
            merged_rows = [row for row in merged_rows if porsche_911.in_generation(row, search["generation"])]
        write_csv(merged, merged_rows, FIELDS)
        sources["merged"] = {"scraped_at": when if new_source else (sources["merged"].get("scraped_at") or previous_stamp),
                             "ok": True, "rows": len(merged_rows), "warning": ""}

        if search["bat_urls"]:
            bat_dest = work / "bat.csv"
            try:
                progress("Checking Bring a Trailer sales")
                if search.get("classifier"):
                    scrape_bat(search["bat_urls"], search["bat_match"], bat_dest, miles_cache,
                               since_days=porsche_911.BAT_SINCE_DAYS)
                    sold = [row for row in read_csv(bat_dest) if porsche_911.in_generation(row, search["generation"])]
                    write_csv(bat_dest, sold, BAT_FIELDS)
                else:
                    scrape_bat(search["bat_urls"], search["bat_match"], bat_dest, miles_cache)
                shutil.copyfile(bat_dest, source_path(slug, "bat", root))
                rows = read_csv(source_path(slug, "bat", root))
                sources["bat"] = {"scraped_at": when, "ok": True, "rows": len(rows), "warning": ""}
                new_source = True
            except (ScrapeError, OSError) as exc:
                saved = source_path(slug, "bat", root)
                saved_when = sources["bat"].get("scraped_at") or ""
                if saved.exists():
                    shown = f" from {saved_when}" if saved_when else ""
                    warnings.append(f"Bring a Trailer failed ({exc}); showing saved sold listings{shown}")
                else:
                    warnings.append(f"Bring a Trailer failed ({exc}); sold overlay unavailable")
                sources["bat"]["ok"] = False
                sources["bat"]["warning"] = str(exc)
                _log(f"[warn] {title}: {warnings[-1]}")

    scraped_at = when if new_source else previous_stamp
    if new_source:
        sources["merged"]["scraped_at"] = when
    meta = {
        "slug": slug,
        "title": title,
        "scraped_at": scraped_at,
        "warnings": warnings,
        "last_attempt_at": when,
        "sources": sources,
    }
    save_meta(slug, meta, root)
    _log(f"[done] {title}: {sources['merged'].get('rows', 0)} cars, data as of {scraped_at}")
    return {
        "slug": slug,
        "title": title,
        "ok": True,
        "skipped": False,
        "changed": scraped_at != previous_stamp or warnings != previous_warnings,
        "scraped_at": scraped_at,
        "warnings": warnings,
    }


def write_report(parsed=None, output=None, days=None, root=None, search_api=None):
    parsed = parsed if parsed is not None else searches()
    output = Path(output or REPORT)
    output.parent.mkdir(parents=True, exist_ok=True)
    days = resolve_fresh_days(days, root)
    search_api = search_api or os.environ.get("AUTOTEMPEST_SEARCH_API", "http://127.0.0.1:8911")
    argv = [
        sys.executable, str(REPORT_PY),
        "--title", "Porsche 911 Tracker",
        "--link", "All cars report|../report.html",
        "-o", str(output),
        "--fresh-days", str(days),
        "--search-api", search_api,
    ]
    written = 0
    for search in parsed:
        merged = source_path(search["slug"], "merged", root)
        if not merged.exists():
            _log(f"[warn] {search['title']}: no saved merged listings, tab omitted")
            continue
        bat = source_path(search["slug"], "bat", root)
        spec = "|".join([
            search["title"],
            str(merged),
            " ".join(search["autotempest_urls"]),
            str(bat) if bat.exists() else "",
            " ".join(search["autotrader_urls"]),
            search["slug"],
            search.get("classifier", ""),
        ])
        argv.extend(["--tab", spec])
        written += 1
    if not written:
        raise ScrapeError("no saved searches to put in the report")
    _log("[building report]")
    _run(argv)
    return output


def refresh_all(*, force=False, fresh_days=None, now=None, root=None, slug=None,
                output=None, write=True, search_api=None,
                scrape_autotempest=None, scrape_autotrader=None, scrape_bat=None):
    parsed = searches(slug)
    report = Path(output or REPORT)
    results = []
    for search in parsed:
        result = refresh_search(
            search, force=force, fresh_days=fresh_days, now=now, root=root,
            scrape_autotempest=scrape_autotempest,
            scrape_autotrader=scrape_autotrader,
            scrape_bat=scrape_bat,
        )
        results.append(result)
        # Rebuild after each generation so the report fills in tab by tab.
        if write and result.get("changed"):
            write_report(searches(), output=report, days=fresh_days, root=root, search_api=search_api)
    if write and not report.exists():
        write_report(searches(), output=report, days=fresh_days, root=root, search_api=search_api)
    elif write and not any(item.get("changed") for item in results):
        _log(f"[skip] report unchanged at {report}")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="Scrape even when saved data is still fresh")
    parser.add_argument("--fresh-days", default=None, help="Freshness window in days (default 2)")
    parser.add_argument("--slug", default="", help="Refresh one generation (992, 991, ... g, early) instead of every one")
    parser.add_argument("--no-report", action="store_true", help="Update saved files without rewriting the report")
    args = parser.parse_args(argv)
    try:
        results = refresh_all(
            force=args.force,
            fresh_days=args.fresh_days,
            slug=args.slug or None,
            write=not args.no_report,
        )
    except ScrapeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    failed = [item for item in results if not item.get("ok")]
    return 1 if failed and all(not item.get("ok") for item in results) else 0


if __name__ == "__main__":
    sys.exit(main())
