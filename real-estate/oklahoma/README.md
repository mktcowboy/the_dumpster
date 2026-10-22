# Oklahoma for-sale tracker

Statewide Oklahoma listings in one local page: sheriff sales, VA and bank REO, optional keyed listing APIs, a map, a table, filters, summary stats, and nearby comps. Distressed property is one category. Commercial, land, and ordinary residential MLS inventory are included only when a source that allows automated access actually returns them.

Open `http://localhost:4083` after start. The page is `oklahoma.html`.

## Run

```bash
cd real-estate/oklahoma
npm install
npm start
```

`npm start` serves the dashboard and syncs only when the saved snapshot is older than six hours. `npm run sync` fetches once and exits. `npm test` runs the unit tests (one Census geocode test is skipped unless `GEO_LIVE=1`).

Optional keys, each skipped when unset:

| Variable | Adapter |
|---|---|
| `RENTCAST_API_KEY` | RentCast sale listings. `RENTCAST_MAX_REQUESTS` defaults to one request per property type. |
| `MASHVISOR_API_KEY` | Mashvisor city listings. `MASHVISOR_CITIES` overrides the default city list. |
| `ATTOM_API_KEY` | ATTOM sale snapshot on addresses already found. `ATTOM_MAX` defaults to 25. |

The radius filter uses downtown Oklahoma City (`config/area.json`: 35.4676, -97.5164). Statewide is the default. Rebuild the county list inside that radius with `npm run build-area` if the center changes.

## What a row can show

Price (list price, or the sheriff opening bid when there is no list price), category, type, size, lot or acreage, price per square foot, price per acre, year built, days on market, and status. Income fields — cap rate, NOI, occupancy or lease percent, tenants, lease terms — appear only when a source provides them or when cap rate can be computed from source-provided income. Computed values are labeled (`computed`, `computed-from-source-noi`, `computed-from-source-income-and-expenses`, `computed-from-list-date`). Gross income without operating expenses does not become NOI.

Comps are attached when the page loads, not stored in `data/listings.json`. They are other active, pending, or auction rows of the same category within 3 miles (residential), 10 (commercial), 15 (land), or 8 (distressed). A size band is preferred; if none match, nearer same-family rows are marked loose. The comparison is price per square foot or per acre when both sides have that unit. A sold comp is included only when that row has a source `recordedSale.price`. Assessor totals stay in their own fields and are not treated as sale prices.

Sheriff rows do not carry a property type. They stay `unknown` rather than being guessed as houses. Plaintiff (usually the lender) is kept. Defendant and attorney names are not stored.

## Sync on 2026-10-22

`node server.js --sync-once` at 2026-10-22T19:46Z. No API keys were set. 115 active listings, 0 removed.

| Source | Result |
|---|---|
| Canadian Sheriff | 21 |
| Grady Sheriff | 9 |
| Lincoln Sheriff | 6 |
| Logan Sheriff | 0 upcoming (feed responded) |
| Caddo Sheriff | 3 |
| Seminole Sheriff | 9 |
| Payne Sheriff | 10 |
| McClain Sheriff | error: captcha; nothing stored |
| VRM | 57 statewide |
| RentCast | skipped, no key |
| Mashvisor | skipped, no key |
| Canadian County assessor | 8 situs matches on listings already found |
| ATTOM | skipped, no key |

By category and type: residential / single-family 57 (all VRM); unknown / unknown 58 (all sheriff). Commercial 0. Land 0. Condo, townhouse, manufactured, and multifamily 0.

By status: scheduled 58, REO 57. All 115 are distressed, because the only live feeds are sheriff sales and REO.

Geography: 54 inside the 50-mile Oklahoma City radius, 58 outside, 3 with no coordinates (no address). Census geocoder: 99 match, 13 no match, 3 no address. VRM inside the radius 17, outside 38. Counties with at least one row include Canadian 23, Seminole 10, Payne 10, Grady 9, Oklahoma 8, Lincoln 6, Comanche 4, Muskogee 4, Caddo 3, Tulsa 3, Rogers 3, Cleveland 3, and smaller counts through 37 county buckets (including 3 with no county).

Fields actually filled on this snapshot:

| Field | Rows | Where it comes from |
|---|---|---|
| Price or opening bid | 96 | VRM list price, or sheriff opening bid. 19 rows have a null appraisal and no price. |
| Square feet | 56 | VRM cards |
| Price per sq ft | 39 | Computed from price and sqft, labeled `computed` |
| Acres, price per acre | 0 | VRM cards have no lot size; sheriff rows have no size |
| Year built, days on market | 0 | Not on these feeds |
| Cap rate, NOI, occupancy, tenants, lease terms | 0 | No live source provided income figures. The metrics exist and are tested; they stay empty. |
| Recorded sale | 0 | No keyless source returns a sale amount. See disclosure below. |
| Assessor value | 8 | Canadian County assessor total value and assessed value, labeled as assessments, not sale prices |

The commercial and land filters are empty on purpose. The page says so. Nothing is filled with placeholder listings.

## Sources

Checked 2026-10-22 with ordinary GET and HEAD requests. No spoofed user agent, no challenge bypass, no bulk harvest of a site that disallows it. Detail is in `research/source-review-2026-10-22.md`. The September 2026 distressed-source review is kept beside it.

### Working

- **County sheriff JSON** (`/dmxConnect/api/SheriffSales/Read.php`) for Canadian, Grady, Lincoln, Logan, Caddo, and Seminole. Address, city, ZIP, case, sale date, appraisal. Opening bid is the statutory two-thirds of appraisal (Payne uses the published starting bid when the page prints one). That two-thirds figure is not treated as a discount. The sites' terms allow copying for personal, non-commercial use.
- **Payne County sheriff sales** at `https://www.paynecountyok.gov/sheriff-sale`. robots.txt allows `/`. The HTML table has no party names.
- **VRM** (`vrmproperties.com`) statewide VA and Mr. Cooper REO. robots.txt allows the listing path. List price, beds, baths, sqft, status. No cap rate, lot, year built, or days on market on the card.
- **Canadian County assessor** FeatureServer layer 3 (`Parcel Data (External)`, Query and Extract). Matched to Canadian County listings by city and the first street tokens. Owner and mail fields are not requested.

### Needs a key

- **RentCast** (`RENTCAST_API_KEY`). Sale listings for single-family, condo, townhouse, manufactured, multifamily, apartment, and land. No office, retail, or industrial. No cap rate. Agent fields are not stored. Default is one request per type, limit 500.
- **Mashvisor** (`MASHVISOR_API_KEY`, header `x-api-key`). One page of listings for twelve larger Oklahoma cities unless `MASHVISOR_CITIES` is set. Cap rate and occupancy are copied only when the listing record itself has them. `last_sale_price` is stored as `recordedSale` when present. City-level investment stats are not copied onto listings.
- **ATTOM** (`ATTOM_API_KEY`, header `APIKey`). Sale snapshot enrichment, not a for-sale search. A sale amount is stored only when the payload has one. Default cap is 25 addresses.

### Manual only

McClain County sheriff (parser kept and tested; live page returned a SiteGround captcha on 2026-10-22). Realtor.com (robots: scraping unauthorized without Move Sales, Inc. permission). Zillow (terms, and robots disallows `/`). Redfin (robots disallows `/stingray/`). Crexi (terms bar scraping; partner Listing API is inbound only). LoopNet, LandWatch, Land.com, LandAndFarm, Lands of America, and CityFeet (Akamai 403 on robots.txt). CommercialSearch (challenge). HUD Home Store (`Disallow: /`). Freddie Mac HomeSteps (listing HTML is allowed, `/search/` is not; September 2026 terms allowed a personal download and forbade republishing, so it stays manual in a public repo). Fannie Mae HomePath, Auction.com, Bid4Assets, Xome, and OSCN (challenge or terms). OKCountyRecords (key, and results are legal descriptions rather than street addresses). Oklahoma County assessor `TaxParcelsPublics_view` did not resolve; a similarly named service was a different jurisdiction and was not used. Commissioners of the Land Office GIS is agricultural lease auctions, not land for sale.

## Disclosure and comps

Oklahoma is not a pure non-disclosure state. 68 O.S. § 3201 imposes a documentary stamp tax of $0.75 per $500 of consideration exclusive of remaining liens, so a recorded deed can imply a consideration range when stamps exist. Many transfers are exempt and show no stamps. There is no free statewide arm's-length sold-price feed. This tracker does not reverse-engineer stamps and does not show a sold price unless a source field states one (ATTOM `saleAmt`, Mashvisor `last_sale_price`), labeled as such. The comps this build can compute without a key are other asking prices and auction bids already in the tracker.

## Tests

`metrics.js`, `comps.js`, and the Payne, McClain, RentCast, Mashvisor, ATTOM, and assessor adapters have unit tests. Existing sheriff, VRM, geocode, and listing-history tests still pass. Sheriff fixtures still assert that defendant names are never stored.

## Privacy

`data/listings.json` is the snapshot the page serves. Feed caches, the geocode cache, the assessor cache, and `data/sync.log` are gitignored. Before commit, from the repository root: `sh scripts/setup_privacy.sh` and `python3 scripts/check_privacy.py`.
