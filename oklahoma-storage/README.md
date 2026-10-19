# Oklahoma Storage Directory

Every self-storage business in Oklahoma, profiled in one self-contained HTML file.

**File:** `oklahoma-storage-directory.html` (open it directly in a browser — no server needed)

## What's inside

- **865 facilities** across 150+ Oklahoma cities — self-storage, mini-storage, boat & RV storage, national chains and independents
- Per-facility profile: name, full address, city, zip, phone, website, brand/operator, type, region, notes
- Interactive map with clustered markers (Leaflet, inlined — no CDN dependency)
- Search box + filters by city, brand, and storage type; sortable table; expandable profile rows; CSV export of filtered results
- Stats bar: total facilities, cities covered, chain vs independent split, top brands

## Coverage by region

- OKC metro: 208 facilities (Oklahoma City, Edmond, Yukon, Norman, Moore, …)
- Tulsa metro: 184 facilities (Tulsa, Broken Arrow, Owasso, Claremore, Sapulpa, …)
- Rest of state: 473 facilities (Lawton, Enid, Ada, Stillwater, Shawnee, Durant, Duncan, …)

## Methodology

Data collected October 19, 2026 via place-search sweeps of every listed city plus storage-directory cross-checks (SpareFoot, SelfStorage.com, Yelp). Deduplicated by name + address + city. Addresses geocoded via Nominatim (860 of 865 placed; city-centroid fallback flagged as approximate).

## Caveats

- A few records carry rebrand/possible-duplicate flags in their notes (e.g., SpareBox vs Doc's Mini Storage in Enid) — shown verbatim in the profile
- Zip/phone/website missing where sources didn't publish them
- Tulsa's south corridor (101st St / Jenks border) may be slightly undercounted
- 18 small towns verified with zero named facilities
- Coordinates are geocoded approximations, not survey data

## Files

- `oklahoma-storage-directory.html` — the directory (everything embedded, works offline except map tiles)
- `oklahoma-storage-master.json` — the underlying dataset (one record per facility)
