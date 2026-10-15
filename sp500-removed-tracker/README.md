# S&P 500 Removed Stocks Tracker

Click into every stock ever removed from the S&P 500 (2007–2026) and see its
chart: price rebased to 100 on the removal date, a red vertical line at
removal, a blue line at the add date when known, SPY rebased alongside, and
performance stats since removal.

## What's inside

- `index.html` — the page (works offline; price data loads from the
  `data_*.js` files next to it, so keep them together)
- Every row links its own source citation (mostly S&P Dow Jones announcements;
  259 of 362 removals have one), and the page has a full "Data sources &
  methodology" section plus CSV download.
- `data_1.js` … `data_8.js` — per-ticker records: removal/add dates, reason,
  monthly closes, precomputed stats
- `removed_list.json` — the 362 removed tickers with dates, names, reasons
- `build_removed.py` — rebuilds `index.html` + `data_*.js` from
  `removed_list.json` + raw Yahoo monthly closes (+ `spy_monthly.json` and
  `changes_20yr.json` from the sibling `sp500-constituent-history` drop);
  per-ticker price series are embedded in `data_*.js`

## Stats (Oct 14, 2026)

- 362 distinct tickers removed since Jan 2007
- 126 with Yahoo price history; 198 delisted with no data (acquired/bankrupt)
  and 38 whose tickers were later reused by a different company (flagged
  "ticker reused" — their price data belongs to the new company, so it is
  excluded rather than shown)
- Median price return since removal: +8.5%; only 30 of 126 beat SPY over
  their post-removal window (price returns, ex-dividends)

## Method

- Removal dates/names/reasons: Wikipedia "Historical components of the S&P 500"
  (retrieved Oct 14, 2026), plus two patches verified against S&P
  announcements and contemporary press (see Coverage): Berkshire Hathaway /
  Burlington Northern Santa Fe (2010-02-16); ticker artifact fix Allegion /
  JCPenney (2013-12-02).
- Prices: SPY + ticker monthly closes, Yahoo Finance. "Since removal" rebases
  to 100 on the first month-end on/after the removal date; runs to the latest
  available price (delisted tickers stop at delisting). Annualized = geometric
  mean over elapsed months. "Still trading" = price data reaches Sep 2026+.

## Coverage

- Wikipedia's table is community-maintained: essentially complete for recent
  years, thinner for 2007–2010 (a few early adds may be missing), and it
  carries occasional errors. Cross-checked two ways: (1) every current
  constituent's "Date added" against the log — all 49 apparent misses
  resolved as ticker renames (EG=RE, META=FB, CPAY=FLT, TT=IR, SATS→ECHO,
  WRK→SW surviving entity, DLPH→APTV) or wrong "Date added" values
  (Dominion, Sempra, T. Rowe Price, Humana, Akamai show no S&P addition
  announcement on those dates); (2) the two patches above.
- Tickers delisted after acquisition/bankruptcy (Lehman, Symbol Tech, …)
  have no Yahoo history — their rows show the removal record only.
