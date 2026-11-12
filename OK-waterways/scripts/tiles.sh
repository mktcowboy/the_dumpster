#!/usr/bin/env bash
# Build vector tiles (PMTiles) from the GeoJSONSeq layers written by process.py,
# then split them into <=24 MiB chunks for Cloudflare Workers Static Assets.
set -euo pipefail
B=${1:-build}; SITE=${2:-site}
python3 - "$B" <<'PY'
import sys, json, geopandas as gpd
b = sys.argv[1]
co = gpd.read_file(f"{b}/counties.geojsonseq")
co.assign(geometry=co.geometry.representative_point()).to_file(f"{b}/county_labels.geojsonseq", driver="GeoJSONSeq")
PY
tippecanoe -o "$B/hydro.pmtiles" --force -n "Oklahoma hydrography (USGS NHD HR)" \
  -A '<a href="https://www.usgs.gov/national-hydrography">USGS NHD</a>' \
  -Z0 -z12 -P -q --no-feature-limit --no-tile-size-limit --simplification=2 --no-tiny-polygon-reduction-at-maximum-zoom \
  -j '{"lines":[">=","$zoom",9],"points":[">=","$zoom",9],"areas":["any",[">=","$zoom",7],[">","ac",2000]]}' \
  -L flowlines:"$B/flowlines.geojsonseq" -L waterbodies:"$B/waterbodies.geojsonseq" \
  -L waterbody_labels:"$B/waterbody_labels.geojsonseq" -L areas:"$B/areas.geojsonseq" \
  -L lines:"$B/lines.geojsonseq" -L points:"$B/points.geojsonseq"
tippecanoe -o "$B/wbd.pmtiles" --force -n "Oklahoma watersheds (USGS WBD)" \
  -Z0 -z12 -P -q --no-feature-limit --no-tile-size-limit --detect-shared-borders --simplification=2 \
  -j '{"hu10":[">=","$zoom",6],"hu12":[">=","$zoom",7],"hu10_labels":[">=","$zoom",8],"hu12_labels":[">=","$zoom",9]}' \
  -L hu2:"$B/hu2.geojsonseq" -L hu4:"$B/hu4.geojsonseq" -L hu6:"$B/hu6.geojsonseq" -L hu8:"$B/hu8.geojsonseq" \
  -L hu10:"$B/hu10.geojsonseq" -L hu12:"$B/hu12.geojsonseq" \
  -L hu2_labels:"$B/hu2_labels.geojsonseq" -L hu4_labels:"$B/hu4_labels.geojsonseq" -L hu6_labels:"$B/hu6_labels.geojsonseq" \
  -L hu8_labels:"$B/hu8_labels.geojsonseq" -L hu10_labels:"$B/hu10_labels.geojsonseq" -L hu12_labels:"$B/hu12_labels.geojsonseq" \
  -L state:"$B/state.geojsonseq" -L counties:"$B/counties.geojsonseq" -L county_labels:"$B/county_labels.geojsonseq"
ls -la "$B"/*.pmtiles
# chunk
python3 - "$B" "$SITE" <<'PY'
import sys, os, json, hashlib
b, site = sys.argv[1:3]
C = 512 * 1024  # small chunks: Workers Static Assets ignore Range, so the Worker reads whole chunks
man = {}
for name in ("hydro", "wbd"):
    p = f"{b}/{name}.pmtiles"; data = open(p, "rb").read()
    d = f"{site}/tiles/{name}"; os.makedirs(d, exist_ok=True)
    for f in os.listdir(d): os.remove(os.path.join(d, f))
    n = 0
    for i in range(0, len(data), C):
        open(f"{d}/{n:03d}.bin", "wb").write(data[i:i + C]); n += 1
    man[name] = {"size": len(data), "chunk": C, "n": n, "etag": hashlib.md5(data).hexdigest()}
json.dump(man, open("worker/manifest.json", "w"), indent=1)
print(man)
PY
