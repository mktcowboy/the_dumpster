# drawdown-check

Command-line tool that, given one or more tickers, reports how far the latest close is below the all-time high and writes a [testfol.io](https://testfol.io/)-style drawdown chart.

Headline numbers use **adjusted close** from Yahoo Finance (total-return-ish: splits and dividends). Unadjusted close is also computed and printed when it differs. If Yahoo fails, the tool falls back to Stooq daily CSV (typically split-adjusted, not dividend-adjusted). The report always states which series and source were used.

Drawdowns are measured against the all-time high since the start of the history window (the first available session, or `--start` if given). The chart is the same window.

## Install

```bash
python3 -m pip install -r requirements.txt
```

## Usage

```bash
python3 drawdown.py QQQ
python3 drawdown.py QQQ NVDA
python3 drawdown.py QQQ,SPY --start 2015-01-01 --end 2024-12-31
python3 drawdown.py QQQ --out-dir ./out
python3 drawdown.py QQQ --no-chart
python3 drawdown.py NVDA --iv
python3 iv.py NVDA QQQ --history --snapshot
```

### Options

| Flag | Meaning |
| --- | --- |
| `tickers` | One or more symbols, space- or comma-separated |
| `--start YYYY-MM-DD` | History start; ATH and drawdowns are computed from this date |
| `--end YYYY-MM-DD` | History end (default: latest available session) |
| `--out-dir DIR` | Where to write `<TICKER>_drawdown.png` (default: `/workspace/drawdown/out`) |
| `--no-chart` | Print stats only; skip PNGs |
| `--iv` | Also print 30-day ATM and 25-delta implied volatility from the live option chain |
| `--iv-snapshot` | With `--iv`, append today's IV metrics to `data/iv_snapshots.csv` |

## Output

For each ticker the tool prints:

- Price basis and data source
- All-time high value and date
- Latest close and date
- Current drawdown %
- Maximum drawdown ever in the window, with peak and trough dates
- Calendar days since the ATH
- Unadjusted-close drawdown, when it differs
- Path to the chart PNG

Charts use a dark navy background (`#131a2e`), a light-blue line (`#6fa8f5`) with a semi-transparent fill down from 0%, a y-axis labeled **Drawdown** in percent with 0% at the top, subtle gridlines, and a legend with the ticker.

## Example

```text
$ python3 drawdown.py QQQ
QQQ
  Price basis:     adjusted close (yfinance, total-return-ish)
  Source:          yfinance
  ATH:             ...
  Latest close:    ...
  Current drawdown: -x.xx%
  Max drawdown:    -xx.xx%  (peak YYYY-MM-DD → trough YYYY-MM-DD)
  Days since ATH:  N
  Chart:           /workspace/drawdown/out/QQQ_drawdown.png
```

## Local HTML page

`drawdown.html` is a self-contained page you can open by double-clicking (a `file://` URL). Type a ticker (or several, comma-separated) and press Enter.

It shows current drawdown from the all-time high as a headline, plus ATH, latest close, max drawdown (peak → trough), and days since ATH. A price chart (adjusted close, with a log/linear toggle and the ATH marked) sits above a testfol.io-style drawdown chart. The 1Y / 5Y / 10Y / Max buttons and chart zoom apply to both panels together.

Yahoo's chart API blocks browser CORS, so the page calls a small Cloudflare Worker that proxies the Yahoo v8 chart endpoint, live 30-day IV, and official vol-index history. Paste that Worker URL into the page's Proxy field, or add `?proxy=` to the page URL. (`range=max&interval=1d` currently returns monthly bars, so the worker requests `period1=0&period2=<now>&interval=1d&events=div,split&includeAdjustedClose=true` instead.)

Source: `worker/src/index.js` (Wrangler config in `worker/wrangler.jsonc`). Endpoints: `GET /chart/TICKER`, `GET /iv/TICKER`, and `GET /volindex/INDEX`.

## Implied volatility

`iv.py` (also available as `drawdown.py --iv`) computes, from the **live** CBOE delayed option chain (yfinance fallback):

- 30-day constant-maturity ATM IV (forward-strike interpolation, total-variance interpolation across the two expiries that bracket 30 calendar days)
- 30-day 25-delta put IV and 25-delta call IV (Black-Scholes deltas from each contract's IV)
- 25-delta put-minus-call skew

CBOE's published `iv30` is printed as a cross-check. Yahoo's option API now requires a crumb and returns 401 without one; the CBOE delayed-quotes JSON is the live source, and it already includes vendor IV and greeks.

**Historical 25-delta put IV for a single stock (the SpotGamma-style series) is not available for free.** There is no CBOE `VXNVDA` index (that CSV 403s). Official free proxies that *do* work:

| Ticker | Proxy | Source (verified) |
| --- | --- | --- |
| SPY (and SPX) | VIX | CBOE CSV from 1990; Yahoo `^VIX` daily history |
| QQQ (and NDX) | VXN | CBOE CSV from 2009; Yahoo `^VXN` daily history |
| IWM | RVX | CBOE CSV |
| AAPL, AMZN, GOOG/GOOGL, GS, IBM | VXAPL, VXAZN, VXGOG, VXGS, VXIBM | CBOE Equity VIX CSVs (Yahoo chart only has a current print) |

These official indexes are VIX-style *variance-strip* 30-day IVs, not 25-delta put IV, so they will not match a SpotGamma 25-delta series exactly.

To **accumulate** our own 30-day 25-delta history going forward, run a weekday snapshot after the cash close (about 16:15 America/New_York):

```bash
python3 /workspace/drawdown/iv.py NVDA QQQ SPY AAPL --snapshot
```

That appends a row to `data/iv_snapshots.csv`. A scheduled routine, such as cron, is the right way to do this daily; this repo does not create one automatically.

Paid sources for *historical* per-ticker 30-day / 25-delta IV (accounts required; unauthenticated probes returned 401): ORATS Delayed Data API (~$199/mo, history to 2007) or the one-time daily-chain archive (~$599); Polygon/Massive options from ~$29/mo (history depth is plan-capped); Tradier (brokerage API); Market Data.app (free tier is limited); CBOE DataShop EOD + greeks (quote / order-form pricing; all-symbol history is expensive). Alpha Vantage historical options is Premium-only.

The HTML page shows live 30-day IV on the ticker card and, when a free official proxy exists, an IV history chart under the drawdown chart. Endpoints on the Worker: `GET /iv/TICKER` and `GET /volindex/INDEX`.
