# Nasdaq-100 earnings straddles

A seller's-view screen of at-the-money earnings straddles for Nasdaq-100 names.
It pulls prices, earnings dates, and option chains from Yahoo Finance through
`yfinance`, checks those dates against Nasdaq's earnings calendar, compares
today's implied move with recent realized earnings moves, and builds a static
HTML site.

The committed `site/` folder is the October 21, 2026 snapshot (analysis as of
16:29 CT, site built 16:32 CT): 101 names, zero failures, and 202 straddle
snapshots (a pm pass plus a later pass the same day). Date check: 81 confirmed,
9 mismatches, 11 unconfirmed. Liquidity: A 4, B 14, C 16, F 67. No name yet has
both a pre-event and a post-event snapshot, so the IV-crush table is empty.

## View the site

Open [`site/index.html`](site/index.html) in a browser, or serve it:

```sh
cd markets/er-straddles/site
python3 -m http.server 8765
```

Then open <http://127.0.0.1:8765>. The index is one sortable table. Green rows
are names where selling looks rich under the rules in `config.json` (rich
score, liquidity grade A/B/C, positive net expectancy after costs, net hit
rate, quarter count, and no date mismatch). Red rows are cheap to sell. Each
ticker links to a detail page with the move chart, the cost-aware P&L, the
quarter table, the straddle snapshot series, and IV-crush history once a name
has a before-and-after pair. Detail charts load Chart.js from a CDN.

## Setup

From the repository root:

```sh
python3 -m venv markets/er-straddles/.venv
. markets/er-straddles/.venv/bin/activate
python3 -m pip install -r markets/er-straddles/requirements.txt
```

`run_daily.sh` and `run_morning.sh` expect that virtualenv at `.venv` inside
this folder. The scripts resolve `output/` and `site/` from their own location,
so they can be run from the repository root or from this directory.

`config.json` (loaded by `config.py`) holds commissions, slippage as a
fraction of the half-spread, liquidity grade thresholds, and the rich-row
rules. Edit that file to retune costs. The site copies it to
`site/data/config.json` on each build.

## Run

One or more tickers. Prints a console report (date check, straddles, naive
move stats, liquidity grade, and the cost-aware net P&L) and writes
`output/<TICKER>_history.csv`, `output/<TICKER>_summary.json`, and
`output/<TICKER>_moves.png`.

```sh
python3 markets/er-straddles/analyze.py AAPL
python3 markets/er-straddles/analyze.py AAPL NVDA
```

Every current Nasdaq-100 name, or an explicit list. Writes the same per-ticker
files plus `output/results.json`. Unless `--no-snapshot` is set, it also
appends today's straddles through `snapshot.py`, then rebuilds
`output/crush_events.csv`. `--limit N` stops after N names.

```sh
python3 markets/er-straddles/batch.py
python3 markets/er-straddles/batch.py --no-snapshot --limit 5
python3 markets/er-straddles/batch.py AAPL MSFT NVDA
```

A full universe run is on the order of several minutes. Yahoo rate-limits
bursts; the batch sleeps briefly between names and retries each name once.
The Nasdaq earnings calendar for the next 120 days is fetched once per process
and cached under `output/cache/nasdaq_cal/` (refetched when a file is older
than 12 hours).

Appends the ATM straddle for the event's post-earnings expiry to
`output/snapshots.csv`. With no arguments it uses the full Nasdaq-100 list.
The event is the most recent earnings if it is within the last 10 calendar
days and that expiry is still listed; otherwise it is the next earnings, with
Yahoo and Nasdaq reconciled. That keeps the same contract on the sheet through
the IV crush. After the event, the row also re-prices the strike held on the
last pre-event snapshot (`held_*` columns).

```sh
python3 markets/er-straddles/snapshot.py AAPL
python3 markets/er-straddles/snapshot.py
python3 markets/er-straddles/snapshot.py --session am --reporters-only
python3 markets/er-straddles/snapshot.py --session pm
```

| Flag | Behavior |
| --- | --- |
| `--session am` or `--session pm` | Tag the rows. Default follows the America/Chicago clock: `am` before the cutoff hour in `config.json` (12), otherwise `pm` |
| `--reporters-only` | Only names whose reaction day is today (reported last night after the close, or before the open today). Candidates come from `output/results.json`, so the morning run stays short |

`crush.py` reads `output/snapshots.csv` and writes `output/crush_events.csv`.
An event is the last pre-announcement snapshot versus the first snapshot on or
after the reaction day, same expiry (the reaction-day `am` row is preferred).
It records the straddle drop, the IV drop, and, when the held-strike columns
are present, seller P&L as a percent of premium.

```sh
python3 markets/er-straddles/crush.py
```

Rebuilds `site/` from `output/results.json` and, when present,
`output/snapshots.csv`. It recomputes crush events, then copies per-ticker
CSV, JSON, and PNG files into `site/data/` and `site/img/`.

```sh
python3 markets/er-straddles/build_site.py
```

`./run_daily.sh` (from this directory) activates `.venv`, runs `batch.py`
(analysis, the pm snapshot append, and the crush table), then `build_site.py`.
The script comment schedules that for weekdays around 14:40 CT, before the
cash close.

`./run_morning.sh` activates `.venv`, runs
`snapshot.py --session am --reporters-only`, then `build_site.py` (which
rewrites the crush table). The script comment schedules that for weekdays
around 09:00 CT.

Constituents come from the Nasdaq.com list, with Wikipedia as a fallback, and
are cached in `output/n100.json` for seven days. Refresh the cache with
`python3 markets/er-straddles/n100.py`.

## What the new columns mean

**Date check** (`earnings_cal.py`). Yahoo's next earnings date is compared
with Nasdaq's calendar. `Confirmed` means the dates agree. `Mismatch` means
the dates differ, or both sources name BMO versus AMC; the expiry is then
chosen so it covers both candidate reaction days, and a timing conflict is
treated as after the close. `Unconfirmed` means only one source has a date
inside the calendar window.

**Liquidity grades.** The post-earnings ATM straddle is graded from combined
call and put open interest, volume, and bid/ask width as a percent of the
straddle. A, B, and C use the thresholds in `config.json`. Anything wider,
thinner, or priced off the last trade is F.

**Cost-aware P&L.** Entry is a sale of the ATM straddle at the close before
the event. Exit is a buyback at the reaction-day close, including residual
time value out to expiry. Net subtracts entry and exit slippage (fractions of
the half-spread) and commissions (`$0.65` per contract per leg per side in the
default config). The naive table on the console still compares today's implied
move with the realized close-to-close move. The NET line is the cost-aware
model. Ex-earnings volatility is the ATM IV of the expiry before earnings, or
63-day realized vol with earnings days removed when that expiry is missing.

**IV crush.** Straddle and IV change from the last pre-event snapshot to the
first post-event snapshot on the same expiry. This snapshot has same-day rows
only, so the crush history is still collecting.

## Files

| File | Purpose |
| --- | --- |
| `core.py` | Earnings dates, realized moves, ATM straddle, liquidity, and the cost-aware model |
| `config.json`, `config.py` | Costs, liquidity thresholds, and rich-row rules |
| `earnings_cal.py` | Nasdaq earnings calendar and Yahoo reconciliation |
| `analyze.py` | Single-ticker report, CSV, JSON, and chart |
| `batch.py` | Nasdaq-100 loop into `output/results.json`, then snapshot and crush |
| `n100.py` | Constituent list and `output/n100.json` cache |
| `snapshot.py` | Append to `output/snapshots.csv`, with `--session` and `--reporters-only` |
| `crush.py` | IV-crush events in `output/crush_events.csv` |
| `build_site.py` | Static site under `site/` |
| `run_daily.sh` | Afternoon batch plus site rebuild |
| `run_morning.sh` | Morning snapshot of names reacting today, then site rebuild |
| `site/` | October 21, 2026 HTML snapshot |
| `output/n100.json` | Cached Nasdaq-100 constituents |
| `output/cache/nasdaq_cal/` | Cached Nasdaq earnings-calendar days |
| `output/snapshots.csv` | Append-only straddle sheet (202 rows in this snapshot) |
| `output/crush_events.csv` | Crush events derived from those snapshots |
| `requirements.txt` | Python dependencies |

A fresh run also writes charts, per-ticker tables, `results.json`, and logs
under `output/`. `.gitignore` leaves those local. `build_site.py` copies the
published files into `site/`. The snapshot sheet and the crush table stay in
`output/` as well, because later `snapshot.py` and `crush.py` runs append to
and read those files. The calendar cache is the fallback when Nasdaq is
unreachable, and it skips a refetch for 12 hours.

## yfinance limits

`yfinance` is a free, unofficial Yahoo Finance scraper.

- Option quotes are delayed by about 15 minutes. After hours, bid and ask can
  be stale or zero; the straddle then falls back to the last trade, and the
  liquidity grade becomes F.
- Earnings dates from Yahoo and from Nasdaq can both be estimates until the
  company announces. Timing that neither source stamps (`UNK`) is treated as
  after the close.
- Yahoo does not provide historical option prices, so past implied moves
  cannot be rebuilt. The backtest applies **today's** term structure to every
  past quarter (up to 12).
- The listed straddle still contains non-earnings time value out to expiry.
  The earnings-only columns, from the term-structure variance difference
  versus the pre-earnings expiry, are the closer comparison to the earnings
  reaction itself. The cost-aware model prices that residual explicitly.
- IV-crush stats exist only for events `snapshot.py` has seen both before and
  after. This snapshot is a single calendar day, October 21, 2026.
