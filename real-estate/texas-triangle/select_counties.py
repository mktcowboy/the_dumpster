#!/usr/bin/env python3
"""One-time setup: pick the Texas counties with any land inside the triangle or its 50-mile ring.

Downloads US county outlines (us-atlas, Census-derived) into data/cache/ and writes
data/counties_target.json, nearest counties first. Only re-run this if you change the
triangle vertices or BUFFER_MI in geo.py.
"""
import json, os, urllib.request

from geo import V, BUFFER_MI, point_in_poly, dist_to_triangle_mi

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "cache", "counties-10m.json")
ATLAS_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/counties-10m.json"
OUT = os.path.join(HERE, "data", "counties_target.json")
SLACK_MI = 2.0  # boundary is sampled, so allow a little slack past BUFFER_MI


def load_atlas():
    if not os.path.exists(CACHE):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        print("downloading", ATLAS_URL)
        urllib.request.urlretrieve(ATLAS_URL, CACHE)
    return json.load(open(CACHE))


def main():
    d = load_atlas()
    sx, sy = d["transform"]["scale"]
    tx0, ty0 = d["transform"]["translate"]
    arcs = []
    for arc in d["arcs"]:  # delta-decode TopoJSON arcs -> [(lat, lon)]
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx; y += dy
            pts.append((y * sy + ty0, x * sx + tx0))
        arcs.append(pts)

    def rings(g):
        polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
        for poly in polys:
            for ring in poly:
                pts = []
                for ai in ring:
                    pts += arcs[ai] if ai >= 0 else arcs[~ai][::-1]
                yield pts

    results = []
    for g in d["objects"]["counties"]["geometries"]:
        if not g["id"].startswith("48") or g["type"] not in ("Polygon", "MultiPolygon"):
            continue
        rs = list(rings(g))
        dist = min(dist_to_triangle_mi(pt) for ring in rs for pt in ring[::7])
        outer = max(rs, key=len)
        if any(point_in_poly(v, outer) for v in V):
            dist = 0.0
        results.append((dist, g["properties"]["name"]))
    results.sort()
    keep = [name for dist, name in results if dist <= BUFFER_MI + SLACK_MI]
    json.dump(keep, open(OUT, "w"))
    print(f"wrote {os.path.relpath(OUT, HERE)}: {len(keep)} counties")


if __name__ == "__main__":
    main()
