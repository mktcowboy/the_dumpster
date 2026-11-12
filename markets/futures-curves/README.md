# Futures Curves

Self-contained HTML report on futures term structure for ~41 markets in 8 groups
(Indices, Energy, Metals, Grains, Meats, Softs, Currencies, Rates).

For each market it shows every listed contract that returns a live quote (last, daily change,
spread vs the front month, 1W/1M change, volume), the forward curve with 1-week and 1-month-ago
overlays, ~1 year of the front-month continuous (or spot) series, and a structure badge with the
annualized front-to-~12-month roll yield. The overview has a sortable table of all markets with
curve sparklines and a roll-yield bar chart. Dark/light theme, group tabs, works offline
(Chart.js 4.4.4 is inlined).

## Rebuild

```sh
python3 build.py --fetch      # fetch fresh data, then build futures-curves.html
python3 shot.py CL Energy     # optional: screenshots into shots/ (needs playwright + Chrome)
```

Requires `yfinance`, `pandas`. Files:

- `fetch.py` – market universe and listed-month cycles; probes Yahoo per-contract tickers
  (e.g. `CLF27.NYM`, `ESH27.CME`, `GCG27.CMX`, `ZCH27.CBT`, `KCH27.NYB`) and writes `data.json`.
- `build.py` – derives front contract, spreads, structure, roll yield; injects data and Chart.js into `template.html`.
- `template.html` – report layout, styles and chart code.

## Data notes

- Source: Yahoo Finance daily bars (delayed; the latest bar can be intraday). Nothing is estimated
  or interpolated; a market without per-contract quotes is shown as unavailable.
- Front = the contract Yahoo's continuous `ROOT=F` currently tracks; earlier delivery months are tagged *expiring*.
- *Stale* = the contract has no bar on the latest date (illiquid back month); its last print is shown as a hollow point.
- Roll yield (annualized) = (front / far)^(12/m) − 1, far = contract nearest 12 months out (9–15 m) among
  contracts that printed on the latest date, else the furthest such contract. Positive = backwardation.
- The US Dollar Index has no Yahoo continuous series, so its history chart uses the spot index `DX-Y.NYB`.
