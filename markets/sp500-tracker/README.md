# S&P 500 Tracker

One standalone page for constituent changes, removed stocks, and ticker performance comparisons. Open `index.html` in any browser. It embeds all styles, scripts, and cached data; it works offline and can be shared as a single file.

## Explore the tracker

- **Constituent changes:** 392 events from January 10, 2007 through October 6, 2026, plotted over SPY monthly prices. Search, filter by year, sort, download the filtered CSV, or click a chart marker to select its date.
- **Removed stocks:** 362 distinct removed tickers, with price coverage and returns versus SPY since their latest removal. Sort by return or excess return, then click any ticker for its membership events and available chart.
- **All tickers in log:** additions and removals together. This is the turnover universe, not a current constituent roster.
- **Ticker detail:** open either side of an event, then add up to three other stocks alongside SPY. Choose the index event or full available history as the start, and a one-, three-, five-year, or latest-available end. Click another membership event to change the anchor.

Comparisons use only months shared by every selected series. All lines start at 100 and all reported returns use the same start and end. Turning SPY off also removes the excess-return comparison. Membership records remain accessible when price history is unavailable.

## Files and rebuilding

| File | Purpose |
| --- | --- |
| `index.html` | Generated standalone tracker; the only file needed for charts and tables |
| `template.html`, `styles.css`, `app.js` | Editable interface sources |
| `build.py` | Offline build using paths relative to the script |
| `changes_20yr.json` | Original constituent changes and row source citations |
| `removed_list.json` | Preserved removal records from the original tracker |
| `spy_monthly.json` | Preserved SPY series for the historical overview |
| `prices.json` | Monthly price cache, availability states, and retrieval dates |
| `fetch_prices.py` | Fetch missing monthly Yahoo histories; optional refresh of all histories |

From the repository root:

```sh
python3 markets/sp500-tracker/build.py
```

To download missing histories, or refresh the entire cache, then rebuild:

```sh
python3 markets/sp500-tracker/fetch_prices.py
python3 markets/sp500-tracker/build.py
# Optional full refresh:
python3 markets/sp500-tracker/fetch_prices.py --refresh
```

Only the downloader needs internet access. It uses the Python standard library, preserves available histories on request failures, and saves progress in batches. The build never downloads data. Price download dates are recorded in UTC; the overview retains its original SPY snapshot.

## Data and limits

Membership data: Wikipedia, “Historical components of the S&P 500,” retrieved October 14, 2026. Per-event citations are retained, mostly S&P Dow Jones announcements, with the Wikipedia table as fallback. These are effective dates. Early coverage is thinner, and one-sided rows represent corporate actions. Repeated entries and ticker renames remain distinct events.

Original patches are preserved: Berkshire Hathaway/Burlington Northern Santa Fe on February 16, 2010 ([Reuters](https://www.reuters.com/article/idUSTRE60P6OO20100126/)), and Allegion/JCPenney ticker artifacts on December 2, 2013. The previous completeness audit reported 49 apparent addition-date mismatches resolved as ticker renames or questionable dates. This consolidation does not constitute a fresh source audit.

Prices are unadjusted monthly Yahoo closes; returns exclude dividends and the latest month may be incomplete. The event anchor is the event month, or the next shared month with data. It is not the exact price on the effective date. Annualization uses elapsed calendar months. The chosen period starts at the baseline rather than measuring a trailing return.

Histories beginning more than a year after a ticker’s earliest recorded event are excluded as possible ticker reuse. This is a conservative heuristic, not an identity verification. Missing price data does not prove delisting or bankruptcy, and surviving ticker changes are not automatically joined. Cache retrieval status does not imply current index membership or current trading status.

During consolidation, the original page referenced eight price chunks, but only two were present in the repository or available Git history. Those available histories were preserved in `prices.json`; missing histories were fetched where Yahoo provided them. No missing history is fabricated.

Change data: Wikipedia, CC BY-SA. Prices: Yahoo Finance.
