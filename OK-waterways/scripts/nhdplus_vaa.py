#!/usr/bin/env python3
"""Extract stream order, drainage area and mean annual flow from NHDPlus HR (per-HU4 GDBs)
keyed by NHD Permanent_Identifier. Usage: nhdplus_vaa.py NHDPLUS_DIR OUT_CSV"""
import sys, glob, pandas as pd, pyogrio
rows = []
for g in sorted(glob.glob(sys.argv[1] + "/NHDPLUS_H_*_HU4_GDB.gdb")):
    fl = pyogrio.read_dataframe(g, layer="NHDFlowline", read_geometry=False, columns=["Permanent_Identifier", "NHDPlusID"])
    v = pyogrio.read_dataframe(g, layer="NHDPlusFlowlineVAA", read_geometry=False, columns=["NHDPlusID", "StreamOrde", "TotDASqKm"])
    e = pyogrio.read_dataframe(g, layer="NHDPlusEROMMA", read_geometry=False, columns=["NHDPlusID", "QEMA"])
    d = fl.merge(v, on="NHDPlusID", how="left").merge(e, on="NHDPlusID", how="left")
    rows.append(d); print(g, len(d), d.StreamOrde.notna().mean(), flush=True)
d = pd.concat(rows).drop_duplicates("Permanent_Identifier")
d.columns = ["permanent_identifier", "nhdplusid", "streamorder", "totdasqkm", "qema"]
d.to_csv(sys.argv[2], index=False)
print(len(d), d.streamorder.value_counts().sort_index().to_dict())
