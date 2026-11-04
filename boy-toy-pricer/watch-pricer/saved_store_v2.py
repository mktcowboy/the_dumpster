#!/usr/bin/env python3
"""Saved scrape results for the Patek 5711 scanner. Same layout as the car scanner.

One folder per search in saved/<slug>/, committed with the repo:
  <source>.csv        one file per source (chrono24.csv, bobs.csv, ...)
  merged.csv          the deduped list the report shows
  meta.json           scraped_at, per-source status, warnings
  price_history.csv   one line per run, variant and source (low/median/high)
  chrono24_details.json  detail-page cache keyed by Chrono24 listing id

A search is fresh while its snapshot is at most `fresh_days` old (default 2).
The window comes from, in order: an explicit argument, PATEK_FRESH_DAYS,
saved/freshness.json, then the default.
"""
import csv
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

HERE = Path(__file__).resolve().parent
SAVED_DIR = HERE / "saved"
DEFAULT_FRESH_DAYS = 2
CHICAGO = "America/Chicago"


def fresh_days(explicit=None, root=None):
    if explicit is not None and explicit != "":
        return float(explicit)
    env = os.environ.get("PATEK_FRESH_DAYS", "").strip()
    if env:
        return float(env)
    try:
        data = json.loads((Path(root or SAVED_DIR) / "freshness.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if data.get("fresh_days") not in (None, ""):
        return float(data["fresh_days"])
    return float(DEFAULT_FRESH_DAYS)


def search_dir(slug, root=None):
    return Path(root or SAVED_DIR) / slug


def meta_path(slug, root=None):
    return search_dir(slug, root) / "meta.json"


def source_path(slug, source, root=None):
    return search_dir(slug, root) / f"{source}.csv"


def parse_time(value):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_now(now=None):
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def stamp(now=None):
    return utc_now(now).isoformat()


def load_meta(slug, root=None):
    try:
        data = json.loads(meta_path(slug, root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def save_meta(slug, meta, root=None):
    _atomic_text(meta_path(slug, root), json.dumps(meta, indent=2, ensure_ascii=False) + "\n")


def is_fresh(meta, days, now=None, merged_exists=True):
    if not merged_exists or not meta:
        return False
    scraped = parse_time(meta.get("scraped_at"))
    if scraped is None:
        return False
    return utc_now(now) - scraped <= timedelta(days=float(days))


def format_as_of(value):
    parsed = parse_time(value)
    if parsed is None:
        return ""
    if ZoneInfo is not None:
        try:
            parsed = parsed.astimezone(ZoneInfo(CHICAGO))
        except Exception:
            parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d %H:%M %Z")


def read_csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fieldnames):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    os.replace(tmp, path)


def append_csv(path, rows, fieldnames):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if new:
            writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
