# Utah Land Listings — 10+ Acres, For Sale

Statewide pull of for-sale land listings in Utah from Realtor.com, captured
October 16, 2026. All 1,184 listings the site reported for this search.

## Files

| File | Contents |
|---|---|
| `utah-land-over-10ac.csv` | 1,184 listings, one row each |
| `utah-land-over-10ac.json` | Same listings as a JSON array |
| `utah-land-10ac.html` | Interactive page: dot map (color = $/acre, size = acreage, hover for details, true-scale circles from zoom 12), county / city / broker / price filters that drive map and table, sortable table, $/acre histogram, CSV export. Open in a browser; needs internet for map tiles |
| `build.py` | Rebuilds the CSV, JSON and page from `raw/`, geocoding as needed |
| `check_raw.py` | Verifies each raw page file against the checksums taken in the browser |
| `page-template.html` | Page template `build.py` fills in |
| `utah-counties.json` | Utah county outlines (US Census 2010 cartographic boundaries) |
| `utah-geocache.json` | Cached address and city lookups, so rebuilds don't re-query |
| `raw/` | 29 page files as captured, plus `page-checksums.json` |

## Columns

| Column | Notes |
|---|---|
| `title` | Address line and city as shown, plus ZIP |
| `price_usd` | Asking price, integer USD |
| `acres` | Lot size in acres (Realtor.com lot sqft / 43,560) |
| `price_per_acre` | Computed |
| `county` | From Realtor.com's county FIPS code; blank for 100 listings that carry none |
| `city`, `zip`, `broker` | As listed |
| `pending` | Flagged pending or contingent |
| `list_date` | Date the listing went up |
| `lat`, `lon`, `placement` | Map position and how it was found (below) |
| `url` | Realtor.com detail page |

## Map positions

| Placement | Count | Source |
|---|---|---|
| realtor | 528 | Realtor.com's own map pin, from the search data |
| address | 4 | Exact match to a UGRC statewide address point |
| city | 651 | City position from OpenStreetMap Nominatim; drawn hollow |
| none | 1 | No city or position at all; not on the map |

UGRC's address points cover towns well but few rural roads, which is why so
few unpinned listings matched.

## How it was collected

Realtor.com search `Utah / type-land / lot-sqft-435600`, sorted "Lowest price"
(`sby-1`) so pages don't reshuffle between loads, 42 listings per page, 29
pages, read from the page's own search data (not the rendered cards, which
lazy-load), paced 7 to 10 seconds per page. No bot checks were hit. Each page
was checksummed in the browser and verified after landing on disk
(`python3 check_raw.py`).

## Scope notes

- **Acreage filter is inclusive** (10+): 111 listings sit at exactly 10.0 acres.
- **Values are as listed.** A $1 and a $16 asking price, and two water-right
  listings showing 4,356,000,000 sqft (100,000 acres), are reproduced verbatim.
- **Duplicates by parcel.** Some parcels are listed twice by different brokers
  or with different ZIPs; each Realtor property id counts once.
- **Terms of use.** Realtor.com's robots.txt says its Terms of Service do not
  allow scraping without written permission from Move Sales, Inc.

## Rebuild

`python3 build.py`
