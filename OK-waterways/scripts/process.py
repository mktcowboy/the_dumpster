#!/usr/bin/env python3
"""Process USGS NHD (High Resolution, Oklahoma state extract) + WBD + NWIS gauges
into GeoJSON-seq layers for tippecanoe and JSON/CSV tables for the web app.

Usage: python scripts/process.py RAW_DIR OUT_DIR SITE_DIR
"""
import sys, os, json, math
import numpy as np, pandas as pd, geopandas as gpd, pyogrio
from shapely import force_2d
from shapely.geometry import mapping

RAW, OUT, SITE = sys.argv[1:4]
GDB = os.path.join(RAW, "NHD_H_Oklahoma_State_GDB.gdb")
EA = "EPSG:5070"  # CONUS Albers equal-area for lengths/areas
KM2MI = 0.621371
os.makedirs(OUT, exist_ok=True); os.makedirs(os.path.join(SITE, "data"), exist_ok=True)
os.makedirs(os.path.join(SITE, "tables"), exist_ok=True)

def log(*a): print(*a, flush=True)

# ---- Oklahoma boundary & counties (US Census cartographic boundaries 2023, 1:500k)
st = gpd.read_file(os.path.join(RAW, "st/cb_2023_us_state_500k.shp"))
ok = st[st.STATEFP == "40"].to_crs(4326)
okgeom = ok.geometry.union_all()
co = gpd.read_file(os.path.join(RAW, "co/cb_2023_us_county_500k.shp"))
co = co[co.STATEFP == "40"].to_crs(4326)[["NAME", "geometry"]].rename(columns={"NAME": "county"})
co.to_file(os.path.join(OUT, "counties.geojsonseq"), driver="GeoJSONSeq")
ok[["NAME", "geometry"]].to_file(os.path.join(OUT, "state.geojsonseq"), driver="GeoJSONSeq")
log("counties", len(co))

# FCode descriptions
fc = pyogrio.read_dataframe(GDB, layer="NHDFCode", read_geometry=False)
fc.columns = [c.lower() for c in fc.columns]
fcodes = {int(r.fcode): r.description for r in fc.itertuples() if pd.notna(r.fcode)}
FTYPE = {460: "Stream/River", 558: "Artificial Path", 336: "Canal/Ditch", 334: "Connector",
         420: "Underground Conduit", 428: "Pipeline", 566: "Coastline", 390: "Lake/Pond",
         436: "Reservoir", 466: "Swamp/Marsh", 361: "Playa", 493: "Estuary", 378: "Ice Mass",
         312: "Bay/Inlet", 307: "Area to be Submerged", 318: "Bridge", 343: "Dam/Weir",
         362: "Flume", 364: "Foreshore", 367: "Gate", 369: "Gaging Station", 373: "Hazard Zone",
         398: "Lock Chamber", 403: "Inundation Area", 431: "Rapids", 441: "Rock",
         445: "Sea/Ocean", 454: "Special Use Zone", 455: "Spillway", 458: "Spring/Seep",
         461: "Submerged Stream", 478: "Tunnel", 483: "Wall", 484: "Wash", 485: "Water Intake/Outflow",
         487: "Waterfall", 503: "Sounding Datum Line", 533: "Special Use Zone Limit",
         537: "Area of Complex Channels", 568: "Levee", 569: "Levee"}
json.dump({"fcode": fcodes, "ftype": FTYPE}, open(os.path.join(SITE, "data/codes.json"), "w"))

def clip_ok(g):
    """keep features intersecting OK, clip geometry to the state outline"""
    g = g[g.geometry.notna()].copy()
    g = g.set_crs(4326, allow_override=True)
    for c in ("gnis_id", "gnis_name", "reachcode"):
        if c in g.columns: g[c] = g[c].fillna("")
    g["geometry"] = force_2d(g.geometry.values)
    idx = g.sindex.query(okgeom, predicate="intersects")
    g = g.iloc[np.sort(idx)].copy()
    inside = g.geometry.within(okgeom)
    part = g[~inside].copy()
    part["geometry"] = part.geometry.intersection(okgeom)
    g = pd.concat([g[inside], part])
    g = g[~g.geometry.is_empty]
    return g

def county_of(g):
    """county by representative point"""
    pts = gpd.GeoDataFrame(geometry=g.geometry.representative_point(), crs=4326, index=g.index)
    j = gpd.sjoin(pts, co, predicate="within", how="left")
    j = j[~j.index.duplicated()]
    return j["county"]

def bbox(gs):
    b = gs.total_bounds
    return [round(float(x), 5) for x in b]

def write_seq(g, path, cols):
    g[cols + ["geometry"]].to_file(path, driver="GeoJSONSeq")

# ---- Flowlines
log("reading flowlines")
fl = pyogrio.read_dataframe(GDB, layer="NHDFlowline", columns=[
    "permanent_identifier", "gnis_id", "gnis_name", "reachcode", "ftype", "fcode"])
# Stream order / drainage area / mean annual flow come from NHDPlus HR (see nhdplus_vaa.py);
# the VAA table in the NHD state extract is mostly empty.
vaa = pd.read_csv(os.path.join(OUT, "nhdplus_vaa.csv"), dtype={"permanent_identifier": str})[
    ["permanent_identifier", "streamorder", "totdasqkm", "qema"]]
fl = fl.merge(vaa, on="permanent_identifier", how="left")
log("flowlines in GDB", len(fl))
fl = clip_ok(fl)
fl = fl.explode(index_parts=False).reset_index(drop=True)
fl = fl[fl.geom_type == "LineString"]
log("flowlines in OK", len(fl))
fl["len_km"] = fl.to_crs(EA).length / 1000.0
fl["huc8"] = fl.reachcode.str[:8]
fl["so"] = fl.streamorder.fillna(0).astype(int)
fl["name"] = fl.gnis_name.fillna("")
def fl_minzoom(r_so, r_ft, named):
    if r_ft == 336: return 9
    if r_ft in (420, 428): return 11
    z = {0: 11, 1: 11, 2: 10, 3: 9, 4: 8, 5: 7, 6: 6, 7: 5, 8: 4, 9: 3, 10: 2}.get(r_so, 0 if r_so > 10 else 11)
    if named and z > 9: z = 9 if r_so >= 2 else 10
    return z
fl["mz"] = [fl_minzoom(s, f, n != "") for s, f, n in zip(fl.so, fl.ftype, fl.name)]
fl["lk"] = fl.len_km.round(3)
fl["da"] = (fl.totdasqkm * 0.386102).round(1)  # sq mi
fl["q"] = fl.qema.round(1)  # cfs, EROM gage-adjusted mean annual flow
fl["ftype"] = fl.ftype.astype(int); fl["fcode"] = fl.fcode.fillna(0).astype(int)
# GeoJSONSeq with tippecanoe minzoom
with open(os.path.join(OUT, "flowlines.geojsonseq"), "w") as f:
    for r in fl[["name", "gnis_id", "ftype", "fcode", "so", "lk", "da", "q", "huc8", "mz", "geometry"]].itertuples(index=False):
        props = {"n": r.name, "ft": r.ftype, "fc": r.fcode, "so": r.so, "km": r.lk, "huc8": r.huc8 or ""}
        if r.gnis_id: props["gid"] = r.gnis_id
        if pd.notna(r.da): props["da"] = float(r.da)
        if pd.notna(r.q) and r.q >= 0: props["q"] = float(r.q)
        f.write(json.dumps({"type": "Feature", "tippecanoe": {"minzoom": int(r.mz)}, "properties": props,
                            "geometry": mapping(r.geometry)}, separators=(",", ":")) + "\n")

# ---- Named stream table
named = fl[(fl.name != "") & fl.ftype.isin([460, 558, 336, 334])].copy()
named["key"] = named.gnis_id + "|" + named.name
log("counties for named streams")
segc = gpd.sjoin(named[["key", "geometry"]], co, predicate="intersects", how="left")
cmap = segc.groupby("key")["county"].apply(lambda s: sorted(set(s.dropna())))
rows = []
for key, g in named.groupby("key"):
    gid, name = key.split("|", 1)
    hl = g.groupby("huc8").len_km.sum().sort_values(ascending=False)
    canal = g.loc[g.ftype == 336, "len_km"].sum() > 0.5 * g.len_km.sum()
    rows.append({"name": name, "gnis_id": gid, "type": "Canal/Ditch" if canal else "Stream/River",
                 "length_mi": round(g.len_km.sum() * KM2MI, 2), "max_order": int(g.so.max()),
                 "max_drainage_sqmi": round(float(g.da.max()), 1) if g.da.notna().any() else None,
                 "max_mean_flow_cfs": round(float(g.q.max()), 1) if g.q.notna().any() else None,
                 "segments": len(g), "huc8": hl.index[0], "huc8_all": ";".join(hl.index),
                 "counties": ";".join(cmap.get(key, [])), "bbox": bbox(g.geometry)})
streams = pd.DataFrame(rows)
log("named streams", len(streams))

# ---- Waterbodies
log("reading waterbodies")
wb = pyogrio.read_dataframe(GDB, layer="NHDWaterbody", columns=[
    "permanent_identifier", "gnis_id", "gnis_name", "reachcode", "ftype", "fcode", "elevation"])
log("waterbodies in GDB", len(wb))
wb = clip_ok(wb)
wb = wb.explode(index_parts=False).reset_index(drop=True); wb = wb[wb.geom_type == "Polygon"]
wbe = wb.to_crs(EA)
wb["acres"] = wbe.area / 4046.8564224
wb["name"] = wb.gnis_name.fillna("")
wb["ftype"] = wb.ftype.astype(int); wb["fcode"] = wb.fcode.fillna(0).astype(int)
def wb_mz(a, named):
    z = 0 if a > 20000 else 3 if a > 5000 else 5 if a > 1000 else 7 if a > 200 else 9 if a > 40 else 10 if a > 10 else 11
    if named: z = min(z, 9)
    return z
wb["mz"] = [wb_mz(a, n != "") for a, n in zip(wb.acres, wb.name)]
log("waterbody polygons in OK", len(wb))
with open(os.path.join(OUT, "waterbodies.geojsonseq"), "w") as f:
    for r in wb[["name", "gnis_id", "ftype", "fcode", "acres", "elevation", "mz", "reachcode", "geometry"]].itertuples(index=False):
        props = {"n": r.name, "ft": r.ftype, "fc": r.fcode, "ac": round(float(r.acres), 2)}
        if r.gnis_id: props["gid"] = r.gnis_id
        if r.reachcode: props["huc8"] = r.reachcode[:8]
        if pd.notna(r.elevation): props["el"] = r.elevation
        f.write(json.dumps({"type": "Feature", "tippecanoe": {"minzoom": int(r.mz)}, "properties": props,
                            "geometry": mapping(r.geometry)}, separators=(",", ":")) + "\n")
# label points for named waterbodies
nwb = wb[wb.name != ""].copy()
nwb["key"] = nwb.gnis_id + "|" + nwb.name
nwb["county"] = county_of(nwb)
lrows = []; lab = []
for key, g in nwb.groupby("key"):
    gid, name = key.split("|", 1)
    big = g.loc[g.acres.idxmax()]
    types = g.ftype.map(FTYPE).value_counts()
    a = g.acres.sum()
    hucs = g.reachcode[g.reachcode != ""].str[:8]
    lrows.append({"name": name, "gnis_id": gid, "type": types.index[0], "area_acres": round(a, 1),
                  "area_sqmi": round(a / 640, 3), "polygons": len(g),
                  "county": ";".join(sorted(set(g.county.dropna()))),
                  "huc8": hucs.mode().iat[0] if len(hucs) else "",
                  "elevation_ft": (round(float(g.elevation.dropna().iloc[0]) * 3.28084) if g.elevation.notna().any() else None),
                  "bbox": bbox(g.geometry)})
    lab.append({"type": "Feature", "tippecanoe": {"minzoom": wb_mz(a, False) + 1 if a < 1000 else wb_mz(a, False)},
                "properties": {"n": name, "ft": int(big.ftype), "ac": round(a, 1)},
                "geometry": mapping(big.geometry.representative_point())})
lakes = pd.DataFrame(lrows)
with open(os.path.join(OUT, "waterbody_labels.geojsonseq"), "w") as f:
    for x in lab: f.write(json.dumps(x, separators=(",", ":")) + "\n")
log("named waterbodies", len(lakes))
wb_stats = {"polygons": int(len(wb)), "acres": float(wb.acres.sum()),
            "by_type": {FTYPE.get(int(k), str(k)): {"count": int(v.size), "acres": round(float(v.sum()), 1)} for k, v in wb.groupby("ftype").acres},
            "named": int(len(lakes)), "over_10_acres": int((wb.acres > 10).sum()), "over_100_acres": int((wb.acres > 100).sum())}

# ---- NHDArea (wide rivers, inundation areas, dams, etc.)
ar = pyogrio.read_dataframe(GDB, layer="NHDArea", columns=["gnis_name", "ftype", "fcode"])
ar = clip_ok(ar); ar = ar.explode(index_parts=False).reset_index(drop=True); ar = ar[ar.geom_type == "Polygon"]
ar["n"] = ar.gnis_name.fillna(""); ar["ft"] = ar.ftype.astype(int); ar["fc"] = ar.fcode.fillna(0).astype(int)
ar["ac"] = (ar.to_crs(EA).area / 4046.8564224).round(1)
write_seq(ar, os.path.join(OUT, "areas.geojsonseq"), ["n", "ft", "fc", "ac"])
log("areas", len(ar))
# ---- NHDLine (dams, levees...) & NHDPoint (springs, waterfalls...)
ln = pyogrio.read_dataframe(GDB, layer="NHDLine", columns=["gnis_name", "ftype", "fcode"])
ln = clip_ok(ln); ln = ln.explode(index_parts=False).reset_index(drop=True); ln = ln[ln.geom_type == "LineString"]
ln["n"] = ln.gnis_name.fillna(""); ln["ft"] = ln.ftype.astype(int); ln["fc"] = ln.fcode.fillna(0).astype(int)
write_seq(ln, os.path.join(OUT, "lines.geojsonseq"), ["n", "ft", "fc"])
pt = pyogrio.read_dataframe(GDB, layer="NHDPoint", columns=["gnis_name", "ftype", "fcode"])
pt = clip_ok(pt); pt = pt[pt.geom_type == "Point"]
pt["n"] = pt.gnis_name.fillna(""); pt["ft"] = pt.ftype.astype(int); pt["fc"] = pt.fcode.fillna(0).astype(int)
write_seq(pt, os.path.join(OUT, "points.geojsonseq"), ["n", "ft", "fc"])
log("lines", len(ln), "points", len(pt))

# ---- WBD
wrows = []
for lvl in (2, 4, 6, 8, 10, 12):
    h = pyogrio.read_dataframe(GDB, layer=f"WBDHU{lvl}", columns=[f"huc{lvl}", "name", "areaacres", "states", "tohuc"] if lvl == 12 else [f"huc{lvl}", "name", "areaacres", "states"])
    h["geometry"] = force_2d(h.geometry.values); h = h.set_crs(4326, allow_override=True)
    h = h[h.intersects(okgeom)].copy()
    inter = h.geometry.intersection(okgeom)
    h["ok_acres"] = gpd.GeoSeries(inter, crs=4326).to_crs(EA).area / 4046.8564224
    h = h[h.ok_acres > 1].copy()
    h["huc"] = h[f"huc{lvl}"]; h["lvl"] = lvl
    h["pct_ok"] = (100 * h.ok_acres / h.areaacres).clip(upper=100).round(1)
    h.rename(columns={"name": "n"})[["huc", "n", "lvl", "geometry"]].to_file(os.path.join(OUT, f"hu{lvl}.geojsonseq"), driver="GeoJSONSeq")
    lp = gpd.GeoDataFrame({"huc": h.huc, "n": h.name, "lvl": lvl}, geometry=h.geometry.representative_point())
    lp.to_file(os.path.join(OUT, f"hu{lvl}_labels.geojsonseq"), driver="GeoJSONSeq")
    for r in h.itertuples():
        wrows.append({"huc": r.huc, "name": r.name, "level": f"HUC{lvl}", "area_sqmi": round(r.areaacres / 640, 2),
                      "area_acres": round(r.areaacres, 1), "pct_in_ok": r.pct_ok, "states": r.states,
                      "tohuc": getattr(r, "tohuc", "") or "", "bbox": [round(float(x), 5) for x in r.geometry.bounds]})
    log(f"HU{lvl}", len(h))
sheds = pd.DataFrame(wrows)
# stream miles per HUC8 (all flowlines + named)
mi8 = (fl.groupby("huc8").len_km.sum() * KM2MI).round(1)
sheds["stream_mi_in_ok"] = sheds.apply(lambda r: mi8.get(r.huc, None) if r.level == "HUC8" else None, axis=1)

# ---- USGS NWIS stream/lake gauges
def rdb(p):
    lines = [l for l in open(p) if not l.startswith("#")]
    hdr = lines[0].rstrip("\n").split("\t")
    return pd.DataFrame([l.rstrip("\n").split("\t") for l in lines[2:]], columns=hdr)
ga = rdb(os.path.join(RAW, "nwis_all.rdb")); act = set(rdb(os.path.join(RAW, "nwis_active.rdb")).site_no)
ga["active"] = ga.site_no.isin(act)
ga["lat"] = ga.dec_lat_va.astype(float); ga["lon"] = ga.dec_long_va.astype(float)
gg = gpd.GeoDataFrame(ga, geometry=gpd.points_from_xy(ga.lon, ga.lat), crs=4326)
gg["county"] = county_of(gg)
gauges = pd.DataFrame({"site_no": gg.site_no, "name": gg.station_nm, "type": gg.site_tp_cd.map({"ST": "Stream", "LK": "Lake/Reservoir"}),
                       "active_realtime": gg.active, "drainage_sqmi": pd.to_numeric(gg.drain_area_va, errors="coerce"),
                       "huc8": gg.huc_cd, "county": gg.county, "lat": gg.lat, "lon": gg.lon})
gj = gpd.GeoDataFrame({"site": gauges.site_no, "n": gauges.name, "t": gauges.type, "act": gauges.active_realtime.astype(int),
                       "da": gauges.drainage_sqmi.fillna(-1)}, geometry=gg.geometry, crs=4326)
gj.to_file(os.path.join(SITE, "data/gauges.geojson"), driver="GeoJSON")
log("gauges", len(gauges), "active", int(gauges.active_realtime.sum()))

# ---- outputs: tables (JSON for app, CSV for download)
def out(df, name, cols):
    df.to_csv(os.path.join(SITE, "tables", name + ".csv"), index=False, columns=[c for c in df.columns if c != "bbox"])
    json.dump({"cols": cols, "rows": df[cols].replace({np.nan: None}).values.tolist()},
              open(os.path.join(SITE, "data", name + ".json"), "w"), separators=(",", ":"))
streams = streams.sort_values("length_mi", ascending=False)
lakes = lakes.sort_values("area_acres", ascending=False)
out(streams, "streams", ["name", "type", "length_mi", "max_order", "huc8", "counties", "gnis_id", "bbox", "max_drainage_sqmi", "max_mean_flow_cfs"])
out(lakes, "lakes", ["name", "type", "area_acres", "county", "huc8", "elevation_ft", "gnis_id", "bbox"])
out(sheds, "watersheds", ["huc", "name", "level", "area_sqmi", "pct_in_ok", "states", "stream_mi_in_ok", "bbox"])
gauges.to_csv(os.path.join(SITE, "tables", "gauges.csv"), index=False)

ftm = (fl.groupby("ftype").len_km.sum() * KM2MI)
stats = {
    "flowline_segments": int(len(fl)),
    "total_flowline_miles": round(float(fl.len_km.sum() * KM2MI), 0),
    "miles_by_type": {FTYPE.get(int(k), str(k)): round(float(v), 0) for k, v in ftm.items()},
    "miles_by_flow": {k: round(float(fl[fl.fcode.isin(c)].len_km.sum() * KM2MI), 0) for k, c in
                      {"perennial": [46006], "intermittent": [46003], "ephemeral": [46007]}.items()},
    "order_coverage_pct": round(float(100 * fl.streamorder.notna().mean()), 2),
    "miles_by_order": {int(k): round(float(v * KM2MI), 0) for k, v in fl.groupby("so").len_km.sum().items()},
    "named_streams": int(len(streams)),
    "named_stream_miles": round(float(named.len_km.sum() * KM2MI), 0),
    "waterbodies": wb_stats,
    "watersheds": {f"HUC{l}": int((sheds.level == f"HUC{l}").sum()) for l in (2, 4, 6, 8, 10, 12)},
    "gauges": int(len(gauges)), "gauges_active_realtime": int(gauges.active_realtime.sum()),
    "nhd_areas": int(len(ar)), "nhd_lines": int(len(ln)), "nhd_points": int(len(pt)),
    "top_streams": streams.head(10)[["name", "length_mi"]].values.tolist(),
    "top_lakes": lakes.head(10)[["name", "area_acres"]].values.tolist(),
}
json.dump(stats, open(os.path.join(SITE, "data/stats.json"), "w"), indent=1)
log(json.dumps(stats, indent=1))
