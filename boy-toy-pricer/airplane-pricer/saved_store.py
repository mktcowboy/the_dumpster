#!/usr/bin/env python3
"""Saved SR22 scrape results. One folder per search, committed with the repo.

A search is fresh while its merged snapshot is at most `fresh_days` old
(default 2). The window is read from, in order: an explicit argument, the
SR22_FRESH_DAYS environment variable, saved/freshness.json, then the default.
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

SOURCE_FILES = {
    "cirrus": "cirrus.csv",
    "cubcrafters": "cubcrafters.csv",
    "aso": "aso.csv",
    "globalair": "globalair.csv",
    "aircraftdealer": "aircraftdealer.csv",
    "barnstormers": "barnstormers.csv",
    "controller": "controller.csv",
    "tradeaplane": "tradeaplane.csv",
    "aircraftcom": "aircraftcom.csv",
    "aerotrader": "aerotrader.csv",
    "ebay": "ebay.csv",
    "merged": "merged.csv",
}


def fresh_days(explicit=None, root=None):
    if explicit is not None and explicit != "":
        return float(explicit)
    env = os.environ.get("SR22_FRESH_DAYS", "").strip()
    if env:
        return float(env)
    path = Path(root or SAVED_DIR) / "freshness.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
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
    name = SOURCE_FILES[source]
    return search_dir(slug, root) / name


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
    path = meta_path(slug, root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def save_meta(slug, meta, root=None):
    folder = search_dir(slug, root)
    folder.mkdir(parents=True, exist_ok=True)
    _atomic_text(meta_path(slug, root), json.dumps(meta, indent=2, ensure_ascii=False) + "\n")


def is_fresh(meta, days, now=None, merged_exists=True):
    """True when the snapshot is present and not older than `days`."""
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
    else:
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


def _atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
