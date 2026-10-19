#!/usr/bin/env python3
"""check_raw.py — verify each raw/realtor-ut-sby1-pg-NN.json against raw/page-checksums.json."""
import glob, json, os, re
RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
want = {p[0]: p[1:] for p in json.load(open(os.path.join(RAW, "page-checksums.json")))["pages"]}
ok = 0
for f in sorted(glob.glob(os.path.join(RAW, "realtor-ut-sby1-pg-*.json"))):
    pg = int(re.search(r"pg-(\d+)", f).group(1))
    rows = json.load(open(f))["rows"]
    got = [len(rows), sum(r[2] or 0 for r in rows), sum(r[3] or 0 for r in rows),
           sum(len(v) for r in rows for v in r if isinstance(v, str))]
    good = got == want[pg]
    ok += good
    print(f"page {pg:2d}: {'OK ' if good else 'BAD'} got {got} want {want[pg]}")
missing = sorted(set(want) - {int(re.search(r'pg-(\d+)', f).group(1)) for f in glob.glob(os.path.join(RAW, 'realtor-ut-sby1-pg-*.json'))})
print(f"{ok} pages verified; missing pages: {missing}")
