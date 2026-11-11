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
```

### Options

| Flag | Meaning |
| --- | --- |
| `tickers` | One or more symbols, space- or comma-separated |
| `--start YYYY-MM-DD` | History start; ATH and drawdowns are computed from this date |
| `--end YYYY-MM-DD` | History end (default: latest available session) |
| `--out-dir DIR` | Where to write `<TICKER>_drawdown.png` (default: `/workspace/drawdown/out`) |
| `--no-chart` | Print stats only; skip PNGs |

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

Yahoo's chart API blocks browser CORS, so the page calls a small Cloudflare Worker that only proxies the Yahoo v8 chart endpoint. Paste that Worker URL into the page's Proxy field, or add `?proxy=` to the page URL. (`range=max&interval=1d` currently returns monthly bars, so the worker requests `period1=0&period2=<now>&interval=1d&events=div,split&includeAdjustedClose=true` instead.)

Source: `worker/src/index.js` (Wrangler config in `worker/wrangler.jsonc`).

