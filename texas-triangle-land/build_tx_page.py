#!/usr/bin/env python3
"""Build texas-triangle-land.html — interactive parcel map + analysis.

Reads ~/workspace/texas-triangle-land/listings.json (array of
{title,price,acres,ppa,lat,lon,city,county,url,zone,dist_tri_mi,loc})
and writes ~/workspace/your_files/texas-triangle-land.html with:
  stat strip, Leaflet map (clustered parcel markers, triangle + 50mi ring
  overlays), $/acre histogram, filterable/sortable table, CSV export.
"""
import json, html, math, gzip, base64, os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "listings.json")
OUT = "/home/hatch/workspace/your_files/texas-triangle-land.html"

# Triangle vertices (lat, lon): Dallas, San Antonio, Houston
V = [(32.7767, -96.7970), (29.4241, -98.4936), (29.7604, -95.3698)]
BUFFER_MI = 50.0


def buffer_ring(vertices, miles, step=2.0):
    """Outward-offset polygon ring (equirectangular approx, fine for display)."""
    cx = sum(v[0] for v in vertices) / 3
    cy = sum(v[1] for v in vertices) / 3
    ring = []
    n = len(vertices)
    for i in range(n):
        a = vertices[i]
        b = vertices[(i + 1) % n]
        # edge midpoint -> outward normal (away from centroid)
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        dx, dy = mx - cx, my - cy
        # perpendicular to edge, pointing outward
        ex, ey = b[0] - a[0], b[1] - a[1]
        elen = math.hypot(ex, ey)
        nx, ny = -ey / elen, ex / elen
        if nx * dx + ny * dy < 0:
            nx, ny = -nx, -ny
        lat0 = math.radians(mx)
        kx = math.cos(lat0) * 69.0
        # offset edge endpoints outward
        def off(p):
            return (p[0] + ny * miles / 69.0, p[1] + nx * miles / kx)
        oa, ob = off(a), off(b)
        # walk along the offset edge
        seg_mi = math.hypot((b[0] - a[0]) * 69.0, (b[1] - a[1]) * kx)
        steps = max(2, int(seg_mi / step))
        for s in range(steps + 1):
            t = s / steps
            ring.append((oa[0] + (ob[0] - oa[0]) * t, oa[1] + (ob[1] - oa[1]) * t))
        # arc around vertex b (from this edge's normal to next edge's normal)
        # approximate: sample a small circle arc centered at b
        na = vertices[(i + 2) % n]
        mex, mey = (b[0] + na[0]) / 2 - cx, (b[1] + na[1]) / 2 - cy
        e2x, e2y = na[0] - b[0], na[1] - b[1]
        e2l = math.hypot(e2x, e2y)
        n2x, n2y = -e2y / e2l, e2x / e2l
        if n2x * mex + n2y * mey < 0:
            n2x, n2y = -n2x, -n2y
        latb = math.radians(b[0])
        kxb = math.cos(latb) * 69.0
        # angles of the two outward normals (in mile-space)
        import math as _m
        a1 = _m.atan2(ny * 69.0, nx * kxb)
        a2 = _m.atan2(n2y * 69.0, n2x * kxb)
        # sweep the short way around the outside
        while a2 - a1 > _m.pi:
            a2 -= 2 * _m.pi
        while a2 - a1 < -_m.pi:
            a2 += 2 * _m.pi
        # outward sweep is the one going away from centroid; take |sweep|<=pi
        for s in range(1, 8):
            t = s / 8
            ang = a1 + (a2 - a1) * t
            ring.append((b[0] + _m.sin(ang) * miles / 69.0,
                         b[1] + _m.cos(ang) * miles / kxb))
    return ring


def main():
    recs = json.load(open(DATA))
    # keep only geocoded inside/buffer records
    recs = [r for r in recs if r.get("zone") in ("inside", "buffer")
            and r.get("lat") is not None and r.get("lon") is not None]
    for r in recs:
        r["ppa"] = round(r["price"] / r["acres"]) if r.get("price") and r.get("acres") else None

    inside = [r for r in recs if r["zone"] == "inside"]
    buffer = [r for r in recs if r["zone"] == "buffer"]

    def med(x):
        x = sorted(x)
        return x[len(x) // 2] if x else None

    prices = sorted(r["price"] for r in recs if r.get("price"))
    ppas = sorted(r["ppa"] for r in recs if r.get("ppa"))
    acres_l = sorted(r["acres"] for r in recs if r.get("acres"))
    ippa = sorted(r["ppa"] for r in inside if r.get("ppa"))
    bppa = sorted(r["ppa"] for r in buffer if r.get("ppa"))

    def fmt(n):
        return "—" if n is None else f"${n:,.0f}"

    def fmt_ac(n):
        return "—" if n is None else f"{n:,.1f}"

    # ---- $/acre histogram (log buckets) ----
    buckets = [0] * 13
    edges = [250, 500, 1000, 2000, 4000, 8000, 16000, 32000, 64000, 128000, 256000, 512000]
    labels = ["<$250", "$250–500", "$500–1k", "$1k–2k", "$2k–4k", "$4k–8k",
              "$8k–16k", "$16k–32k", "$32k–64k", "$64k–128k", "$128k–256k",
              "$256k–512k", ">$512k"]
    for v in ppas:
        b = sum(1 for e in edges if v >= e)
        buckets[min(b, 12)] += 1
    bmax = max(buckets) if buckets else 1
    W, H, PAD = 760, 190, 34
    bw = (W - PAD * 2) / 13
    svg_bars = []
    for i, b in enumerate(buckets):
        h = (H - PAD - 26) * b / bmax if bmax else 0
        x = PAD + i * bw + 2
        y = H - 26 - h
        svg_bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw-4:.1f}" height="{h:.1f}" '
            f'fill="#23406b" opacity="0.85">'
            f'<title>{labels[i]}: {b} parcels</title></rect>'
            f'<text x="{x + (bw-4)/2:.1f}" y="{H-12}" font-size="8.5" text-anchor="middle" '
            f'fill="#666">{labels[i]}</text>'
            + (f'<text x="{x + (bw-4)/2:.1f}" y="{y-4:.1f}" font-size="8.5" '
                f'text-anchor="middle" fill="#333">{b}</text>' if b else ''))
    hist_svg = (
        f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Price per acre distribution">'
        f'<line x1="{PAD}" y1="{H-26}" x2="{W-PAD}" y2="{H-26}" stroke="#999"/>'
        + "".join(svg_bars) + "</svg>")

    counties = sorted(set(r["county"] for r in recs if r.get("county")))
    cities = sorted(set(r["city"] for r in recs if r.get("city")))

    # compact records for the browser
    slim = [{
        "t": r.get("title"), "p": r.get("price"), "a": r.get("acres"), "g": r.get("ppa"),
        "la": round(r["lat"], 5), "lo": round(r["lon"], 5),
        "c": r.get("city"), "k": r.get("county"), "u": r.get("url"),
        "z": r.get("zone"), "d": r.get("dist_tri_mi"), "lc": r.get("loc", "parcel"),
    } for r in recs]
    data_json = json.dumps(slim, separators=(",", ":"))
    data_blob = base64.b64encode(gzip.compress(data_json.encode())).decode()

    tri_json = json.dumps([[v[0], v[1]] for v in V])
    ring = buffer_ring(V, BUFFER_MI)
    ring_json = json.dumps([[round(p[0], 4), round(p[1], 4)] for p in ring])

    def opt(v):
        return f'<option value="{html.escape(v)}">{html.escape(v)}</option>'

    approx_n = sum(1 for r in recs if r.get("loc") != "parcel")

    # Inline Leaflet + markercluster so the page works in sandboxed file viewers
    # that block external CDN requests (only map tiles still need network).
    _adir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
    _css = (open(os.path.join(_adir, "leaflet.css")).read()
            + open(os.path.join(_adir, "markercluster.css")).read()
            + open(os.path.join(_adir, "markercluster-default.css")).read())
    _js1 = open(os.path.join(_adir, "leaflet.js")).read()
    _js2 = open(os.path.join(_adir, "markercluster.js")).read()

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Texas Triangle Land — 5+ Acres · {len(recs):,} Parcels</title>
<style>
{_css}
</style>
<style>
  :root {{ --ink:#1a1a1a; --muted:#5c5c5c; --hair:#e3e0d8; --paper:#fbfaf7;
           --navy:#23406b; --accent:#b4552d; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--paper); color:var(--ink);
         font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         font-variant-numeric:tabular-nums; }}
  .wrap {{ max-width:1180px; margin:0 auto; padding:28px 22px 60px; }}
  h1 {{ font-family:Georgia,"Times New Roman",serif; font-weight:400; font-size:34px; margin:0 0 6px; }}
  .sub {{ color:var(--muted); font-size:14px; margin:0 0 4px; }}
  .caveat {{ font-size:12.5px; color:var(--muted); border-top:1px solid var(--hair);
             border-bottom:1px solid var(--hair); padding:10px 0; margin:16px 0 22px; line-height:1.55; }}
  .stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:0; border:1px solid var(--hair);
            background:#fff; margin-bottom:22px; }}
  .stat {{ padding:16px 18px; border-left:1px solid var(--hair); }}
  .stat:first-child {{ border-left:none; }}
  .stat .k {{ font-size:11px; text-transform:uppercase; letter-spacing:1.2px; color:var(--muted); margin-bottom:6px; }}
  .stat .v {{ font-family:Georgia,serif; font-size:26px; }}
  .stat .d {{ font-size:12px; color:var(--muted); margin-top:4px; }}
  h2 {{ font-family:Georgia,serif; font-weight:400; font-size:21px; margin:30px 0 10px; }}
  #map {{ height:520px; border:1px solid var(--hair); background:#eef0ee; }}
  .mapnote {{ font-size:12px; color:var(--muted); margin-top:6px; }}
  .legend {{ display:flex; gap:18px; font-size:12.5px; color:var(--muted); margin-top:8px; flex-wrap:wrap; }}
  .dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; vertical-align:baseline; }}
  .hist {{ border:1px solid var(--hair); background:#fff; padding:14px 14px 6px; }}
  .filters {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px 14px; border:1px solid var(--hair);
              background:#fff; padding:16px; margin-bottom:6px; }}
  .filters label {{ font-size:11px; text-transform:uppercase; letter-spacing:1px; color:var(--muted);
              display:block; margin-bottom:5px; }}
  .filters input, .filters select {{ width:100%; padding:8px 9px; font-size:13.5px; border:1px solid #cfcabf;
              border-radius:2px; background:#fff; font-variant-numeric:tabular-nums; }}
  .frow2 {{ display:flex; gap:10px; align-items:center; margin:12px 0; flex-wrap:wrap; }}
  .btn {{ padding:9px 16px; font-size:13px; border:1px solid var(--navy); background:var(--navy); color:#fff;
          border-radius:2px; cursor:pointer; }}
  .btn.ghost {{ background:#fff; color:var(--navy); }}
  #count {{ font-size:13px; color:var(--muted); }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--hair); font-size:13px; }}
  th {{ text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:1px; color:var(--muted);
       padding:11px 10px; border-bottom:2px solid var(--hair); cursor:pointer; white-space:nowrap; user-select:none; }}
  th .arr {{ color:var(--navy); }}
  td {{ padding:9px 10px; border-bottom:1px solid var(--hair); vertical-align:top; }}
  tr:hover td {{ background:#f4f2ec; }}
  td.num, th.num {{ text-align:right; white-space:nowrap; }}
  a {{ color:var(--navy); text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  .zone-in {{ color:var(--navy); font-weight:600; }}
  .zone-buf {{ color:var(--accent); font-weight:600; }}
  .foot {{ margin-top:34px; padding-top:14px; border-top:1px solid var(--hair); font-size:12.5px;
           color:var(--muted); line-height:1.6; }}
  @media (max-width:760px) {{ .stats {{ grid-template-columns:repeat(2,1fr); }}
    .filters {{ grid-template-columns:repeat(2,1fr); }} }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Texas Triangle Land &mdash; 5+ Acres</h1>
  <p class="sub">{len(recs):,} for-sale parcels &middot; Realtor.com snapshot, October 2026 &middot;
  {len(inside):,} inside the triangle, {len(buffer):,} in the 50-mile ring</p>
  <div class="caveat"><b>Coverage.</b> Pulled from Realtor.com county land searches (Land, 5+ acre lot filter)
  across 86 Texas counties in/around the triangle; figures are the listings captured, not a certified census
  &mdash; the site rate-limited automated access during collection and some result pages rendered partial card
  sets. <b>Locations.</b> Parcel coordinates come from batch-geocoding listing addresses; rural parcels listed
  without a street address ("TBD", county roads) are plotted at their city center and marked ~approx
  ({approx_n} of {len(recs):,}). Zone classification (inside vs 50-mile ring) uses the geocoded point.
  <b>Triangle.</b> Vertices at Dallas (32.78,&thinsp;-96.80), San Antonio (29.42,&thinsp;-98.49),
  Houston (29.76,&thinsp;-95.37); the ring is 50 statute miles from the triangle edges.</div>

  <div class="stats">
    <div class="stat"><div class="k">Parcels</div><div class="v">{len(recs):,}</div>
      <div class="d">{len(inside):,} inside &middot; {len(buffer):,} in ring</div></div>
    <div class="stat"><div class="k">Median price</div><div class="v">{fmt(med(prices))}</div>
      <div class="d">range {fmt(prices[0]) if prices else "—"}&ndash;{fmt(prices[-1]) if prices else "—"}</div></div>
    <div class="stat"><div class="k">Median $/acre</div><div class="v">{fmt(med(ppas))}</div>
      <div class="d">inside {fmt(med(ippa))} &middot; ring {fmt(med(bppa))}</div></div>
    <div class="stat"><div class="k">Median acres</div><div class="v">{fmt_ac(med(acres_l))}</div>
      <div class="d">minimum 5.0 by filter</div></div>
  </div>

  <h2>Parcel map</h2>
  <div id="map"></div>
  <div class="legend">
    <span><span class="dot" style="background:#23406b"></span>Inside triangle</span>
    <span><span class="dot" style="background:#b4552d"></span>50-mile ring</span>
    <span><span style="display:inline-block;width:22px;border-top:2px dashed #23406b;vertical-align:middle"></span> Triangle</span>
    <span><span style="display:inline-block;width:22px;border-top:2px dashed #999;vertical-align:middle"></span> 50-mile boundary</span>
  </div>
  <p class="mapnote">Markers cluster at wide zoom; click to expand, click a parcel for details and the listing link.
  ~approx markers sit at the city center (no street address published).</p>

  <h2>Price per acre distribution</h2>
  <div class="hist">{hist_svg}</div>

  <h2>Parcels</h2>
  <div class="filters">
    <div><label>Search</label><input id="f_q" type="text" placeholder="title, city, county&hellip;"></div>
    <div><label>Zone</label><select id="f_zone">
      <option value="">Inside + ring</option><option value="inside">Inside triangle only</option>
      <option value="buffer">50-mile ring only</option></select></div>
    <div><label>County</label><select id="f_county"><option value="">All counties</option>
      {"".join(opt(c) for c in counties)}</select></div>
    <div><label>City</label><select id="f_city"><option value="">All cities</option>
      {"".join(opt(c) for c in cities)}</select></div>
    <div><label>Min price</label><input id="f_pmin" type="number" min="0" placeholder="0"></div>
    <div><label>Max price</label><input id="f_pmax" type="number" min="0" placeholder="no max"></div>
    <div><label>Min acres</label><input id="f_amin" type="number" min="0" step="0.1" placeholder="5"></div>
    <div><label>Max $/acre</label><input id="f_ppa" type="number" min="0" placeholder="no max"></div>
  </div>
  <div class="frow2">
    <button class="btn" id="dl">Download filtered CSV</button>
    <button class="btn ghost" id="reset">Reset</button>
    <span id="count"></span>
  </div>
  <table>
    <thead><tr>
      <th data-k="t">Parcel <span class="arr"></span></th>
      <th data-k="p" class="num">Price <span class="arr"></span></th>
      <th data-k="a" class="num">Acres <span class="arr"></span></th>
      <th data-k="g" class="num">$/acre <span class="arr"></span></th>
      <th data-k="c">City <span class="arr"></span></th>
      <th data-k="k">County <span class="arr"></span></th>
      <th data-k="z">Zone <span class="arr"></span></th>
      <th data-k="d" class="num">Mi to triangle <span class="arr"></span></th>
    </tr></thead>
    <tbody id="rows"></tbody>
  </table>

  <div class="foot">
    Source: Realtor.com county searches (Texas, Land, 5+ acre lot filter, for sale), October 2026.
    Values reproduced from listing cards; blank where the card showed nothing. Coordinates via
    OpenStreetMap/Nominatim geocoding of listing addresses; ~approx rows use the street or city center.
    Triangle vertices: Dallas (32.7767,&thinsp;-96.7970), San Antonio (29.4241,&thinsp;-98.4936),
    Houston (29.7604,&thinsp;-95.3698); ring = 50 statute miles from triangle edges.
  </div>
</div>

<script>
{_js1}
</script>
<script>
{_js2}
</script>
<script>
const DATA_BLOB = "{data_blob}";
const TRI = {tri_json};
const RING = {ring_json};
let DATA = [];
const $ = id => document.getElementById(id);
const money = n => n == null ? "\\u2014" : "$" + Math.round(n).toLocaleString("en-US");
const ac = n => n == null ? "\\u2014" : Number(n.toFixed(1)).toLocaleString("en-US");
const esc = s => String(s == null ? "" : s).replace(/&/g,"&amp;").replace(/</g,"&lt;")
  .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
const zoneName = z => z === "inside" ? "Inside" : "Ring";

async function boot() {{
try {{
  const bin = Uint8Array.from(atob(DATA_BLOB), c => c.charCodeAt(0));
  const ds = new DecompressionStream("gzip");
  const w = ds.writable.getWriter();
  await w.write(bin); await w.close();
  DATA = JSON.parse(await new Response(ds.readable).text());
}} catch (e) {{
  document.querySelector(".wrap").insertAdjacentHTML("afterbegin",
    '<p style="color:#900;padding:12px">Parcel data could not be decoded in this browser.</p>');
  return;
}}

/* ---------- map ---------- */
try {{
  const map = L.map("map").setView([30.9, -96.9], 7);
  const osm = L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",
    {{ maxZoom: 14, attribution: "&copy; OpenStreetMap contributors" }});
  const carto = L.tileLayer("https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png",
    {{ maxZoom: 19, attribution: "&copy; OpenStreetMap contributors &copy; CARTO" }});
  osm.addTo(map);
  /* if the primary tile host is blocked, fail over to CARTO once */
  osm.on("tileerror", () => {{
    if (map.hasLayer(osm)) {{ map.removeLayer(osm); carto.addTo(map); }}
  }});
  L.polygon(RING.map(p => [p[0], p[1]]), {{ color:"#999", weight:1.5, dashArray:"6 6",
    fill:false }}).addTo(map);
  L.polygon(TRI.map(p => [p[0], p[1]]), {{ color:"#23406b", weight:2.5, dashArray:"8 6",
    fillColor:"#23406b", fillOpacity:0.06 }}).addTo(map);
  const clusters = L.markerClusterGroup({{ maxClusterRadius: 46, disableClusteringAtZoom: 12 }});
  const dot = z => L.divIcon({{ className:"", html:
    '<div style="width:11px;height:11px;border-radius:50%;background:' +
    (z === "inside" ? "#23406b" : "#b4552d") +
    ';border:1.5px solid #fff;box-shadow:0 0 2px rgba(0,0,0,.5)"></div>',
    iconSize:[11,11], iconAnchor:[5,5] }});
  for (const r of DATA) {{
    const m = L.marker([r.la, r.lo], {{ icon: dot(r.z) }});
    m.bindPopup("<b>" + esc(r.t) + "</b>" + (r.lc !== "parcel" ? " ~approx" : "") +
      "<br>" + money(r.p) + " &middot; " + ac(r.a) + " ac &middot; " + money(r.g) + "/ac" +
      "<br>" + esc(r.c || "") + (r.k ? ", " + esc(r.k) + " Co" : "") +
      " &middot; " + zoneName(r.z) +
      (r.u ? '<br><a href="' + esc(r.u) + '">View listing</a>' : ""));
    clusters.addLayer(m);
  }}
  map.addLayer(clusters);
  map.fitBounds(L.polygon(RING.map(p => [p[0], p[1]])).getBounds().pad(0.04));
}} catch (err) {{
  $("map").innerHTML =
    '<p style="padding:40px;color:#666">Map unavailable offline &mdash; the table below works fully.</p>';
}}

/* ---------- table ---------- */
let sortK = "p", sortDir = -1;
const ths = document.querySelectorAll("th[data-k]");
function paintArrows() {{
  ths.forEach(th => th.querySelector(".arr").textContent =
    th.dataset.k === sortK ? (sortDir === 1 ? "\\u25b2" : "\\u25bc") : "");
}}
ths.forEach(th => th.addEventListener("click", () => {{
  const k = th.dataset.k;
  if (sortK === k) sortDir *= -1;
  else {{ sortK = k; sortDir = (k === "t" || k === "c" || k === "k" || k === "z") ? 1 : -1; }}
  apply();
}}));

function filtered() {{
  const q = $("f_q").value.trim().toLowerCase(),
        zn = $("f_zone").value, ky = $("f_county").value, ct = $("f_city").value,
        pmin = parseFloat($("f_pmin").value) || 0, pmax = parseFloat($("f_pmax").value) || Infinity,
        amin = parseFloat($("f_amin").value) || 0, ppamax = parseFloat($("f_ppa").value) || Infinity;
  return DATA.filter(r =>
    (!q || ((r.t||"") + " " + (r.c||"") + " " + (r.k||"")).toLowerCase().includes(q)) &&
    (!zn || r.z === zn) && (!ky || r.k === ky) && (!ct || r.c === ct) &&
    (r.p == null || (r.p >= pmin && r.p <= pmax)) &&
    (r.a == null || r.a >= amin) &&
    (r.g == null || r.g <= ppamax));
}}
function cmp(a, b) {{
  let x = a[sortK], y = b[sortK];
  if (x == null) return 1; if (y == null) return -1;
  return (x < y ? -1 : x > y ? 1 : 0) * sortDir;
}}
function apply() {{
  const rows = filtered().sort(cmp);
  const shown = rows.slice(0, 1500);
  $("count").textContent = rows.length.toLocaleString() + " of " + DATA.length.toLocaleString() +
    " parcels" + (rows.length > 1500 ? " (first 1,500 shown — refine filters)" : "");
  $("rows").innerHTML = shown.map(r =>
    "<tr><td>" + (r.u ? '<a href="' + esc(r.u) + '">' + esc(r.t) + "</a>"
                       : esc(r.t)) + (r.lc !== "parcel" ? " ~approx" : "") + "</td>" +
    '<td class="num">' + money(r.p) + "</td>" +
    '<td class="num">' + ac(r.a) + "</td>" +
    '<td class="num">' + money(r.g) + "</td>" +
    "<td>" + esc(r.c) + "</td><td>" + esc(r.k) + "</td>" +
    '<td class="' + (r.z === "inside" ? "zone-in" : "zone-buf") + '">' + zoneName(r.z) + "</td>" +
    '<td class="num">' + (r.d == null ? "—" : r.d.toFixed(0)) + "</td></tr>").join("");
  paintArrows();
}}
["f_q","f_zone","f_county","f_city","f_pmin","f_pmax","f_amin","f_ppa"].forEach(id =>
  $(id).addEventListener("input", apply));
$("reset").addEventListener("click", () => {{
  ["f_q","f_pmin","f_pmax","f_amin","f_ppa"].forEach(id => $(id).value = "");
  ["f_zone","f_county","f_city"].forEach(id => $(id).value = "");
  apply();
}});
$("dl").addEventListener("click", () => {{
  const rows = filtered().sort(cmp);
  const q = s => '"' + String(s == null ? "" : s).replace(/"/g, '""') + '"';
  const csv = "title,price_usd,acres,price_per_acre,lat,lon,city,county,zone,mi_to_triangle,url\\n" +
    rows.map(r => [q(r.t), r.p ?? "", r.a ?? "", r.g ?? "", r.la ?? "", r.lo ?? "",
      q(r.c), q(r.k), r.z, r.d ?? "", q(r.u)].join(",")).join("\\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], {{type:"text/csv"}}));
  a.download = "texas-triangle-land-filtered.csv"; a.click();
}});
paintArrows(); apply();
}}
boot();
</script>
</body>
</html>
"""
    open(OUT, "w").write(page)
    print("wrote", OUT, f"{len(page)/1024:.0f} KB | parcels:", len(recs))


if __name__ == "__main__":
    main()
