# Patek tracker: Nautilus 5711 and blue/green Aquanaut

**Scope:** two saved searches. The folder is still called `Watches_patek_5711` so the workflow and every path keep working.

- `patek5711`: Patek Philippe Nautilus 5711, every variant.
- `aquanaut_bluegreen`: Patek Philippe Aquanaut with a blue or green dial, grouped by reference + dial.

Both are weekly scans, built on the same pattern as `Cars_autotempest_scan/` v2:

per-search config (`SEARCHES` in `refresh_searches_v2.py`) → scrape each source → `saved/<slug>/<source>.csv` → merge and dedupe → `merged.csv` + `meta.json` with a freshness window → one HTML report with a **Data as of** header → weekly GitHub Actions run that commits `output/report.html` and `saved/`.

Open `output/report.html` in a browser. It has a source-status table, low/median/high asking price per variant with the change since the last snapshot, the price on each source, the merged listing table (filter by variant, sort by column), and the price history.

## Files

- `chrono24_scraper_v2.py`: Chrono24 (the primary source). Reads every search page, then each listing's detail page for the reference, year, condition, box/papers, location and seller. Detail pages are cached in `saved/patek5711/chrono24_details.json`, so a weekly run only opens new listings.
- `dealer_scrapers_v2.py`: every other source, one function each, plus the checks for sites that block.
- `merge_listings_v2.py`: cross-site dedupe (below).
- `generate_report_v2.py`: the HTML report.
- `refresh_searches_v2.py`: the orchestrator. Holds `SEARCHES` and writes `price_history.csv`.
- `saved_store_v2.py`: saved files and the freshness logic, same as the car scanner.
- `watch_common_v2.py`: 5711 reference parsing, variant buckets, shared fields.
- `models_v2.py`: what each search tracks. It holds each site's search term, Chrono24's search URLs, the match rule and the variant rule. This is where the Aquanaut references and dials live.
- `run_patek_weekly_v2.sh`: the scheduled entry point.
- `test_patek_v2.py`: offline tests for reference parsing and the merge.

```bash
pip install -r requirements.txt && python -m playwright install chromium
./run_patek_weekly_v2.sh --force                      # scrape everything, rebuild the report
python3 refresh_searches_v2.py                        # skip if saved data is still fresh (2 days)
python3 refresh_searches_v2.py --force --only chrono24,bobs
```

## Saved data (`saved/patek5711/` and `saved/aquanaut_bluegreen/`)

- `<source>.csv`: one file per source, for example `chrono24.csv` and `bobs.csv`.
- `merged.csv`: the deduped list the report shows.
- `meta.json`: `scraped_at`, plus each source's status, row count and warning.
- `price_history.csv`: one line per run, per variant and per source, with count, low, median and high asking price. It is only ever appended to, and week-over-week change is computed from it.

When a source fails, its last good file is kept and a warning goes into `meta.json`. The run itself does not fail. The freshness window is 2 days by default. Change it in `saved/freshness.json`, with `--fresh-days`, or with the `PATEK_FRESH_DAYS` environment variable.

## Sources: what worked for the 5711 (first run, 2026-10-30)

| Source | Result | How |
|---|---|---|
| **Chrono24** (primary) | **Worked.** 516 results (the site says 540 including promoted listings), 513 of them 5711s | plain HTTP plus each detail page |
| Bob's Watches | Worked, 1 listing | HTTP, product JSON-LD |
| The 1916 Company (formerly WatchBox) | Worked, 1 listing | HTTP, search-page JSON-LD |
| Swiss Watch Expo | Worked, 4 for sale (sold tiles carry no price, so they are skipped) | HTTP, search tiles |
| DavidSW | Worked, 7 listings, all out of stock (kept with their last price, left out of the asking stats) | HTTP, product JSON-LD |
| Grailzee | Worked, 1 listing (auction ended unsold, buy-now price) | headless Chromium, reading the auction search the page loads |
| Analog Shift | Worked, but no 5711 for sale (every 5711 it has is sold, with no price) | HTTP, Shopify product JSON |
| Hodinkee Shop | Worked, 0 results for 5711 | HTTP |
| Watchfinder & Co. | Worked in a browser, but no 5711 in stock | headless Chromium |
| Jomashop | Worked in a browser, but no 5711 in stock | headless Chromium |
| eBay (active and sold) | **Blocked**: HTTP 403 from a script and from headless Chromium | none |
| WatchCharts | **Blocked**: Cloudflare challenge (HTTP 403) | none |
| Crown & Caliber | **Not available**: search and collection URLs return 404 | none |
| Bezel | **Not scraped**: listings load from a private API after the page renders | none |
| Wristcheck | **Not scraped**: the search parameter is ignored and listings come from a private API | none |
| Luxury Bazaar | **Not scraped**: search results are rendered by JavaScript | none |
| European Watch Co. | **Not scraped**: search results are rendered by JavaScript | none |

The blocked and unscraped sites are still tried on every run. If one starts answering, the Sources table in the report shows it. Supporting Bezel, Wristcheck, Luxury Bazaar or EWC would need browser automation against each site's private API, so that was left out on purpose. No site login or API key is used anywhere.

## Aquanaut, blue and green dials

Chrono24 is read from its own Aquanaut dial-colour pages: blue (`aquanaut-blue--mod92-dc710`) and green (`aquanaut-green--mod92-dc716`). On 2026-10-30 they said 494 blue and 332 green listings, and the scraper collected 781 distinct ones. Every detail page is opened (cached in `saved/aquanaut_bluegreen/chrono24_details.json`). The dealer sites are searched for "aquanaut", and black, white, grey and brown dials are dropped.

Grouping is by reference family + dial, for example `5168G white gold 42 mm · Green`. When a full reference is known, the dial comes from Patek's numbering and wins over the seller's wording. Otherwise the listing's dial field or title decides, and failing that the Chrono24 colour page it came from. Each reference→dial mapping was checked against the dial field on the Chrono24 detail pages (counts are listings):

| Reference | Dial on Chrono24 detail pages | Used as |
|---|---|---|
| 5168G-001 white gold 42 mm | Blue 113, blank 2 | Blue |
| 5168G-010 white gold 42 mm | Green 133, blank 5, Blue 2 (mislabelled) | Green (khaki) |
| 5968G-001 white gold chronograph | Blue 79 | Blue |
| 5968G-010 white gold chronograph | Green 98 | Green (khaki) |
| 5164G-001 white gold Travel Time | Blue 36, blank 6 | Blue |
| 5267/200A-011 Luce chronograph steel | Green 67, blank 2 | Green (khaki) |
| 5261R-001 Luce annual calendar rose gold | Blue 76, blank 5 | Blue |
| 5269R-001 Luce rose gold | Blue 53, blank 5 | Blue |
| 5650G-001 Advanced Research | Blue 15 | Blue |
| 5268/461G-001 Luce white gold, diamonds | Blue 4 | Blue |
| 5067A-014 / -017 / -022 Luce steel | Blue 4 / 5 / 7 | Blue |
| 5067A-012, -013, -025 | mixed or single listings | the listing's own dial field |

Checked against the brief: **no steel 5167A or 5167/1A with a blue or green dial exists in Patek's numbering.** 5167A-001 and 5167/1A-001 are black, and 5167R-001 is brown, so they are excluded. In the whole blue and green Chrono24 set, one 5167A-014 listing is tagged blue, and it stays in the data only as that seller describes it.

Other blue or green Aquanauts that showed up and are tracked: 5650G, 5268/461G, 5067A Luce, 7968/300R, a 4960A and a 5066A. The last two are single listings tagged blue by their seller.

### Aquanaut sources (2026-10-30)

| Source | Result |
|---|---|
| **Chrono24** | **Worked.** 780 blue or green Aquanauts kept |
| Grailzee | Worked, 4 (auctions ended unsold, buy-now prices) |
| Watchfinder & Co. | Worked, 1 (5168G-001) |
| DavidSW | Worked, 1 (5968G blue, out of stock) |
| Bob's Watches, The 1916 Company, Swiss Watch Expo, Analog Shift, Hodinkee, Jomashop | Reachable, but nothing blue or green for sale (their Aquanauts are black or sold) |
| eBay, WatchCharts, Crown & Caliber, Bezel, Wristcheck, Luxury Bazaar, European Watch Co. | Blocked or not scraped, same as for the 5711 |

Dedupe found **no** cross-site duplicates for the Aquanaut: 786 rows became 786 watches. One candidate, a Grailzee 5261R at $189,599 against a Chrono24 one at $192,205, stays apart because the sellers differ. That pair is why generic words like "private seller" no longer count as a seller-name match.

## 5711 variants

References are normalised from every way the sites write them (`5711/1A-010`, `57111A010`, `5711A`, `5711 1A 010`) and grouped into buckets:

- `5711/1A-010` blue
- `5711/1A-001` early blue
- `5711/1A-011` white
- `5711/1A-014` olive green
- `5711/1A-018` Tiffany
- `5711/1A` when the site gives no suffix
- `5711/1300A` diamond bezel
- `5711/1R-001` rose gold bracelet
- `5711R-001` rose gold strap
- `5711G` white gold
- `5711J` yellow gold
- `5711/1P` platinum
- `5711/112P` platinum
- `5711/110P` platinum
- `5711/113P` emerald bezel
- other

The original brief listed `5711/1A-011` as the green dial. The green (olive) dial is actually `-014`, and `-011` is the white dial; the buckets follow Patek's numbering.

## Dedupe

Watches have no VIN. The merge works like this:

1. A repeated listing id from the same source is kept once.
2. Two rows with the same serial or stock number are the same watch.
3. A dealer's own listing joins a Chrono24 listing only when all of these hold:
   - the variant matches;
   - the price is within 2%;
   - the year does not conflict;
   - the seller name on Chrono24 matches the dealer.

   A price match from a different seller stays a separate watch. The first run turned up two such coincidences, and they stay apart.
4. Dealer-to-dealer rows merge on variant plus price within 2%, as long as the year does not conflict.
5. Two Chrono24 listings never merge with each other.

A merged row shows every site's price as a chip.

## Caveats

- These are asking prices, not sold prices. eBay sold listings and WatchCharts were the sold and market-price sources, and both block scripts.
- "Price on request" listings (189 on the first run) are kept in the table but are not in the stats.
- Lots from auction houses on Chrono24 (Christie's, Phillips and others) show estimates, not asking prices. They are marked as such and left out of the stats.
- Chrono24 shows non-US dealers' prices converted to USD for a US visitor. Prices can be negotiable and may exclude import duty.
- Rows priced under $5,000 are dropped as parts (one was a $395 5168G strap listed on Chrono24).
- Chrono24's colour pages rely on the seller's dial tag. A blue or green Aquanaut tagged with another colour, or not tagged at all, is missed. Over the 826 listings Chrono24 counts, 781 distinct ones were collected.
- High-end outliers, such as one-off Tiffany or gem-set pieces listed under a standard reference, raise the "high" column. The median is the number to watch.

## What runs on the schedule

`.github/workflows/patek-5711-weekly.yml` covers both searches. It runs Mondays at 7:00 AM Central (the same two-cron trick as the car workflow) and on manual dispatch. It runs `run_patek_weekly_v2.sh --force` and commits `Watches_patek_5711/output/report.html` and `Watches_patek_5711/saved`. GitHub's runner IPs may get blocked by more sites than a home connection does. Any source that blocks shows up as a warning, and its last good file stays in use.
