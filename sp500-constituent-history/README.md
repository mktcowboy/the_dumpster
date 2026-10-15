# S&P 500 Constituent Changes — 20 Years

An interactive, self-contained HTML page showing every recorded S&P 500
addition and removal from **2007-01-10 through 2026-10-06 (392 events)**, plotted as
markers over 20 years of SPY monthly closes.

## What's inside

- `index.html` — the page (loads its data from `events.js` next to it; keep them together).
  Open in any browser (works offline, no CDN).
  - SPY chart (monthly closes) with a vertical marker for every change date
    (blue = net additions, red = net removals, gray = balanced; count badge
    when several changes share a date)
  - Hover any marker for that day's tickers/companies; click it to jump to
    the row in the table
  - Additions vs. removals bar strip by year
  - Full searchable/sortable change log: effective date, ticker + company
    added, ticker + company removed, reason
- `events.js` — the 392 change events as a JS variable (page data)
- `changes_20yr.json` — the 392 change events (date, added/removed
  ticker + name, reason), newest source pull
- `spy_monthly.json` — 240 SPY monthly closes (Nov 2006 – Oct 2026, Yahoo)
- `build.py` — regenerates `index.html` from the two JSON files

## Stats

- 392 change events · 372 additions · 369 removals
- Busiest year: 2016 (30 changes); busiest days: Dec 18, 2009 and
  Jul 26, 2017 (5 changes each)

## Patches vs Wikipedia (Oct 14, 2026)

- Added the missing 2010-02-16 swap: Berkshire Hathaway (BRK.B) replaced
  Burlington Northern Santa Fe (BNI), which Berkshire acquired — verified
  against contemporary S&P/Reuters reporting.
- Fixed ticker artifacts on the 2013-12-02 Allegion/JCPenney row.
- Cross-checked all 49 current constituents whose "Date added" had no
  matching log event: all resolved as ticker renames (EG=RE, META=FB,
  CPAY=FLT, TT=IR, SATS→ECHO, WRK→SW, DLPH→APTV) or erroneous "Date added"
  values (D, SRE, TROW, HUM, AKAM — no S&P addition announcement exists on
  those dates). No other gaps found.

## Sources

- Change log: Wikipedia, "Historical components of the S&P 500"
  (retrieved 2026-10-14). Effective dates as published; announcement and
  effective dates can differ by a day.
- Prices: SPY monthly closes, Yahoo Finance.

## Coverage caveats

- Wikipedia's table is community-maintained and essentially complete for
  recent years; a handful of early-2000s entries may be missing.
- One-sided rows (empty Added or Removed cell) reflect spin-offs / corporate
  actions recorded as single-sided index changes.
- The index had ~500 members throughout; this log tracks the turnover only.
