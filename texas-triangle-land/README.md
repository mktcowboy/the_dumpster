# Texas Triangle Land — Parcels for Sale

All for-sale land parcels **larger than 5 acres** inside the Dallas–San Antonio–Houston
triangle ("the Texas Triangle") plus a **50-mile buffer** around its edges, scraped from
Realtor.com county searches. Interactive map page with price/acre, listing links, filters,
and CSV export.

## What's here

| Path | What it is |
|---|---|
| `texas-triangle-land.html` | The interactive deliverable — open in a browser. Clustered map (navy = inside triangle, burnt orange = 50-mi ring), $/acre histogram, filters, sortable table, CSV export. Fully self-contained (Leaflet inlined); only map tiles need network. |
| `data/listings.json` | Assembled parcel records: title, price, acres, lat/lon, city, county, listing URL, zone (`inside`/`buffer`), distance to triangle edge, geocode precision (`parcel`/`street`/`city`). |
| `data/chunks/texas-<County>.json` | Raw per-county scrape output: `{u, p, a, c, t}` = detail URL, price USD, acres, city, title. |
| `data/counties_target.json` | The 86 Texas counties with land inside the triangle or 50-mi ring. |
| `data/county_urls.json`, `data/chunk_urls.json`, `data/chunks_plan.json` | Search-URL maps and the 14-chunk scrape plan. |
| `data/geocode_cache.json` | Nominatim geocode cache (makes rebuilds fast). |
| `pipeline_v1.py` | Chunks → dedupe → geocode (Nominatim cascade: full address → street → city) → classify inside/buffer → `listings.json`. |
| `build_tx_page.py` | `listings.json` → `texas-triangle-land.html`. |
| `geo.py` | Triangle geometry: point-in-polygon + distance-to-edge in miles. |
| `counties_tight.py` | County selection (us-atlas counties-10m + Census county list). |
| `vendor/` | Leaflet 1.9.4 + markercluster assets inlined by the builder. |

## Rebuild

```bash
python3 pipeline_v1.py   # geocode + classify -> data/listings.json
python3 build_tx_page.py # -> texas-triangle-land.html
```

## Coverage & caveats

- Snapshot as of **October 18, 2026**. Only **4 of 86 counties** captured so far
  (Bexar, Harris, Burleson, Coryell — 501 raw records → 454 in the triangle/ring);
  the sweep continues and this folder will be refreshed.
- Realtor.com only — LandWatch, Lands of America, land.com, landandfarm, and Redfin
  all hard-block automated access; Realtor.com itself rate-limits aggressively (bot wall),
  so the scrape runs in short windows.
- ~55% of rural parcels list no street address ("TBD", county roads); those are plotted
  at the street or city center and marked **~approx** on the page.
- Triangle vertices: Dallas (32.7767, -96.7970), San Antonio (29.4241, -98.4936),
  Houston (29.7604, -95.3698). Ring = 50 statute miles from triangle edges.
- Prices/acres reproduced from listing cards; blank where the card showed nothing.
