# Oklahoma Waterways — interactive map

An interactive map and searchable tables of **every mapped waterway in Oklahoma**: rivers, streams, canals and ditches,
lakes, reservoirs and ponds, swamps, dams and levees, springs and waterfalls, USGS stream/lake gauges, and watershed
boundaries at every HUC level (HUC2 → HUC12).

**Live map:** deployed as a Cloudflare Worker (see `wrangler.jsonc`).

**Source:** this `OK-waterways/` folder on the repository default branch. Run all commands from inside `OK-waterways/`.

## Features
- Every NHD High Resolution flowline and waterbody inside Oklahoma, as vector tiles (PMTiles). Major rivers show at state
  zoom; smaller streams and ponds appear as you zoom in (all features visible by zoom 11).
- Streams styled by Strahler stream order (NHDPlus HR) and colored by flow permanence (perennial / intermittent / ephemeral).
- Layer toggles for streams, canals/ditches, pipelines, lakes, swamps, NHD areas/lines/points, each WBD HUC level,
  gauges (active/inactive), counties, and basemap.
- Labels for named features; click popups (name, type, stream order, drainage area, mean annual flow, segment/total length,
  area, elevation, HUC8 + watershed name, counties, GNIS ID; gauge links to USGS Water Data).
- Search across named rivers/streams, lakes/reservoirs, watersheds (by name or HUC code) and gauges.
- Sortable/filterable tables (click a row to zoom + highlight) with CSV downloads:
  `site/tables/streams.csv`, `lakes.csv`, `watersheds.csv`, `gauges.csv`.
- Statewide summary stats.

## Data sources
| Data | Source | Vintage |
|---|---|---|
| Flowlines, waterbodies, areas, lines, points | USGS NHD High Resolution, Oklahoma state extract `NHD_H_Oklahoma_State_GDB` (The National Map staged products) | published 2023-12-27 (final NHD release; NHD is now retired/static) |
| Watershed boundaries HUC2–HUC12 | USGS WBD layers in the same staged GDB | 2023-12 |
| Stream order, drainage area, mean annual flow (EROM QEMA) | USGS NHDPlus HR, HU4 GDBs 1104, 1105, 1106, 1107, 1109, 1110, 1111, 1112, 1113, 1114 | NHDPlus HR (Beta) staged products |
| Gauges | USGS NWIS site service (stream + lake sites in OK with daily or instantaneous data; "active" = active IV) | fetched at build time |
| State outline, counties | US Census Bureau cartographic boundary files 2023, 1:500k | 2023 |

## Build
```bash
# tools: GDAL, tippecanoe, python3 + geopandas/pyogrio/shapely, e.g.
micromamba create -n geo -c conda-forge gdal tippecanoe geopandas pyogrio shapely pandas
micromamba activate geo
./build.sh          # downloads ~2.6 GB, writes site/data, site/tables and site/tiles (chunked PMTiles)
npx wrangler deploy # Cloudflare Worker + Static Assets (see wrangler.jsonc)
```
`scripts/process.py` clips everything to the Oklahoma boundary, computes lengths/areas in CONUS Albers (EPSG:5070),
builds the tables and stats. `scripts/tiles.sh` runs tippecanoe (max zoom 12) and splits each PMTiles archive into
512 KiB chunks, because Workers Static Assets caps files at 25 MiB; `worker/index.js` reassembles byte ranges so the
browser sees a normal `tiles/<name>.pmtiles` that supports HTTP Range requests.

Generated data (`site/tiles`, `site/data`, `site/tables`) is not all committed; run the build to regenerate.

## Notes / limitations
- Tables list **named** features only (GNIS names); unnamed streams/ponds are on the map and in the statewide totals.
- Lengths/areas are the in-state portions (e.g. Red River and Lake Texoma are clipped at the state line).
- Stream order/flow come from NHDPlus HR and are joined by NHD Permanent Identifier; a small share of flowlines
  (edited after NHDPlus HR was built, or outside the network) have no order and are styled as the smallest streams.
- Geometry is simplified by tippecanoe at low zooms; full detail at zoom 12+.
