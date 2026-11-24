#!/usr/bin/env python3
"""Optimized HTML report generator (v3 -> report_v2.html + per-tab data files).

Preserves every feature and visual element of generate_report_v2.py while
drastically cutting payload size, startup CPU, memory, and DOM lag:

Payload optimizations:
- Compact JSON (no whitespace) with positional row/BaT arrays and a shared tag table.
- Precomputes exterior color and BaT modified flag in Python; drops unused/constant
  fields (listing_id, single-source duplicates, constant BaT dealer/site/prefix,
  and BaT auction descriptions).
- Splits each tab's rows + BaT comps into a lazy-loaded JS file (<out>_data/<slug>.js)
  that works over GitHub Pages (https://), local HTTP servers, AND direct file:// opens.
  The first tab loads in parallel via <script defer>; remaining tabs load on demand
  (and prefetch on hover). Pass --single-file to inline everything if desired.

Runtime & UX optimizations:
- Lazy tab initialization: only the active tab is unpacked, modeled, and rendered on load.
- Progressive table rendering (150 rows initially, auto-loads more on scroll + Show all).
- Table sorting only re-sorts and re-renders visible table rows (no chart destroy/rebuild).
- Chart.js updates datasets in place instead of destroying/recreating the chart.
- O(N log N) BaT market index via sorted prefix sums + binary search (was O(N^2)).
- Faster single-pass XtX + Gauss-Jordan matrix inversion for OLS.
- Lazy fuzzy-search tokenization (only splits words when the user types a search query).
- Clean static-host mode: disables localhost polling/Search tab/1s interval on GitHub Pages.
"""
import argparse
import csv
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import porsche_911
from saved_store_v2 import format_as_of, fresh_days as resolve_fresh_days, parse_time

PRICE_RE = re.compile(r"[\d,]+")
MILEAGE_RE = re.compile(r"[\d,]+")
YEAR_RE = re.compile(r"(19|20)\d{2}")

BAT_PREFIX = "https://bringatrailer.com/listing/"

COLOR_WORDS = [
    ("Black", re.compile(r"\b(black|nero|noir|obsidian|onyx|ebony|schwarz)\b", re.I | re.ASCII)),
    ("White", re.compile(r"\b(white|bianco|blanc|polar|diamond white|glacier)\b", re.I | re.ASCII)),
    ("Gray", re.compile(r"\b(gr[ae]y|grigio|graphite|gunmetal|selenite|magno|chalk|crayon|nardo|charcoal|slate|tungsten)\b", re.I | re.ASCII)),
    ("Silver", re.compile(r"\b(silver|argento|iridium|platinum silver)\b", re.I | re.ASCII)),
    ("Red", re.compile(r"\b(red|rosso|rouge|burgundy|maroon|crimson|tango)\b", re.I | re.ASCII)),
    ("Blue", re.compile(r"\b(blue|blu|azzurro|navy|cobalt|sepang|ascari|kyanite)\b", re.I | re.ASCII)),
    ("Green", re.compile(r"\b(green|verde|olive|emerald|british racing|sage)\b", re.I | re.ASCII)),
    ("Yellow", re.compile(r"\b(yellow|giallo|amarillo)\b", re.I | re.ASCII)),
    ("Orange", re.compile(r"\b(orange|arancio|arancione)\b", re.I | re.ASCII)),
    ("Brown/Tan", re.compile(r"\b(brown|bronze|beige|tan|marrone|copper|desert sand)\b", re.I | re.ASCII)),
    ("Gold", re.compile(r"\b(gold|oro|champagne)\b", re.I | re.ASCII)),
    ("Purple", re.compile(r"\b(purple|viola|violet)\b", re.I | re.ASCII)),
]
COLOR_NAMES = ["Unknown"] + [name for name, _ in COLOR_WORDS]
COLOR_INDEX = {name: i for i, name in enumerate(COLOR_NAMES)}

MODIFIED_RE = re.compile(
    r"\b(modified|tuned|renntech|weistec|capristo|brabus|mansory|novitec|stage [123]"
    r"|aftermarket (?:turbo|supercharger|exhaust|tune)|built engine|widebody)\b",
    re.I | re.ASCII,
)


def parse_price(s):
    m = PRICE_RE.search(s or "")
    return int(m.group(0).replace(",", "")) if m else None


def parse_mileage(s):
    m = MILEAGE_RE.search(s or "")
    return int(m.group(0).replace(",", "")) if m else None


def parse_year(title):
    m = YEAR_RE.search(title or "")
    return int(m.group(0)) if m else None


def detect_color(title, description):
    text = f"{title or ''} {description or ''}"
    best = "Unknown"
    best_at = len(text) + 1
    for name, rx in COLOR_WORDS:
        m = rx.search(text)
        if m and m.start() < best_at:
            best = name
            best_at = m.start()
    return best


def parse_sources(raw):
    if isinstance(raw, list):
        data = raw
    elif not raw:
        return []
    else:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return []
    if not isinstance(data, list):
        return []
    sources = []
    for item in data:
        if not isinstance(item, dict):
            continue
        sources.append({
            "site": item.get("site_code") or item.get("site") or "",
            "price": parse_price(str(item.get("price") or "")),
            "price_with_fees": parse_price(str(item.get("price_with_fees") or "")),
            "link": item.get("link") or "",
            "listing_id": str(item.get("listing_id") or ""),
        })
    return sources


def normalize_rows(raw_rows):
    rows = []
    for r in raw_rows:
        rows.append({
            "listing_id": r.get("listing_id", ""),
            "title": r.get("title", ""),
            "year": parse_year(r.get("title", "")),
            "price": parse_price(r.get("price", "")),
            "mileage": parse_mileage(r.get("mileage", "")),
            "deal_rating": r.get("deal_rating", ""),
            "is_hot": str(r.get("is_hot", "")).lower() == "true",
            "posted_date": r.get("posted_date", ""),
            "city": r.get("city", ""),
            "distance": r.get("distance", ""),
            "dealer": r.get("dealer", ""),
            "site_code": r.get("site_code", ""),
            "description": r.get("description", ""),
            "link": r.get("link", ""),
            "msrp": parse_price(str(r.get("msrp") or "")),
            "msrp_source": r.get("msrp_source", ""),
            "vin": (r.get("vin") or "").strip().upper(),
            "extra_sites": r.get("extra_sites", "") or "",
            "sources": parse_sources(r.get("sources")),
        })
    return rows


def load_rows(path):
    path = str(path)
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            raw_rows = json.load(f)
    else:
        with open(path, newline="", encoding="utf-8") as f:
            raw_rows = list(csv.DictReader(f))
    return normalize_rows(raw_rows)


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "tab"


def snapshot_meta(csv_path):
    path = Path(csv_path).parent / "meta.json" if csv_path else None
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def js_json(obj):
    """Compact JSON safe to embed inside a <script> block."""
    return (
        json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def pack_row(r, tag_index):
    srcs = r.get("sources") or []
    sources_compact = None
    if len(srcs) > 1:
        sources_compact = [
            [s.get("site") or "", s.get("price"), s.get("price_with_fees"), s.get("link") or ""]
            for s in srcs
        ]
    elif len(srcs) == 1:
        fee = srcs[0].get("price_with_fees")
        if fee is not None and fee != r.get("price"):
            sources_compact = fee  # scalar fee_price for single-source listings with fees

    color_idx = COLOR_INDEX[detect_color(r.get("title"), r.get("description"))]
    tags = [tag_index[t] for t in (r.get("tags") or []) if t in tag_index]
    return [
        r.get("title") or "",
        r.get("year"),
        r.get("price"),
        r.get("mileage"),
        r.get("deal_rating") or "",
        1 if r.get("is_hot") else 0,
        r.get("posted_date") or "",
        r.get("city") or "",
        r.get("distance") or "",
        r.get("dealer") or "",
        r.get("site_code") or "",
        r.get("description") or "",
        r.get("link") or "",
        r.get("msrp"),
        r.get("msrp_source") or "",
        r.get("vin") or "",
        r.get("extra_sites") or "",
        sources_compact,
        tags,
        color_idx,
    ]


def pack_bat(b, tag_index):
    link = b.get("link") or ""
    if link.startswith(BAT_PREFIX):
        link = link[len(BAT_PREFIX):]
    modified = 1 if MODIFIED_RE.search(f"{b.get('title') or ''} {b.get('description') or ''}") else 0
    tags = [tag_index[t] for t in (b.get("tags") or []) if t in tag_index]
    return [
        b.get("title") or "",
        b.get("year"),
        b.get("price"),
        b.get("mileage"),
        b.get("posted_date") or "",
        b.get("city") or "",
        link,
        tags,
        modified,
    ]


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__PAGE_TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script>
window.__TAB_CACHE__ = Object.create(null);
window.__TAB_WAIT__ = Object.create(null);
window.__LOAD_TAB__ = function(slug, data) {
  window.__TAB_CACHE__[slug] = data;
  var q = window.__TAB_WAIT__[slug];
  if (q) { delete window.__TAB_WAIT__[slug]; q.forEach(function(fn) { fn(data); }); }
};
</script>
__PRELOAD_SCRIPTS__<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js" defer></script>
<style>
  :root {
    --bg: #0b0d12; --panel: #12151c; --panel-2: #181c25; --border: #232836; --border-strong: #2f3545;
    --text: #e6e9ef; --muted: #8b93a3; --faint: #5d6575;
    --accent: #5aa9ff; --good: #34d399; --great: #fbbf24; --fair: #f87171;
    --radius: 12px;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 14px; line-height: 1.45; -webkit-font-smoothing: antialiased;
  }
  .num, td, .kpi b, .stat b { font-variant-numeric: tabular-nums; }
  .shell { max-width: 1440px; margin: 0 auto; padding: 28px 24px 48px; }
  @media (max-width: 640px) { .shell { padding: 16px; } }

  /* page header */
  .page-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
  .page-title { display: grid; gap: 4px; min-width: 0; }
  .update { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .update[hidden] { display: none; }
  .update-status { font-size: 12px; color: var(--muted); }
  .update-status.error { color: var(--fair); }
  .btn-update { letter-spacing: 0.08em; padding: 9px 22px; }
  .btn-update.secondary { background: transparent; color: var(--muted); box-shadow: inset 0 0 0 1px var(--border-strong); }
  .btn-update.secondary:hover:not(:disabled) { color: var(--text); }
  .btn-update:disabled { opacity: 0.55; cursor: default; }

  /* status bar: the open tab's data age and any refresh in progress */
  .statusbar {
    position: sticky; top: 0; z-index: 5; display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    margin: -8px 0 16px; padding: 9px 14px; border-radius: 10px; font-size: 13px;
    background: var(--panel); box-shadow: inset 0 0 0 1px var(--border);
  }
  .sb-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--faint); flex: none; }
  .statusbar[data-tone=fresh] .sb-dot { background: var(--good); }
  .statusbar[data-tone=stale] .sb-dot { background: var(--great); }
  .statusbar[data-tone=busy] .sb-dot { background: var(--accent); animation: sb-pulse 1.2s ease-in-out infinite; }
  .statusbar[data-tone=error] .sb-dot { background: var(--fair); }
  .statusbar[data-tone=error] .sb-main { color: var(--fair); }
  @keyframes sb-pulse { 50% { opacity: 0.3; } }
  .sb-main { color: var(--text); min-width: 0; flex: 1 1 200px; }
  .sb-side { margin-left: auto; color: var(--muted); font-size: 12px; }
  .tab-btn.stale::after {
    content: ""; display: inline-block; width: 6px; height: 6px; margin-left: 6px; border-radius: 50%;
    background: var(--great); vertical-align: middle;
  }
  h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.01em; margin: 0; }
  .meta { color: var(--muted); font-size: 13px; }
  .asof { color: var(--muted); font-size: 13px; }
  .data-warn { color: var(--fair); font-size: 12px; }
  .data-warn[hidden] { display: none; }
  .tab-title { display: grid; gap: 2px; }
  .meta a { color: var(--muted); text-decoration: underline; text-decoration-color: var(--border-strong); text-underline-offset: 3px; }
  .meta a:hover { color: var(--text); }

  /* tab nav */
  .tabs { display: flex; gap: 4px; flex-wrap: wrap; padding: 4px; background: var(--panel); border: 1px solid var(--border); border-radius: 12px; margin-bottom: 22px; }
  .tab-btn {
    background: transparent; border: 0; color: var(--muted); padding: 8px 14px; border-radius: 8px;
    cursor: pointer; font: inherit; font-size: 13px; font-weight: 600; white-space: nowrap;
  }
  .tab-btn:hover { color: var(--text); background: var(--panel-2); }
  .tab-btn.active { color: var(--text); background: var(--panel-2); box-shadow: inset 0 0 0 1px var(--border-strong); }
  .tab-btn .count-pill { color: var(--faint); font-weight: 500; margin-left: 6px; }
  .tab-btn.live { color: var(--accent); }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }
  .tab-loading { color: var(--muted); text-align: center; padding: 64px 16px; background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); }

  /* tab header + KPI strip */
  .tab-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
  .tab-head h2 { font-size: 18px; margin: 0; font-weight: 700; letter-spacing: -0.01em; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin-bottom: 18px; }
  .kpi { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); padding: 12px 14px; min-width: 0; }
  .kpi > span { display: block; font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .kpi b { display: block; font-size: 20px; font-weight: 700; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .kpi em { display: block; font-style: normal; font-size: 12px; color: var(--muted); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .kpi.bat { border-color: #2c3342; background: linear-gradient(180deg, #151923, var(--panel)); }
  .kpi a { color: inherit; text-decoration: none; }
  .kpi a:hover { color: var(--accent); }

  /* cards */
  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 18px; margin-bottom: 18px; }
  .card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin: -2px 0 12px; }
  .card-head h3 { font-size: 13px; font-weight: 700; margin: 0; letter-spacing: 0.01em; }
  .card-head .sub { color: var(--muted); font-size: 12px; }
  .at-links { display: flex; gap: 8px; flex-wrap: wrap; }
  .at-links:empty { display: none; }
  .at-link {
    display: inline-flex; align-items: center; gap: 6px; color: var(--text); background: var(--panel-2);
    border: 1px solid var(--border-strong); text-decoration: none; padding: 7px 12px; border-radius: 8px; font-size: 13px; font-weight: 600;
  }
  .at-link:hover { border-color: var(--accent); color: var(--accent); }
  .search-row { display: flex; gap: 8px; }
  .search-input, .zip-input, .filter-grid input, .filter-grid select {
    background: var(--bg); border: 1px solid var(--border-strong); color: var(--text);
    border-radius: 8px; padding: 8px 12px; font: inherit; font-size: 14px;
  }
  .search-input { flex: 1; min-width: 0; }
  .zip-input { width: 90px; }
  .btn-primary {
    background: var(--accent); color: #0f1115; border: 0; border-radius: 8px;
    padding: 8px 20px; font-weight: 600; font-size: 14px; cursor: pointer;
  }
  .btn-primary:disabled { opacity: 0.5; cursor: wait; }
  .btn-ghost {
    background: transparent; color: var(--muted); border: 1px solid var(--border);
    border-radius: 8px; padding: 7px 14px; font-size: 13px; cursor: pointer;
  }
  .btn-ghost:hover { color: var(--text); }
  .status { font-size: 12px; color: var(--muted); margin-top: 8px; }
  .status.busy { color: var(--accent); }
  .status.error { color: var(--fair); }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
  .chips:empty { display: none; }
  .chip { background: #1d212b; border: 1px solid var(--border); border-radius: 999px; padding: 2px 10px; font-size: 12px; }
  .chip b { color: var(--muted); font-weight: 600; margin-right: 4px; }
  .filter-grid { display: flex; gap: 14px 20px; flex-wrap: wrap; align-items: flex-end; }
  .filter-grid label {
    display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.04em;
  }
  .filter-grid .pair { display: flex; align-items: center; gap: 6px; text-transform: none; letter-spacing: 0; }
  .filter-grid input, .filter-grid select { padding: 6px 8px; font-size: 13px; width: 92px; }
  .filter-grid select { width: auto; min-width: 92px; padding-right: 26px; }
  .search-input:focus, .zip-input:focus, .filter-grid input:focus, .filter-grid select:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(90,169,255,0.15); }
  .filter-grid input.wide { width: 100%; }
  .filter-grid label.grow { flex: 1; min-width: 220px; }
  .count { color: var(--muted); font-size: 12px; }
  .chartWrap { position: relative; height: 480px; }
  .chartWrap canvas { cursor: crosshair; }
  .brush { position: absolute; border: 1px solid var(--accent); background: rgba(90,169,255,0.12); border-radius: 2px; pointer-events: none; }
  .sel-bar { display: flex; align-items: center; gap: 8px 14px; flex-wrap: wrap; padding: 8px 12px; margin: 0 0 12px; border: 1px solid rgba(90,169,255,0.35); background: rgba(90,169,255,0.08); border-radius: 10px; font-size: 13px; }
  .sel-bar[hidden], .brush[hidden] { display: none; }
  .sel-bar b { font-weight: 600; }
  .sel-bar .sel-actions { display: flex; gap: 8px; margin-left: auto; }
  .btn-ghost.sm { padding: 4px 10px; font-size: 12px; }
  .spec-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); }
  .spec-row[hidden] { display: none; }
  .spec-row > span { font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; margin-right: 4px; }
  .spec-chip { font: inherit; font-size: 12px; font-weight: 600; color: var(--muted); background: var(--bg); border: 1px solid var(--border-strong); border-radius: 999px; padding: 4px 11px; cursor: pointer; }
  .spec-chip:hover { color: var(--text); border-color: var(--muted); }
  .spec-chip[aria-pressed="true"] { color: var(--text); background: rgba(90,169,255,0.15); border-color: var(--accent); }
  .spec-chip i { font-style: normal; color: var(--faint); font-weight: 500; margin-left: 4px; }
  .spec-chip[aria-pressed="true"] i { color: var(--muted); }
  .spec-row.tagged { flex-direction: column; align-items: stretch; gap: 8px; }
  .spec-line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .spec-line > span { width: 72px; flex: none; font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
  .spec-sep { width: 1px; height: 18px; background: var(--border-strong); margin: 0 2px; }
  .chart-tools { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
  .chart-tools [hidden] { display: none; }
  .switch { display: inline-flex; align-items: center; gap: 10px; cursor: pointer; font-size: 13px; color: var(--muted); user-select: none; }
  .switch:hover { color: var(--text); }
  .switch input { appearance: none; -webkit-appearance: none; width: 34px; height: 20px; border-radius: 999px; background: var(--border-strong); position: relative; margin: 0; cursor: pointer; transition: background .15s; flex: 0 0 auto; }
  .switch input::after { content: ''; position: absolute; top: 3px; left: 3px; width: 14px; height: 14px; border-radius: 50%; background: #fff; transition: transform .15s; }
  .switch input:checked { background: var(--accent); }
  .switch input:checked::after { transform: translateX(14px); }
  .switch input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .switch .tri { color: var(--text); }
  .bat-filters { margin: 0 0 14px; padding: 12px 14px; background: var(--panel-2); border: 1px solid var(--border); border-radius: 10px; }
  .bat-filters[hidden] { display: none; }
  .filter-grid label.check { flex-direction: row; align-items: center; gap: 6px; text-transform: none; letter-spacing: 0; font-size: 13px; padding-bottom: 6px; }
  .filter-grid label.check input { width: auto; accent-color: var(--accent); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--border); white-space: nowrap; }
  th { cursor: pointer; user-select: none; color: var(--muted); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; position: sticky; top: 0; background: var(--panel); z-index: 1; }
  th:hover { color: var(--text); }
  th.no-sort { cursor: default; }
  th.r, td.r { text-align: right; }
  tbody tr:hover td { background: var(--panel-2); }
  td small { display: block; font-size: 11px; color: var(--muted); }
  .table-wrap { overflow: auto; max-height: 680px; margin: 0 -18px -16px; border-top: 1px solid var(--border); }
  .table-more { display: flex; align-items: center; justify-content: center; gap: 10px; padding: 12px 16px; border-top: 1px solid var(--border); color: var(--muted); font-size: 12px; background: var(--panel); }
  .table-more[hidden] { display: none; }
  td.title-cell { white-space: normal; min-width: 240px; max-width: 340px; }
  td.source-cell { white-space: normal; min-width: 120px; max-width: 280px; }
  td.source-cell a.view-link { margin: 0 4px 4px 0; display: inline-block; }
  td.vin-cell { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
  .muted { color: var(--muted); }
  a.view-link {
    color: var(--muted); text-decoration: none; border: 1px solid var(--border-strong);
    padding: 3px 10px; border-radius: 6px; font-size: 12px;
  }
  a.title-link { color: var(--text); text-decoration: underline; text-decoration-color: var(--border); text-underline-offset: 3px; }
  a.title-link:hover { color: var(--accent); text-decoration-color: var(--accent); }
  a.view-link:hover { border-color: var(--accent); color: var(--accent); }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
  .badge.good { background: rgba(63,214,126,0.15); color: var(--good); }
  .badge.great { background: rgba(255,212,59,0.15); color: var(--great); }
  .badge.fair { background: rgba(255,135,135,0.15); color: var(--fair); }
  .hot { color: #ff6b6b; font-weight: 700; }
  .empty { color: var(--muted); text-align: center; padding: 32px 0; }
  .below { color: var(--good); font-weight: 600; }
  .above { color: var(--fair); }
  .badge.outlier { background: rgba(154,161,172,0.15); color: var(--muted); }
  .analysis h2 { font-size: 13px; font-weight: 700; margin: 0 0 10px; }
  .analysis h3 { font-size: 12px; margin: 18px 0 8px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
  .analysis .lede { font-size: 14px; line-height: 1.5; margin: 0 0 6px; max-width: 900px; }
  .analysis .footnote { font-size: 12px; color: var(--muted); line-height: 1.5; margin: 6px 0 0; max-width: 900px; }
  .analysis-grid { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 28px; }
  @media (max-width: 1100px) { .analysis-grid { grid-template-columns: 1fr; } }
  .analysis-grid > div { min-width: 0; overflow-x: auto; }
  .analysis th { position: static; background: none; }
  .analysis table.effects { width: auto; min-width: 100%; }
  .analysis table.effects tr:hover td { background: none; }
  .analysis td.neg { color: var(--fair); }
  .analysis td.pos, .analysis .pos { color: var(--good); }
  .analysis .sure { color: var(--text); }
  .checks { display: flex; gap: 6px 16px; flex-wrap: wrap; margin-top: 12px; font-size: 13px; }
  .check { display: flex; align-items: center; gap: 6px; cursor: pointer; }
  .calc-out { margin-top: 14px; display: grid; gap: 10px; }
  .stat { display: grid; grid-template-columns: 1fr auto; gap: 2px 12px; align-items: baseline; padding: 10px 12px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; }
  .stat span { color: var(--muted); font-size: 12px; }
  .stat b { font-size: 16px; text-align: right; }
  .stat em { grid-column: 1 / -1; font-style: normal; font-size: 11px; color: var(--muted); }
</style>
</head>
<body>
<div class="shell">
  <header class="page-head">
    <div class="page-title">
      <h1>__PAGE_TITLE__</h1>
      <div class="meta">Report built __GENERATED_AT__ &middot; listings from <a href="https://www.autotempest.com" target="_blank" rel="noopener">AutoTempest</a> &middot; sold prices from <a href="https://bringatrailer.com" target="_blank" rel="noopener">Bring a Trailer</a>__PAGE_LINKS__</div>
    </div>
    <div class="update" id="updateBox" hidden>
      <span class="update-status" id="updateStatus" role="status"></span>
      <button class="btn-primary btn-update" id="refreshTabBtn" title="Scrape the open car again now, even if its saved data is still fresh">REFRESH THIS CAR</button>
      <button class="btn-primary btn-update secondary" id="updateBtn" title="Scrape every search again, even if the saved data is still fresh">UPDATE ALL</button>
    </div>
  </header>
  <div class="statusbar" id="statusBar" role="status" aria-live="polite" data-tone="idle">
    <span class="sb-dot"></span><span class="sb-main" id="sbMain">__DATA_AS_OF__</span><span class="sb-side" id="sbSide"></span>
  </div>

  <nav class="tabs" id="tabButtons" aria-label="Searches"></nav>
  <div id="tabPanels"></div>
</div>

<script>
const TABS = __TABS_JSON__;
const TAG_LIST = __TAG_LIST__;
const COLOR_NAMES = __COLOR_NAMES__;
const BAT_PREFIX = __BAT_PREFIX__;
const RAW_SEARCH_API = __SEARCH_API__;
const IS_LOCAL = location.protocol === 'file:' || /^(127\.0\.0\.1|localhost)$/.test(location.hostname);
const SEARCH_API = !IS_LOCAL ? null : (/^https?:$/.test(location.protocol) ? location.origin : RAW_SEARCH_API);
const DEFAULT_ZIP = __DEFAULT_ZIP__;
const NOW_MS = __NOW_MS__;
const FRESH_DAYS = __FRESH_DAYS__;
const TAG_GROUPS = __TAG_GROUPS__;
const PAGE_SIZE = 150;
__INLINE_DATA__
if (SEARCH_API) {
  TABS.push({ title: 'Search', slug: 'search', count: 0, bat_count: 0, rows: [], bat: [], url: '', live: true, urls: [], tokens: [], alts: {} });
}

const DEAL_RANK = { fair: 1, good: 2, great: 3 };

const COLS = [
  { key: 'score', label: 'Match', live: true },
  { key: 'year', label: 'Year' },
  { key: 'title', label: 'Title' },
  { key: 'price', label: 'Price', r: true, tip: 'Asking price. When the same VIN is listed on more than one site, this is the lowest price.' },
  { key: 'expected', label: 'Market value', r: true, tip: 'What this car should ask, from same-year AutoTempest listings adjusted for miles and specs' },
  { key: 'vs_market', label: 'Vs market', r: true },
  { key: 'bat_value', label: 'BaT value', r: true, tip: 'Likely Bring a Trailer sale today for this year and mileage, from recent stock BaT sales' },
  { key: 'pct_msrp', label: 'MSRP (stated)', r: true },
  { key: 'mileage', label: 'Mileage', r: true },
  { key: 'color', label: 'Color' },
  { key: 'posted_date', label: 'Posted' },
  { key: 'city', label: 'Location' },
  { key: 'dealer', label: 'Dealer' },
  { key: 'site_code', label: 'Source' },
  { key: 'vin', label: 'VIN' },
  { key: null, label: 'Link' },
];

// ---------- unpacking compact per-tab data ----------
function unpackRow(a) {
  let sources = [];
  const sc = a[17];
  if (Array.isArray(sc)) {
    sources = sc.map(s => ({ site: s[0], price: s[1], price_with_fees: s[2], link: s[3] }));
  } else if (typeof sc === 'number') {
    sources = [{ site: a[10], price: a[2], price_with_fees: sc, link: a[12] }];
  }
  const tags = a[18] ? a[18].map(i => TAG_LIST[i]) : [];
  return {
    title: a[0], year: a[1], price: a[2], mileage: a[3],
    deal_rating: a[4], is_hot: !!a[5], posted_date: a[6],
    city: a[7], distance: a[8], dealer: a[9], site_code: a[10],
    description: a[11], link: a[12], msrp: a[13], msrp_source: a[14],
    vin: a[15], extra_sites: a[16], sources, tags,
    color: COLOR_NAMES[a[19]] || 'Unknown',
  };
}

function unpackBat(a) {
  const link = a[6] && !/^https?:\/\//i.test(a[6]) ? BAT_PREFIX + a[6] : (a[6] || '');
  const tags = a[7] ? a[7].map(i => TAG_LIST[i]) : [];
  return {
    title: a[0], year: a[1], price: a[2], mileage: a[3],
    posted_date: a[4], city: a[5], link, tags,
    _modified: !!a[8],
  };
}

const _scriptLoading = Object.create(null);
function loadTabScript(tab) {
  if (!tab.data_file) return Promise.resolve(null);
  const key = tab.slug;
  if (window.__TAB_CACHE__[key]) return Promise.resolve(window.__TAB_CACHE__[key]);
  return new Promise((resolve, reject) => {
    (window.__TAB_WAIT__[key] = window.__TAB_WAIT__[key] || []).push(resolve);
    if (_scriptLoading[key]) return;
    _scriptLoading[key] = true;
    const s = document.createElement('script');
    s.src = tab.data_file;
    s.async = true;
    s.onerror = () => {
      delete _scriptLoading[key];
      const q = window.__TAB_WAIT__[key];
      delete window.__TAB_WAIT__[key];
      if (q) reject(new Error('Failed to load ' + tab.data_file));
    };
    document.head.appendChild(s);
  });
}

function prefetchTab(tab) {
  if (tab.live || tab._inited || !tab.data_file) return;
  if (window.__TAB_CACHE__[tab.slug] || _scriptLoading[tab.slug]) return;
  loadTabScript(tab).catch(() => {});
}

// ---------- helpers ----------
function fmtPrice(p) { return p == null ? 'N/A' : '$' + p.toLocaleString(); }
function sourceLabel(s) {
  let label = s.site || 'listing';
  if (s.price != null) label += ' ' + fmtPrice(s.price);
  if (s.price_with_fees != null && s.price_with_fees !== s.price) label += ' (' + fmtPrice(s.price_with_fees) + ' w/ fees)';
  return label;
}
function priceCell(d) {
  let out = `<b>${fmtPrice(d.price)}</b>`;
  const sources = d.sources || [];
  if (sources.length > 1) {
    const nums = sources.map(s => s.price).filter(v => v != null);
    if (new Set(nums).size > 1) out += `<small>${sources.length} sites</small>`;
  } else if (sources.length === 1) {
    const fee = sources[0].price_with_fees;
    if (fee != null && fee !== d.price) out += `<small>${fmtPrice(fee)} with fees</small>`;
  }
  return out;
}
function extraNote(d) {
  if ((d.sources || []).length > 1 || !d.extra_sites) return '';
  return ` <span class="muted" title="AutoTempest also sees this car on other sites">${escapeHtml(d.extra_sites)}</span>`;
}
function sourceCell(d) {
  const sources = d.sources || [];
  if (sources.length > 1) {
    return sources.map(s => {
      const link = safeUrl(s.link);
      const label = escapeHtml(sourceLabel(s));
      return link ? `<a class="view-link" href="${escapeHtml(link)}" target="_blank" rel="noopener">${label}</a>` : label;
    }).join(' ');
  }
  return escapeHtml(d.site_code) + extraNote(d);
}
function fmtMiles(m) { return m == null ? 'N/A' : m.toLocaleString() + ' mi.'; }
function urlYears(u, i) {
  try {
    const q = new URL(u).searchParams, lo = q.get('minyear'), hi = q.get('maxyear');
    if (lo && hi) return lo === hi ? lo : lo + '–' + hi;
  } catch (e) { /* not a URL */ }
  return String(i + 1);
}

const ESC_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ESC_MAP[c]);
}
function safeUrl(u) { return /^https?:\/\//i.test(u || '') ? u : ''; }
function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}
function numOrNull(v) {
  if (v == null) return null;
  const s = String(v).replace(/[$,\s]/g, '');
  if (s === '') return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}
function colorForYear(i, n) {
  const hue = n <= 1 ? 200 : Math.round(220 - (i / (n - 1)) * 220);
  return `hsl(${hue}, 70%, 60%)`;
}

// ---------- fuzzy matching (lazy tokenization) ----------
function wordsOf(s) { return (s || '').toLowerCase().match(/[a-z0-9]+/g) || []; }

function editDistance(a, b, max) {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    let rowMin = i;
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      const v = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
      cur.push(v);
      if (v < rowMin) rowMin = v;
    }
    if (rowMin > max) return max + 1;
    prev = cur;
  }
  return prev[b.length];
}

// 0 = no match, 1 = typo-tolerant, 2 = substring, 3 = whole word
function matchStrength(text, words, token) {
  if (!token) return 0;
  if (words.includes(token)) return 3;
  if (text.includes(token)) return 2;
  if (token.length >= 5) {
    for (const w of words) if (editDistance(w, token, 1) <= 1) return 1;
  }
  return 0;
}

const COLOR_WORDS = [
  ['Black', /\b(black|nero|noir|obsidian|onyx|ebony|schwarz)\b/],
  ['White', /\b(white|bianco|blanc|polar|diamond white|glacier)\b/],
  ['Gray', /\b(gr[ae]y|grigio|graphite|gunmetal|selenite|magno|chalk|crayon|nardo|charcoal|slate|tungsten)\b/],
  ['Silver', /\b(silver|argento|iridium|platinum silver)\b/],
  ['Red', /\b(red|rosso|rouge|burgundy|maroon|crimson|tango)\b/],
  ['Blue', /\b(blue|blu|azzurro|navy|cobalt|sepang|ascari|kyanite)\b/],
  ['Green', /\b(green|verde|olive|emerald|british racing|sage)\b/],
  ['Yellow', /\b(yellow|giallo|amarillo)\b/],
  ['Orange', /\b(orange|arancio|arancione)\b/],
  ['Brown/Tan', /\b(brown|bronze|beige|tan|marrone|copper|desert sand)\b/],
  ['Gold', /\b(gold|oro|champagne)\b/],
  ['Purple', /\b(purple|viola|violet)\b/],
];

function detectColor(row) {
  const text = ((row.title || '') + ' ' + (row.description || '')).toLowerCase();
  let best = null, bestAt = Infinity;
  for (const [name, re] of COLOR_WORDS) {
    const m = text.match(re);
    if (m && m.index < bestAt) { best = name; bestAt = m.index; }
  }
  return best || 'Unknown';
}

function prepRow(row) {
  if (!row.color) row.color = detectColor(row);
  row._specs = detectSpecs(row);
  row.pct_msrp = row.msrp && row.price != null ? Math.round((row.price / row.msrp - 1) * 1000) / 10 : null;
  return row;
}

function ensureRowSearch(row) {
  if (row._text != null) return;
  row._title = (row.title || '').toLowerCase();
  row._titleWords = wordsOf(row._title);
  row._text = [row.title, row.dealer, row.city, row.description, row.site_code, row.vin || '', row.year].join(' ').toLowerCase();
  row._words = wordsOf(row._text);
}

function altStrength(text, words, alt) {
  const parts = alt.split(/\s+/).filter(Boolean);
  if (parts.length <= 1) return matchStrength(text, words, alt);
  let min = 3;
  for (const p of parts) {
    const s = matchStrength(text, words, p);
    if (!s) return 0;
    if (s < min) min = s;
  }
  return min;
}

function scoreRow(row, tokens, alts) {
  if (!tokens.length) return null;
  ensureRowSearch(row);
  let total = 0;
  for (const t of tokens) {
    let best = 0;
    for (const alt of (alts[t] || [t])) {
      const inTitle = altStrength(row._title, row._titleWords, alt);
      const inText = altStrength(row._text, row._words, alt) * 0.6;
      best = Math.max(best, inTitle, inText);
    }
    total += best;
  }
  return Math.round((total / (3 * tokens.length)) * 100);
}

// ---------- market model (fast single-pass XtX + Gauss-Jordan inverse) ----------
const SPEC_TERMS = [
  ['Platinum', /\bplatinum\b/, { title: true, display: true, group: 'trim' }],
  ['Limited', /\blimited\b/, { title: true, group: 'trim' }],
  ['King Ranch', /\bking ranch\b/, { title: true, group: 'trim' }],
  ['Premium', /\bpremium\b/, { title: true, display: true, group: 'trim' }],
  ['Luxury', /\bluxury\b/, { title: true, display: true, group: 'trim' }],
  ['Overtrail', /\bovertrail\b/, { title: true, display: true, group: 'trim' }],
  ['Dynamic', /\bdynamic\b/, { title: true, display: true, group: 'trim' }],
  ['Autobiography', /\bautobiography\b/, { title: true, display: true, group: 'trim' }],
  ['First Edition', /\bfirst edition\b/, { title: true, display: true }],
  ['Edition 1', /\bedition 1\b/, { title: true, display: true }],
  ['Final Edition', /\bfinal edition\b/, { title: true, display: true }],
  ['S model', /63 ?s\b/, { title: true, display: true }],
  ['Coupe', /\bcoupe\b/, { title: true, display: true }],
  ['P400', /\bp400\b/, { title: true, display: true, group: 'engine' }],
  ['Performance', /\bperformance\b/],
  ['Manufaktur', /\bmanufaktur\b/],
  ['Night package', /\bnight (package|edition)\b/],
  ['Grand Edition', /\bgrand edition\b/],
  ['Carbon', /\bcarbon\b/],
  ['Ceramic brakes', /\bceramic\b/],
  ['Assetto Fiorano', /\bassetto\b|\bfiorano\b/],
  ['Spider', /\bspider\b/],
  ['Tremor', /\btremor\b/],
  ['High Output', /\bhigh output\b/],
  ['P530 V8', /\bp530\b/, { group: 'engine' }],
  ['PPF', /\bppf\b|paint protection film/],
  ['Certified pre-owned', /\bcertified\b|\bcpo\b/],
];
const MIN_SPEC_COUNT = 4;

const SPEC_GROUP = Object.fromEntries(SPEC_TERMS.map(([name, , o]) => [name, (o && o.group) || name]));
TAG_GROUPS.forEach(g => g.names.forEach(n => { SPEC_GROUP[n] = g.exclusive ? 'tag:' + g.key : n; }));

function groupSpecs(selected) {
  const groups = {};
  for (let i = 0; i < selected.length; i++) {
    const n = selected[i], g = SPEC_GROUP[n];
    (groups[g] = groups[g] || []).push(n);
  }
  return Object.values(groups);
}

function specsMatchGroups(groups, specs) {
  for (let i = 0; i < groups.length; i++) {
    const any = groups[i];
    let ok = false;
    for (let j = 0; j < any.length; j++) {
      if (specs.includes(any[j])) { ok = true; break; }
    }
    if (!ok) return false;
  }
  return true;
}

function detectSpecs(row) {
  if (TAG_GROUPS.length) return row.tags || [];
  const title = (row.title || '').toLowerCase();
  const text = title + ' ' + (row.description || '').toLowerCase();
  return SPEC_TERMS.filter(([, re, o]) => re.test(o && o.title ? title : text)).map(([name]) => name);
}

// Single augmented Gauss-Jordan elimination on [A | I | b] -> solves beta and A^-1 together in O(p^3).
function invertAndSolve(A, b) {
  const n = b.length;
  const cols = 2 * n + 1;
  const M = new Array(n);
  for (let i = 0; i < n; i++) {
    const row = new Float64Array(cols);
    for (let j = 0; j < n; j++) row[j] = A[i][j];
    row[n + i] = 1;
    row[2 * n] = b[i];
    M[i] = row;
  }
  for (let c = 0; c < n; c++) {
    let p = c, maxv = Math.abs(M[c][c]);
    for (let r = c + 1; r < n; r++) {
      const av = Math.abs(M[r][c]);
      if (av > maxv) { maxv = av; p = r; }
    }
    if (maxv < 1e-12) return null;
    if (p !== c) { const tmp = M[c]; M[c] = M[p]; M[p] = tmp; }
    const piv = M[c][c], pc = M[c];
    for (let j = c; j < cols; j++) pc[j] /= piv;
    for (let r = 0; r < n; r++) {
      if (r === c) continue;
      const pr = M[r], k = pr[c];
      if (k === 0) continue;
      for (let j = c; j < cols; j++) pr[j] -= k * pc[j];
    }
  }
  const beta = new Array(n), diagInv = new Array(n);
  for (let i = 0; i < n; i++) {
    beta[i] = M[i][2 * n];
    diagInv[i] = M[i][n + i];
  }
  return { beta, diagInv };
}

function ols(X, y) {
  const n = X.length, p = X[0].length;
  const XtX = Array.from({ length: p }, () => new Float64Array(p));
  const Xty = new Float64Array(p);
  for (let k = 0; k < n; k++) {
    const r = X[k], yk = y[k];
    for (let i = 0; i < p; i++) {
      const ri = r[i];
      if (ri === 0) continue;
      Xty[i] += ri * yk;
      const row = XtX[i];
      for (let j = i; j < p; j++) row[j] += ri * r[j];
    }
  }
  for (let i = 0; i < p; i++) {
    for (let j = 0; j < i; j++) XtX[i][j] = XtX[j][i];
  }
  const sol = invertAndSolve(XtX, Xty);
  if (!sol) return null;
  const { beta, diagInv } = sol;
  const resid = new Array(n);
  let ssRes = 0;
  for (let k = 0; k < n; k++) {
    const r = X[k];
    let pred = 0;
    for (let j = 0; j < p; j++) pred += r[j] * beta[j];
    const e = y[k] - pred;
    resid[k] = e;
    ssRes += e * e;
  }
  const s2 = ssRes / Math.max(1, n - p);
  return { beta, resid, se: diagInv.map(d => Math.sqrt(Math.max(0, s2 * d))) };
}

function quantile(sorted, q) {
  const i = (sorted.length - 1) * q, lo = Math.floor(i), hi = Math.ceil(i);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (i - lo);
}

const MIN_YEAR_COUNT = 3;

function tagModelSpecs(counts, common) {
  const out = [];
  TAG_GROUPS.forEach(g => {
    let names = (Array.isArray(g.model) ? g.model : g.model ? g.names : []).filter(common);
    if (g.model === 'ref' && names.length) {
      const base = names.reduce((a, n) => ((counts[n] || 0) > (counts[a] || 0) ? n : a), names[0]);
      names = names.filter(n => n !== base);
    }
    out.push(...names);
  });
  return out;
}

function buildModel(rows, maxSpecs = Infinity) {
  const priced = rows.filter(r => r.price != null && r.mileage != null && r.year != null);
  if (priced.length < 15) return null;

  const allYears = [...new Set(priced.map(r => r.year))].sort((a, b) => a - b);
  let genCut = null;
  for (let i = 1; i < allYears.length; i++) if (allYears[i] - allYears[i - 1] >= 5) genCut = allYears[i - 1];
  const current = priced.filter(r => genCut == null || r.year > genCut);

  const yearCounts = {};
  current.forEach(r => { yearCounts[r.year] = (yearCounts[r.year] || 0) + 1; });
  const years = Object.keys(yearCounts).map(Number).filter(y => yearCounts[y] >= MIN_YEAR_COUNT).sort((a, b) => a - b);
  const thinYears = Object.keys(yearCounts).map(Number).filter(y => yearCounts[y] < MIN_YEAR_COUNT).sort((a, b) => a - b);
  const yearSet = new Set(years);
  const data = current.filter(r => yearSet.has(r.year));
  if (data.length < 15) return null;
  const baseYear = years.reduce((a, y) => (yearCounts[y] > yearCounts[a] ? y : a), years[0]);

  const specCounts = {};
  data.forEach(r => r._specs.forEach(n => { specCounts[n] = (specCounts[n] || 0) + 1; }));
  const common = name => {
    const n = specCounts[name] || 0;
    return n >= MIN_SPEC_COUNT && n <= data.length - MIN_SPEC_COUNT;
  };
  const specs = (TAG_GROUPS.length ? tagModelSpecs(specCounts, common)
    : SPEC_TERMS.filter(([, , o]) => !(o && o.display)).map(([name]) => name).filter(common)).slice(0, maxSpecs);
  const retry = () => (specs.length ? buildModel(rows, specs.length - 1) : null);

  const terms = [{ key: 'const', f: () => 1 }];
  years.filter(y => y !== baseYear).forEach(y => terms.push({ key: 'year', year: y, f: r => +(r.year === y) }));
  terms.push({ key: 'miles', label: 'Each 10,000 miles', f: r => r.mileage / 10000 });
  specs.forEach(name => terms.push({ key: 'spec', label: name, spec: name, f: r => +r._specs.includes(name) }));

  const design = r => terms.map(t => t.f(r));
  const dataDesign = data.map(design);
  const dataLogP = data.map(r => Math.log(r.price));
  const dot = (vec, beta) => { let s = 0; for (let j = 0; j < beta.length; j++) s += vec[j] * beta[j]; return s; };

  let fitIdx = data.map((_, i) => i), fit = null, outliers = new Set();
  for (let pass = 0; pass < 3; pass++) {
    if (fitIdx.length < terms.length + 8) return retry();
    const X = fitIdx.map(i => dataDesign[i]);
    const y = fitIdx.map(i => dataLogP[i]);
    fit = ols(X, y);
    if (!fit) return retry();
    const absRes = fit.resid.map(Math.abs).sort((a, b) => a - b);
    const cutoff = Math.max(3 * 1.4826 * quantile(absRes, 0.5), 0.2);
    const next = new Set();
    for (let i = 0; i < data.length; i++) {
      if (Math.abs(dataLogP[i] - dot(dataDesign[i], fit.beta)) > cutoff) next.add(data[i]);
    }
    if (next.size === outliers.size && [...next].every(r => outliers.has(r))) break;
    outliers = next;
    fitIdx = [];
    for (let i = 0; i < data.length; i++) if (!outliers.has(data[i])) fitIdx.push(i);
  }

  const fitRows = fitIdx.map(i => data[i]);
  const y = fitIdx.map(i => dataLogP[i]);
  const yBar = y.reduce((s, v) => s + v, 0) / y.length;
  const ssTot = y.reduce((s, v) => s + (v - yBar) ** 2, 0);
  const ssRes = fit.resid.reduce((s, v) => s + v * v, 0);
  const res = [...fit.resid].sort((a, b) => a - b);
  const sortedBy = (list, f) => list.map(f).sort((a, b) => a - b);

  const byYear = years.map(yr => {
    const list = fitRows.filter(r => r.year === yr);
    const prices = sortedBy(list, r => r.price), miles = sortedBy(list, r => r.mileage);
    return {
      year: yr, n: list.length,
      medPrice: quantile(prices, 0.5), lo: quantile(prices, 0.1), hi: quantile(prices, 0.9),
      medMiles: quantile(miles, 0.5),
    };
  });

  return {
    terms, beta: fit.beta, se: fit.se, genCut, specs, years, thinYears, yearCounts, outliers, byYear,
    n: fitRows.length, r2: ssTot ? 1 - ssRes / ssTot : 0,
    typicalPrice: quantile(sortedBy(fitRows, r => r.price), 0.5),
    medianMiles: quantile(sortedBy(fitRows, r => r.mileage), 0.5),
    resLo: quantile(res, 0.1), resHi: quantile(res, 0.9),
    spread: quantile(res.map(Math.abs).sort((a, b) => a - b), 0.5),
    covers: r => r.year != null && yearSet.has(r.year),
    predict: r => Math.exp(dot(design(r), fit.beta)),
  };
}

function applyModel(tab) {
  const m = tab._model = buildModel(tab.rows);
  tab.rows.forEach(r => {
    r.expected = null; r.vs_market = null; r._outlier = false; r._skip = '';
    if (!m || r.year == null || r.mileage == null) return;
    if (m.genCut != null && r.year <= m.genCut) { r._skip = 'older generation'; return; }
    if (!m.covers(r)) { r._skip = 'too few comps'; return; }
    r.expected = Math.round(m.predict(r) / 100) * 100;
    if (r.price != null) {
      r.vs_market = Math.round((r.price / r.expected - 1) * 1000) / 10;
      r._outlier = m.outliers.has(r);
    }
  });
}

function fmtPct(v, digits = 0) {
  const mag = Math.abs(v).toFixed(digits);
  if (Number(mag) === 0) return (0).toFixed(digits) + '%';
  return (v > 0 ? '+' : '−') + mag + '%';
}
function fmtDollarDelta(v) {
  return (v > 0 ? '+' : v < 0 ? '−' : '') + '$' + Math.abs(Math.round(v / 100) * 100).toLocaleString();
}

function vsMarketCell(d) {
  if (d._skip) return `<span class="muted" title="Not compared: ${d._skip === 'older generation' ? 'different generation from the rest of this search' : 'fewer than ' + MIN_YEAR_COUNT + ' same-year listings'}">${d._skip}</span>`;
  if (d.vs_market == null) return '<span class="muted">–</span>';
  const cls = d.vs_market <= -5 ? 'below' : d.vs_market >= 5 ? 'above' : 'muted';
  return `<span class="${cls}">${fmtPct(d.vs_market)}</span>${d._outlier ? ' <span class="badge outlier" title="Too far from the model to trust; left out of the fit">check</span>' : ''}`;
}

function msrpCell(d) {
  if (!d.msrp) return '<span class="muted">–</span>';
  const src = d.msrp_source === 'cargurus' ? 'Dealer-reported MSRP on CarGurus' : 'MSRP quoted in the listing description';
  const pct = d.pct_msrp != null ? ` <span class="${d.pct_msrp < 0 ? 'below' : 'muted'}">${fmtPct(d.pct_msrp)}</span>` : '';
  return `<span title="${src}">${fmtPrice(d.msrp)}</span>${pct}`;
}

function msrpSummary(rows) {
  const pcts = rows.filter(r => r.pct_msrp != null).map(r => r.pct_msrp).sort((a, b) => a - b);
  return pcts.length ? { n: pcts.length, med: quantile(pcts, 0.5) } : null;
}

function yearSummaries(rows) {
  const groups = new Map();
  rows.forEach(r => {
    const year = r.year ?? null;
    if (!groups.has(year)) groups.set(year, []);
    groups.get(year).push(r);
  });
  return [...groups].sort(([a], [b]) => a == null ? 1 : b == null ? -1 : a - b).map(([year, list]) => {
    const prices = list.map(r => r.price).filter(v => v != null).sort((a, b) => a - b);
    const miles = list.map(r => r.mileage).filter(v => v != null).sort((a, b) => a - b);
    return { year, n: list.length, medPrice: prices.length ? quantile(prices, 0.5) : null,
      lo: prices.length ? quantile(prices, 0.1) : null, hi: prices.length ? quantile(prices, 0.9) : null,
      medMiles: miles.length ? quantile(miles, 0.5) : null, msrp: msrpSummary(list) };
  });
}

function renderYearSummary(tab, rows) {
  const box = tab._panel.querySelector('[data-role=analysis]');
  const tbody = box && box.querySelector('[data-role=yearrows]');
  if (!tbody) return;
  const m = tab._model;
  const price = (v, step) => v == null ? '–' : fmtPrice(Math.round(v / step) * step);
  box.querySelector('[data-role=analysiscount]').textContent = `${rows.length} of ${tab.rows.length} listings`;
  tbody.innerHTML = yearSummaries(rows).map(b => {
    const exp = m && b.medMiles != null && m.covers({ year: b.year })
      ? m.predict({ year: b.year, mileage: b.medMiles, _specs: [] }) : null;
    return `<tr><td>${b.year ?? 'Unknown'}</td><td>${b.n}</td><td>${price(b.medPrice, 100)}</td>
      <td>${price(b.lo, 500)} – ${price(b.hi, 500)}</td>
      <td>${b.medMiles == null ? '–' : fmtMiles(Math.round(b.medMiles / 100) * 100)}</td>
      <td>${price(exp, 500)}</td>
      <td>${b.msrp ? `${fmtPct(b.msrp.med)} <span class="muted">(${b.msrp.n})</span>` : '<span class="muted">–</span>'}</td></tr>`;
  }).join('') || '<tr><td colspan="7" class="empty">No listings match these filters.</td></tr>';
}

function renderAnalysis(tab) {
  const box = tab._panel.querySelector('[data-role=analysis]');
  if (!box) return;
  const m = tab._model;
  const yearTable = `<h3>By model year <span class="count" data-role="analysiscount"></span></h3>
    <table class="effects">
      <thead><tr><th class="no-sort">Year</th><th class="no-sort">Listings</th><th class="no-sort">Median ask</th><th class="no-sort">Middle 80%</th><th class="no-sort">Median miles</th><th class="no-sort">Expected at median miles</th><th class="no-sort" title="Median asking price vs the MSRP stated on the listing; count in brackets">Ask vs MSRP</th></tr></thead>
      <tbody data-role="yearrows"></tbody>
    </table>`;
  if (!m) {
    box.innerHTML = `<h2>Market analysis</h2><p class="muted">Not enough listings with price, year and mileage to model this market${tab.live ? ' yet' : ''}.</p>${yearTable}`;
    renderYearSummary(tab, tab._visibleRows || visibleRows(tab));
    return;
  }

  const effectRows = m.terms.map((t, j) => ({ t, b: m.beta[j], se: m.se[j] })).filter(e => e.t.key === 'miles' || e.t.key === 'spec').map(({ t, b, se }) => {
    const pct = (Math.exp(b) - 1) * 100;
    const solid = Math.abs(b) > 2 * se;
    return `<tr>
      <td>${escapeHtml(t.label)}</td>
      <td class="${pct < 0 ? 'neg' : 'pos'}">${fmtPct(pct, 1)}</td>
      <td>${fmtDollarDelta(m.typicalPrice * pct / 100)}</td>
      <td>${solid ? '<span class="sure">clear</span>' : '<span class="muted">weak / unclear</span>'}</td>
    </tr>`;
  }).join('');

  const left = [];
  if (m.genCut != null) left.push(`${tab.rows.filter(r => r.year != null && r.year <= m.genCut).length} older-generation cars (${m.genCut} and earlier)`);
  if (m.thinYears.length) left.push(`${m.thinYears.map(y => `${y} (${m.yearCounts[y]})`).join(', ')}: too few same-year listings`);
  if (m.outliers.size) left.push(`${m.outliers.size} priced far off their year's market, flagged <span class="badge outlier">check</span>`);

  const fitWord = m.r2 >= 0.7 ? 'explain most of' : m.r2 >= 0.4 ? 'explain a fair share of' : 'explain only a small part of';
  const yearOpts = m.years.map(y => `<option${y === m.years[m.years.length - 1] ? ' selected' : ''}>${y}</option>`).join('');
  const specBoxes = m.specs.map(s => `<label class="check"><input type="checkbox" data-calc-spec="${escapeHtml(s)}"> ${escapeHtml(s)}</label>`).join('');

  box.innerHTML = `
    <h2>Market analysis</h2>
    <p class="lede">Each car is compared only with <b>same-model-year</b> listings, adjusted for miles${m.specs.length ? ' and the specs below' : ''}. Market benchmark built from <b>${m.n}</b> listings across ${m.years.join(', ')} in the full search.
      Year, miles${m.specs.length ? ' and specs' : ''} ${fitWord} the price differences (R² ${m.r2.toFixed(2)}); half of listings sit within <b>±${Math.round((Math.exp(m.spread) - 1) * 100)}%</b> of their expected price. The rest is options, condition, color and dealer pricing the listings don't show.</p>
    <p class="footnote">MSRP is shown only where the listing states it (${tab.rows.filter(r => r.msrp).length} of ${tab.rows.length} listings here): the dealer-reported sticker on CarGurus, which it gives for new cars, or a figure quoted in the description. Nothing is estimated.</p>
    ${left.length ? `<p class="footnote">Left out of the comparison: ${left.join('; ')}.</p>` : ''}
    <div class="analysis-grid">
      <div>
        ${yearTable}
        <h3>What moves the price within a year</h3>
        <table class="effects">
          <thead><tr><th class="no-sort">Factor</th><th class="no-sort">Effect</th><th class="no-sort">On a ${fmtPrice(Math.round(m.typicalPrice / 1000) * 1000)} car</th><th class="no-sort">Signal</th></tr></thead>
          <tbody>${effectRows}</tbody>
        </table>
      </div>
      <div class="calc">
        <h3>What to expect</h3>
        <div class="filter-grid">
          <label>Year<select data-calc="year">${yearOpts}</select></label>
          <label>Miles<input data-calc="miles" inputmode="numeric"></label>
          <label>Miles / year after<input data-calc="perYear" inputmode="numeric" value="3000"></label>
        </div>
        ${specBoxes ? `<div class="checks">${specBoxes}</div>` : ''}
        <div class="calc-out" data-role="calcOut"></div>
      </div>
    </div>
    <p class="footnote">How this works: a regression of log price on model year (as separate groups), miles${m.specs.length ? ' and spec keywords found in titles/descriptions' : ''}, re-fit after setting aside listings priced far from their year's market. Descriptions are cut off by AutoTempest, so many options go undetected. "Vs market" in the table is each car's asking price against what the model expects for its year, miles and specs. Each VIN is one car; when several sites list it, the price used here is the lowest ask.</p>`;

  const yearSel = box.querySelector('[data-calc=year]'), milesIn = box.querySelector('[data-calc=miles]');
  const syncMiles = () => {
    if (milesIn.dataset.touched) return;
    const b = m.byYear.find(b => b.year === Number(yearSel.value));
    milesIn.value = Math.round((b ? b.medMiles : m.medianMiles) / 500) * 500;
  };
  milesIn.addEventListener('input', () => { milesIn.dataset.touched = '1'; });
  yearSel.addEventListener('change', syncMiles);
  syncMiles();

  const update = () => updateCalc(tab);
  box.querySelectorAll('[data-calc], [data-calc-spec]').forEach(el => {
    el.addEventListener('input', update);
    el.addEventListener('change', update);
  });
  update();
}

function updateCalc(tab) {
  const m = tab._model, box = tab._panel.querySelector('[data-role=analysis]');
  const year = Number(box.querySelector('[data-calc=year]').value);
  const miles = numOrNull(box.querySelector('[data-calc=miles]').value) ?? m.medianMiles;
  const perYear = numOrNull(box.querySelector('[data-calc=perYear]').value) ?? 0;
  const specs = [...box.querySelectorAll('[data-calc-spec]:checked')].map(el => el.dataset.calcSpec);
  const car = { year, mileage: miles, _specs: specs };

  const mid = m.predict(car);
  const lo = mid * Math.exp(m.resLo), hi = mid * Math.exp(m.resHi);
  const round = v => fmtPrice(Math.round(v / 500) * 500);

  let outlook;
  if (m.years.includes(year - 1)) {
    const later = m.predict({ year: year - 1, mileage: miles + perYear, _specs: specs });
    outlook = `<div class="stat"><span>In 12 months (+${perYear.toLocaleString()} mi)</span><b>${round(later)}</b><em>${fmtPct((later / mid - 1) * 100, 1)} · rough, based on today's gap between ${year} and ${year - 1} cars</em></div>`;
  } else {
    outlook = `<div class="stat"><span>In 12 months</span><b class="muted">–</b><em>No ${year - 1} listings to compare with, so no projection.</em></div>`;
  }

  box.querySelector('[data-role=calcOut]').innerHTML = `
    <div class="stat"><span>Expected asking price</span><b>${round(mid)}</b></div>
    <div class="stat"><span>Typical range (middle 80%)</span><b>${round(lo)} – ${round(hi)}</b></div>
    <div class="stat"><span>Strong buy below</span><b class="pos">${round(lo)}</b><em>cheaper than 9 in 10 comparable listings</em></div>
    ${outlook}`;
}

// ---------- tab state / filtering ----------
function newState(live) {
  return {
    showBat: false,
    area: null,
    bat: { days: 730, text: '', country: '', stock: true, matchSearch: true, adjust: false },
    sortKey: live ? 'score' : 'price',
    sortDir: live ? -1 : 1,
    filters: { yearMin: null, yearMax: null, priceMin: null, priceMax: null, milesMin: null, milesMax: null, deal: '', color: '', vs: '', text: '', specs: [] },
  };
}

function sortVal(row, key) {
  if (key === 'deal_rating') return DEAL_RANK[row.deal_rating] || null;
  const v = row[key];
  return v === '' ? null : v;
}

function sortRowsInPlace(rows, sortKey, sortDir) {
  rows.sort((a, b) => {
    const av = sortVal(a, sortKey), bv = sortVal(b, sortKey);
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === 'string') return av.localeCompare(bv) * sortDir;
    return (av - bv) * sortDir;
  });
}

// ---------- BaT sold overlay (O(N log N) market index + lazy search) ----------
const MODIFIED_RE = /\b(modified|tuned|renntech|weistec|capristo|brabus|mansory|novitec|stage [123]|aftermarket (turbo|supercharger|exhaust|tune)|built engine|widebody)\b/i;
const DAY_MS = 86400000;

function prepBatRow(row) {
  if (typeof row._modified !== 'boolean') {
    const full = ((row.title || '') + ' ' + (row.description || '')).toLowerCase();
    row._modified = MODIFIED_RE.test(full);
  }
  row._soldMs = Date.parse(row.posted_date) || null;
  return row;
}

function ensureBatSearch(row) {
  if (row._title != null) return;
  row._title = (row.title || '').toLowerCase();
  row._titleWords = wordsOf(row._title);
  row._full = (row._title + ' ' + (row.tags || []).join(' ') + ' ' + (row.description || '')).toLowerCase();
  row._fullWords = wordsOf(row._full);
}

function hasToken(text, words, t) {
  return t.length <= 2 ? words.includes(t) : matchStrength(text, words, t) > 0;
}

function visibleBatRows(tab) {
  const f = tab._state.filters, b = tab._state.bat;
  const within = (v, lo, hi) => v != null && (lo == null || v >= lo) && (hi == null || v <= hi);
  const tokens = b.text ? b.text.toLowerCase().split(/\s+/).filter(Boolean) : [];
  const include = tokens.filter(t => !t.startsWith('-'));
  const exclude = tokens.filter(t => t.startsWith('-') && t.length > 1).map(t => t.slice(1));
  const needText = include.length > 0 || exclude.length > 0;
  const cutoff = b.days ? NOW_MS - b.days * DAY_MS : null;
  const sr = tab._range;
  const specGroups = TAG_GROUPS.length && f.specs.length ? groupSpecs(f.specs) : null;
  return (tab.bat || []).filter(r => {
    if (r.price == null || r.mileage == null) return false;
    if (b.matchSearch && sr && !(within(r.year, sr.yMin, sr.yMax) && (sr.mMax == null || r.mileage <= sr.mMax))) return false;
    if ((f.yearMin != null || f.yearMax != null) && !within(r.year, f.yearMin, f.yearMax)) return false;
    if ((f.priceMin != null || f.priceMax != null) && !within(r.price, f.priceMin, f.priceMax)) return false;
    if ((f.milesMin != null || f.milesMax != null) && !within(r.mileage, f.milesMin, f.milesMax)) return false;
    if (!inArea(tab, r)) return false;
    if (specGroups && !specsMatchGroups(specGroups, r.tags || [])) return false;
    if (cutoff != null && (r._soldMs == null || r._soldMs < cutoff)) return false;
    if (b.country && r.city !== b.country) return false;
    if (b.stock && r._modified) return false;
    if (needText) {
      ensureBatSearch(r);
      if (!include.every(t => hasToken(r._title, r._titleWords, t))) return false;
      if (exclude.some(t => hasToken(r._full, r._fullWords, t))) return false;
    }
    return true;
  });
}

function median(nums) {
  const a = nums.filter(n => n != null).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : Math.round((a[m - 1] + a[m]) / 2);
}

function searchRange(rows) {
  let yMin = Infinity, yMax = -Infinity, mMax = -Infinity;
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    if (r.year != null) { if (r.year < yMin) yMin = r.year; if (r.year > yMax) yMax = r.year; }
    if (r.mileage != null && r.mileage > mMax) mMax = r.mileage;
  }
  if (!Number.isFinite(yMin)) return null;
  return { yMin, yMax, mMax: Number.isFinite(mMax) ? mMax : null };
}

function solve3(A, b) {
  const M = A.map((row, i) => [...row, b[i]]);
  for (let c = 0; c < 3; c++) {
    let piv = c;
    for (let r = c + 1; r < 3; r++) if (Math.abs(M[r][c]) > Math.abs(M[piv][c])) piv = r;
    [M[c], M[piv]] = [M[piv], M[c]];
    if (Math.abs(M[c][c]) < 1e-12) return null;
    for (let r = 0; r < 3; r++) {
      if (r === c) continue;
      const f = M[r][c] / M[c][c];
      for (let k = c; k < 4; k++) M[r][k] -= f * M[c][k];
    }
  }
  return M.map((row, i) => row[3] / row[i]);
}

function lowerBound(arr, target) {
  let lo = 0, hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (arr[mid] < target) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

function computeMarketIndex(tab) {
  const pts = (tab.bat || []).filter(r => !r._modified && r.price && r.mileage != null && r.year != null && r._soldMs);
  tab._market = null;
  if (pts.length < 12) return;
  let ySum = 0, yMin = Infinity, yMax = -Infinity, mMax = -Infinity;
  for (let i = 0; i < pts.length; i++) {
    const r = pts[i];
    ySum += r.year;
    if (r.year < yMin) yMin = r.year;
    if (r.year > yMax) yMax = r.year;
    if (r.mileage > mMax) mMax = r.mileage;
  }
  const yBar = ySum / pts.length;
  const A = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
  const bv = [0, 0, 0];
  for (let k = 0; k < pts.length; k++) {
    const r = pts[k], x1 = r.mileage / 1e4, x2 = r.year - yBar, lp = Math.log(r.price);
    A[0][0] += 1; A[0][1] += x1; A[0][2] += x2;
    A[1][1] += x1 * x1; A[1][2] += x1 * x2;
    A[2][2] += x2 * x2;
    bv[0] += lp; bv[1] += x1 * lp; bv[2] += x2 * lp;
  }
  A[1][0] = A[0][1]; A[2][0] = A[0][2]; A[2][1] = A[1][2];
  const beta = solve3(A, bv);
  if (!beta) return;

  for (let k = 0; k < pts.length; k++) {
    const r = pts[k];
    r._resid = Math.log(r.price) - (beta[0] + beta[1] * (r.mileage / 1e4) + beta[2] * (r.year - yBar));
  }

  // Sort by sale time and build prefix sums for O(log N) window averages.
  pts.sort((a, b) => a._soldMs - b._soldMs);
  const times = new Float64Array(pts.length);
  const pref = new Float64Array(pts.length + 1);
  for (let i = 0; i < pts.length; i++) {
    times[i] = pts[i]._soldMs;
    pref[i + 1] = pref[i] + pts[i]._resid;
  }
  const meanResid = (lo, hi) => {
    const l = lowerBound(times, lo), r = lowerBound(times, hi), n = r - l;
    return n ? { v: (pref[r] - pref[l]) / n, n } : { v: null, n: 0 };
  };

  const recent = meanResid(NOW_MS - 365 * DAY_MS, NOW_MS + DAY_MS);
  const prior = meanResid(NOW_MS - 730 * DAY_MS, NOW_MS - 365 * DAY_MS);
  if (recent.n < 3) return;

  (tab.bat || []).forEach(r => {
    r._adj = null;
    if (!r._soldMs || r._soldMs >= NOW_MS - 365 * DAY_MS) { r._adj = 1; return; }
    for (const half of [183, 365]) {
      const local = meanResid(r._soldMs - half * DAY_MS, r._soldMs + half * DAY_MS);
      if (local.n >= 5) { r._adj = Math.exp(recent.v - local.v); return; }
    }
  });
  const level = recent.v;
  tab._market = {
    n: pts.length,
    trend: prior.n >= 3 ? Math.exp(recent.v - prior.v) - 1 : null,
    milesPct: Math.exp(beta[1]) - 1,
    yMin, yMax, mMax,
    predict: r => Math.exp(beta[0] + beta[1] * r.mileage / 1e4 + beta[2] * (r.year - yBar) + level),
  };
}

function batAlpha(ageDays) {
  return Math.max(0.25, Math.min(1, 1 - (ageDays - 180) / 900));
}
function pct(v) { return fmtPct(v * 100); }

function batPoints(tab) {
  const adjust = tab._state.bat.adjust && tab._market;
  return visibleBatRows(tab).map(d => {
    const now = adjust && d._adj ? Math.round(d.price * d._adj) : d.price;
    const restated = now !== d.price ? ` · ≈ ${fmtPrice(now)} in today's market` : '';
    return {
      x: d.mileage, y: now, title: d.title, link: d.link, date: d.posted_date,
      age: d._soldMs ? (NOW_MS - d._soldMs) / DAY_MS : 9999,
      dealer: `sold ${fmtPrice(d.price)} on ${d.posted_date} (BaT)${restated}`,
    };
  });
}

function applyBatValues(tab) {
  const m = tab._market;
  tab.rows.forEach(r => {
    r.bat_value = null; r.vs_bat = null;
    if (!m || r.year == null || r.mileage == null) return;
    if (r.year < m.yMin || r.year > m.yMax || r.mileage > m.mMax * 1.1) return;
    r.bat_value = Math.round(m.predict(r) / 500) * 500;
    if (r.price != null) r.vs_bat = r.price / r.bat_value - 1;
  });
}

function batValueCell(d) {
  if (d.bat_value == null) return '<span class="muted">–</span>';
  const gap = d.vs_bat != null ? `<small>ask ${pct(d.vs_bat)}</small>` : '';
  return `${fmtPrice(d.bat_value)}${gap}`;
}

function kpi(label, value, note, cls = '') {
  return `<div class="kpi ${cls}"><span>${label}</span><b>${value}</b>${note ? `<em>${note}</em>` : ''}</div>`;
}

function renderKpis(tab, visible, batPts) {
  const el = tab._panel.querySelector('[data-role=kpis]');
  const rows = (visible || visibleRows(tab)).filter(r => r.price != null);
  if (!rows.length) { el.innerHTML = ''; return; }
  const cards = [];
  const askMed = median(rows.map(r => r.price)), milesMed = median(rows.map(r => r.mileage));
  let yMin = Infinity, yMax = -Infinity;
  let best = null;
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    if (r.year) { if (r.year < yMin) yMin = r.year; if (r.year > yMax) yMax = r.year; }
    if (r.vs_market != null && !r._outlier && (!best || r.vs_market < best.vs_market)) best = r;
  }
  cards.push(kpi('For sale', rows.length.toLocaleString(), `median ask ${fmtPrice(askMed)}`));
  cards.push(kpi('Median miles', milesMed != null ? milesMed.toLocaleString() : '–', Number.isFinite(yMin) ? `model years ${yMin}–${yMax}` : ''));

  if (best) {
    const link = safeUrl(best.link);
    const note = `${best.year ?? ''} · ${fmtPrice(best.price)} · ${fmtMiles(best.mileage)}`;
    cards.push(kpi('Best vs market', `<span class="${best.vs_market < 0 ? 'below' : ''}">${fmtPct(best.vs_market)}</span>`,
      link ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener" title="${escapeHtml(best.title)}">${escapeHtml(note)} &#8599;</a>` : escapeHtml(note)));
  }

  if (tab.bat && tab.bat.length) {
    const pts = batPts || batPoints(tab);
    const days = tab._state.bat.days;
    const win = days ? (days % 365 === 0 ? `${days / 365 * 12} mo` : `${Math.round(days / 30)} mo`) : 'all time';
    if (pts.length) {
      const soldMed = median(pts.map(d => d.y)), soldMiles = median(pts.map(d => d.x));
      cards.push(kpi(`BaT sold · ${win}`, pts.length.toLocaleString(), `median ${fmtPrice(soldMed)} at ${fmtMiles(soldMiles)}`, 'bat'));
      cards.push(pts.length >= 3
        ? kpi('Asking vs sold', pct(askMed / soldMed - 1), 'median ask vs median BaT sale', 'bat')
        : kpi('Asking vs sold', '–', `only ${pts.length} BaT sale; too few to compare`, 'bat'));
    } else {
      cards.push(kpi(`BaT sold · ${win}`, '0', 'no matching sales; widen the BaT filters', 'bat'));
    }
    const m = tab._market;
    cards.push(kpi('BaT market · 12 mo', m && m.trend != null ? pct(m.trend) : '–',
      m && m.trend != null ? 'same miles and year, vs prior 12 mo' : 'too few recent BaT sales', 'bat'));
  }
  el.innerHTML = cards.join('');
}

function visibleRows(tab) {
  const f = tab._state.filters;
  const textTokens = f.text ? f.text.toLowerCase().split(/\s+/).filter(Boolean) : [];
  const dealMin = f.deal ? DEAL_RANK[f.deal] : 0;
  const specGroups = f.specs.length ? groupSpecs(f.specs) : null;
  const within = (v, lo, hi) => v != null && (lo == null || v >= lo) && (hi == null || v <= hi);

  const rows = tab.rows.filter(r => {
    if ((f.yearMin != null || f.yearMax != null) && !within(r.year, f.yearMin, f.yearMax)) return false;
    if ((f.priceMin != null || f.priceMax != null) && !within(r.price, f.priceMin, f.priceMax)) return false;
    if ((f.milesMin != null || f.milesMax != null) && !within(r.mileage, f.milesMin, f.milesMax)) return false;
    if (dealMin && (DEAL_RANK[r.deal_rating] || 0) < dealMin) return false;
    if (f.color && r.color !== f.color) return false;
    if (specGroups && !specsMatchGroups(specGroups, r._specs)) return false;
    if (f.vs) {
      if (r.vs_market == null || r._outlier) return false;
      if (f.vs === 'below' && r.vs_market > -5) return false;
      if (f.vs === 'below10' && r.vs_market > -10) return false;
      if (f.vs === 'above' && r.vs_market < 5) return false;
    }
    if (textTokens.length) {
      ensureRowSearch(r);
      for (const t of textTokens) if (!matchStrength(r._text, r._words, t)) return false;
    }
    if (!inArea(tab, r)) return false;
    return true;
  });

  sortRowsInPlace(rows, tab._state.sortKey, tab._state.sortDir);
  return rows;
}

// ---------- rendering ----------
function panelHTML(tab) {
  const searchBar = tab.live ? `
    <div class="panel">
      <div class="search-row">
        <input class="search-input" data-role="q" type="text" autocomplete="off"
               placeholder='Try "930 porsche white", "g wagon black 2024" or "997 gt3 silver"'>
        <input class="zip-input" data-role="zip" type="text" value="${escapeHtml(DEFAULT_ZIP)}" maxlength="5" inputmode="numeric" title="ZIP code (used for distance)">
        <button class="btn-primary" data-role="go">Search</button>
      </div>
      <div class="status" data-role="status">Runs a live AutoTempest search (10-20 seconds). Needs the local server: ../scanner/.venv/bin/python3 search_server_v2.py (in 911s)</div>
      <div class="chips" data-role="chips"></div>
    </div>` : '';

  const heads = COLS.filter(c => !c.live || tab.live).map(c =>
    c.key ? `<th data-key="${c.key}"${c.r ? ' class="r"' : ''}${c.tip ? ` title="${escapeHtml(c.tip)}"` : ''}>${c.label}<span class="arrow"></span></th>` : `<th class="no-sort">${c.label}</th>`
  ).join('');

  const hasBat = (tab.bat && tab.bat.length) || tab.bat_count > 0;
  return `
    <div class="tab-head">
      <div class="tab-title">
        <h2>${escapeHtml(tab.live ? 'Live search' : tab.title)}</h2>
        <div class="asof" data-role="asof"></div>
        <div class="data-warn" data-role="datawarn" role="status" hidden></div>
      </div>
      <div class="at-links" data-role="atlinks"></div>
    </div>
    <div class="kpis" data-role="kpis"></div>
    ${searchBar}
    <div class="panel">
      <div class="card-head"><h3>Filters</h3><span class="count" data-role="count"></span></div>
      <div class="filter-grid">
        <label>Year<span class="pair"><input data-f="yearMin" inputmode="numeric" placeholder="from"> to <input data-f="yearMax" inputmode="numeric" placeholder="to"></span></label>
        <label>Price<span class="pair"><input data-f="priceMin" inputmode="numeric" placeholder="min"> to <input data-f="priceMax" inputmode="numeric" placeholder="max"></span></label>
        <label>Mileage<span class="pair"><input data-f="milesMin" inputmode="numeric" placeholder="min"> to <input data-f="milesMax" inputmode="numeric" placeholder="max"></span></label>
        <label>Deal rating<select data-f="deal"><option value="">Any</option><option value="good">Good or better</option><option value="great">Great only</option></select></label>
        <label>Color<select data-f="color" data-role="color"><option value="">Any</option></select></label>
        <label>Vs market<select data-f="vs"><option value="">Any</option><option value="below">5%+ below</option><option value="below10">10%+ below</option><option value="above">5%+ above</option></select></label>
        <label class="grow">Refine (fuzzy)<input class="wide" data-f="text" type="text" placeholder="title, dealer, city, description..."></label>
        <button class="btn-ghost" data-role="reset">Reset filters</button>
      </div>
      <div class="spec-row" data-role="specs" hidden></div>
    </div>
    <div class="panel">
      <div class="card-head">
        <div><h3>Price vs mileage</h3><span class="sub">Colored by model year &middot; drag to filter the chart and tables &middot; click a point to open the listing</span></div>
        <div class="chart-tools">
          <button class="btn-ghost sm" data-role="resetview" hidden title="Clear the chart selection; your other filters stay as they are">&#8634; Reset chart filter</button>
          ${hasBat ? `<label class="switch"><input type="checkbox" role="switch" data-role="bat"> Bring a Trailer sold <span class="tri">&#9651;</span></label>` : ''}
        </div>
      </div>
      ${hasBat ? `
      <div class="filter-grid bat-filters" data-role="batfilters" hidden>
        <label>Sold within<select data-bf="days">
          <option value="180">6 months</option><option value="365">12 months</option>
          <option value="730" selected>24 months</option><option value="1095">3 years</option><option value="">All time</option>
        </select></label>
        <label class="grow">BaT title has<input class="wide" data-bf="text" type="text" placeholder='e.g. "gt3" or "-cabriolet" to exclude'></label>
        <label>Location<select data-bf="country"><option value="">Anywhere</option><option value="US">US only</option></select></label>
        <label class="check"><input type="checkbox" data-bf="stock" checked> Hide modified/tuned</label>
        <label class="check" data-role="matchwrap" title="Only BaT cars inside this search's model years and mileage"><input type="checkbox" data-bf="matchSearch" checked> <span data-role="matchlabel">Match this search</span></label>
        <label class="check" data-role="adjustwrap"><input type="checkbox" data-bf="adjust"> Restate older sales in today's market</label>
      </div>` : ''}
      <div class="sel-bar" data-role="sel" hidden></div>
      <div class="chartWrap"><canvas data-role="canvas"></canvas><div class="brush" data-role="brush" hidden></div></div>
    </div>
    <div class="panel analysis" data-role="analysis"></div>
    <div class="panel">
      <div class="card-head"><div><h3>Listings</h3><span class="sub">Click a column to sort &middot; hover Market value or BaT value for how they're worked out</span></div><span class="count" data-role="listcount"></span></div>
      <div class="table-wrap" data-role="tablewrap">
        <table>
          <thead><tr>${heads}</tr></thead>
          <tbody data-role="tbody"></tbody>
        </table>
        <div class="table-more" data-role="tablemore" hidden>
          <span data-role="moreinfo"></span>
          <button type="button" class="btn-ghost sm" data-role="showmore">Show more</button>
          <button type="button" class="btn-ghost sm" data-role="showall">Show all</button>
        </div>
      </div>
    </div>`;
}

function renderAtLinks(tab) {
  const urls = (tab.urls || []).map(safeUrl).filter(Boolean);
  const atr = String(tab.autotrader_url || '').split(/\s+/).filter(Boolean).map(safeUrl).filter(Boolean);
  const tempest = urls.map((u, i) =>
    `<a class="at-link" href="${escapeHtml(u)}" target="_blank" rel="noopener">Open this search on AutoTempest${urls.length > 1 ? ' (' + urlYears(u, i) + ')' : ''} &#8599;</a>`
  );
  const trader = atr.map((u, i) =>
    `<a class="at-link" href="${escapeHtml(u)}" target="_blank" rel="noopener">Open this search on Autotrader${atr.length > 1 ? ' (' + (i + 1) + ')' : ''} &#8599;</a>`
  );
  tab._panel.querySelector('[data-role=atlinks]').innerHTML = tempest.concat(trader).join('');
}

function rowHTML(d, isLive) {
  const link = safeUrl(d.link);
  return `<tr>${isLive ? `<td>${d.score != null ? d.score + '%' : ''}</td>` : ''}<td>${d.year ?? 'N/A'}</td><td class="title-cell">${d.is_hot ? '<span class="hot">HOT</span> ' : ''}${link ? `<a class="title-link" href="${escapeHtml(link)}" target="_blank" rel="noopener">${escapeHtml(d.title)}</a>` : escapeHtml(d.title)}</td><td class="r">${priceCell(d)}</td><td class="r">${d.expected != null ? fmtPrice(d.expected) : '<span class="muted">–</span>'}</td><td class="r">${vsMarketCell(d)}</td><td class="r">${batValueCell(d)}</td><td class="r">${msrpCell(d)}</td><td class="r">${fmtMiles(d.mileage)}</td><td>${d.color === 'Unknown' ? '<span class="muted">?</span>' : escapeHtml(d.color)}</td><td>${escapeHtml(d.posted_date)}</td><td>${escapeHtml(d.city)}${d.distance ? ' <span class="muted">' + escapeHtml(d.distance) + '</span>' : ''}</td><td>${escapeHtml(d.dealer)}</td><td class="source-cell">${sourceCell(d)}</td><td class="vin-cell">${d.vin ? escapeHtml(d.vin) : '<span class="muted">–</span>'}</td><td>${link ? `<a class="view-link" href="${escapeHtml(link)}" target="_blank" rel="noopener">View</a>` : ''}</td></tr>`;
}

function updateMoreBar(tab) {
  const bar = tab._panel.querySelector('[data-role=tablemore]');
  const rows = tab._visibleRows || [];
  if (tab._shown >= rows.length) { bar.hidden = true; return; }
  const rem = rows.length - tab._shown;
  const next = Math.min(PAGE_SIZE, rem);
  bar.querySelector('[data-role=moreinfo]').textContent = `Showing ${tab._shown.toLocaleString()} of ${rows.length.toLocaleString()} listings`;
  bar.querySelector('[data-role=showmore]').textContent = `Show ${next} more`;
  bar.hidden = false;
}

function appendMoreRows(tab, count) {
  const rows = tab._visibleRows || [];
  if (tab._shown >= rows.length) return;
  const end = Math.min(rows.length, tab._shown + count);
  const tbody = tab._panel.querySelector('[data-role=tbody]');
  let buf = '';
  for (let i = tab._shown; i < end; i++) buf += rowHTML(rows[i], tab.live);
  tbody.insertAdjacentHTML('beforeend', buf);
  tab._shown = end;
  updateMoreBar(tab);
}

function renderTable(tab, rows) {
  const tbody = tab._panel.querySelector('[data-role=tbody]');
  const colSpan = COLS.filter(c => !c.live || tab.live).length;
  tab._visibleRows = rows;
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="${colSpan}" class="empty">${tab.rows.length ? 'No listings match these filters.' : (tab.live ? 'Run a search to see listings.' : 'No listings.')}</td></tr>`;
    tab._shown = 0;
  } else {
    const end = Math.min(rows.length, PAGE_SIZE);
    let buf = '';
    for (let i = 0; i < end; i++) buf += rowHTML(rows[i], tab.live);
    tbody.innerHTML = buf;
    tab._shown = end;
  }
  updateMoreBar(tab);
  tab._panel.querySelectorAll('th[data-key]').forEach(th => {
    const arrow = th.querySelector('.arrow');
    arrow.textContent = th.dataset.key === tab._state.sortKey ? (tab._state.sortDir === 1 ? ' ▲' : ' ▼') : '';
  });
}

function buildSpecChips(tab) {
  const box = tab._panel.querySelector('[data-role=specs]');
  const counts = {};
  tab.rows.forEach(r => r._specs.forEach(n => { counts[n] = (counts[n] || 0) + 1; }));
  const rank = n => ({ trim: 0, engine: 1 }[SPEC_GROUP[n]] ?? 2);
  const names = SPEC_TERMS.map(([n]) => n).filter(n => counts[n]).sort((a, b) => rank(a) - rank(b) || counts[b] - counts[a]);
  const sel = tab._state.filters.specs;
  const chip = n => `<button type="button" class="spec-chip" data-spec="${escapeHtml(n)}" aria-pressed="${sel.includes(n)}">${escapeHtml(n)}<i>${counts[n]}</i></button>`;
  let out = '';
  if (TAG_GROUPS.length) {
    out = TAG_GROUPS.map(g => {
      const list = g.names.filter(n => counts[n]);
      if (!list.length || (g.exclusive && list.length < 2)) return '';
      return `<div class="spec-line"><span>${escapeHtml(g.label)}</span>${list.map(chip).join('')}</div>`;
    }).join('');
  } else if (names.length) {
    out = '<span>Specs</span>';
    let last = null;
    names.forEach(n => {
      if (last != null && rank(n) !== last) out += '<span class="spec-sep" aria-hidden="true"></span>';
      last = rank(n);
      out += chip(n);
    });
  }
  if (!out) { box.hidden = true; box.innerHTML = ''; return; }
  box.classList.toggle('tagged', TAG_GROUPS.length > 0);
  box.innerHTML = out;
  box.hidden = false;
}

function syncSpecChips(tab) {
  const box = tab._panel.querySelector('[data-role=specs]');
  if (!box || box.hidden) return;
  const sel = tab._state.filters.specs;
  box.querySelectorAll('[data-spec]').forEach(b => {
    b.setAttribute('aria-pressed', String(sel.includes(b.dataset.spec)));
  });
}

function renderCount(tab, rows) {
  const f = tab._state.filters;
  const filtered = !!tab._state.area || Object.entries(f).some(([k, v]) => Array.isArray(v) ? v.length > 0 : v != null && v !== '');
  const text = `${rows.length} of ${tab.rows.length} listings` + (filtered && rows.length !== tab.rows.length ? ' (filters active)' : '');
  tab._panel.querySelectorAll('[data-role=count], [data-role=listcount]').forEach(el => { el.textContent = text; });
}

function renderChart(tab, rows, batPts) {
  tab._chartDirty = false;
  if (typeof Chart === 'undefined') return;

  const byYear = new Map();
  const unknown = [];
  for (let i = 0; i < rows.length; i++) {
    const d = rows[i];
    if (d.price == null || d.mileage == null) continue;
    const pt = { x: d.mileage, y: d.price, title: d.title, link: d.link, dealer: d.dealer, city: d.city, vin: d.vin, sources: d.sources, tags: d.tags };
    if (d.year == null) unknown.push(pt);
    else {
      let arr = byYear.get(d.year);
      if (!arr) { arr = []; byYear.set(d.year, arr); }
      arr.push(pt);
    }
  }

  const yearColor = y => colorForYear(tab._years.indexOf(y), tab._years.length);
  const years = [...byYear.keys()].sort((a, b) => a - b);
  const datasets = years.map(y => ({
    label: String(y),
    data: byYear.get(y),
    backgroundColor: yearColor(y),
    pointRadius: 5,
    pointHoverRadius: 8,
  }));
  if (unknown.length) {
    datasets.push({
      label: 'Unknown year',
      data: unknown,
      backgroundColor: 'hsl(0, 0%, 60%)',
      pointRadius: 5,
      pointHoverRadius: 8,
    });
  }
  if (tab.bat && tab.bat.length && tab._state.showBat) {
    const pts = batPts || batPoints(tab);
    const white = a => `rgba(255,255,255,${a})`;
    datasets.push({
      label: 'BaT sold',
      data: pts,
      pointStyle: 'triangle',
      backgroundColor: c => white(c.raw ? batAlpha(c.raw.age) * 0.15 : 0.08),
      borderColor: c => white(c.raw ? batAlpha(c.raw.age) : 1),
      borderWidth: 1.5,
      pointRadius: 7,
      pointHoverRadius: 10,
    });
  }

  if (tab._chart) {
    tab._chart.data.datasets = datasets;
    tab._chart.update('none');
    return;
  }

  tab._chart = new Chart(tab._panel.querySelector('[data-role=canvas]').getContext('2d'), {
    type: 'scatter',
    data: { datasets },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          title: { display: true, text: 'Mileage', color: '#8b93a3' },
          ticks: { color: '#8b93a3', callback: v => v.toLocaleString() },
          grid: { color: '#1e2330' },
        },
        y: {
          title: { display: true, text: 'Price ($)', color: '#8b93a3' },
          ticks: { color: '#8b93a3', callback: v => '$' + v.toLocaleString() },
          grid: { color: '#1e2330' },
        },
      },
      plugins: {
        legend: { labels: { color: '#e6e9ef', usePointStyle: true, boxWidth: 8, boxHeight: 8, padding: 14 }, title: { display: true, text: 'Model Year', color: '#8b93a3' } },
        tooltip: {
          callbacks: {
            label: c => {
              const d = c.raw;
              const sites = d.sources && d.sources.length > 1 ? d.sources.map(sourceLabel).join(' · ') : '';
              return [d.title, (d.tags || []).join(' · '), fmtPrice(d.y), fmtMiles(d.x), d.vin, sites, d.dealer || d.city].filter(Boolean);
            },
          },
        },
      },
      onClick: (evt, elements) => {
        if (tab._justBrushed || !elements.length) return;
        const el = elements[0];
        const ds = tab._chart.data.datasets[el.datasetIndex];
        const link = safeUrl(ds && ds.data[el.index] && ds.data[el.index].link);
        if (link) window.open(link, '_blank', 'noopener');
      },
      onHover: (evt, elements) => {
        evt.native.target.style.cursor = elements.length ? 'pointer' : 'crosshair';
      },
    },
  });
}

// ---------- drag-to-select on the chart ----------
function inArea(tab, r) {
  const a = tab._state.area;
  return !a || (r.mileage != null && r.price != null &&
    r.mileage >= a.milesMin && r.mileage <= a.milesMax && r.price >= a.priceMin && r.price <= a.priceMax);
}

function setArea(tab, area) {
  tab._state.area = area;
  renderTab(tab);
}

function renderSelection(tab, rows) {
  const bar = tab._panel.querySelector('[data-role=sel]');
  const reset = tab._panel.querySelector('[data-role=resetview]');
  const a = tab._state.area;
  reset.hidden = !a;
  if (!a) { bar.hidden = true; return; }
  bar.innerHTML = `<span>Filtered to <b>${a.milesMin.toLocaleString()} – ${a.milesMax.toLocaleString()} mi</b> · <b>${fmtPrice(a.priceMin)} – ${fmtPrice(a.priceMax)}</b> &middot; <b>${rows.length}</b> listing${rows.length === 1 ? '' : 's'}</span>
    <span class="sel-actions"><button class="btn-ghost sm" data-act="view">View listings &darr;</button></span>`;
  bar.querySelector('[data-act=view]').onclick = () => tab._panel.querySelector('.table-wrap').scrollIntoView({ behavior: 'smooth', block: 'start' });
  bar.hidden = false;
}

function setupBrush(tab) {
  const wrap = tab._panel.querySelector('.chartWrap');
  const canvas = wrap.querySelector('canvas');
  const box = wrap.querySelector('[data-role=brush]');
  let start = null;
  const pos = e => { const r = canvas.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
  const area = () => tab._chart && tab._chart.chartArea;
  const inside = p => { const a = area(); return a && p.x >= a.left && p.x <= a.right && p.y >= a.top && p.y <= a.bottom; };
  const clamp = p => { const a = area(); return { x: Math.min(Math.max(p.x, a.left), a.right), y: Math.min(Math.max(p.y, a.top), a.bottom) }; };
  const isDrag = (a, b) => Math.abs(a.x - b.x) >= 6 || Math.abs(a.y - b.y) >= 6;

  canvas.addEventListener('pointerdown', e => {
    if (e.pointerType === 'touch' || e.button !== 0 || !inside(pos(e))) return;
    start = pos(e);
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointermove', e => {
    if (!start) return;
    const p = clamp(pos(e));
    if (!isDrag(start, p)) { box.hidden = true; return; }
    Object.assign(box.style, {
      left: Math.min(start.x, p.x) + 'px', top: Math.min(start.y, p.y) + 'px',
      width: Math.abs(p.x - start.x) + 'px', height: Math.abs(p.y - start.y) + 'px',
    });
    box.hidden = false;
  });
  canvas.addEventListener('pointerup', e => {
    if (!start) return;
    const s = start, p = clamp(pos(e));
    start = null;
    box.hidden = true;
    if (!isDrag(s, p)) return;
    tab._justBrushed = true;
    setTimeout(() => { tab._justBrushed = false; }, 0);
    const { x, y } = tab._chart.scales;
    const down = (v, step) => Math.max(0, Math.floor(v / step) * step);
    const up = (v, step) => Math.ceil(v / step) * step;
    setArea(tab, {
      milesMin: down(x.getValueForPixel(Math.min(s.x, p.x)), 500),
      milesMax: up(x.getValueForPixel(Math.max(s.x, p.x)), 500),
      priceMin: down(y.getValueForPixel(Math.max(s.y, p.y)), 500),
      priceMax: up(y.getValueForPixel(Math.min(s.y, p.y)), 500),
    });
  });
  canvas.addEventListener('pointercancel', () => { start = null; box.hidden = true; });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && start) { start = null; box.hidden = true; } });
}

function renderTab(tab) {
  const rows = visibleRows(tab);
  const batPts = (tab.bat && tab.bat.length) ? batPoints(tab) : null;
  renderTable(tab, rows);
  renderYearSummary(tab, rows);
  renderCount(tab, rows);
  renderKpis(tab, rows, batPts);
  syncSpecChips(tab);
  renderSelection(tab, rows);
  if (tab._panel.classList.contains('active')) renderChart(tab, rows, batPts);
  else tab._chartDirty = true;
}

function setRows(tab, rows) {
  tab.rows = rows.map(prepRow);
  tab.count = tab.rows.length;
  tab._years = [...new Set(tab.rows.map(d => d.year).filter(y => y != null))].sort((a, b) => a - b);
  if (tab.live) {
    tab.rows.forEach(r => { r.score = scoreRow(r, tab.tokens, tab.alts); });
  }
  applyModel(tab);
  renderColorOptions(tab);
  buildSpecChips(tab);
  renderAnalysis(tab);
  updateMatchLabel(tab);
  tab._btn.innerHTML = escapeHtml(tab.live ? 'Search' : tab.title) + (tab.rows.length ? `<span class="count-pill">${tab.rows.length}</span>` : '');
}

function updateMatchLabel(tab) {
  const wrap = tab._panel && tab._panel.querySelector('[data-role=matchwrap]');
  if (!wrap) return;
  const r = searchRange(tab.rows);
  if (!r) { wrap.hidden = true; return; }
  wrap.hidden = false;
  wrap.querySelector('[data-role=matchlabel]').textContent =
    `Match this search (${r.yMin === r.yMax ? r.yMin : r.yMin + '–' + r.yMax}${r.mMax != null ? ', ≤' + r.mMax.toLocaleString() + ' mi' : ''})`;
}

function renderColorOptions(tab) {
  const sel = tab._panel && tab._panel.querySelector('[data-role=color]');
  if (!sel) return;
  const counts = {};
  tab.rows.forEach(r => { counts[r.color] = (counts[r.color] || 0) + 1; });
  const names = COLOR_WORDS.map(c => c[0]).filter(n => counts[n]);
  if (counts.Unknown) names.push('Unknown');
  const cur = sel.value;
  sel.innerHTML = '<option value="">Any</option>' +
    names.map(n => `<option value="${escapeHtml(n)}">${escapeHtml(n)} (${counts[n]})</option>`).join('');
  sel.value = names.includes(cur) ? cur : '';
}

function initTab(tab) {
  if (tab._inited) return;
  tab._inited = true;
  const panel = tab._panel;
  panel.innerHTML = panelHTML(tab);

  setRows(tab, tab.rows || []);
  renderAtLinks(tab);
  paintAsOf(tab);
  paintWarning(tab, tab.warnings);

  const batToggle = panel.querySelector('[data-role=bat]');
  if (batToggle) {
    (tab.bat || []).forEach(prepBatRow);
    tab._range = searchRange(tab.rows);
    computeMarketIndex(tab);
    applyBatValues(tab);
    const batFilters = panel.querySelector('[data-role=batfilters]');
    if (!tab._market) {
      const wrap = panel.querySelector('[data-role=adjustwrap]');
      wrap.title = 'Needs at least 3 BaT sales in the last 12 months';
      wrap.style.opacity = 0.5;
      wrap.querySelector('input').disabled = true;
    }
    batToggle.addEventListener('change', () => {
      tab._state.showBat = batToggle.checked;
      batFilters.hidden = !batToggle.checked;
      const batPts = batPoints(tab);
      renderChart(tab, tab._visibleRows || visibleRows(tab), batPts);
      renderKpis(tab, tab._visibleRows, batPts);
    });
    const onBatFilter = debounce(() => {
      const b = tab._state.bat;
      batFilters.querySelectorAll('[data-bf]').forEach(el => {
        const k = el.dataset.bf;
        b[k] = el.type === 'checkbox' ? el.checked : k === 'days' ? numOrNull(el.value) : el.value;
      });
      const batPts = batPoints(tab);
      renderChart(tab, tab._visibleRows || visibleRows(tab), batPts);
      renderKpis(tab, tab._visibleRows, batPts);
    }, 150);
    batFilters.querySelectorAll('[data-bf]').forEach(el => {
      el.addEventListener('input', onBatFilter);
      el.addEventListener('change', onBatFilter);
    });
  }

  // Event delegation for spec chips (no listener churn on filter changes).
  panel.querySelector('[data-role=specs]').addEventListener('click', e => {
    const b = e.target.closest('[data-spec]');
    if (!b) return;
    const f = tab._state.filters, n = b.dataset.spec;
    f.specs = f.specs.includes(n) ? f.specs.filter(x => x !== n) : [...f.specs, n];
    renderTab(tab);
  });

  const onFilter = debounce(() => {
    const f = tab._state.filters;
    panel.querySelectorAll('[data-f]').forEach(el => {
      const k = el.dataset.f;
      f[k] = (k === 'deal' || k === 'color' || k === 'vs' || k === 'text') ? el.value : numOrNull(el.value);
    });
    renderTab(tab);
  }, 150);
  panel.querySelectorAll('[data-f]').forEach(el => {
    el.addEventListener('input', onFilter);
    el.addEventListener('change', onFilter);
  });

  panel.querySelector('[data-role=reset]').addEventListener('click', () => {
    panel.querySelectorAll('[data-f]').forEach(el => { el.value = ''; });
    tab._state.filters = newState(false).filters;
    renderTab(tab);
  });

  // Sorting only re-sorts the cached filtered rows and repaints the visible table chunk.
  panel.querySelectorAll('th[data-key]').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.key, st = tab._state;
      if (st.sortKey === key) st.sortDir *= -1;
      else { st.sortKey = key; st.sortDir = key === 'score' ? -1 : 1; }
      const rows = tab._visibleRows || visibleRows(tab);
      sortRowsInPlace(rows, st.sortKey, st.sortDir);
      panel.querySelector('[data-role=tablewrap]').scrollTop = 0;
      renderTable(tab, rows);
    });
  });

  // Progressive table loading: buttons + scroll-near-bottom autoload.
  const tw = panel.querySelector('[data-role=tablewrap]');
  tw.addEventListener('scroll', () => {
    if (tab._shown < (tab._visibleRows ? tab._visibleRows.length : 0) &&
        tw.scrollTop + tw.clientHeight >= tw.scrollHeight - 320) {
      appendMoreRows(tab, PAGE_SIZE);
    }
  }, { passive: true });
  panel.querySelector('[data-role=showmore]').addEventListener('click', () => appendMoreRows(tab, PAGE_SIZE));
  panel.querySelector('[data-role=showall]').addEventListener('click', () => appendMoreRows(tab, Infinity));

  if (tab.live) {
    panel.querySelector('[data-role=go]').addEventListener('click', () => runSearch(tab));
    panel.querySelector('[data-role=q]').addEventListener('keydown', e => { if (e.key === 'Enter') runSearch(tab); });
  }

  setupBrush(tab);
  panel.querySelector('[data-role=resetview]').addEventListener('click', () => setArea(tab, null));
  renderTab(tab);
}

async function ensureTabReady(tab) {
  if (tab._inited) return;
  if (!tab.live && !tab._dataLoaded) {
    const cached = window.__TAB_CACHE__[tab.slug];
    if (cached) {
      tab.rows = (cached.rows || []).map(unpackRow);
      tab.bat = (cached.bat || []).map(unpackBat);
      tab._dataLoaded = true;
    } else if (tab.data_file) {
      tab._panel.innerHTML = `<div class="tab-loading">Loading ${escapeHtml(tab.title)} listings…</div>`;
      try {
        const payload = await loadTabScript(tab);
        if (payload && !tab._dataLoaded) {
          tab.rows = (payload.rows || []).map(unpackRow);
          tab.bat = (payload.bat || []).map(unpackBat);
          tab._dataLoaded = true;
        }
      } catch (err) {
        tab._panel.innerHTML = `<div class="tab-loading" style="color:var(--fair)">Could not load ${escapeHtml(tab.data_file)}.</div>`;
        return;
      }
    }
  }
  initTab(tab);
}

async function activateTab(slug) {
  TABS.forEach(tab => {
    const on = tab.slug === slug;
    tab._btn.classList.toggle('active', on);
    tab._panel.classList.toggle('active', on);
  });
  const tab = TABS.find(t => t.slug === slug);
  if (!tab) return;
  paintStatus();
  await ensureTabReady(tab);
  if (!tab._panel.classList.contains('active')) return; // user switched tabs while loading
  if (tab._chartDirty || !tab._chart) renderChart(tab, tab._visibleRows || visibleRows(tab));
  else tab._chart.resize();
  if (tab.live) {
    const q = tab._panel.querySelector('[data-role=q]');
    if (q) q.focus();
  }
  paintStatus();
}

// ---------- live search ----------
function renderChips(tab, info) {
  const chips = tab._panel.querySelector('[data-role=chips]');
  const parts = [];
  if (info.make) parts.push(['make', info.make]);
  if (info.model) parts.push(['model', info.model]);
  if (info.years) parts.push(['years', info.years]);
  if (info.color) parts.push(['color', info.color]);
  if (info.keywords && info.keywords.length) parts.push(['keywords', info.keywords.join(' / ')]);
  if (info.note) parts.push(['note', info.note]);
  chips.innerHTML = parts.map(([k, v]) => `<span class="chip"><b>${escapeHtml(k)}</b>${escapeHtml(v)}</span>`).join('');
}

async function runSearch(tab) {
  const panel = tab._panel;
  const q = panel.querySelector('[data-role=q]').value.trim();
  const zip = panel.querySelector('[data-role=zip]').value.trim() || DEFAULT_ZIP;
  const status = panel.querySelector('[data-role=status]');
  const go = panel.querySelector('[data-role=go]');
  if (!q) { status.className = 'status'; status.textContent = 'Type something to search, e.g. 930 porsche white'; return; }

  go.disabled = true;
  status.className = 'status busy';
  status.textContent = 'Searching AutoTempest... this takes 10-20 seconds.';
  try {
    const res = await fetch(`${SEARCH_API}/api/search?` + new URLSearchParams({ q, zip }));
    let data = {};
    try { data = await res.json(); } catch (_) { /* non-JSON error body */ }
    if (!res.ok) throw new Error(data.error || `Server error ${res.status}`);

    tab.urls = data.at_urls || [];
    tab.tokens = data.tokens || [];
    tab.alts = data.token_alternatives || {};
    setRows(tab, data.rows || []);
    renderAtLinks(tab);
    renderChips(tab, data.interpreted || {});
    status.className = 'status';
    status.textContent = `${tab.rows.length} listings for "${q}"` + (data.cached ? ' (cached, under 10 min old)' : ` in ${data.elapsed_s}s`) + '. Use the filters below to narrow down.';
    renderTab(tab);
  } catch (err) {
    status.className = 'status error';
    status.textContent = err instanceof TypeError
      ? 'Search server is not running. Start it with: python3 search_server_v2.py  then open http://127.0.0.1:8911'
      : err.message;
  } finally {
    go.disabled = false;
  }
}

// ---------- saved snapshot & status bar ----------
const _dateFmt = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago', month: 'short', day: 'numeric', year: 'numeric',
  hour: 'numeric', minute: '2-digit', hour12: true, timeZoneName: 'short'
});
function formatAsOf(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const parts = _dateFmt.formatToParts(d);
  const get = type => (parts.find(part => part.type === type) || {}).value || '';
  return `${get('month')} ${get('day')}, ${get('year')}, ${get('hour')}:${get('minute')} ${get('dayPeriod')} ${get('timeZoneName')}`.trim();
}
function ageMs(iso) {
  const t = Date.parse(iso || '');
  return Number.isNaN(t) ? Infinity : Date.now() - t;
}
function isStale(tab, days) {
  if (tab.live || !tab.saved_slug) return false;
  return ageMs(tab.scraped_at) > Number(days) * 24 * 60 * 60 * 1000;
}
function paintAsOf(tab, extra) {
  const el = tab._panel && tab._panel.querySelector('[data-role=asof]');
  if (!el) return;
  if (tab.live || !tab.scraped_at) { el.hidden = true; el.textContent = ''; return; }
  el.hidden = false;
  el.textContent = 'Data as of ' + formatAsOf(tab.scraped_at) + (extra ? ' · ' + extra : '');
}
function paintWarning(tab, warnings) {
  const el = tab._panel && tab._panel.querySelector('[data-role=datawarn]');
  if (!el) return;
  const text = (warnings || []).filter(Boolean).join(' ');
  el.hidden = !text;
  el.textContent = text;
}

let serverState = SEARCH_API ? 'checking' : 'none';
let freshDaysNow = FRESH_DAYS;
const clockText = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
function ageText(iso) {
  const ms = ageMs(iso);
  if (!Number.isFinite(ms)) return '';
  const min = Math.max(0, Math.round(ms / 60000));
  if (min < 2) return 'just now';
  if (min < 60) return `${min} min old`;
  const h = Math.round(min / 60);
  if (h < 48) return `${h} h old`;
  return `${Math.round(h / 24)} days old`;
}
function activeTab() {
  return TABS.find(tab => tab._panel && tab._panel.classList.contains('active')) || TABS[0];
}
function paintHeaderAsOf() { paintStatus(); }
function paintStatus() {
  const bar = document.getElementById('statusBar');
  if (!bar) return;
  const main = document.getElementById('sbMain');
  const side = document.getElementById('sbSide');
  const btn = document.getElementById('refreshTabBtn');
  const tab = activeTab();
  const offline = 'Local server not running. In 911s, start it with ../scanner/.venv/bin/python3 search_server_v2.py, then open http://127.0.0.1:8911';
  let tone = 'idle', text = '';
  if (!tab) {
    text = '';
  } else if (tab.live) {
    text = 'Live search runs on demand.';
  } else if (tab._job) {
    tone = 'busy';
    const secs = (tab._job.elapsed_s || 0) + (Date.now() - tab._job.seen) / 1000;
    text = `${tab.title} · ${tab._job.stage || 'Refreshing'}… · ${clockText(secs)} elapsed`;
  } else if (tab._error) {
    tone = 'error';
    text = `${tab.title} · ${tab._error}`;
  } else {
    tone = isStale(tab, freshDaysNow) ? 'stale' : 'fresh';
    const done = tab._done && Date.now() - tab._done.at < 120000
      ? (tab._done.skipped ? ' · already fresh, nothing to fetch' : ` · refreshed in ${clockText(tab._done.elapsed_s || 0)}, ${tab.count} cars`)
      : '';
    text = tab.scraped_at
      ? `${tab.title} · data as of ${formatAsOf(tab.scraped_at)} (${ageText(tab.scraped_at)})${done}`
      : `${tab.title} · no saved data yet`;
  }
  bar.dataset.tone = tone;
  main.textContent = text;
  const parts = [];
  if (SEARCH_API) {
    const stale = TABS.filter(t => isStale(t, freshDaysNow));
    const busy = TABS.filter(t => t._job);
    if (busy.length > (tab && tab._job ? 1 : 0)) parts.push(`${busy.length} refreshing`);
    if (stale.length) parts.push(`${stale.length} of ${TABS.filter(t => !t.live).length} cars older than ${freshDaysNow} days`);
    parts.push(serverState === 'up' ? 'Server connected' : serverState === 'checking' ? 'Checking server…' : 'Server offline');
    side.textContent = (serverState === 'down' && tone !== 'busy' && tab && !tab._error && !tab.live) ? offline : parts.join(' · ');
    TABS.forEach(t => t._btn && t._btn.classList.toggle('stale', isStale(t, freshDaysNow) && !t._job));
  } else {
    const totalCars = TABS.reduce((s, t) => s + (t.count || 0), 0);
    side.textContent = `${totalCars.toLocaleString()} listings across ${TABS.length} generations`;
  }
  if (btn) {
    btn.disabled = !tab || tab.live || !tab.saved_slug || !!tab._job || serverState === 'none';
    btn.textContent = tab && tab._job ? 'REFRESHING…' : 'REFRESH THIS CAR';
    btn.title = serverState === 'down' ? offline : 'Scrape the open car again now, even if its saved data is still fresh';
  }
}

let _statusTimer = null;
function scheduleStatusTick() {
  if (!SEARCH_API) return;
  const anyBusy = TABS.some(t => t._job);
  clearTimeout(_statusTimer);
  _statusTimer = setTimeout(() => { paintStatus(); scheduleStatusTick(); }, anyBusy ? 1000 : 30000);
}

function applySnapshot(tab, data) {
  if (data.scraped_at) tab.scraped_at = data.scraped_at;
  tab.warnings = data.warnings || [];
  if (Array.isArray(data.rows)) {
    tab.rows = data.rows;
    tab._dataLoaded = true;
    if (Array.isArray(data.bat)) tab.bat = data.bat;
    if (tab._inited) {
      setRows(tab, tab.rows);
      if (Array.isArray(data.bat)) {
        tab.bat.forEach(prepBatRow);
        tab._range = searchRange(tab.rows);
        computeMarketIndex(tab);
        applyBatValues(tab);
      }
      renderTab(tab);
    } else {
      tab.count = tab.rows.length;
      tab._btn.innerHTML = escapeHtml(tab.title) + (tab.count ? `<span class="count-pill">${tab.count}</span>` : '');
    }
  }
  paintAsOf(tab);
  paintWarning(tab, tab.warnings);
  paintHeaderAsOf();
}

function watchRefresh(tab) {
  const tick = async () => {
    try {
      const res = await fetch(`${SEARCH_API}/api/refresh?slug=${encodeURIComponent(tab.saved_slug)}`, { cache: 'no-store' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Refresh failed');
      serverState = 'up';
      tab._misses = 0;
      if (data.running) {
        tab._job = { stage: data.stage, elapsed_s: data.elapsed_s || 0, seen: Date.now() };
        paintStatus();
        scheduleStatusTick();
        return;
      }
      clearInterval(tab._refreshTimer);
      tab._refreshTimer = null;
      tab._job = null;
      tab._done = { at: Date.now(), elapsed_s: data.elapsed_s || 0, skipped: data.skipped };
      applySnapshot(tab, data);
      if (data.ok === false) {
        tab._error = 'Refresh failed. Showing saved data.';
        paintWarning(tab, (data.warnings && data.warnings.length) ? data.warnings : [tab._error]);
      }
      paintStatus();
    } catch (err) {
      if (err instanceof TypeError && (tab._misses = (tab._misses || 0) + 1) < 10) return;
      clearInterval(tab._refreshTimer);
      tab._refreshTimer = null;
      tab._job = null;
      if (err instanceof TypeError) serverState = 'down';
      tab._error = err instanceof TypeError ? 'Lost the server. Showing saved data.' : (err.message || 'Refresh failed. Showing saved data.');
      paintAsOf(tab);
      paintWarning(tab, [tab._error]);
      paintStatus();
    }
  };
  if (tab._refreshTimer) clearInterval(tab._refreshTimer);
  tab._misses = 0;
  tab._refreshTimer = setInterval(tick, 3000);
  tick();
}

async function startRefresh(tab, force) {
  paintAsOf(tab, force ? 'Updating…' : 'Refreshing in the background…');
  tab._error = null;
  tab._done = null;
  tab._job = { stage: 'Starting', elapsed_s: 0, seen: Date.now() };
  paintStatus();
  scheduleStatusTick();
  try {
    const res = await fetch(`${SEARCH_API}/api/refresh?slug=${encodeURIComponent(tab.saved_slug)}&force=${force ? 1 : 0}`, { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(res.status === 409 ? 'A full update is running; this car is included in it.' : (data.error || 'Refresh failed'));
    serverState = 'up';
    watchRefresh(tab);
  } catch (err) {
    tab._job = null;
    if (err instanceof TypeError) serverState = 'down';
    tab._error = err instanceof TypeError ? 'Could not reach the local server. Showing saved data.' : err.message;
    paintAsOf(tab);
    paintWarning(tab, [tab._error]);
    paintStatus();
  }
}

document.getElementById('refreshTabBtn').addEventListener('click', () => {
  const tab = activeTab();
  if (tab && !tab.live && tab.saved_slug && !tab._job) startRefresh(tab, true);
});

async function refreshIfStale() {
  if (!SEARCH_API) return;
  let days = FRESH_DAYS;
  try {
    const res = await fetch(`${SEARCH_API}/api/health`, { cache: 'no-store' });
    if (!res.ok) throw new Error('health check failed');
    const body = await res.json();
    if (body.fresh_days) days = Number(body.fresh_days);
  } catch (_) {
    serverState = 'down';
    paintStatus();
    return;
  }
  serverState = 'up';
  freshDaysNow = days;
  paintStatus();
  TABS.forEach(tab => { if (isStale(tab, days)) startRefresh(tab, false); });
}

function setupUpdate() {
  const box = document.getElementById('updateBox');
  const btn = document.getElementById('updateBtn');
  const status = document.getElementById('updateStatus');
  if (!SEARCH_API) return;
  box.hidden = false;
  let sawRunning = false, timer = null;
  const clock = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  const offline = 'Start the local server first: python3 search_server_v2.py, then open http://127.0.0.1:8911';

  const show = st => {
    status.classList.remove('error');
    if (st.running) {
      sawRunning = true;
      btn.disabled = true;
      btn.textContent = 'UPDATING ALL…';
      const step = st.current === 'Building report' ? 'Building report' : `Search ${Math.max(st.done, 1)} of ${st.total || '?'}: ${st.current}`;
      status.textContent = `${step} · ${clock(st.elapsed_s || 0)}`;
      return;
    }
    clearInterval(timer); timer = null;
    btn.disabled = false;
    btn.textContent = 'UPDATE ALL';
    if (!sawRunning) return;
    if (st.ok) {
      status.textContent = `Updated in ${clock(st.elapsed_s || 0)}. Reloading…`;
      setTimeout(() => location.reload(), 800);
    } else {
      status.classList.add('error');
      status.textContent = st.current || 'Update failed; see update.log';
    }
  };
  const poll = async () => {
    try { show(await (await fetch(`${SEARCH_API}/api/update`)).json()); }
    catch (_) { /* server restarted or stopped */ }
  };
  const follow = () => { if (!timer) timer = setInterval(poll, 2000); };

  btn.addEventListener('click', async () => {
    btn.disabled = true;
    status.classList.remove('error');
    status.textContent = 'Starting…';
    try {
      const res = await fetch(`${SEARCH_API}/api/update`, { method: 'POST' });
      const st = await res.json();
      if (!res.ok) throw new Error(st.error || `Server error ${res.status}`);
      sawRunning = true;
      show(st);
      follow();
    } catch (err) {
      btn.disabled = false;
      status.classList.add('error');
      status.textContent = err instanceof TypeError ? offline : err.message;
    }
  });

  fetch(`${SEARCH_API}/api/update`).then(r => r.json()).then(st => { if (st.running) { show(st); follow(); } }).catch(() => {});
}

// ---------- init (runs on DOMContentLoaded after deferred first-tab + Chart.js scripts) ----------
function init() {
  setupUpdate();
  const tabButtons = document.getElementById('tabButtons');
  const tabPanels = document.getElementById('tabPanels');

  TABS.forEach((tab, idx) => {
    tab._state = newState(!!tab.live);
    tab.urls = tab.urls && tab.urls.length ? tab.urls : (tab.url ? tab.url.split(/\s+/).filter(Boolean) : []);

    const btn = document.createElement('button');
    btn.className = 'tab-btn' + (tab.live ? ' live' : '') + (idx === 0 ? ' active' : '');
    btn.innerHTML = escapeHtml(tab.live ? 'Search' : tab.title) + (tab.count ? `<span class="count-pill">${tab.count}</span>` : '');
    btn.addEventListener('click', () => activateTab(tab.slug));
    btn.addEventListener('pointerenter', () => prefetchTab(tab));
    btn.addEventListener('focus', () => prefetchTab(tab));
    tabButtons.appendChild(btn);
    tab._btn = btn;

    const panel = document.createElement('div');
    panel.className = 'tab-panel' + (idx === 0 ? ' active' : '');
    tabPanels.appendChild(panel);
    tab._panel = panel;
  });

  if (TABS.length) activateTab(TABS[0].slug);
  paintHeaderAsOf();
  scheduleStatusTick();
  refreshIfStale();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", help="Single CSV/JSON file (shorthand for one tab)")
    ap.add_argument("--title", default="AutoTempest Results", help="Page title")
    ap.add_argument("--tab", action="append", default=[], metavar="LABEL|PATH[|URL[|BAT_PATH[|AT_URL[|SLUG[|CLASSIFIER]]]]]", help="Add a tab. Repeatable.")
    ap.add_argument("-o", "--output", default="report_v2.html", help="Output HTML path")
    ap.add_argument("--data-dir", default=None, help="Directory for split per-tab JS files (default: <output_stem>_data next to output)")
    ap.add_argument("--single-file", action="store_true", help="Inline all packed tab data inside the HTML instead of splitting files")
    ap.add_argument("--search-api", default="http://127.0.0.1:8911", help='Base URL of search_server_v2.py; "" disables')
    ap.add_argument("--fresh-days", default=None, help="How many days saved data stays fresh (default 2)")
    ap.add_argument("--zip", default="73102", help="Default ZIP shown in the Search tab")
    ap.add_argument("--link", action="append", default=[], metavar="LABEL|HREF", help="Link to another report in the header. Repeatable.")
    args = ap.parse_args()

    tab_specs = []
    if args.tab:
        for spec in args.tab:
            parts = spec.split("|")
            if len(parts) < 2 or not parts[1]:
                print(f"error: --tab must be LABEL|PATH[|URL[|BAT_PATH]], got {spec!r}", file=sys.stderr)
                sys.exit(1)
            while len(parts) < 7:
                parts.append("")
            tab_specs.append(tuple(parts[:7]))
    elif args.input:
        tab_specs.append((args.title, args.input, "", "", "", "", ""))
    else:
        print("error: provide an input file, or one or more --tab LABEL|PATH[|URL]", file=sys.stderr)
        sys.exit(1)

    loaded = []
    tagged = False
    tag_set = set()
    for label, path, url, bat_path, atr_url, saved_slug, classifier in tab_specs:
        bat = [r for r in load_rows(bat_path) if r["price"] is not None] if bat_path else []
        rows = load_rows(path)
        if classifier == "911":
            porsche_911.add_tags(rows)
            porsche_911.add_tags(bat)
            tagged = True
        for r in rows:
            tag_set.update(r.get("tags") or [])
        for b in bat:
            tag_set.update(b.get("tags") or [])
        meta = snapshot_meta(path)
        loaded.append({
            "title": label,
            "slug": slugify(label),
            "saved_slug": saved_slug,
            "scraped_at": meta.get("scraped_at") or "",
            "warnings": meta.get("warnings") or [],
            "rows": rows,
            "url": url,
            "bat": bat,
            "autotrader_url": atr_url,
        })

    tag_list = sorted(tag_set)
    tag_index = {t: i for i, t in enumerate(tag_list)}

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data_dir = Path(args.data_dir) if args.data_dir else out_path.parent / f"{out_path.stem}_data"
    if not args.single_file:
        data_dir.mkdir(parents=True, exist_ok=True)
    rel_data_dir = data_dir.relative_to(out_path.parent).as_posix() if not args.single_file else ""

    manifest = []
    inline_chunks = []
    preload_scripts = ""
    for idx, tab in enumerate(loaded):
        packed_rows = [pack_row(r, tag_index) for r in tab["rows"]]
        packed_bat = [pack_bat(b, tag_index) for b in tab["bat"]]
        payload = {"rows": packed_rows, "bat": packed_bat}
        file_stem = tab["saved_slug"] or tab["slug"]
        data_file = ""
        if args.single_file:
            inline_chunks.append(f"window.__LOAD_TAB__({js_json(tab['slug'])},{js_json(payload)});")
        else:
            fname = f"{file_stem}.js"
            data_file = f"{rel_data_dir}/{fname}"
            (data_dir / fname).write_text(
                f"window.__LOAD_TAB__({js_json(tab['slug'])},{js_json(payload)});\n",
                encoding="utf-8",
            )
            if idx == 0:
                preload_scripts = f'<script src="{html.escape(data_file)}" defer></script>\n'

        manifest.append({
            "title": tab["title"],
            "slug": tab["slug"],
            "saved_slug": tab["saved_slug"],
            "scraped_at": tab["scraped_at"],
            "warnings": tab["warnings"],
            "count": len(packed_rows),
            "bat_count": len(packed_bat),
            "data_file": data_file,
            "url": tab["url"],
            "autotrader_url": tab["autotrader_url"],
        })

    page_title = args.title if args.tab else tab_specs[0][0]
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    first = next((parse_time(tab.get("scraped_at")) for tab in loaded if parse_time(tab.get("scraped_at"))), None)
    data_as_of = ("Data as of " + format_as_of(first.isoformat())) if first is not None else ""
    fresh = resolve_fresh_days(args.fresh_days)
    fresh_js = str(int(fresh)) if float(fresh).is_integer() else str(fresh)
    page_links = ""
    for spec in args.link:
        label, _, href = spec.partition("|")
        page_links += f' &middot; <a href="{html.escape(href)}"><b>{html.escape(label)}</b></a>'

    inline_data = ("\n".join(inline_chunks) + "\n") if inline_chunks else ""

    out = (
        TEMPLATE
        .replace("__PAGE_TITLE__", html.escape(page_title))
        .replace("__DATA_AS_OF__", html.escape(data_as_of))
        .replace("__GENERATED_AT__", generated_at)
        .replace("__PAGE_LINKS__", page_links)
        .replace("__PRELOAD_SCRIPTS__", preload_scripts)
        .replace("__NOW_MS__", str(int(datetime.now(timezone.utc).timestamp() * 1000)))
        .replace("__FRESH_DAYS__", fresh_js)
        .replace("__SEARCH_API__", js_json(args.search_api or None))
        .replace("__DEFAULT_ZIP__", js_json(args.zip))
        .replace("__TAG_GROUPS__", js_json(porsche_911.TAG_GROUPS if tagged else []))
        .replace("__TAG_LIST__", js_json(tag_list))
        .replace("__COLOR_NAMES__", js_json(COLOR_NAMES))
        .replace("__BAT_PREFIX__", js_json(BAT_PREFIX))
        .replace("__INLINE_DATA__", inline_data)
        .replace("__TABS_JSON__", js_json(manifest))
    )

    out_path.write_text(out, encoding="utf-8")

    total = sum(len(t["rows"]) for t in loaded)
    total_bat = sum(len(t["bat"]) for t in loaded)
    print(
        f"[done] wrote {out_path} ({len(out):,} bytes) with {len(loaded)} tab(s), "
        f"{total:,} listings, {total_bat:,} BaT comps"
        + ("" if args.single_file else f" (data in {data_dir})"),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
