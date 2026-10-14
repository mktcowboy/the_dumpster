# Colorado Land Listings — 10+ Acres, For Sale

Statewide pull of for-sale land listings in Colorado from Realtor.com,
captured October 12–13, 2026.

## Files

| File | Contents |
|---|---|
| `colorado-land-over-10ac.csv` | 999 unique listings, one row each |
| `colorado-land-over-10ac.json` | Same 999 listings as a JSON array |
| `build.py` | Reproducible build: loads `raw/`, normalizes, dedupes, writes CSV + JSON |
| `raw/` | The 13 raw per-range JSON chunk files as scraped |

## Reassembly

The full CSV and JSON exceed single-push size limits, so they ship as
parts (`colorado-land-over-10ac.csv.part1/.part2`,
`colorado-land-over-10ac.json.part1/.part2/.part3`). To rebuild locally:

```bash
cat colorado-land-over-10ac.csv.part1 colorado-land-over-10ac.csv.part2 > colorado-land-over-10ac.csv
cat colorado-land-over-10ac.json.part1 colorado-land-over-10ac.json.part2 colorado-land-over-10ac.json.part3 > colorado-land-over-10ac.json
```

## Columns

| Column | Notes |
|---|---|
| `title` | Listing title/address as shown on the card |
| `price_usd` | Asking price, integer USD; null when the card showed none (17 records) |
| `acres` | Lot size in acres; null when the card showed none (30 records) |
| `county` | Always null — Realtor.com cards do not display county |
| `city` | Parsed from the card address; null for 1 record |
| `url` | Absolute Realtor.com detail-page URL; null for 3 records (see below) |
| `broker` | "Brokered by" line; null when the card showed none (22 records) |

## Coverage — read this

Realtor.com reported **~3,090 matching listings across 74 pages** for this
search. This drop contains **999 unique listings** with all 74 pages covered.

Why the gap: per-page card counts varied. Pages 1–5 and 31–33 returned the
site's full ~42 cards per page, but the remaining pages returned only 10 cards
each (the observable subset the scraper could extract, likely before lazy-load
completed). Estimated coverage is roughly one-third of the site's reported
total. A second pass targeting the truncated pages could close the gap.

## Scope notes

- **Acreage filter is inclusive.** Realtor.com's filter is "10+ acres"
  (lot-sqft-435600); the site offers no strict ">10" filter. 28 records sit at
  exactly 10.0 acres and are kept. No records under 10 acres were returned.
  Records with no acreage shown (30) are kept, since they passed the site filter.
- **Sort drift.** The search uses Realtor.com's default "Relevant listings"
  sort, which reshuffles slightly between loads. Pages re-captured hours apart
  show some different cards. Dedupe is by detail URL (primary key), so the
  same listing appearing on two pages is counted once; a relisted parcel with
  a new URL counts separately.
- **3 records have no detail URL.** They come from early partial captures
  ("1404 N US Highway 287, Fort Collins"; "County Road 939, Tyrone, CO 80802";
  "6000 County Road 43 1/2, Hudson, CO 80649") whose cards rotated off the
  page before a full re-capture. Kept as-is rather than dropped.
- **Pending/contingent listings included.** Cards flagged Pending were still
  active search results and are included with the shown price.
- **Source quirks.** A few titles/URLs carry the site's own slug oddities
  (e.g. a Cortez listing whose URL slug says a different ZIP). Values are
  reproduced verbatim from the cards, not "corrected".

## How it was built

`python3 build.py` — loads `raw/realtor-*.json`, drops the two early partial
captures' records that were superseded by full re-captures (matched by title:
17 records), normalizes types, dedupes by URL (fallback: title + price when
the URL is null), and writes the CSV and JSON. The audit summary prints to
stdout.

## Source

- Search: `https://www.realtor.com/realestateandhomes-search/Colorado/type-land/lot-sqft-435600`
- Filters: Colorado statewide · Property type Land · Lot 10+ acres · For sale · default "Relevant listings" sort
- Captured: Oct 12 (evening) – Oct 13 (early morning), 2026
- Collection notes: Realtor.com served an intermittent bot wall overnight;
  scraping was paced and resumed after cooldowns. Dedicated land sites
  (LandWatch, Lands of America, Land And Farm) hard-block automated access
  and were not usable.
