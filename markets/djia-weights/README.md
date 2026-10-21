# Dow Jones Weighting History

A standalone page showing how the Dow Jones Industrial Average's price-weighted member weights changed from April 2004 through October 2026. Open `index.html` in any browser. All styles, scripts, and data are embedded, so the page works offline and can be shared as a single file.

## What is in the report

- **Today's weights:** all 30 members ranked by weight, with price, weight, and the October 20, 2026 close.
- **Weight history:** month-end stacked area chart, April 2004 through September 2026. Switch between the top 10 names by average weight and the top 10 today. The shaded band is every other member.
- **Concentration:** top-1, top-5, and top-10 share of the index, plus the effective number of equally weighted stocks.
- **Era snapshots:** the ten largest weights at six dates, with coverage noted for each.
- **Membership log:** every addition, removal, and ticker rename since April 2004.
- **Methodology:** sources, coverage gaps, and the divisor checks used to validate the data.

## Method

The Dow is price-weighted, so a member's index weight is its price divided by the sum of all 30 member prices. The report uses the roster in force at each month-end from Wikipedia's historical components table.

Monthly prices are Yahoo Finance closes converted back to the price actually quoted at each month-end. Yahoo's `Close` series is adjusted for later splits and spinoffs, so each month-end close is multiplied by every split ratio dated after that month-end. The current weights use the October 20, 2026 daily close.

The implied divisor is the price sum divided by the Dow close. It is displayed next to the published divisor as a consistency check.

Ticker continuity follows the current listing where the company survived a rename: SBC Communications is `T`, and United Technologies is `RTX`. Era cards show the ticker in force at the time, such as `UTX` before April 2020. AT&T Corporation, which left the index in 2004, is kept as a separate pseudo-ticker without price history and is labeled "AT&T (old)".

## Coverage and limits

Five members have no usable price history for some or all of their index tenure, so weights are renormalized over the priced members:

| Ticker | Company | Reason |
| --- | --- | --- |
| `DD` | DuPont | Yahoo's pre-2019 history does not reconcile with DuPont's reported quarterly price ranges after the DowDuPont merger and 2019 split; excluded from historical weights |
| `GM` | General Motors | Delisted after the 2009 bankruptcy; no accessible unadjusted history |
| `KFT` | Kraft Foods | Delisted after the 2012 split; no accessible unadjusted history |
| `DWDP` | DowDuPont | Delisted after the 2019 split; no accessible unadjusted history |
| `WBA` | Walgreens Boots Alliance | Delisted in 2025; no accessible unadjusted history |

Coverage ranges from 27 to 30 of 30 members. The chart tooltip and era cards show the number priced for each month. The current roster is fully priced. Missing histories are never fabricated.

Data sources: Wikipedia, [Historical components of the Dow Jones Industrial Average](https://en.wikipedia.org/wiki/Historical_components_of_the_Dow_Jones_Industrial_Average), CC BY-SA, retrieved October 21, 2026; Yahoo Finance prices, retrieved October 21, 2026. Not investment advice.

## Validation

- The method reproduces the published June 29, 2026 divisor of `0.16824816528350`; the October 20 price sum implies `0.16824825463`, a difference consistent with price rounding.
- The December 31, 2019 price sum is `4,207.87` once Walgreens is included.
- The March 31, 2008 priced sum reconciles with the published divisor after allowing for the excluded DuPont and General Motors prices.
- Current weights match published Dow ETF weights within normal one-day price drift; this report uses the prior close while the benchmark snapshot is one day later.

## Files and rebuilding

| File | Purpose |
| --- | --- |
| `index.html` | Generated standalone report; the only file needed to view it |
| `template.html`, `styles.css`, `app.js` | Editable page shell, styles, and chart/table code |
| `build.py` | Offline build; parses the roster, computes weights, and embeds the page |
| `fetch_prices.py` | Optional Yahoo Finance refresh for monthly closes, splits, and validation-day anchors |
| `data/prices.json` | Cached monthly closes, splits, and anchor closes (48 tickers) |
| `data/report_data.json` | Generated data payload embedded in `index.html` |
| `source/historical_components.wikitext` | Preserved Wikipedia roster source |

From the repository root:

```sh
python3 markets/djia-weights/build.py
```

The build reads local files only. To refresh prices first (requires `pandas` and `yfinance`), then rebuild:

```sh
python3 -m pip install pandas yfinance
python3 markets/djia-weights/fetch_prices.py
python3 markets/djia-weights/build.py
```
