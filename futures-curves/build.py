"""Build futures-curves.html from data.json + template.html (Chart.js inlined, works offline).

Usage:  python3 build.py           # build from existing data.json
        python3 build.py --fetch   # refresh data from Yahoo Finance first
"""
import json, os, sys, subprocess, datetime as dt
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(HERE, *a)
CT = ZoneInfo("America/Chicago")

def mi(c): return c["y"] * 12 + c["m"] - 1          # absolute month index

def derive(r, asof):
    cs = r["c"]
    if not cs:
        r["ok"] = False; return r
    r["ok"] = True
    # front = contract Yahoo's continuous ROOT=F currently tracks (closest last price, prefer earlier on ties);
    # anything before it is an expiring / delivery-month contract.
    fi = 0
    if r.get("h") and r.get("hsrc", "").endswith("=F"):
        ref = r["h"][-1]
        fi = min(range(min(3, len(cs))), key=lambda i: (abs(cs[i]["last"] - ref) / ref, i))
    r["fi"] = fi
    f = cs[fi]
    for c in cs:
        c["chg"] = c["last"] - c["prev"]
        c["chgp"] = (c["last"] / c["prev"] - 1) * 100 if c["prev"] else None
        c["sp"] = c["last"] - f["last"]
        c["spp"] = (c["last"] / f["last"] - 1) * 100
        c["dm"] = mi(c) - mi(f)
        c["stale"] = c["d"] < asof
    fwd = cs[fi + 1:]
    far, kind = None, None
    live = [c for c in fwd if not c["stale"]] or fwd      # prefer contracts that printed on the latest date
    if live:
        near12 = [c for c in live if 9 <= c["dm"] <= 15]
        if near12:
            far = min(near12, key=lambda c: abs(c["dm"] - 12)); kind = "12M"
        else:
            far = live[-1]; kind = "last"
    if far:
        ry = ((f["last"] / far["last"]) ** (12 / far["dm"]) - 1) * 100   # + = backwardation (long roll earns)
        r["ry"] = ry; r["far"] = far["lab"]; r["fark"] = kind; r["fardm"] = far["dm"]
        r["fsp"] = (far["last"] / f["last"] - 1) * 100
        r["st"] = "Flat" if abs(ry) < 0.5 else ("Backwardation" if ry > 0 else "Contango")
        nxt = cs[fi + 1]
        r["f2"] = (nxt["last"] / f["last"] - 1) * 100
        # shape: count sign flips of month-to-month spreads among non-stale contracts
        seq = [c["last"] for c in cs[fi:] if not c["stale"]]
        diffs = [b - a for a, b in zip(seq, seq[1:]) if abs(b - a) / a > 0.002]
        flips = sum(1 for a, b in zip(diffs, diffs[1:]) if (a > 0) != (b > 0))
        r["shape"] = "Seasonal / mixed" if flips >= 2 else ("Humped" if flips == 1 else "Monotonic")
        # 1M-ago structure for comparison
        if f.get("m1") and far.get("m1"):
            r["ry1m"] = ((f["m1"] / far["m1"]) ** (12 / far["dm"]) - 1) * 100
    else:
        r["st"] = "Single contract"
    r["front"] = f["lab"]; r["ft"] = f["t"]; r["last"] = f["last"]; r["chgp"] = f["chgp"]
    if r.get("h"):
        h = r["h"]; r["p1y"] = (h[-1] / h[0] - 1) * 100; r["p1m"] = (h[-1] / h[-22] - 1) * 100 if len(h) > 22 else None
    return r

def main():
    if "--fetch" in sys.argv:
        subprocess.run([sys.executable, P("fetch.py")], check=True)
    d = json.load(open(P("data.json")))
    asof = d["asof_bar"]
    for g in d["groups"].values():
        for r in g: derive(r, asof)
    gen = dt.datetime.fromisoformat(d["generated"]).astimezone(CT)
    d["gen_ct"] = gen.strftime("%b %-d, %Y · %-I:%M %p CT")
    d["asof_nice"] = dt.date.fromisoformat(asof).strftime("%b %-d, %Y")
    t = open(P("template.html")).read()
    js = open(P("vendor", "chart.umd.min.js")).read()
    h = t.replace("/*__CHARTJS__*/", js).replace("__DATA__", json.dumps(d, separators=(",", ":")))
    open(P("futures-curves.html"), "w").write(h)
    n = sum(1 for g in d["groups"].values() for r in g if r["ok"])
    print(f"wrote futures-curves.html ({len(h)/1e6:.2f} MB) · {n} markets with curves · generated {d['gen_ct']}")

if __name__ == "__main__":
    main()
