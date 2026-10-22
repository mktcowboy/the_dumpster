# Dow Jones Weighting History

A standalone page showing how the Dow Jones Industrial Average's price-weighted member weights changed from April 2004 through October 2026. Open `index.html` in any browser. All styles, scripts, and data are embedded, so the page works offline and can be shared as a single file.

## What is in the report

- **Latest weights:** all 30 members ranked by weight, with price, weight, and the October 20, 2026 close.
- **Weight history:** month-end stacked area chart, April 2004 through September 2026. Switch between the top 10 names by average weight and the top 10 today. The shaded band is every other member.
- **Concentration:** top-1, top-5, and top-10 share of the index, plus the effective number of equally weighted stocks.
- **Era snapshots:** the ten largest weights at six dates, with full 30/30 coverage.
- **Membership log:** every addition, removal, and ticker rename since April 2004.
- **Methodology:** sources, reconstructed histories, and the divisor checks used to validate the data.

## Method

The Dow is price-weighted, so a member's index weight is its price divided by the sum of all 30 member prices. The report uses the roster in force at each month-end from Wikipedia's historical components table.

Monthly prices are Yahoo Finance closes converted back to the price actually quoted at each month-end. Yahoo's `Close` series is adjusted for later splits and spinoffs, so each month-end close is multiplied by every split ratio dated after that month-end. The current weights use the October 20, 2026 daily close. Delisted and successor series are stored as already-quoted prices and bypass that adjustment.

The implied divisor is the price sum divided by the Dow close. It is displayed next to the published divisor as a consistency check.

Ticker continuity follows the current listing where the company survived a rename: SBC Communications is `T`, and United Technologies is `RTX`. Era cards show the ticker in force at the time, such as `UTX` before April 2020. AT&T Corporation, which left the index in 2004, is kept as a separate pseudo-ticker without price history and is labeled "AT&T (old)".

## Coverage and sources

All 30 members are priced in every month from April 2004 through September 2026. Five delisted or successor histories need separate treatment:

| Ticker | Company | Source |
| --- | --- | --- |
| `DD` | DuPont | Digrin month-end real prices through August 2017 |
| `GM` | General Motors | Reconstructed from SEC 10-K anchors and Dow divisor continuity; monthly values are estimates |
| `KFT` | Kraft Foods | Yahoo `MDLZ` close before the October 2012 change; the pre-2012 series is the Kraft listing |
| `DWDP` | DowDuPont | Digrin month-end real prices, September 2017–March 2019 |
| `WBA` | Walgreens Boots Alliance | Digrin month-end real prices, June 2018–February 2024 |

The GM anchors are the June 30 closes reported in GM's 10-K filings for 2004–2008 (`$46.59`, `$34.00`, `$29.79`, `$37.80`, `$11.50`) plus the December 31, 2008 close (`$3.20`). Intervening months use the divisor in force between anchors and known membership/corporate actions. GM is the only estimated series; its anchors are reported closes and the intervening values are derived, not observed.

Data sources: Wikipedia, [Historical components of the Dow Jones Industrial Average](https://en.wikipedia.org/wiki/Historical_components_of_the_Dow_Jones_Industrial_Average), CC BY-SA, retrieved October 21, 2026; Yahoo Finance prices, retrieved October 21, 2026; [Digrin](https://www.digrin.com/) historical prices; GM SEC 10-K filings. Not investment advice.

## Validation

- The method reproduces the published June 29, 2026 divisor of `0.16824816528350`; the October 20 price sum implies `0.16824825463`, a difference consistent with price rounding.
- The December 31, 2019 full 30-member price sum is `4,207.87`, including Walgreens.
- At June 30, 2008 the full 30-member sum is `1,386.03`; the implied divisor is `0.1221170741`, matching the GM SEC anchor of `$11.50`.
- At March 31, 2008 the full sum is `1,500.23`, including GM's reconstructed `$22.89`.
- Current weights match published Dow ETF weights within normal one-day price drift; this report uses the prior close while the benchmark snapshot is one day later.

## Files and rebuilding

| File | Purpose |
| --- | --- |
| `index.html` | Generated standalone report; the only file needed to view it |
| `NOTES.md` | Detailed source, reconstruction, validation, and limitations notes |
| `template.html`, `styles.css`, `app.js` | Editable page shell, styles, and chart/table code |
| `build.py` | Offline build; parses the roster, computes weights, and embeds the page |
| `fetch_prices.py` | Optional Yahoo Finance refresh for monthly closes, splits, and validation-day anchors; preserves the manual series |
| `data/prices.json` | Cached monthly closes, splits, and anchor closes (50 stocks plus DJI) |
| `data/manual_prices.json` | Already-quoted delisted/successor series and GM reconstruction notes |
| `data/report_data.json` | Generated data payload embedded in `index.html` |
| `source/historical_components.wikitext` | Preserved Wikipedia roster source |

From the repository root:

```sh
python3 markets/djia-weights/build.py
```

The build reads local files only. To refresh prices first (requires `pandas` and `yfinance`; `data/manual_prices.json` is merged automatically), then rebuild:

```sh
python3 -m pip install pandas yfinance
python3 markets/djia-weights/fetch_prices.py
python3 markets/djia-weights/build.py
```
