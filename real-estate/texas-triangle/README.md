# Texas Triangle Land: Parcels for Sale

Every for-sale property on **5+ acres** (land, farm/ranch, houses on acreage, mobile, multi-family) inside the Dallas, San Antonio and Houston triangle, plus a
**50-mile ring** around it. The data comes from Realtor.com and appears on one interactive map page
(`texas-triangle-land.html`) that includes $/acre, filters, listing links and CSV export.

The whole process is scripted. Run one command to refresh it, with no AI or browser involved.

**Current snapshot (2026-10-18):** 16,048 parcels (5,525 inside the triangle, 10,523 in the ring)
across 86 counties: land, farm/ranch, houses on acreage, mobile and multi-family. Median price is
about $690k, median $/acre about $38k, median size about 13 acres.

## Refresh the data (the only thing you normally do)

```bash
sh update.sh
```

Then open `texas-triangle-land.html` in a browser. The first run creates `.venv/` and installs
the one dependency ([HomeHarvest](https://github.com/ZacharyHampton/HomeHarvest)). Each run takes
about 10 minutes for the scrape, mostly spent waiting politely between counties. The *first* run
also spends about 45 minutes geocoding the ~1,900 listings that have no coordinates. Those results
are cached in `data/geocode_cache.json`, so later runs only geocode newly appeared listings.

- **It's safe to re-run.** Each run saves to `data/raw/<today>/`. If some counties fail (network
  blip, rate limit), the script exits with an error and names them. Run `sh update.sh` again and
  it pulls only the missing counties.
- **`sh update.sh --force`** re-pulls every county even if today's snapshot already has it.
- **Run it weekly, or as often as you like.** Each run is a dated snapshot, so the page can
  flag listings that are **new** since the previous run and show **"was $X"** when a price changed.
  The "Only listings new since the previous run" checkbox filters to the new ones.

## How it works

```
data/counties_target.json ──► scrape.py ──► data/raw/YYYY-MM-DD/<County>.json.gz
                                              │
                                              ▼
                               process.py ──► data/listings.json
                                              │
                                              ▼
                             build_page.py ──► texas-triangle-land.html
```

| Step | File | What it does |
|---|---|---|
| 1 | `scrape.py` | For each county, asks Realtor.com's search API (via HomeHarvest) for `for_sale` + lot ≥ 217,800 sq ft (5 ac), all property types. It keeps only property facts (id, URL, address, price, lot size, lat/lon, status, style `LAND`/`FARM`, list date) and drops agent and office contact fields. |
| 2 | `process.py` | Reads the newest snapshot. Dedupes by property id (Realtor returns some properties twice; it keeps the newest listing). Keeps `FOR_SALE` only (drops pending/contingent), ≥ 5 acres and price ≥ $1,000 (drops $1 placeholders), and fills missing coordinates by geocoding. Classifies each listing as `inside`, `buffer` (≤ 50 mi) or `outside` (dropped), and adds `first_seen` / `prev_price` from earlier snapshots. |
| 3 | `build_page.py` | Builds the self-contained HTML page. Every filter drives the map, stats, $/acre histogram and table together. Leaflet is inlined from `vendor/`, so only the map tiles need network. |
| setup | `select_counties.py` | Picks the counties that touch the triangle or its ring and writes them to `data/counties_target.json`. Re-run it only if you change the triangle or the ring width. |
| shared | `geo.py` | Triangle vertices, `BUFFER_MI`, point-in-polygon and distance-to-edge. |
| shared | `privacy_filter.py` | Drops any listing whose text matches the repo's privacy blocklist (`../../scripts/check_privacy.py`), so a coincidental address never lands in a committed file. One listing was dropped in the 2026-10-18 snapshot. |

You can run the steps one at a time (use `.venv/bin/python` after the first `update.sh`):

```bash
.venv/bin/python scrape.py --counties Bexar Hays   # just some counties
.venv/bin/python process.py --date 2026-10-18      # rebuild from an older snapshot
.venv/bin/python process.py --no-geocode           # offline; uses cached geocodes only
.venv/bin/python build_page.py
```

## Data files

| Path | Contents |
|---|---|
| `data/raw/YYYY-MM-DD/<County>.json.gz` | Raw per-county pull (gzipped JSON, about 1.2 MB per snapshot), one row per listing as Realtor.com returned it. `_meta.json` has row counts and timestamps. Keep these: they are the history used for "new" and "was $X". Read one with `gzip -dc data/raw/2026-10-18/Hays.json.gz \| python3 -m json.tool`. |
| `data/listings.json` | `{snapshot, listings: [...]}`. Each listing has `title, price, acres, lat, lon, city, county, url, zone, dist_tri_mi, loc, list_date, first_seen, prev_price`. |
| `data/geocode_cache.json` | Nominatim results for listings that Realtor.com publishes without coordinates. Keeping it makes re-runs fast. |
| `data/counties_target.json` | The 86 target counties, nearest to the triangle first. |
| `data/cache/` | Downloaded county outlines (git-ignored, re-downloaded on demand). |

## Key facts and decisions

- **Triangle vertices:** Dallas (32.7767, -96.7970), San Antonio (29.4241, -98.4936),
  Houston (29.7604, -95.3698). The ring is 50 statute miles from the triangle edges.
  Change either in `geo.py`, then re-run `select_counties.py`.
- **Acres** come from Realtor.com's `lot_sqft ÷ 43,560`.
- **Location precision (`loc`):** `parcel` = Realtor.com's own coordinates (88% of
  listings). Otherwise the point is geocoded to `street`, `zip` or `city` and shows as
  **~approx** on the page. These are usually "TBD" or county-road listings with no address.
- **Source is Realtor.com only.** LandWatch, Lands of America, land.com, Land and Farm and
  Redfin all block automated access, so listings exclusive to those sites are missing.
  Realtor.com aggregates MLS listings, so most broker-listed land is covered.
- **Some data is just wrong at the source.** For example, a San Antonio lot is listed as
  7,500 acres for $50k, which is almost certainly 7,500 sq ft. Sort by $/acre to spot these.
- **Pending/contingent listings are excluded.** Edit `KEEP_STATUS` in `process.py` to include them.

## If something breaks

- **`scrape.py` fails for every county.** Realtor.com probably changed its API. Update the
  library with `.venv/bin/pip install -U homeharvest` and re-run. If that doesn't fix it,
  check the HomeHarvest GitHub issues.
- **Lots of rate-limit errors.** Wait an hour and re-run. Finished counties are skipped.
  You can also raise the `time.sleep(random.uniform(2, 5))` delay in `scrape.py`.
- **The map is blank or shows "Access blocked" / "API key required" tiles.** The page uses
  Esri tiles because OpenStreetMap's and CARTO's tile servers both return a placeholder image
  to pages opened as local files. If Esri starts doing the same, swap the `L.tileLayer(...)`
  URL in `build_page.py` and re-run it. Test a candidate first with
  `curl -o t.png <tile url>` and look at the image.

## Previewing the page

Opening the HTML file directly works. To serve it locally instead:

```bash
python3 -m http.server 8765 --directory real-estate/texas-triangle
```

Then visit http://localhost:8765/texas-triangle-land.html.

## History

- The first version (October 2026) was collected by hand-driving a browser through Realtor.com
  search pages. It covered only 4 of 86 counties, and most points sat at city centers. It was
  replaced by the scripted HomeHarvest pipeline above, which covers all counties and uses
  Realtor.com's own coordinates.
- Fixed at the same time:
  - The page hung with no data once the dataset grew. A gzip-stream deadlock in the
    page's loader; it now uses `pipeThrough`.
  - The dashed 50-mile ring was drawn wrong on two sides. It is now the exact convex hull
    of 50-mile circles around the vertices.

## Commercial real estate (CRE): not covered, and why

Realtor.com has no commercial, industrial or investment listings. The CRE listing sites (LoopNet,
Crexi, CommercialCafe, Showcase) and the Land.com network all refuse automated requests (HTTP 403)
and forbid scraping; CoStar (LoopNet, Showcase, Land.com) litigates against scrapers. Legitimate
options, if they become available:

- **MLS feed through a Texas broker** (HAR, NTREIS, ABoR, SABOR carry commercial and land) via
  RESO Web API / IDX. This plugs into this pipeline as another `scrape_*.py`.
- **Paid data access** (Crexi, CoStar).
- **County appraisal rolls** (free, public): every parcel with land use, acreage and owner, but
  not for-sale status.
- **Tax-sale properties** (free public JSON at `taxsales.lgbs.com/api/property_sales/?state=TX`):
  checked 2026-10-18, 2,516 in the triangle counties but median value about $32k, with no acreage
  or property type. Not added.

## Ideas for later

- Price-history chart per listing (all snapshots are kept in `data/raw/`).
- Flag listings that disappeared since the previous run (sold or withdrawn).
- Schedule `update.sh` weekly (cron or launchd) and commit the new snapshot.
