#!/usr/bin/env bash
# Reproducible build: download sources -> process -> vector tiles -> site/ ready to deploy.
# Requires: curl, unzip, GDAL, tippecanoe, Python 3 with geopandas/pyogrio/shapely.
# Easiest: micromamba create -n geo -c conda-forge gdal tippecanoe geopandas pyogrio shapely pandas
set -euo pipefail
RAW=${RAW:-raw}; B=${B:-build}
mkdir -p "$RAW" "$B"
S3=https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHD/State/GDB
[ -f "$RAW/NHD_H_Oklahoma_State_GDB.zip" ] || curl -fL -o "$RAW/NHD_H_Oklahoma_State_GDB.zip" "$S3/NHD_H_Oklahoma_State_GDB.zip"
[ -d "$RAW/NHD_H_Oklahoma_State_GDB.gdb" ] || unzip -q -o "$RAW/NHD_H_Oklahoma_State_GDB.zip" -d "$RAW"
for x in state county; do
  [ -d "$RAW/${x:0:2}" ] || { curl -fL -o "$RAW/$x.zip" "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_${x}_500k.zip"; unzip -q -o "$RAW/$x.zip" -d "$RAW/${x:0:2}"; }
done
P=https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHDPlusHR/Beta/GDB
mkdir -p "$RAW/nhdplus"
for h in 1104 1105 1106 1107 1109 1110 1111 1112 1113 1114; do
  [ -d "$RAW/nhdplus/NHDPLUS_H_${h}_HU4_GDB.gdb" ] || { curl -fL -o "$RAW/nhdplus/$h.zip" "$P/NHDPLUS_H_${h}_HU4_GDB.zip"; unzip -q -o "$RAW/nhdplus/$h.zip" -d "$RAW/nhdplus"; }
done
python3 scripts/nhdplus_vaa.py "$RAW/nhdplus" "$B/nhdplus_vaa.csv"
NW="https://waterservices.usgs.gov/nwis/site/?format=rdb&stateCd=ok&siteType=ST,LK"
curl -fsS -o "$RAW/nwis_all.rdb" "$NW&siteStatus=all&hasDataTypeCd=iv,dv&siteOutput=expanded"
curl -fsS -o "$RAW/nwis_active.rdb" "$NW&siteStatus=active&hasDataTypeCd=iv"
python3 scripts/process.py "$RAW" "$B" site
bash scripts/tiles.sh "$B" site
echo "Done. Deploy with: python3 scripts/deploy.py (see README)"
