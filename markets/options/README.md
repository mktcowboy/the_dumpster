# Options — max pain

A SPY × QQQ max-pain report, a scanner for the entire QQQ universe, and the
reproducible pipeline behind both.

For an auto-refreshing dashboard with click-through ticker details, see
[`markets/options-live/`](../options-live/).

| File | Purpose |
| --- | --- |
| `index.html` | Standalone SPY × QQQ report for the Oct 23, 2026 expiry, based on the Oct 19 close |
| `qqq-max-pain.html` | Ranked board for every loadable QQQ holding (Oct 20, 2026 snapshot) |
| `max_pain.py` | Fetches live chains from Cboe, computes the metrics, and writes JSON snapshots |
| `data/` | Dated snapshots produced by `max_pain.py` |
| `requirements.txt` | `requests` (the only dependency) |

The two HTML files are presentation layers. The script produces the numbers;
it does not rewrite the hand-authored report.

## Quick start

```sh
python3 -m pip install -r markets/options/requirements.txt

# Two-ticker snapshot
python3 markets/options/max_pain.py --tickers SPY QQQ --expiry 2026-10-23

# Every QQQ holding, plus a standalone HTML board
python3 markets/options/max_pain.py --universe qqq --expiry 2026-10-23 \
  --html-out markets/options/qqq-max-pain.html
```

The script prints a ranked summary and writes JSON to
`markets/options/data/`. Use `--out` to override the path.

```
Ticker      Spot   OI max    Away  Vol max    Blend     Shelf         Exp  DTE      Pin
CSX        48.04    48.00  -0.08%    39.00    48.00        48         10/23    3      Low
AAPL      342.06   342.50  +0.13%   340.00   342.50     342.5         10/23    3 Moderate
GOOGL     343.90   345.00  +0.32%   342.50   345.00       345         10/23    3 Moderate
LIN       501.96   500.00  -0.39%   500.00   500.00       500     11/20+28d   31     High
...
```

The generated board loaded all 101 QQQ holdings. 78 had the requested Oct 23
weekly; 23 names without that weekly fell back to the Nov 20 monthly and are
marked with a `+28d` drift.

## Universe mode

`--universe qqq` reads the current Nasdaq-100 constituent list from the
[Wikipedia holdings table](https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies),
deduplicates the tickers, and fetches each chain from Cboe.

| Flag | Behavior |
| --- | --- |
| `--expiry-mode exact` | Skip a ticker if the requested expiry is not listed |
| `--expiry-mode nearest` | Use the next listed expiry when the requested one is missing |
| `--expiry-mode auto` | Exact for explicit tickers; nearest for `--universe qqq` |
| `--workers N` | Parallel requests (default 4) |
| `--chains full` | Include every strike in the JSON (auto: on for tickers, off for a universe) |
| `--chains none` | Omit per-strike chains to keep the snapshot small |
| `--summary-limit N` | Rows printed to the terminal (default 25 for a universe, all for tickers) |
| `--html-out PATH` | Write the standalone sortable board |

The script throttles Cboe requests and automatically retries tickers that hit a
rate limit. A full universe run takes about a minute.

## What the snapshot contains

Each snapshot has top-level metadata (`as_of`, `requested_expiry`, `expiry_mode`,
`settlement`, `source`, `universe`, `method`) and one object per ticker under
`snapshots`:

- `spot`, `prev_close`, `change_pct`
- `expiry`, `requested_expiry`, `expiry_drift_days`, `dte`
- `chain` (optional): every listed strike, with call and put `oi`, `volume`,
  `iv`, `delta`, `gamma`, `bid`, `ask`, `mid`, and `last`. IVs are decimal
  fractions (`0.1534` is 15.34%)
- `metrics.max_pain`: OI, volume, and blended max pain, the 1% shelf, distance
  from spot, and a method-spread confidence score
- `metrics.payout`: modeled payout at spot, the minimum payout, and the pain
  slope per $1
- `metrics.walls`: largest call-OI and put-OI strikes
- `metrics.ratios`: put/call open interest and volume
- `metrics.volatility`: ATM strike, ATM IV, ATM straddle, 1σ move and range,
  and the 25-delta risk reversal
- `metrics.gamma`: modeled net GEX per 1% move and the gamma flip
- `metrics.top_strikes`: top 12 strikes by combined OI, with tags
- `metrics.totals`: call/put OI and volume, and the strike count

`universe.skipped` records any ticker that could not be loaded and why.

## Definitions

**Max pain.** For each listed strike, compute the intrinsic payout to option
holders if the underlying settles there:

```
calls: OI × max(0, settlement − strike) × 100
puts:  OI × max(0, strike − settlement) × 100
```

The strike with the smallest total is the max-pain level. The volume variant
uses session volume; the blend uses `OI + 0.5 × volume` on each side. The
script brute-forces every listed strike, so nothing is interpolated.

**Pain shelf.** Every strike within 1% of the minimum payout. It shows how
flat the bottom of the curve is; a wider shelf is a weaker pin.

**Pin confidence.** A heuristic, not a probability: High when the OI, volume,
and blend levels are within 0.5% of spot, Moderate within 1%, otherwise Low.

**1σ range.** `spot × ATM IV × √(DTE / 365)`, where ATM IV is the mean of the
nearest-strike call and put IVs. If the nearest strike has no usable quotes,
the script walks outward to the closest strike with an IV.

**25-delta risk reversal.** 25-delta put IV minus 25-delta call IV, in
volatility points. Positive means puts are richer than calls.

**Net GEX.** Black-Scholes gamma at each hypothetical spot × OI × 100 × S² ×
0.01, with calls positive and puts negative. The gamma flip is the nearest
zero crossing within ±15% of spot.

## Data source and caveats

- The script uses Cboe's delayed-quote endpoint for the full chain, including
  OI, volume, IV, and Greeks. Yahoo Finance via yfinance is the source named in
  the hand-authored report; the endpoint was unreliable when this pipeline was
  built.
- The QQQ universe is the Nasdaq-100 list, not Invesco's exact share-level
  holdings. It includes dual-class lines such as `GOOG`/`GOOGL` and does not
  apply index weights.
- Open interest is the exchange's latest published value. Intraday volume is
  partial, so a snapshot taken during the session will differ from a
  close-of-day snapshot.
- Tickers without the requested weekly fall back to the next listed expiry in
  universe mode. Their `expiry_drift_days` field makes the mismatch explicit;
  do not compare their DTE-sensitive metrics directly with the weekly names.
- The sign convention assumes dealers are short calls and long puts. Actual
  positioning is unobservable.
- Max pain is descriptive, not a price target. PM settlement, closing-auction
  flow, and large unwinds can move the level.
