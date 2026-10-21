# Nasdaq-100 earnings straddles

A seller's-view screen of at-the-money earnings straddles for Nasdaq-100 names.
It pulls prices, earnings dates, and option chains from Yahoo Finance through
`yfinance`, compares today's implied move with recent realized earnings moves,
and builds a static HTML site.

The committed `site/` folder is the October 21, 2026 snapshot (analysis as of
15:21 CT, site built 15:23 CT): 101 names, zero failures, and 101 straddle
snapshots.

## View the site

Open [`site/index.html`](site/index.html) in a browser, or serve it:

```sh
cd markets/er-straddles/site
python3 -m http.server 8765
```

Then open <http://127.0.0.1:8765>. The index is one sortable table. Green rows
are names where selling looks rich; red rows are names where the implied move
is below recent history. Each ticker links to a detail page with the move
chart, quarter-by-quarter table, and the straddle snapshot series. Detail
charts load Chart.js from a CDN.

## Setup

From the repository root:

```sh
python3 -m venv markets/er-straddles/.venv
. markets/er-straddles/.venv/bin/activate
python3 -m pip install -r markets/er-straddles/requirements.txt
```

`run_daily.sh` expects that virtualenv at `.venv` inside this folder. The
scripts resolve `output/` and `site/` from their own location, so they can be
run from the repository root or from this directory.

## Run

One or more tickers. Prints a console report and writes
`output/<TICKER>_history.csv`, `output/<TICKER>_summary.json`, and
`output/<TICKER>_moves.png`.

```sh
python3 markets/er-straddles/analyze.py AAPL
python3 markets/er-straddles/analyze.py AAPL NVDA
```

Every current Nasdaq-100 name, or an explicit list. Writes the same per-ticker
files plus `output/results.json`. Unless `--no-snapshot` is set, it also
appends today's straddles through `snapshot.py`. `--limit N` stops after N
names.

```sh
python3 markets/er-straddles/batch.py
python3 markets/er-straddles/batch.py --no-snapshot --limit 5
python3 markets/er-straddles/batch.py AAPL MSFT NVDA
```

A full universe run is on the order of several minutes. Yahoo rate-limits
bursts; the batch sleeps briefly between names and retries each name once.

Appends the ATM straddle for the event's post-earnings expiry to
`output/snapshots.csv`. With no arguments it uses the full Nasdaq-100 list.
The event is the most recent earnings if it is within the last 10 calendar
days and that expiry is still listed; otherwise it is the next earnings. That
keeps the same contract on the sheet through the IV crush.

```sh
python3 markets/er-straddles/snapshot.py AAPL
python3 markets/er-straddles/snapshot.py
```

Rebuilds `site/` from `output/results.json` and, when present,
`output/snapshots.csv`. Per-ticker CSV, JSON, and PNG files are copied into
`site/data/` and `site/img/`.

```sh
python3 markets/er-straddles/build_site.py
```

`./run_daily.sh` (from this directory) activates `.venv`, runs `batch.py`
(analysis plus the snapshot append), then `build_site.py`. A weekday run
around 14:45 CT, before the cash close, matches the comment in the script.

Constituents come from the Nasdaq.com list, with Wikipedia as a fallback, and
are cached in `output/n100.json` for seven days. Refresh the cache with
`python3 markets/er-straddles/n100.py`.

## Files

| File | Purpose |
| --- | --- |
| `core.py` | Earnings dates, realized moves, ATM straddle, and implied-move math |
| `analyze.py` | Single-ticker report, CSV, JSON, and chart |
| `batch.py` | Nasdaq-100 loop into `output/results.json` |
| `n100.py` | Constituent list and `output/n100.json` cache |
| `snapshot.py` | Daily append to `output/snapshots.csv` |
| `build_site.py` | Static site under `site/` |
| `run_daily.sh` | Batch plus site rebuild |
| `site/` | October 21, 2026 HTML snapshot |
| `output/n100.json` | Cached Nasdaq-100 constituents from that run |
| `requirements.txt` | Python dependencies |

A fresh run writes charts, per-ticker tables, `results.json`, `snapshots.csv`,
and logs under `output/`. `.gitignore` leaves that working directory local.
`build_site.py` copies the published files into `site/`, and that copy is what
the repository keeps. The October 21 per-ticker files already live in
`site/data` and `site/img`. `output/n100.json` stays tracked so the scripts
can fall back to it when Nasdaq and Wikipedia are unreachable.

## yfinance limits

`yfinance` is a free, unofficial Yahoo Finance scraper.

- Option quotes are delayed by about 15 minutes. After hours, bid and ask can
  be stale or zero; the straddle then falls back to the last trade.
- Future earnings dates and times are often estimates. Timing that Yahoo does
  not stamp (`UNK`) is treated as after the close.
- Yahoo does not provide historical option prices, so past implied moves
  cannot be rebuilt. The backtest applies **today's** implied move to every
  past quarter (up to 12). Reported P&L ignores residual time value, the
  bid-ask spread, commissions, and assignment.
- The listed straddle still contains non-earnings time value out to expiry.
  The earnings-only columns, from the term-structure variance difference
  versus the pre-earnings expiry, are the closer comparison to the earnings
  reaction itself.
- Straddle-price history on the detail pages exists only for days
  `snapshot.py` has been run. This snapshot has a single day, October 21, 2026.
