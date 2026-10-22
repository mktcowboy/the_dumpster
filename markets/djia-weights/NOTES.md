# Dow Weighting History: Build Notes

This file records the sources, data decisions, reconstruction work, validation, and known limitations behind the Dow Jones weighting-history report. The user-facing summary is in `README.md`.

## Goal

Build a standalone page showing the price-weighted member weights of the Dow Jones Industrial Average for every month from April 2004 through September 2026, plus the current October 20, 2026 roster. The final build has full 30/30 coverage in all 270 months; no member is dropped or renormalized.

The report is generated from local files and embeds all CSS, JavaScript, and JSON into `index.html`.

## Output

- `index.html`: standalone deliverable.
- `data/report_data.json`: generated page data.
- 270 monthly observations.
- 49 tickers in the report payload.
- 30 current members.
- 16 membership/rename events.
- Current index close: `52,495.88`.
- Current member price sum: `$8,832.34`.
- Implied divisor: `0.16824825463`.
- Published divisor used as a check: `0.16824816528350`.
- Current top weight: Goldman Sachs, about `10.0%`.
- Current top-10 share: about `54.5%`.

## Membership source

Source:

- [Historical components of the Dow Jones Industrial Average](https://en.wikipedia.org/wiki/Historical_components_of_the_Dow_Jones_Industrial_Average), Wikipedia, CC BY-SA.
- Retrieved October 21, 2026.
- Preserved locally at `source/historical_components.wikitext`.

Method:

1. Parse each dated section of the Wikipedia components table.
2. Keep the first 30 active members in each section; ignore the “Dropped from Average” rows.
3. Map company names to tickers with the `ALIASES` table in `build.py`.
4. For each month-end, use the roster whose effective date is the latest date on or before that month-end.
5. For the current weights, use the roster in force on October 20, 2026.

Ticker continuities and display identities:

- SBC Communications is treated as `T`; it was renamed AT&T Inc. in November 2005.
- United Technologies is treated as `RTX`; era cards display `UTX` and “United Technologies” before April 2020.
- AT&T Corporation, removed in April 2004, is a separate pseudo-ticker `ATTC` and is labeled “AT&T (old)” in the change log.
- Honeywell is displayed as “Honeywell Technologies” after the June 2026 rename.

Membership and rename changes in the report period:

| Date | Change |
| --- | --- |
| 2004-04-08 | Pfizer, AIG, and Verizon replace AT&T, Kodak, and International Paper; report starts |
| 2005-11-21 | SBC Communications renamed AT&T Inc.; ticker remains `T` |
| 2008-02-19 | Altria and Honeywell replaced by Chevron and Bank of America |
| 2008-09-22 | Kraft Foods added after AIG removed |
| 2009-06-08 | General Motors and Citigroup replaced by Travelers and Cisco |
| 2012-09-24 | Kraft Foods replaced by UnitedHealth |
| 2013-09-23 | Alcoa, Bank of America, and HP replaced by Goldman Sachs, Visa, and Nike |
| 2015-03-19 | AT&T replaced by Apple |
| 2017-09-01 | DuPont merged into DowDuPont; `DWDP` became the member |
| 2018-06-26 | General Electric replaced by Walgreens |
| 2019-04-02 | DowDuPont split; Dow Inc. (`DOW`) became the member |
| 2020-04-06 | United Technologies renamed Raytheon Technologies after Carrier/Otis separation |
| 2020-08-31 | Exxon Mobil, Pfizer, and Raytheon replaced by Salesforce, Amgen, and Honeywell |
| 2024-02-26 | Walgreens replaced by Amazon |
| 2024-11-08 | Intel and Dow replaced by Nvidia and Sherwin-Williams |
| 2026-06-29 | Verizon replaced by Alphabet; Honeywell renamed Honeywell Technologies |

## Price semantics

The Dow is price-weighted:

```text
weight_i = price_i / sum(all 30 prices)
```

The report uses the price actually quoted at each month-end, not an adjusted total-return series.

### Yahoo Finance series

For current and continuously listed tickers, prices come from Yahoo Finance monthly `Close` values. The refresh script uses:

```python
yf.download(ticker, interval="1mo", auto_adjust=False)
```

Yahoo’s `Close` is already adjusted for later stock splits and many spinoffs. To recover the quoted price at a past date, multiply by every split/spinoff ratio dated after that month-end:

```text
raw_price = Yahoo Close × product(all split ratios after month-end)
```

That logic is `factor_after()` and `unadjust()` in `build.py`.

Examples of factors that matter:

- Apple, Nvidia, Nike, Walmart, and other post-2004 splits.
- AIG’s 1-for-20 reverse split.
- Citigroup’s reverse split.
- GE, AT&T, Honeywell, 3M, and other later corporate actions.

### Manual/delisted series

Five histories could not be taken cleanly from Yahoo’s current ticker pages. They are stored in `data/manual_prices.json` and marked with `RAW_TICKERS` in `build.py`, so `unadjust()` uses their values directly.

| Ticker | Tenure used | Source and treatment |
| --- | --- | --- |
| `DD` | 2004-04 through 2017-08 | Digrin month-end “Real price” |
| `DWDP` | 2017-09 through 2019-03 | Digrin month-end “Real price” |
| `WBA` | 2018-06 through 2024-02 | Digrin month-end “Real price” |
| `KFT` | 2008-09 through 2012-08 | Yahoo `MDLZ` monthly close before the October 2012 change |
| `GM` | 2004-04 through 2009-05 | Reconstructed from SEC 10-K anchors and Dow divisor continuity |

The manual series are already quoted prices; they must not be multiplied by Yahoo split factors again.

## Delisted-history details

### DuPont, DowDuPont, and Walgreens

Digrin pages used:

- `https://www.digrin.com/stocks/detail/DD/price`
- `https://www.digrin.com/stocks/detail/DWDP/price`
- `https://www.digrin.com/stocks/detail/WBA/price`

Each page contains a table with:

- `Date`
- `Adjusted price`
- `Real price`

`Real price` is the already-quoted historical price. Values were parsed with `pandas.read_html`, with `$` and commas removed, and stored by month.

Important boundary: the DD page is a reused ticker. After August 2017 its series follows the DowDuPont/new DuPont history rather than old DuPont. The report therefore uses DD only through August 2017, then DWDP from September 2017 through March 2019. This matches the roster changes and avoids splicing the wrong company into DD.

Spot checks:

- DD June 2004: `$40.70`
- DD March 2008: `$36.85`
- DD August 2017: `$66.65`
- DWDP September 2017: `$69.23`
- DWDP March 2019: `$53.31`
- WBA June 2018: `$60.02`
- WBA January 2024: `$22.57`

WBA’s Digrin page contains stale/repeated values in later periods; only the June 2018–February 2024 range is used.

### Kraft Foods

Kraft Foods traded as `KFT` until the October 2012 split into Mondelez and Kraft Foods Group. Yahoo’s `MDLZ` history before October 2012 is the Kraft Foods listing, so its monthly `Close` values are used as raw KFT prices.

Source URL pattern used for the monthly chart JSON:

```text
https://query1.finance.yahoo.com/v8/finance/chart/MDLZ?period1=...&period2=...&interval=1mo&includeAdjustedClose=true
```

Spot checks:

- September 2008: `$32.75`
- August 2012: `$41.51`
- September 2012: `$41.35`
- October 2012: `$26.55` (Mondelez, not used for KFT)

KFT is used only through August 2012; the September 2012 month-end roster already uses UnitedHealth.

### General Motors

Old GM (`GMGMQ`/pre-bankruptcy GM) has no usable public monthly history through the obvious sources:

- `investor.gm.com` and `investors.gm.com` returned HTTP 403 (Akamai) even through a browser.
- Q4/Q4IR API access was blocked.
- `stockquote.io` only had current GM, not old GM/MTLQQ.
- Roic.ai required an API key.
- MarketWatch, WSJ, Barchart, and similar pages were blocked, paywalled, or lacked downloadable old-GM monthly data.

The reconstruction uses month-end closing prices disclosed in GM’s SEC 10-K filings:

| Date | GM close |
| --- | ---: |
| 2004-06-30 | `$46.59` |
| 2005-06-30 | `$34.00` |
| 2006-06-30 | `$29.79` |
| 2007-06-30 | `$37.80` |
| 2008-06-30 | `$11.50` |
| 2008-12-31 | `$3.20` |

Also noted: the March 5, 2008 grant-date close was `$22.97`. That is not used as a divisor anchor.

The June 30, 2008 close is independently confirmed by the 10-K: “The closing price on June 30, 2008 as reported on the New York Stock Exchange was $11.50 per share.” A contemporaneous news report also describes GM closing at `$11.50` on June 30, 2008.

#### GM divisor reconstruction

For an anchor month:

```text
D = (sum of all other member raw prices + GM price) / DJIA close
```

This gives the Dow divisor implied by the anchor. For a month between anchors:

```text
GM price = D × DJIA close − sum of all other member raw prices
```

`D` is adjusted at known membership changes and corporate actions:

- Membership change: compute GM at the prior close from the old roster, then rescale D by the new-roster sum.
- True stock split: use the split ratio for the affected stock.
- Spinoff: use the actual post-event parent price, not the Yahoo adjustment ratio, because the spinoff drop is not `pre-price ÷ ratio`.

The reconstruction starts from the latest available June anchor and resets at each subsequent anchor to avoid accumulating drift. For April–May 2004, the June 2004 anchor is propagated backward through Procter & Gamble’s June 21, 2004 2-for-1 split.

Events used in the 2004–2009 GM window:

- PG 2-for-1, 2004-06-21
- RTX/UTX 2-for-1, 2005-06-13
- CAT 2-for-1, 2005-07-14
- AXP/Ameriprise spinoff, 2005-10-03
- VZ spinoff, 2006-11-20
- Altria/Kraft spinoff, 2007-04-02
- DIS spinoff, 2007-06-13
- 2008-02-19 membership change
- VZ spinoff, 2008-04-01
- 2008-09-22 membership change

The Altria/Kraft spinoff is not present in Yahoo’s split events. It was added manually using the actual MO price move: March 30, 2007 `$87.81` to April 2, 2007 `$68.22`.

GM’s monthly values are therefore estimates. The anchors are reported closes; intervening values are derived. They should be treated as reconstructed data, not as directly observed monthly closes.

## Divisor and coverage checks

### 2019-12-31

Full 30-member price sum:

```text
$4,207.87
```

This includes Walgreens and all other members; the earlier renormalized build had the same sum only after adding WBA back.

### 2008-06-30

Full 30-member sum:

```text
$1,386.03
```

Implied divisor:

```text
1,386.03 / 11,350.0098 = 0.1221170741
```

This matches the SEC GM anchor of `$11.50`.

### 2008-03-31

Full sum including the GM estimate:

```text
$1,500.23
```

The GM estimate for that month is `$22.89`. This month is less clean than June 2008 because no direct March 31 GM close was available; it is documented here as an estimate.

### Current

```text
price sum = $8,832.34
DJIA close = 52,495.88
implied divisor = 0.16824825463
published divisor = 0.16824816528350
```

The small difference is consistent with price rounding and the use of the prior close.

## Coverage history

The first build deliberately excluded five tickers and renormalized weights over the priced members:

- `DD`
- `GM`
- `KFT`
- `DWDP`
- `WBA`

Coverage was 27–30 of 30, with `PRICE_UNAVAILABLE` in `build.py`.

After the manual series were added:

- `PRICE_UNAVAILABLE` was replaced with `RAW_TICKERS`.
- `unadjust()` uses manual values directly for those tickers.
- The `unavailable` report field is now empty.
- Coverage is 30/30 in all months.
- The UI no longer has a renormalized-coverage state.

## Build pipeline

Files:

| File | Role |
| --- | --- |
| `build.py` | Parses rosters, resolves aliases, computes raw prices and weights, builds payload and standalone page |
| `fetch_prices.py` | Optional Yahoo refresh; merges `data/manual_prices.json` and skips Yahoo for manual tickers |
| `data/prices.json` | Cached monthly closes, daily anchor closes, split factors, and manual metadata |
| `data/manual_prices.json` | Already-quoted DD/DWDP/WBA/KFT/GM series and source notes |
| `data/report_data.json` | Generated JSON embedded into the page |
| `template.html` | Page shell and methodology text |
| `styles.css` | Report styling and responsive layout |
| `app.js` | Charts, tables, tooltips, era cards, change log |
| `index.html` | Generated standalone report |
| `source/historical_components.wikitext` | Preserved Wikipedia roster source |

Build:

```sh
python3 markets/djia-weights/build.py
```

Optional refresh:

```sh
python3 -m pip install pandas yfinance
python3 markets/djia-weights/fetch_prices.py
python3 markets/djia-weights/build.py
```

The build reads local data only. The refresh script does not overwrite the manual series.

## Validation and QA

- `python3 scripts/check_privacy.py` passed.
- `python3 -m py_compile build.py fetch_prices.py` passed.
- `node --check app.js` passed.
- Browser load: no console or page errors.
- Current table: 30 rows.
- Era cards: 6.
- Change log: 16 rows.
- Every month has `coverage == 30`.
- Weight sums are 100 within `0.0005` percentage points because of four-decimal rounding.
- Tooltip shows `30/30 priced`.
- Mobile viewport at 390 px has `document.documentElement.scrollWidth == 390` (no horizontal page overflow).
- Desktop and mobile screenshots were inspected.

## Known limitations

1. **GM is reconstructed.** The June/December 10-K anchors are solid, but monthly values between anchors depend on divisor continuity and corporate-action adjustments. March–May 2008 are the least certain.
2. **Digrin is a secondary retail source.** DD, DWDP, and WBA values are stored to the cent. They match spot checks and roster boundaries, but are not exchange-grade data.
3. **Yahoo spinoff factors are incomplete.** The MO/Kraft spinoff was handled manually; other small corporate actions may have similar gaps outside the GM reconstruction window.
4. **Current weights use the prior close.** The October 20, 2026 close is the report’s “as of” price, so published weights from a later snapshot can differ by normal one-day drift.
5. **Manual series bypass split normalization.** This is intentional, but anyone editing `data/manual_prices.json` must supply already-quoted prices, not Yahoo-adjusted closes.
6. **The report is not investment advice.** Membership dates and prices can contain source errors; the original sources are linked in the page and README.

## Reproducing the manual data

The manual series were assembled as follows:

1. **DD/DWDP/WBA:** fetch the Digrin price page, parse the `Real price` column, convert dates to `YYYY-MM`, and keep only the roster tenure.
2. **KFT:** fetch Yahoo `MDLZ` monthly history, use `Close` for 2008-09 through 2012-08, and do not use October 2012 onward.
3. **GM:** compute anchor divisors from month-end raw prices and DJIA closes, propagate through the event list above, and dump the resulting monthly values.
4. Store the five series and their provenance in `data/manual_prices.json`.
5. Rebuild and confirm every month has 30 priced members.

The important invariant is that all values in the final price table are quoted-price equivalents for the month-end date. Adjusted-close series must be unadjusted before they enter the weight calculation; already-quoted manual series must not be adjusted again.
