#!/usr/bin/env python3
"""Step 3: data/listings.json -> texas-triangle-land.html (interactive map + analysis).

Self-contained page: stat strip, Leaflet map (clustered parcel markers, triangle + 50mi ring
overlays), $/acre histogram, filterable/sortable table, CSV export. Leaflet is inlined from
vendor/ so only the map tiles need network.
"""
import json, html, math, gzip, base64, os, datetime

from geo import V, BUFFER_MI

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "listings.json")
COUNTIES = os.path.join(HERE, "data", "counties_target.json")
OUT = os.path.join(HERE, "texas-triangle-land.html")


def buffer_ring(vertices, miles, n=120):
    """Ring `miles` outside a convex polygon = convex hull of circles around its vertices.

    Circles are drawn in miles at each vertex's latitude; the hull is taken in lat/lon,
    which is fine because convex hulls survive the (affine) degrees<->miles scaling.
    """
    pts = []
    for lat, lon in vertices:
        kx = math.cos(math.radians(lat)) * 69.0
        for i in range(n):
            a = 2 * math.pi * i / n
            pts.append((lat + math.sin(a) * miles / 69.0, lon + math.cos(a) * miles / kx))
    pts = sorted(set(pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def main():
    doc = json.load(open(DATA))
    snapshot, recs = doc["snapshot"], doc["listings"]
    snap_label = datetime.date.fromisoformat(snapshot).strftime("%B %-d, %Y")
    n_counties = len(json.load(open(COUNTIES)))
    # keep only geocoded inside/buffer records
    recs = [r for r in recs if r.get("zone") in ("inside", "buffer")
            and r.get("lat") is not None and r.get("lon") is not None]
    inside_n = sum(1 for r in recs if r["zone"] == "inside")
    approx_n = sum(1 for r in recs if r.get("loc") != "parcel")
    first_run = min((r.get("first_seen") or snapshot for r in recs), default=snapshot) == snapshot
    new_n = 0 if first_run else sum(1 for r in recs if r.get("first_seen") == snapshot)

    # compact records for the browser
    slim = [{
        "t": r.get("title"), "p": r.get("price"), "a": r.get("acres"),
        "g": round(r["price"] / r["acres"]) if r.get("price") and r.get("acres") else None,
        "la": round(r["lat"], 5), "lo": round(r["lon"], 5),
        "c": r.get("city"), "k": r.get("county"), "u": r.get("url"),
        "z": r.get("zone"), "d": r.get("dist_tri_mi"), "lc": r.get("loc", "parcel"),
        "f": r.get("first_seen"), "pp": r.get("prev_price"), "ld": r.get("list_date"),
        "ty": r.get("type") or "Land",
    } for r in recs]
    data_blob = base64.b64encode(
        gzip.compress(json.dumps(slim, separators=(",", ":")).encode())).decode()

    counties = sorted(set(r["county"] for r in recs if r.get("county")))
    types = sorted(set(r.get("type") or "Land" for r in recs))
    ring = buffer_ring(V, BUFFER_MI)

    # Leaflet + markercluster are inlined so the page works offline / in sandboxed viewers
    # (only map tiles need network).
    vdir = os.path.join(HERE, "vendor")
    vendor = lambda f: open(os.path.join(vdir, f)).read()

    subs = {
        "__TOTAL__": f"{len(recs):,}",
        "__INSIDE__": f"{inside_n:,}",
        "__RINGN__": f"{len(recs) - inside_n:,}",
        "__APPROX__": f"{approx_n:,}",
        "__NCOUNTIES__": str(n_counties),
        "__SNAPLABEL__": snap_label,
        "__NEWN__": f"{new_n:,}",
        "__COUNTY_OPTS__": "".join(f'<option value="{html.escape(c)}">{html.escape(c)}</option>'
                                   for c in counties),
        "__TYPE_OPTS__": "".join(f'<option value="{html.escape(t)}">{html.escape(t)}</option>'
                                 for t in types),
        "__SNAPSHOT__": snapshot,
        "__TRI__": json.dumps([[v[0], v[1]] for v in V]),
        "__RING__": json.dumps([[round(p[0], 4), round(p[1], 4)] for p in ring]),
        "__DATA_BLOB__": data_blob,
        # vendor code last so nothing inside it gets substituted
        "__VENDOR_CSS__": vendor("leaflet.css") + vendor("markercluster.css")
                          + vendor("markercluster-default.css"),
        "__VENDOR_JS__": vendor("leaflet.js") + "\n</script>\n<script>\n" + vendor("markercluster.js"),
    }
    page = TEMPLATE
    for k, v in subs.items():
        page = page.replace(k, v)
    open(OUT, "w").write(page)
    print("wrote", os.path.relpath(OUT, HERE), f"{len(page)/1024:.0f} KB | parcels:", len(recs))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Texas Triangle Land</title>
<style>
__VENDOR_CSS__
</style>
<style>
  :root { --ink:#1a1a1a; --muted:#5c5c5c; --hair:#e3e0d8; --paper:#fbfaf7;
          --navy:#23406b; --accent:#b4552d; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--paper); color:var(--ink);
         font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         font-variant-numeric:tabular-nums; }
  .wrap { max-width:1180px; margin:0 auto; padding:28px 22px 60px; }
  h1 { font-family:Georgia,"Times New Roman",serif; font-weight:400; font-size:34px; margin:0 0 6px; }
  .sub { color:var(--muted); font-size:14px; margin:0 0 4px; }
  .caveat { font-size:12.5px; color:var(--muted); border-top:1px solid var(--hair);
            border-bottom:1px solid var(--hair); padding:10px 0; margin:16px 0 18px; line-height:1.55; }
  .caveat summary { cursor:pointer; color:var(--ink); }

  /* filter bar: sticks to the top so it stays reachable while looking at map / table */
  .fbar { position:sticky; top:0; z-index:1100; background:var(--paper); padding:10px 0 8px;
          border-bottom:1px solid var(--hair); margin-bottom:16px; }
  .filters { display:grid; grid-template-columns:2fr repeat(4,1.1fr); gap:8px 12px; }
  .ranges { display:grid; grid-template-columns:repeat(3,1fr); gap:8px 12px; margin-top:8px; }
  .fbar label { font-size:10.5px; text-transform:uppercase; letter-spacing:1px; color:var(--muted);
                display:block; margin-bottom:4px; }
  .fbar input[type=text], .fbar input[type=number], .fbar select { width:100%; padding:7px 8px;
                font-size:13.5px; border:1px solid #cfcabf; border-radius:2px; background:#fff;
                font-variant-numeric:tabular-nums; }
  .pair { display:flex; gap:6px; align-items:center; }
  .pair span { color:var(--muted); font-size:12px; }
  .frow2 { display:flex; gap:10px; align-items:center; margin-top:10px; flex-wrap:wrap; }
  .btn { padding:7px 14px; font-size:13px; border:1px solid var(--navy); background:var(--navy); color:#fff;
         border-radius:2px; cursor:pointer; }
  .btn.ghost { background:#fff; color:var(--navy); }
  .fbar label.chk { font-size:13px; color:var(--muted); display:flex; gap:6px; align-items:center;
                    text-transform:none; letter-spacing:0; margin:0; cursor:pointer; }
  #count { font-size:13px; color:var(--ink); margin-left:auto; }
  #count b { font-weight:600; }

  .stats { display:grid; grid-template-columns:repeat(4,1fr); border:1px solid var(--hair);
           background:#fff; margin-bottom:18px; }
  .stat { padding:14px 18px; border-left:1px solid var(--hair); }
  .stat:first-child { border-left:none; }
  .stat .k { font-size:11px; text-transform:uppercase; letter-spacing:1.2px; color:var(--muted); margin-bottom:6px; }
  .stat .v { font-family:Georgia,serif; font-size:26px; }
  .stat .d { font-size:12px; color:var(--muted); margin-top:4px; }
  h2 { font-family:Georgia,serif; font-weight:400; font-size:21px; margin:26px 0 10px; }
  #map { height:560px; border:1px solid var(--hair); background:#eef0ee; }
  .mapnote { font-size:12px; color:var(--muted); margin-top:6px; }
  .legend { display:flex; gap:18px; font-size:12.5px; color:var(--muted); margin-top:8px; flex-wrap:wrap; }
  .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; vertical-align:baseline; }
  .hist { border:1px solid var(--hair); background:#fff; padding:14px 14px 6px; }
  .hist rect.bar { cursor:pointer; }
  .hist rect.bar:hover { opacity:1; }
  .hnote { font-size:12px; color:var(--muted); margin-top:6px; }
  .tag { font-size:10.5px; letter-spacing:.5px; text-transform:uppercase; color:var(--accent); margin-left:6px; }
  table { width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--hair); font-size:13px; }
  th { text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:1px; color:var(--muted);
       padding:11px 10px; border-bottom:2px solid var(--hair); cursor:pointer; white-space:nowrap; user-select:none; }
  th .arr { color:var(--navy); }
  td { padding:9px 10px; border-bottom:1px solid var(--hair); vertical-align:top; }
  tbody tr:hover td { background:#f4f2ec; }
  td.num, th.num { text-align:right; white-space:nowrap; }
  a { color:var(--navy); text-decoration:none; }
  a:hover { text-decoration:underline; }
  .zone-in { color:var(--navy); font-weight:600; }
  .zone-buf { color:var(--accent); font-weight:600; }
  .more { font-size:13px; color:var(--muted); padding:10px 0; }
  .foot { margin-top:34px; padding-top:14px; border-top:1px solid var(--hair); font-size:12.5px;
          color:var(--muted); line-height:1.6; }
  @media (max-width:760px) {
    .fbar { position:static; }
    .stats { grid-template-columns:repeat(2,1fr); }
    .stat:nth-child(3) { border-left:none; }
    .filters, .ranges { grid-template-columns:1fr 1fr; }
    #map { height:420px; }
    .tablewrap { overflow-x:auto; }
  }
</style>
</head>
<body>
<div class="wrap">
  <h1>Texas Triangle Property &mdash; 5+ Acres</h1>
  <p class="sub">__TOTAL__ for-sale parcels &middot; Realtor.com snapshot, __SNAPLABEL__ &middot;
  __INSIDE__ inside the triangle, __RINGN__ in the 50-mile ring</p>
  <details class="caveat"><summary>About this data</summary>
  <b>Coverage.</b> Every Realtor.com for-sale listing with a lot of 5+ acres (land, farm/ranch, houses on acreage, mobile, multi-family; condo/townhome units excluded because they report the shared complex lot), searched
  county by county across the __NCOUNTIES__ Texas counties that touch the triangle or its 50-mile ring; pending and
  contingent listings excluded. Only Realtor.com is covered, so listings exclusive to other land sites are missing.
  <b>Locations.</b> Coordinates are Realtor.com's own; listings Realtor.com publishes without coordinates are
  geocoded to their street, ZIP or city center and marked ~approx (__APPROX__ of __TOTAL__).
  Zone classification (inside vs 50-mile ring) uses that point.
  <b>Triangle.</b> Vertices at Dallas (32.78,&thinsp;-96.80), San Antonio (29.42,&thinsp;-98.49),
  Houston (29.76,&thinsp;-95.37); the ring is 50 statute miles from the triangle edges.</details>

  <div class="fbar">
    <div class="filters">
      <div><label for="f_q">Search</label><input id="f_q" type="text" placeholder="address, road, city, county&hellip;"></div>
      <div><label for="f_type">Type</label><select id="f_type"><option value="">All types</option>
        __TYPE_OPTS__</select></div>
      <div><label for="f_zone">Zone</label><select id="f_zone">
        <option value="">Inside + ring</option><option value="inside">Inside triangle only</option>
        <option value="buffer">50-mile ring only</option></select></div>
      <div><label for="f_county">County</label><select id="f_county"><option value="">All counties</option>
        __COUNTY_OPTS__</select></div>
      <div><label for="f_city">City</label><select id="f_city"><option value="">All cities</option></select></div>
    </div>
    <div class="ranges">
      <div><label>Price ($)</label><div class="pair">
        <input id="f_pmin" type="number" min="0" step="10000" placeholder="min"><span>&ndash;</span>
        <input id="f_pmax" type="number" min="0" step="10000" placeholder="max"></div></div>
      <div><label>Acres</label><div class="pair">
        <input id="f_amin" type="number" min="0" step="1" placeholder="5"><span>&ndash;</span>
        <input id="f_amax" type="number" min="0" step="1" placeholder="max"></div></div>
      <div><label>$ per acre</label><div class="pair">
        <input id="f_gmin" type="number" min="0" step="1000" placeholder="min"><span>&ndash;</span>
        <input id="f_gmax" type="number" min="0" step="1000" placeholder="max"></div></div>
    </div>
    <div class="frow2">
      <label class="chk"><input id="f_exact" type="checkbox"> Exact locations only</label>
      <label class="chk"><input id="f_new" type="checkbox"> New since previous run (__NEWN__)</label>
      <button class="btn ghost" id="reset">Reset filters</button>
      <button class="btn ghost" id="zoom">Zoom map to results</button>
      <button class="btn" id="dl">Download CSV</button>
      <span id="count"></span>
    </div>
  </div>

  <div class="stats">
    <div class="stat"><div class="k">Parcels</div><div class="v" id="s_n">&mdash;</div><div class="d" id="s_nd"></div></div>
    <div class="stat"><div class="k">Median price</div><div class="v" id="s_p">&mdash;</div><div class="d" id="s_pd"></div></div>
    <div class="stat"><div class="k">Median $/acre</div><div class="v" id="s_g">&mdash;</div><div class="d" id="s_gd"></div></div>
    <div class="stat"><div class="k">Median acres</div><div class="v" id="s_a">&mdash;</div><div class="d" id="s_ad"></div></div>
  </div>

  <h2>Parcel map</h2>
  <div id="map"></div>
  <div class="legend">
    <span><span class="dot" style="background:#23406b"></span>Inside triangle</span>
    <span><span class="dot" style="background:#b4552d"></span>50-mile ring</span>
    <span><span style="display:inline-block;width:22px;border-top:2px dashed #23406b;vertical-align:middle"></span> Triangle</span>
    <span><span style="display:inline-block;width:22px;border-top:2px dashed #999;vertical-align:middle"></span> 50-mile boundary</span>
  </div>
  <p class="mapnote">The map shows only parcels matching the filters. Markers cluster at wide zoom; click a cluster
  to expand, a parcel for details.
  ~approx markers sit at a street, ZIP or city center (Realtor.com published no coordinates).</p>

  <h2>Price per acre</h2>
  <div class="hist" id="hist"></div>
  <p class="hnote">Click a bar to filter to that $/acre range; click it again to clear.</p>

  <h2>Parcels</h2>
  <div class="tablewrap"><table>
    <thead><tr>
      <th data-k="t">Parcel <span class="arr"></span></th>
      <th data-k="ty">Type <span class="arr"></span></th>
      <th data-k="p" class="num">Price <span class="arr"></span></th>
      <th data-k="a" class="num">Acres <span class="arr"></span></th>
      <th data-k="g" class="num">$/acre <span class="arr"></span></th>
      <th data-k="c">City <span class="arr"></span></th>
      <th data-k="k">County <span class="arr"></span></th>
      <th data-k="z">Zone <span class="arr"></span></th>
      <th data-k="d" class="num">Mi to triangle <span class="arr"></span></th>
    </tr></thead>
    <tbody id="rows"></tbody>
  </table></div>
  <div class="more" id="more"></div>

  <div class="foot">
    Source: Realtor.com county searches (Texas, all property types, 5+ acre lot, for sale) pulled __SNAPLABEL__ with the
    HomeHarvest library. Acres = Realtor.com lot size. Coordinates from Realtor.com; ~approx rows geocoded via
    OpenStreetMap/Nominatim to a street, ZIP or city center. Map tiles &copy; Esri.
    Triangle vertices: Dallas (32.7767,&thinsp;-96.7970), San Antonio (29.4241,&thinsp;-98.4936),
    Houston (29.7604,&thinsp;-95.3698); ring = 50 statute miles from triangle edges.
  </div>
</div>

<script>
__VENDOR_JS__
</script>
<script>
const DATA_BLOB = "__DATA_BLOB__";
const SNAPSHOT = "__SNAPSHOT__";
const TRI = __TRI__;
const RING = __RING__;
const PAGE = 500;  // table rows per "show more"

let DATA = [], FIRST = "", VIEW = [], shownN = PAGE;
let map = null, clusters = null, ringBounds = null;
let sortK = "p", sortDir = -1;
const $ = id => document.getElementById(id);
const money = n => n == null ? "—" : "$" + Math.round(n).toLocaleString("en-US");
const ac = n => n == null ? "—" : Number(n.toFixed(1)).toLocaleString("en-US");
const esc = s => String(s == null ? "" : s).replace(/&/g,"&amp;").replace(/</g,"&lt;")
  .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
const zoneName = z => z === "inside" ? "Inside" : "Ring";
const tags = r => (r.f === SNAPSHOT && r.f !== FIRST ? '<span class="tag">new</span>' : "") +
  (r.pp != null ? '<span class="tag">was ' + money(r.pp) + "</span>" : "");
const median = xs => { if (!xs.length) return null; const s = xs.slice().sort((a, b) => a - b);
  const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const num = id => { const v = parseFloat($(id).value); return isNaN(v) ? null : v; };

/* $/acre histogram buckets (log scale) */
const EDGES = [0, 250, 500, 1000, 2000, 4000, 8000, 16000, 32000, 64000, 128000, 256000, 512000, Infinity];
const BLABEL = ["<$250", "$250–500", "$500–1k", "$1k–2k", "$2k–4k", "$4k–8k", "$8k–16k",
  "$16k–32k", "$32k–64k", "$64k–128k", "$128k–256k", "$256k–512k", ">$512k"];

async function boot() {
  try {
    const bin = Uint8Array.from(atob(DATA_BLOB), c => c.charCodeAt(0));
    /* pipe (not write-then-read): a blocking write deadlocks once the data outgrows the stream buffer */
    const stream = new Blob([bin]).stream().pipeThrough(new DecompressionStream("gzip"));
    DATA = JSON.parse(await new Response(stream).text());
  } catch (e) {
    document.querySelector(".wrap").insertAdjacentHTML("afterbegin",
      '<p style="color:#900;padding:12px">Parcel data could not be decoded in this browser.</p>');
    return;
  }
  FIRST = DATA.reduce((m, r) => r.f && r.f < m ? r.f : m, SNAPSHOT);
  initMap();
  initControls();
  fillCities();
  apply({ fit: false });
}

/* ---------- map ---------- */
function popupHtml(r) {
  return "<b>" + esc(r.t) + "</b>" + (r.lc !== "parcel" ? " ~approx" : "") + tags(r) +
    "<br>" + esc(r.ty) + " &middot; " + money(r.p) + " &middot; " + ac(r.a) + " ac &middot; " + money(r.g) + "/ac" +
    "<br>" + esc(r.c || "") + (r.k ? ", " + esc(r.k) + " Co" : "") + " &middot; " + zoneName(r.z) +
    (r.u ? '<br><a href="' + esc(r.u) + '" target="_blank" rel="noopener">View listing &#8599;</a>' : "");
}
function initMap() {
  try {
    map = L.map("map", { preferCanvas: true });
    /* Esri tiles work keyless from a file:// page. OpenStreetMap and CARTO both answer such
       pages with a placeholder image ("Access blocked" / "API key required") that loads
       "successfully", so no tileerror fallback can catch it. */
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 19, attribution: "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, USGS, OpenStreetMap contributors" }).addTo(map);
    const ringPoly = L.polygon(RING, { color:"#999", weight:1.5, dashArray:"6 6", fill:false,
      interactive:false }).addTo(map);
    L.polygon(TRI, { color:"#23406b", weight:2.5, dashArray:"8 6", fillColor:"#23406b",
      fillOpacity:0.06, interactive:false }).addTo(map);
    ringBounds = ringPoly.getBounds().pad(0.04);
    map.fitBounds(ringBounds);
    clusters = L.markerClusterGroup({ maxClusterRadius: 46, disableClusteringAtZoom: 12,
      chunkedLoading: true, showCoverageOnHover: false });
    const icon = z => L.divIcon({ className:"", html:
      '<div style="width:11px;height:11px;border-radius:50%;background:' +
      (z === "inside" ? "#23406b" : "#b4552d") +
      ';border:1.5px solid #fff;box-shadow:0 0 2px rgba(0,0,0,.5)"></div>',
      iconSize:[11,11], iconAnchor:[5,5] });
    const icons = { inside: icon("inside"), buffer: icon("buffer") };
    for (const r of DATA) {
      r.m = L.marker([r.la, r.lo], { icon: icons[r.z] || icons.buffer });
      r.m.bindPopup(() => popupHtml(r));
    }
    map.addLayer(clusters);
  } catch (err) {
    map = null;
    $("map").innerHTML =
      '<p style="padding:40px;color:#666">Map unavailable &mdash; the filters and table still work.</p>';
  }
}
function drawMap(rows, fit) {
  if (!map) return;
  clusters.clearLayers();
  clusters.addLayers(rows.map(r => r.m));
  if (fit) zoomToResults(rows);
}
function zoomToResults(rows) {
  if (!map) return;
  rows = rows || VIEW;
  if (!rows.length || rows.length === DATA.length) { map.fitBounds(ringBounds); return; }
  const b = L.latLngBounds(rows.map(r => [r.la, r.lo]));
  map.fitBounds(b.pad(0.08), { maxZoom: 13 });
}
/* ---------- filters ---------- */
function filters() {
  return {
    q: $("f_q").value.trim().toLowerCase(), zone: $("f_zone").value, type: $("f_type").value,
    county: $("f_county").value, city: $("f_city").value,
    pmin: num("f_pmin"), pmax: num("f_pmax"), amin: num("f_amin"), amax: num("f_amax"),
    gmin: num("f_gmin"), gmax: num("f_gmax"),
    exact: $("f_exact").checked, onlyNew: $("f_new").checked,
  };
}
/* a row with no value never passes a range filter that is set */
const inRange = (v, lo, hi) => (lo == null || (v != null && v >= lo)) && (hi == null || (v != null && v <= hi));
function matches(r, f) {
  return (!f.q || ((r.t || "") + " " + (r.c || "") + " " + (r.k || "")).toLowerCase().includes(f.q)) &&
    (!f.zone || r.z === f.zone) && (!f.type || r.ty === f.type) && (!f.county || r.k === f.county) && (!f.city || r.c === f.city) &&
    inRange(r.p, f.pmin, f.pmax) && inRange(r.a, f.amin, f.amax) && inRange(r.g, f.gmin, f.gmax) &&
    (!f.exact || r.lc === "parcel") && (!f.onlyNew || (r.f === SNAPSHOT && r.f !== FIRST));
}
function cmp(a, b) {
  const x = a[sortK], y = b[sortK];
  if (x == null && y == null) return 0;
  if (x == null) return 1;
  if (y == null) return -1;
  return (x < y ? -1 : x > y ? 1 : 0) * sortDir;
}
function fillCities() {
  const county = $("f_county").value, cur = $("f_city").value;
  const cities = [...new Set(DATA.filter(r => r.c && (!county || r.k === county)).map(r => r.c))].sort();
  $("f_city").innerHTML = '<option value="">All cities' + (county ? " in " + esc(county) : "") + "</option>" +
    cities.map(c => '<option value="' + esc(c) + '">' + esc(c) + "</option>").join("");
  if (cities.includes(cur)) $("f_city").value = cur;
}

function apply(opts) {
  const f = filters();
  VIEW = DATA.filter(r => matches(r, f)).sort(cmp);
  shownN = PAGE;
  drawMap(VIEW, opts && opts.fit);
  drawStats(VIEW);
  drawHist(VIEW, f);
  drawTable();
  const n = VIEW.length;
  $("count").innerHTML = n === DATA.length ? "All <b>" + n.toLocaleString() + "</b> parcels"
    : "<b>" + n.toLocaleString() + "</b> of " + DATA.length.toLocaleString() + " parcels match";
}

/* ---------- stats ---------- */
function drawStats(rows) {
  const ins = rows.filter(r => r.z === "inside"), rng = rows.filter(r => r.z !== "inside");
  const vals = (rs, k) => rs.map(r => r[k]).filter(v => v != null);
  const prices = vals(rows, "p");
  $("s_n").textContent = rows.length.toLocaleString();
  $("s_nd").textContent = ins.length.toLocaleString() + " inside · " + rng.length.toLocaleString() + " in ring";
  $("s_p").textContent = money(median(prices));
  $("s_pd").textContent = prices.length ? "range " + money(Math.min(...prices)) + "–" + money(Math.max(...prices)) : "";
  $("s_g").textContent = money(median(vals(rows, "g")));
  $("s_gd").textContent = "inside " + money(median(vals(ins, "g"))) + " · ring " + money(median(vals(rng, "g")));
  const acres = vals(rows, "a");
  $("s_a").textContent = acres.length ? ac(median(acres)) : "—";
  $("s_ad").textContent = acres.length ? ac(acres.reduce((s, v) => s + v, 0)) + " acres total" : "";
}

/* ---------- histogram ---------- */
function drawHist(rows, f) {
  const counts = new Array(BLABEL.length).fill(0);
  for (const r of rows) {
    if (r.g == null) continue;
    let b = 0; while (r.g >= EDGES[b + 1]) b++;
    counts[b]++;
  }
  const max = Math.max(1, ...counts), W = 760, H = 190, PAD = 34, bw = (W - PAD * 2) / BLABEL.length;
  let svg = '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" role="img" aria-label="Price per acre distribution">' +
    '<line x1="' + PAD + '" y1="' + (H - 26) + '" x2="' + (W - PAD) + '" y2="' + (H - 26) + '" stroke="#999"/>';
  counts.forEach((c, i) => {
    const lo = EDGES[i], hi = EDGES[i + 1];
    const active = f.gmin === (lo || null) && f.gmax === (hi === Infinity ? null : hi - 1) && (f.gmin != null || f.gmax != null);
    const h = (H - PAD - 26) * c / max, x = PAD + i * bw + 2, y = H - 26 - h, cx = x + (bw - 4) / 2;
    svg += '<rect class="bar" data-b="' + i + '" x="' + x.toFixed(1) + '" y="' + (H - 26 - Math.max(h, 0)).toFixed(1) +
      '" width="' + (bw - 4).toFixed(1) + '" height="' + Math.max(h, 0).toFixed(1) + '" fill="' +
      (active ? "#b4552d" : "#23406b") + '" opacity="0.85"><title>' + BLABEL[i] + ": " + c + " parcels</title></rect>" +
      /* invisible full-height hit area so short bars are easy to click */
      '<rect class="bar" data-b="' + i + '" x="' + x.toFixed(1) + '" y="' + PAD + '" width="' + (bw - 4).toFixed(1) +
      '" height="' + (H - 26 - PAD) + '" fill="transparent"><title>' + BLABEL[i] + ": " + c + " parcels</title></rect>" +
      '<text x="' + cx.toFixed(1) + '" y="' + (H - 12) + '" font-size="8.5" text-anchor="middle" fill="#666">' + BLABEL[i] + "</text>" +
      (c ? '<text x="' + cx.toFixed(1) + '" y="' + (y - 4).toFixed(1) + '" font-size="8.5" text-anchor="middle" fill="#333">' +
        c.toLocaleString() + "</text>" : "");
  });
  $("hist").innerHTML = svg + "</svg>";
}
function histClick(e) {
  const t = e.target.closest("rect.bar");
  if (!t) return;
  const i = +t.dataset.b, lo = EDGES[i], hi = EDGES[i + 1];
  const loV = lo || "", hiV = hi === Infinity ? "" : hi - 1;
  const same = $("f_gmin").value === String(loV) && $("f_gmax").value === String(hiV);
  $("f_gmin").value = same ? "" : loV;
  $("f_gmax").value = same ? "" : hiV;
  apply({ fit: false });
}

/* ---------- table ---------- */
function drawTable() {
  const rows = VIEW.slice(0, shownN);
  $("rows").innerHTML = rows.map(r =>
    '<tr><td>' + (r.u ? '<a href="' + esc(r.u) + '" target="_blank" rel="noopener">' + esc(r.t) + "</a>"
                       : esc(r.t)) + (r.lc !== "parcel" ? " ~approx" : "") + tags(r) + "</td>" +
    "<td>" + esc(r.ty) + "</td>" +
    '<td class="num">' + money(r.p) + "</td>" +
    '<td class="num">' + ac(r.a) + "</td>" +
    '<td class="num">' + money(r.g) + "</td>" +
    "<td>" + esc(r.c) + "</td><td>" + esc(r.k) + "</td>" +
    '<td class="' + (r.z === "inside" ? "zone-in" : "zone-buf") + '">' + zoneName(r.z) + "</td>" +
    '<td class="num">' + (r.d == null ? "—" : r.d.toFixed(0)) + "</td></tr>").join("");
  const left = VIEW.length - rows.length;
  $("more").innerHTML = left > 0
    ? 'Showing ' + rows.length.toLocaleString() + " of " + VIEW.length.toLocaleString() +
      ' &middot; <a href="#" id="showmore">show ' + Math.min(PAGE, left).toLocaleString() + " more</a>" +
      ' &middot; <a href="#" id="showall">show all</a>'
    : (VIEW.length ? "" : "No parcels match these filters.");
  document.querySelectorAll("th[data-k]").forEach(th => th.querySelector(".arr").textContent =
    th.dataset.k === sortK ? (sortDir === 1 ? "▲" : "▼") : "");
}

/* ---------- wiring ---------- */
function initControls() {
  let timer = null;
  const later = (fit) => { clearTimeout(timer); timer = setTimeout(() => apply({ fit }), 200); };
  /* typing: debounce, don't move the map; picking a place: move the map to it */
  ["f_pmin","f_pmax","f_amin","f_amax","f_gmin","f_gmax"].forEach(id =>
    $(id).addEventListener("input", () => later(false)));
  $("f_q").addEventListener("input", () => later(true));
  $("f_county").addEventListener("change", () => { fillCities(); $("f_city").value = ""; apply({ fit: true }); });
  ["f_city","f_zone","f_type"].forEach(id => $(id).addEventListener("change", () => apply({ fit: true })));
  ["f_exact","f_new"].forEach(id => $(id).addEventListener("change", () => apply({ fit: false })));
  $("reset").addEventListener("click", () => {
    ["f_q","f_pmin","f_pmax","f_amin","f_amax","f_gmin","f_gmax","f_zone","f_type","f_county"].forEach(id => $(id).value = "");
    $("f_exact").checked = $("f_new").checked = false;
    fillCities(); $("f_city").value = "";
    apply({ fit: true });
  });
  $("zoom").addEventListener("click", () => zoomToResults());
  $("hist").addEventListener("click", histClick);
  document.querySelectorAll("th[data-k]").forEach(th => th.addEventListener("click", () => {
    const k = th.dataset.k;
    if (sortK === k) sortDir *= -1;
    else { sortK = k; sortDir = (k === "t" || k === "ty" || k === "c" || k === "k" || k === "z") ? 1 : -1; }
    VIEW.sort(cmp); drawTable();
  }));
  $("more").addEventListener("click", e => {
    if (e.target.id === "showmore") { e.preventDefault(); shownN += PAGE; drawTable(); }
    if (e.target.id === "showall") { e.preventDefault(); shownN = VIEW.length; drawTable(); }
  });
  $("dl").addEventListener("click", () => {
    const q = s => '"' + String(s == null ? "" : s).replace(/"/g, '""') + '"';
    const csv = "title,type,price_usd,acres,price_per_acre,lat,lon,approx_location,city,county,zone,mi_to_triangle,list_date,first_seen,prev_price,url\n" +
      VIEW.map(r => [q(r.t), q(r.ty), r.p ?? "", r.a ?? "", r.g ?? "", r.la ?? "", r.lo ?? "", r.lc !== "parcel" ? 1 : 0,
        q(r.c), q(r.k), r.z, r.d ?? "", r.ld ?? "", r.f ?? "", r.pp ?? "", q(r.u)].join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = "texas-triangle-land-filtered.csv"; a.click();
  });
}
boot();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
