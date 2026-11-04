#!/usr/bin/env python3
"""Build the single-page Patek report from saved/<slug>/ (v2).

Same look as Cars_autotempest_scan/generate_report_v2.py: dark theme, the same
CSS variables, a "Data as of" header (America/Chicago), one tab per saved
search, KPI cards, a Filters card, a Chart.js price scatter, a sortable
listings table, plus the per-variant price stats with the change since the
last snapshot (price_history.csv) and the Sources table (what worked, what
blocked) with the dedupe counts.

    python3 generate_report_v2.py -o output/report.html
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from models_v2 import MODELS
from saved_store_v2 import format_as_of, load_meta, read_csv, search_dir, source_path
from watch_common_v2 import price_int

ASKING = ("For sale", "Auction live", "Buy-now (auction ended unsold)")
SLUGS = ["patek5711", "aquanaut_bluegreen"]


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def tab_data(slug, root=None):
    meta = load_meta(slug, root) or {}
    merged = read_csv(source_path(slug, "merged", root))
    model = MODELS[meta.get("model") or "5711"]
    hist_rows = read_csv(search_dir(slug, root) / "price_history.csv")
    labels = {k: (v.get("label") or k) for k, v in (meta.get("sources") or {}).items()}
    labels.setdefault("chrono24", "Chrono24")

    variants = sorted({r.get("variant") for r in merged if r.get("variant")} |
                      {r["variant"] for r in hist_rows}, key=model.variant_key)
    runs = sorted({r["run_at"] for r in hist_rows})
    last = runs[-1] if runs else None
    prev = runs[-2] if len(runs) > 1 else None
    by = {}
    for r in hist_rows:
        by.setdefault((r["variant"], r["source"]), {})[r["run_at"]] = r

    stats = []
    for v in variants:
        h = by.get((v, "all (merged)"), {})
        cur = h.get(last)
        if not cur:
            continue
        before = h.get(prev) if prev else None
        per = []
        for (vv, src), m in by.items():
            if vv == v and src != "all (merged)" and last in m:
                x = m[last]
                per.append({"source": labels.get(src, src), "count": _int(x["count"]),
                            "low": _int(x["low"]), "median": _int(x["median"])})
        stats.append({
            "variant": v, "count": _int(cur["count"]), "low": _int(cur["low"]),
            "median": _int(cur["median"]), "high": _int(cur["high"]),
            "prev_median": _int(before["median"]) if before else None, "per_source": per,
        })

    history = {"runs": runs[-12:], "series": []}
    for v in variants:
        h = by.get((v, "all (merged)"), {})
        if any(x in h for x in history["runs"]):
            history["series"].append({"variant": v, "points": [
                {"median": _int(h[x]["median"]), "count": _int(h[x]["count"])} if x in h else None
                for x in history["runs"]]})

    rows = []
    for r in merged:
        try:
            srcs = json.loads(r.get("sources") or "[]")
        except ValueError:
            srcs = []
        rows.append({
            "reference": r.get("reference") or "", "variant": r.get("variant") or "",
            "dial": r.get("dial") or "", "year": _int(r.get("year")),
            "box_papers": r.get("box_papers") or "", "condition": r.get("condition") or "",
            "price": price_int(r.get("price")), "status": r.get("status") or "",
            "asking": (r.get("status") or "For sale") in ASKING,
            "seller": r.get("seller") or "", "location": r.get("location") or "",
            "title": r.get("title") or "", "link": r.get("link") or "",
            "sites": [labels.get(c, c) for c in (r.get("site_code") or "").split(",") if c],
            "sources": [{"site": labels.get(s.get("site_code"), s.get("site_code")),
                         "price": price_int(s.get("price")), "link": s.get("link") or "",
                         "status": s.get("status") or ""} for s in srcs],
        })

    sources = []
    raw_rows = 0
    for name, st in (meta.get("sources") or {}).items():
        sources.append({
            "name": labels.get(name, name), "ok": bool(st.get("ok")), "rows": st.get("rows"),
            "scraped_at": st.get("scraped_at") or "", "warning": st.get("warning") or "",
        })
        if st.get("ok") or source_path(slug, name, root).exists():
            raw_rows += len(read_csv(source_path(slug, name, root))) if source_path(slug, name, root).exists() else 0
    multi = sum(1 for r in rows if len(r["sites"]) > 1)
    return {
        "slug": slug, "title": meta.get("title", slug), "scraped_at": meta.get("scraped_at") or "",
        "as_of_text": format_as_of(meta.get("scraped_at")), "warnings": meta.get("warnings") or [],
        "variants": variants, "rows": rows, "stats": stats, "history": history, "sources": sources,
        "dedupe": {"raw": raw_rows, "merged": len(rows), "multi": multi},
        "prev_run": prev or "", "last_run": last or "",
    }


def build(slugs, output, root=None):
    tabs = []
    for slug in slugs:
        if source_path(slug, "merged", root).exists():
            tabs.append(tab_data(slug, root))
    generated = datetime.now(timezone.utc).isoformat()
    page = (TEMPLATE
            .replace("__PAGE_TITLE__", "Patek Tracker")
            .replace("__TABS_JSON__", json.dumps(tabs, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__GENERATED_AT__", json.dumps(generated)))
    Path(output).write_text(page, encoding="utf-8")
    return output


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__PAGE_TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
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
  .num, td, .kpi b { font-variant-numeric: tabular-nums; }
  .shell { max-width: 1440px; margin: 0 auto; padding: 28px 24px 48px; }
  @media (max-width: 640px) { .shell { padding: 16px; } }
  .page-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
  .page-title { display: grid; gap: 4px; min-width: 0; }
  h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.01em; margin: 0; }
  .meta { color: var(--muted); font-size: 13px; }
  .asof { color: var(--muted); font-size: 13px; }
  .data-warn { color: var(--fair); font-size: 12px; }
  .data-warn[hidden] { display: none; }
  .tab-title { display: grid; gap: 2px; }
  .tabs { display: flex; gap: 4px; flex-wrap: wrap; padding: 4px; background: var(--panel); border: 1px solid var(--border); border-radius: 12px; margin-bottom: 22px; }
  .tab-btn { background: transparent; border: 0; color: var(--muted); padding: 8px 14px; border-radius: 8px; cursor: pointer; font: inherit; font-size: 13px; font-weight: 600; white-space: nowrap; }
  .tab-btn:hover { color: var(--text); background: var(--panel-2); }
  .tab-btn.active { color: var(--text); background: var(--panel-2); box-shadow: inset 0 0 0 1px var(--border-strong); }
  .tab-btn .count-pill { color: var(--faint); font-weight: 500; margin-left: 6px; }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }
  .tab-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
  .tab-head h2 { font-size: 18px; margin: 0; font-weight: 700; letter-spacing: -0.01em; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin-bottom: 18px; }
  .kpi { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); padding: 12px 14px; min-width: 0; }
  .kpi > span { display: block; font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .kpi b { display: block; font-size: 20px; font-weight: 700; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .kpi em { display: block; font-style: normal; font-size: 12px; color: var(--muted); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .kpi a { color: inherit; text-decoration: none; }
  .kpi a:hover { color: var(--accent); }
  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 18px; margin-bottom: 18px; }
  .card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin: -2px 0 12px; }
  .card-head h3 { font-size: 13px; font-weight: 700; margin: 0; letter-spacing: 0.01em; }
  .card-head .sub { color: var(--muted); font-size: 12px; margin-left: 8px; }
  .filter-grid { display: flex; gap: 14px 20px; flex-wrap: wrap; align-items: flex-end; }
  .filter-grid label { display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
  .filter-grid .pair { display: flex; align-items: center; gap: 6px; text-transform: none; letter-spacing: 0; }
  .filter-grid input, .filter-grid select { background: var(--bg); border: 1px solid var(--border-strong); color: var(--text); border-radius: 8px; font: inherit; padding: 6px 8px; font-size: 13px; width: 92px; }
  .filter-grid select { width: auto; min-width: 92px; max-width: 320px; padding-right: 26px; }
  .filter-grid input:focus, .filter-grid select:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(90,169,255,0.15); }
  .filter-grid input.wide { width: 100%; }
  .filter-grid label.grow { flex: 1; min-width: 220px; }
  .filter-grid label.check { flex-direction: row; align-items: center; gap: 6px; text-transform: none; letter-spacing: 0; font-size: 13px; padding-bottom: 6px; }
  .filter-grid label.check input { width: auto; accent-color: var(--accent); }
  .btn-ghost { background: transparent; color: var(--muted); border: 1px solid var(--border); border-radius: 8px; padding: 7px 14px; font-size: 13px; cursor: pointer; font: inherit; }
  .btn-ghost:hover { color: var(--text); }
  .count { color: var(--muted); font-size: 12px; }
  .chartWrap { position: relative; height: 480px; }
  .chart-tools { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
  .seg { display: inline-flex; border: 1px solid var(--border-strong); border-radius: 8px; overflow: hidden; }
  .seg button { background: transparent; border: 0; color: var(--muted); padding: 5px 12px; font: inherit; font-size: 12px; font-weight: 600; cursor: pointer; }
  .seg button.on { background: rgba(90,169,255,0.15); color: var(--text); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--border); white-space: nowrap; }
  th { cursor: pointer; user-select: none; color: var(--muted); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; position: sticky; top: 0; background: var(--panel); z-index: 1; }
  th:hover { color: var(--text); }
  th.no-sort { cursor: default; }
  th.r, td.r { text-align: right; }
  tbody tr:hover td { background: var(--panel-2); }
  td small { display: block; font-size: 11px; color: var(--muted); }
  .table-wrap { overflow: auto; max-height: 680px; margin: 0 -18px -16px; border-top: 1px solid var(--border); }
  .table-wrap.short { max-height: none; }
  td.title-cell { white-space: normal; min-width: 220px; max-width: 320px; }
  td.source-cell { white-space: normal; min-width: 140px; max-width: 300px; }
  td.source-cell a.view-link { margin: 0 4px 4px 0; display: inline-block; }
  td.wrap { white-space: normal; }
  .muted { color: var(--muted); }
  a.view-link { color: var(--muted); text-decoration: none; border: 1px solid var(--border-strong); padding: 3px 10px; border-radius: 6px; font-size: 12px; }
  a.view-link:hover { border-color: var(--accent); color: var(--accent); }
  a.title-link { color: var(--text); text-decoration: underline; text-decoration-color: var(--border); text-underline-offset: 3px; }
  a.title-link:hover { color: var(--accent); text-decoration-color: var(--accent); }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
  .badge.good { background: rgba(63,214,126,0.15); color: var(--good); }
  .badge.great { background: rgba(255,212,59,0.15); color: var(--great); }
  .badge.fair { background: rgba(255,135,135,0.15); color: var(--fair); }
  .badge.outlier { background: rgba(154,161,172,0.15); color: var(--muted); }
  .empty { color: var(--muted); text-align: center; padding: 32px 0; }
  .below { color: var(--good); font-weight: 600; }
  .above { color: var(--fair); }
  .dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; vertical-align: 0; }
  .two-col { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 18px; }
  @media (max-width: 1100px) { .two-col { grid-template-columns: 1fr; } }
  .two-col > .panel { min-width: 0; }
  .footnote { font-size: 12px; color: var(--muted); line-height: 1.5; margin: 10px 0 0; }
</style>
</head>
<body>
<div class="shell">
  <header class="page-head">
    <div class="page-title">
      <h1>__PAGE_TITLE__</h1>
      <div class="meta"><span id="dataAsOf"></span>Updated <span id="genAt"></span> &middot; listings from <a href="https://www.chrono24.com" target="_blank" rel="noopener">Chrono24</a> and dealer sites &middot; asking prices, not sold prices</div>
    </div>
  </header>
  <nav class="tabs" id="tabButtons" aria-label="Searches"></nav>
  <div id="tabPanels"></div>
</div>
<script>
const TABS = __TABS_JSON__;
const GENERATED_AT = __GENERATED_AT__;

// ---------- helpers ----------
function fmtPrice(p) { return p == null ? 'N/A' : '$' + p.toLocaleString(); }
function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function safeUrl(u) { return /^https?:\/\//i.test(u || '') ? u : ''; }
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
function numOrNull(v) {
  if (v == null) return null;
  const s = String(v).replace(/[$,\s]/g, '').replace(/k$/i, '000');
  if (s === '') return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}
function median(nums) {
  const a = nums.filter(v => v != null).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : Math.round((a[m - 1] + a[m]) / 2);
}
function formatAsOf(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Chicago', month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit', hour12: true, timeZoneName: 'short'
  }).formatToParts(d);
  const get = type => (parts.find(part => part.type === type) || {}).value || '';
  return `${get('month')} ${get('day')}, ${get('year')}, ${get('hour')}:${get('minute')} ${get('dayPeriod')} ${get('timeZoneName')}`.trim();
}
function colorFor(i, n) {
  const hue = n <= 1 ? 200 : Math.round(220 - (i / (n - 1)) * 300 + 360) % 360;
  return `hsl(${hue}, 70%, 60%)`;
}
function delta(now, before) {
  if (now == null) return '';
  if (before == null) return '<span class="muted">first snapshot</span>';
  const d = now - before;
  if (d === 0) return '<span class="muted">no change</span>';
  const pct = (d / before * 100).toFixed(1);
  return `<span class="${d > 0 ? 'above' : 'below'}">${d > 0 ? '+' : '−'}$${Math.abs(d).toLocaleString()} (${d > 0 ? '+' : ''}${pct}%)</span>`;
}
function kpi(label, value, note) {
  return `<div class="kpi"><span>${label}</span><b>${value}</b>${note ? `<em>${note}</em>` : ''}</div>`;
}
function hashStr(s) { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) | 0; return h; }

const COLS = [
  { key: 'reference', label: 'Reference' },
  { key: 'variant', label: 'Variant' },
  { key: 'dial', label: 'Dial' },
  { key: 'year', label: 'Year', r: true },
  { key: 'box_papers', label: 'Box / papers' },
  { key: 'condition', label: 'Condition' },
  { key: 'price', label: 'Price', r: true, tip: 'Asking price. When the same watch is listed on more than one site, this is the lowest price.' },
  { key: 'status', label: 'Status' },
  { key: 'seller', label: 'Seller' },
  { key: 'location', label: 'Location' },
  { key: 'sites', label: 'Price per source' },
  { key: null, label: 'Link' },
];

function newState() {
  return { filters: { priceMin: null, priceMax: null, yearMin: null, yearMax: null, variant: '', reference: '',
                      dial: '', box: '', source: '', text: '', sold: false },
           sortKey: 'price', sortDir: 1, chartMode: 'year' };
}

function prepRow(r) {
  r._text = [r.reference, r.variant, r.dial, r.seller, r.location, r.title, r.condition, r.box_papers, r.sites.join(' '), r.year].join(' ').toLowerCase();
  return r;
}

function visibleRows(tab) {
  const f = tab._state.filters;
  const tokens = f.text ? f.text.toLowerCase().split(/\s+/).filter(Boolean) : [];
  const within = (v, lo, hi) => v != null && (lo == null || v >= lo) && (hi == null || v <= hi);
  const rows = tab.rows.filter(r => {
    if (!f.sold && !r.asking) return false;
    if ((f.priceMin != null || f.priceMax != null) && !within(r.price, f.priceMin, f.priceMax)) return false;
    if ((f.yearMin != null || f.yearMax != null) && !within(r.year, f.yearMin, f.yearMax)) return false;
    if (f.variant && r.variant !== f.variant) return false;
    if (f.reference && r.reference !== f.reference) return false;
    if (f.dial && r.dial !== f.dial) return false;
    if (f.box && (r.box_papers || 'Not stated') !== f.box) return false;
    if (f.source && !r.sites.includes(f.source)) return false;
    for (const t of tokens) if (!r._text.includes(t)) return false;
    return true;
  });
  const { sortKey, sortDir } = tab._state;
  const val = (r, k) => k === 'sites' ? r.sites.join(',') : r[k];
  rows.sort((a, b) => {
    let av = val(a, sortKey), bv = val(b, sortKey);
    if (av === '') av = null; if (bv === '') bv = null;
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === 'string') return av.localeCompare(bv) * sortDir;
    return (av - bv) * sortDir;
  });
  return rows;
}

function optionList(values, any = 'Any') {
  return `<option value="">${any}</option>` + values.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
}
function uniq(list) { return [...new Set(list.filter(v => v != null && v !== ''))]; }

function panelHTML(tab) {
  const heads = COLS.map(c => c.key
    ? `<th data-key="${c.key}"${c.r ? ' class="r"' : ''}${c.tip ? ` title="${escapeHtml(c.tip)}"` : ''}>${c.label}<span class="arrow"></span></th>`
    : `<th class="no-sort">${c.label}</th>`).join('');
  const refs = uniq(tab.rows.map(r => r.reference)).sort();
  const dials = uniq(tab.rows.map(r => r.dial)).sort();
  const boxes = uniq(tab.rows.map(r => r.box_papers || 'Not stated')).sort();
  const sites = uniq(tab.rows.flatMap(r => r.sites)).sort();
  return `
    <div class="tab-head">
      <div class="tab-title">
        <h2>${escapeHtml(tab.title)}</h2>
        <div class="asof">Data as of ${escapeHtml(formatAsOf(tab.scraped_at))} (America/Chicago)</div>
        <div class="data-warn" data-role="datawarn" role="status" ${tab.warnings.length ? '' : 'hidden'}>${tab.warnings.length} source(s) failed or blocked the scraper this run; see Sources below. Their last good rows (if any) are still shown.</div>
      </div>
    </div>
    <div class="kpis" data-role="kpis"></div>
    <div class="panel">
      <div class="card-head"><h3>Filters</h3><span class="count" data-role="count"></span></div>
      <div class="filter-grid">
        <label>Price<span class="pair"><input data-f="priceMin" inputmode="numeric" placeholder="min"> to <input data-f="priceMax" inputmode="numeric" placeholder="max"></span></label>
        <label>Year<span class="pair"><input data-f="yearMin" inputmode="numeric" placeholder="from"> to <input data-f="yearMax" inputmode="numeric" placeholder="to"></span></label>
        <label>Variant<select data-f="variant">${optionList(tab.variants)}</select></label>
        <label>Reference<select data-f="reference">${optionList(refs)}</select></label>
        <label>Dial<select data-f="dial">${optionList(dials)}</select></label>
        <label>Box &amp; papers<select data-f="box">${optionList(boxes)}</select></label>
        <label>Source<select data-f="source">${optionList(sites)}</select></label>
        <label class="grow">Search<input class="wide" data-f="text" type="text" placeholder="reference, seller, city, condition..."></label>
        <label class="check"><input type="checkbox" data-f="sold"> Include sold / out of stock / auction estimates</label>
        <button class="btn-ghost" data-role="reset">Reset filters</button>
      </div>
    </div>
    <div class="panel">
      <div class="card-head">
        <div><h3 style="display:inline">Price scatter</h3><span class="sub" data-role="chartsub"></span></div>
        <div class="chart-tools"><div class="seg" data-role="mode">
          <button data-mode="year" class="on">Price vs year</button><button data-mode="variant">Price by variant</button>
        </div></div>
      </div>
      <div class="chartWrap"><canvas data-role="canvas"></canvas></div>
    </div>
    <div class="panel">
      <div class="card-head"><div><h3 style="display:inline">Asking prices by variant</h3><span class="sub">For-sale listings after dedupe &middot; change compares the median with the previous snapshot in price_history.csv${tab.prev_run ? ' (' + escapeHtml(formatAsOf(tab.prev_run)) + ')' : ''}</span></div></div>
      <div class="table-wrap short"><table data-role="stats"></table></div>
    </div>
    <div class="panel">
      <div class="card-head"><div><h3 style="display:inline">Listings</h3><span class="sub">Click a column to sort &middot; price chips link to each site's listing</span></div></div>
      <div class="table-wrap">
        <table><thead><tr>${heads}</tr></thead><tbody data-role="tbody"></tbody></table>
      </div>
    </div>
    <div class="two-col">
      <div class="panel">
        <div class="card-head"><div><h3 style="display:inline">Sources</h3><span class="sub">Every source is tried each run; a failure keeps its last good file</span></div></div>
        <div class="table-wrap short"><table data-role="sources"></table></div>
      </div>
      <div class="panel">
        <div class="card-head"><h3>Dedupe &amp; price history</h3></div>
        <div data-role="dedupe"></div>
        <div class="table-wrap short" style="margin-top:12px"><table data-role="history"></table></div>
      </div>
    </div>`;
}

function renderKpis(tab, rows) {
  const priced = rows.filter(r => r.price != null && r.asking);
  const el = tab._panel.querySelector('[data-role=kpis]');
  const cards = [];
  const med = median(priced.map(r => r.price));
  cards.push(kpi('For sale', rows.filter(r => r.asking).length.toLocaleString(), `${priced.length} priced · median ${fmtPrice(med)}`));
  if (priced.length) {
    const lo = priced.reduce((a, b) => (b.price < a.price ? b : a));
    const link = safeUrl(lo.link);
    const note = `${lo.reference} · ${lo.seller || lo.sites.join(', ')}`;
    cards.push(kpi('Lowest ask', fmtPrice(lo.price), link ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener">${escapeHtml(note)} &#8599;</a>` : escapeHtml(note)));
    cards.push(kpi('Highest ask', fmtPrice(Math.max(...priced.map(r => r.price))), `${uniq(priced.map(r => r.variant)).length} variants in view`));
  }
  const years = rows.map(r => r.year).filter(Boolean);
  cards.push(kpi('Years', years.length ? `${Math.min(...years)}–${Math.max(...years)}` : '–', `${years.length} listings state a year`));
  const bp = rows.filter(r => r.box_papers === 'Box & papers').length;
  cards.push(kpi('Box & papers', rows.length ? Math.round(bp / rows.length * 100) + '%' : '–', `${bp} of ${rows.length} listings`));
  // Biggest median move vs the last snapshot (whole search, not just the filtered view)
  const moved = tab.stats.filter(s => s.prev_median != null && s.median != null && s.prev_median !== s.median)
    .sort((a, b) => Math.abs(b.median / b.prev_median - 1) - Math.abs(a.median / a.prev_median - 1))[0];
  cards.push(moved
    ? kpi('Biggest move vs last', `<span class="${moved.median > moved.prev_median ? 'above' : 'below'}">${((moved.median / moved.prev_median - 1) * 100).toFixed(1)}%</span>`, escapeHtml(moved.variant))
    : kpi('Change vs last', tab.prev_run ? 'flat' : '–', tab.prev_run ? 'no variant median moved' : 'first snapshot'));
  cards.push(kpi('After dedupe', tab.dedupe.merged.toLocaleString(), `${tab.dedupe.raw.toLocaleString()} rows · ${tab.dedupe.multi} on 2+ sites`));
  el.innerHTML = cards.join('');
}

function priceCell(d) {
  let html = `<b>${d.price != null ? fmtPrice(d.price) : '<span class="muted">on request</span>'}</b>`;
  if (d.sources.length > 1) html += `<small>${d.sources.length} sites</small>`;
  return html;
}
function sourceCell(d) {
  return d.sources.map(s => {
    const link = safeUrl(s.link);
    const label = escapeHtml(s.site + ' ' + (s.price != null ? fmtPrice(s.price) : 'n/a'));
    return link ? `<a class="view-link" href="${escapeHtml(link)}" target="_blank" rel="noopener">${label}</a>` : label;
  }).join(' ');
}
function statusCell(d) {
  if (d.asking && d.status === 'For sale') return '<span class="badge good">for sale</span>';
  if (d.asking) return `<span class="badge great">${escapeHtml(d.status.toLowerCase())}</span>`;
  return `<span class="badge outlier">${escapeHtml(d.status.toLowerCase())}</span>`;
}

function renderTable(tab, rows) {
  const tbody = tab._panel.querySelector('[data-role=tbody]');
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="${COLS.length}" class="empty">No listings match these filters.</td></tr>`;
  } else {
    tbody.innerHTML = rows.slice(0, 1500).map(d => {
      const link = safeUrl(d.link);
      return `<tr>
        <td>${link ? `<a class="title-link" href="${escapeHtml(link)}" target="_blank" rel="noopener" title="${escapeHtml(d.title)}">${escapeHtml(d.reference)}</a>` : escapeHtml(d.reference)}</td>
        <td><span class="dot" style="background:${tab._color(d.variant)}"></span>${escapeHtml(d.variant)}</td>
        <td>${escapeHtml(d.dial) || '<span class="muted">–</span>'}</td>
        <td class="r">${d.year ?? '<span class="muted">–</span>'}</td>
        <td>${escapeHtml(d.box_papers) || '<span class="muted">–</span>'}</td>
        <td>${escapeHtml(d.condition) || '<span class="muted">–</span>'}</td>
        <td class="r">${priceCell(d)}</td>
        <td>${statusCell(d)}</td>
        <td class="wrap">${escapeHtml(d.seller)}</td>
        <td class="wrap">${escapeHtml(d.location)}</td>
        <td class="source-cell">${sourceCell(d)}</td>
        <td>${link ? `<a class="view-link" href="${escapeHtml(link)}" target="_blank" rel="noopener">View</a>` : ''}</td>
      </tr>`;
    }).join('');
  }
  tab._panel.querySelectorAll('th[data-key]').forEach(th => {
    th.querySelector('.arrow').textContent = th.dataset.key === tab._state.sortKey ? (tab._state.sortDir === 1 ? ' ▲' : ' ▼') : '';
  });
}

function renderCount(tab, rows) {
  const f = tab._state.filters;
  const active = Object.entries(f).some(([k, v]) => k !== 'sold' && v != null && v !== '' && v !== false);
  tab._panel.querySelector('[data-role=count]').textContent =
    `${rows.length} of ${tab.rows.length} listings` + (active ? ' (filters active)' : '');
}

function renderChart(tab, rows) {
  if (tab._chart) { tab._chart.destroy(); tab._chart = null; }
  if (typeof Chart === 'undefined') return;
  const mode = tab._state.chartMode;
  const pts = rows.filter(d => d.price != null && (mode === 'variant' || d.year != null));
  const vIndex = v => tab.variants.indexOf(v);
  const jitter = d => ((hashStr(d.link || d.reference) % 1000) / 1000 - 0.5) * (mode === 'variant' ? 0.5 : 0.6);
  const toPoint = d => ({ x: (mode === 'variant' ? vIndex(d.variant) : d.year) + jitter(d), y: d.price, d });
  const variants = tab.variants.filter(v => pts.some(d => d.variant === v));
  const datasets = variants.map(v => ({
    label: v, data: pts.filter(d => d.variant === v).map(toPoint),
    backgroundColor: tab._color(v), pointRadius: 4, pointHoverRadius: 7,
  }));
  tab._panel.querySelector('[data-role=chartsub]').textContent =
    `${pts.length} priced listings · colored by variant · log price scale · click a point to open the listing` +
    (mode === 'year' ? ` · ${rows.filter(d => d.price != null && d.year == null).length} without a year not shown` : '');
  const xScale = mode === 'variant'
    ? { type: 'linear', min: -0.6, max: tab.variants.length - 0.4,
        ticks: { color: '#8b93a3', stepSize: 1, autoSkip: false, maxRotation: 50, minRotation: 30,
                 callback: v => Number.isInteger(v) && tab.variants[v] ? tab.variants[v].split(' · ')[0].split(',')[0] : '' },
        grid: { color: '#1e2330' } }
    : { title: { display: true, text: 'Year', color: '#8b93a3' }, ticks: { color: '#8b93a3', stepSize: 1, callback: v => Number.isInteger(v) ? String(v) : '' }, grid: { color: '#1e2330' } };
  tab._chart = new Chart(tab._panel.querySelector('[data-role=canvas]').getContext('2d'), {
    type: 'scatter',
    data: { datasets },
    options: {
      animation: false, responsive: true, maintainAspectRatio: false,
      scales: {
        x: xScale,
        y: { type: 'logarithmic', title: { display: true, text: 'Price ($)', color: '#8b93a3' },
             ticks: { color: '#8b93a3', callback: v => { const s = String(v)[0]; return ['1', '2', '5'].includes(s) ? '$' + v.toLocaleString() : ''; } },
             grid: { color: '#1e2330' } },
      },
      plugins: {
        legend: { position: 'right', labels: { color: '#e6e9ef', usePointStyle: true, boxWidth: 8, boxHeight: 8, padding: 10, font: { size: 11 } }, title: { display: true, text: 'Variant', color: '#8b93a3' } },
        tooltip: { callbacks: { label: c => {
          const d = c.raw.d;
          const sites = d.sources.length > 1 ? d.sources.map(s => s.site + ' ' + fmtPrice(s.price)).join(' · ') : d.sites.join(', ');
          return [d.reference + ' · ' + d.variant, fmtPrice(d.price) + (d.year ? ' · ' + d.year : ''), d.box_papers, sites, d.seller || d.location].filter(Boolean);
        } } },
      },
      onClick: (evt, els) => {
        if (!els.length) return;
        const el = els[0];
        const link = safeUrl(datasets[el.datasetIndex].data[el.index].d.link);
        if (link) window.open(link, '_blank', 'noopener');
      },
      onHover: (evt, els) => { evt.native.target.style.cursor = els.length ? 'pointer' : 'default'; },
    },
  });
}

function renderStats(tab) {
  const el = tab._panel.querySelector('[data-role=stats]');
  el.innerHTML = `<thead><tr><th class="no-sort">Variant</th><th class="no-sort r">Count</th><th class="no-sort r">Low</th><th class="no-sort r">Median</th><th class="no-sort r">High</th><th class="no-sort">Change vs last snapshot</th><th class="no-sort">By source (count · low · median)</th></tr></thead><tbody>` +
    tab.stats.map(s => `<tr>
      <td><span class="dot" style="background:${tab._color(s.variant)}"></span><a href="#" class="title-link" data-variant="${escapeHtml(s.variant)}">${escapeHtml(s.variant)}</a></td>
      <td class="r">${s.count}</td><td class="r">${fmtPrice(s.low)}</td><td class="r"><b>${fmtPrice(s.median)}</b></td><td class="r">${fmtPrice(s.high)}</td>
      <td>${delta(s.median, s.prev_median)}</td>
      <td class="wrap muted" style="font-size:12px">${s.per_source.map(p => `${escapeHtml(p.source)}: ${p.count} · ${fmtPrice(p.low)} · ${fmtPrice(p.median)}`).join('<br>')}</td>
    </tr>`).join('') + '</tbody>';
  el.querySelectorAll('[data-variant]').forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    tab._state.filters.variant = a.dataset.variant;
    tab._panel.querySelector('[data-f=variant]').value = a.dataset.variant;
    renderTab(tab);
    tab._panel.querySelector('[data-role=tbody]').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));
}

function renderSources(tab) {
  const el = tab._panel.querySelector('[data-role=sources]');
  el.innerHTML = `<thead><tr><th class="no-sort">Source</th><th class="no-sort">Status</th><th class="no-sort r">Rows kept</th><th class="no-sort">Last good scrape</th><th class="no-sort">Note</th></tr></thead><tbody>` +
    tab.sources.map(s => {
      const badge = s.ok ? (s.rows ? '<span class="badge good">worked</span>' : '<span class="badge outlier">worked, none listed</span>') : '<span class="badge fair">blocked / failed</span>';
      return `<tr><td>${escapeHtml(s.name)}</td><td>${badge}</td><td class="r">${s.rows ?? ''}</td>
        <td class="muted">${s.scraped_at ? escapeHtml(formatAsOf(s.scraped_at)) : '–'}</td><td class="wrap muted" style="font-size:12px">${escapeHtml(s.warning)}</td></tr>`;
    }).join('') + '</tbody>';
}

function renderDedupe(tab) {
  const d = tab.dedupe;
  tab._panel.querySelector('[data-role=dedupe]').innerHTML = `
    <div class="kpis" style="margin-bottom:6px">${kpi('Source rows', d.raw.toLocaleString(), 'all sources, before merge')}${kpi('Watches', d.merged.toLocaleString(), 'after dedupe')}${kpi('On 2+ sites', d.multi, 'merged across sources')}</div>
    <p class="footnote">Same listing id on one source is kept once. A dealer's own listing joins a Chrono24 listing only when the variant matches, the price is within 2%, the year does not conflict and the Chrono24 seller is that dealer. Two Chrono24 listings never merge.</p>`;
  const h = tab.history;
  const el = tab._panel.querySelector('[data-role=history]');
  if (!h.runs.length) { el.innerHTML = ''; return; }
  el.innerHTML = `<thead><tr><th class="no-sort">Median by snapshot</th>${h.runs.map(r => `<th class="no-sort r">${escapeHtml(formatAsOf(r).replace(/, \d{4},/, ','))}</th>`).join('')}</tr></thead><tbody>` +
    h.series.map(s => `<tr><td class="wrap"><span class="dot" style="background:${tab._color(s.variant)}"></span>${escapeHtml(s.variant)}</td>${s.points.map(p => `<td class="r">${p ? fmtPrice(p.median) + ` <span class="muted">(${p.count})</span>` : ''}</td>`).join('')}</tr>`).join('') + '</tbody>';
}

function renderTab(tab) {
  const rows = visibleRows(tab);
  renderKpis(tab, rows);
  renderCount(tab, rows);
  renderTable(tab, rows);
  renderChart(tab, rows);
}

function readFilters(tab) {
  const f = tab._state.filters;
  tab._panel.querySelectorAll('[data-f]').forEach(el => {
    const k = el.dataset.f;
    if (el.type === 'checkbox') f[k] = el.checked;
    else if (['priceMin', 'priceMax', 'yearMin', 'yearMax'].includes(k)) f[k] = numOrNull(el.value);
    else f[k] = el.value.trim();
  });
}

function activateTab(slug) {
  TABS.forEach(t => {
    const on = t.slug === slug;
    t._btn.classList.toggle('active', on);
    t._panel.classList.toggle('active', on);
    if (on) renderChart(t, visibleRows(t));
  });
  history.replaceState(null, '', '#' + slug);
}

// ---------- init ----------
const tabButtons = document.getElementById('tabButtons');
const tabPanels = document.getElementById('tabPanels');
const times = TABS.map(t => Date.parse(t.scraped_at)).filter(t => !Number.isNaN(t));
document.getElementById('dataAsOf').textContent = times.length ? 'Data as of ' + formatAsOf(new Date(Math.min(...times)).toISOString()) + ' (America/Chicago) · ' : '';
document.getElementById('genAt').textContent = formatAsOf(GENERATED_AT);
const start = TABS.some(t => '#' + t.slug === location.hash) ? location.hash.slice(1) : (TABS[0] || {}).slug;

TABS.forEach(tab => {
  tab._state = newState();
  tab.rows.forEach(prepRow);
  tab._color = v => colorFor(Math.max(0, tab.variants.indexOf(v)), tab.variants.length);
  const btn = document.createElement('button');
  btn.className = 'tab-btn' + (tab.slug === start ? ' active' : '');
  btn.innerHTML = `${escapeHtml(tab.title)}<span class="count-pill">${tab.rows.filter(r => r.asking).length}</span>`;
  btn.addEventListener('click', () => activateTab(tab.slug));
  tabButtons.appendChild(btn);
  tab._btn = btn;
  const panel = document.createElement('div');
  panel.className = 'tab-panel' + (tab.slug === start ? ' active' : '');
  panel.innerHTML = panelHTML(tab);
  tabPanels.appendChild(panel);
  tab._panel = panel;

  const rerender = debounce(() => { readFilters(tab); renderTab(tab); }, 150);
  panel.querySelectorAll('[data-f]').forEach(el => el.addEventListener(el.tagName === 'SELECT' || el.type === 'checkbox' ? 'change' : 'input', rerender));
  panel.querySelector('[data-role=reset]').addEventListener('click', () => {
    panel.querySelectorAll('[data-f]').forEach(el => { if (el.type === 'checkbox') el.checked = false; else el.value = ''; });
    readFilters(tab); renderTab(tab);
  });
  panel.querySelectorAll('th[data-key]').forEach(th => th.addEventListener('click', () => {
    const k = th.dataset.key;
    tab._state.sortDir = tab._state.sortKey === k ? -tab._state.sortDir : 1;
    tab._state.sortKey = k;
    renderTable(tab, visibleRows(tab));
  }));
  panel.querySelectorAll('[data-mode]').forEach(b => b.addEventListener('click', () => {
    tab._state.chartMode = b.dataset.mode;
    panel.querySelectorAll('[data-mode]').forEach(x => x.classList.toggle('on', x === b));
    renderChart(tab, visibleRows(tab));
  }));
  renderStats(tab);
  renderSources(tab);
  renderDedupe(tab);
  renderTab(tab);
});
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=str(Path(__file__).resolve().parent / "output" / "report.html"))
    ap.add_argument("--slug", action="append", default=None)
    a = ap.parse_args()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    build(a.slug or SLUGS, a.out)


if __name__ == "__main__":
    main()
