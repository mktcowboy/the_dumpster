/* Oklahoma Waterways — MapLibre + PMTiles front end */
(function () {
const protocol = new pmtiles.Protocol();
maplibregl.addProtocol('pmtiles', protocol.tile);
const BASE = new URL('.', location.origin + location.pathname).href;
const HYDRO = 'pmtiles://' + BASE + 'tiles/hydro.pmtiles';
const WBD = 'pmtiles://' + BASE + 'tiles/wbd.pmtiles';
const FONT_R = ['Noto Sans Regular'], FONT_I = ['Noto Sans Italic'], FONT_B = ['Noto Sans Bold'];
const OK_BOUNDS = [[-103.01, 33.6], [-94.42, 37.01]];
const HU_COLORS = {2: '#7a1f1f', 4: '#b03a2e', 6: '#d35400', 8: '#b7950b', 10: '#1e8449', 12: '#5d6d7e'};
const HU_WIDTH = {2: 3.2, 4: 2.6, 6: 2, 8: 1.6, 10: 1.1, 12: 0.7};
const HU_LABELZ = {2: [3, 7], 4: [5, 8], 6: [6, 9], 8: [7, 11], 10: [9, 13], 12: [10.5, 24]};
let CODES = {fcode: {}, ftype: {}}, T = {}, STATS = null;

const BASEMAPS = {
  light: {tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}'], attribution: 'Basemap © Esri, HERE, Garmin, © OpenStreetMap contributors', maxzoom: 16},
  osm: {tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', maxzoom: 19},
  topo: {tiles: ['https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}'], attribution: 'USGS The National Map', maxzoom: 16},
  imagery: {tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'], attribution: 'Imagery © Esri, Maxar, Earthstar Geographics', maxzoom: 19},
};

const soWidth = (k) => ['interpolate', ['exponential', 1.6], ['zoom'],
  4, ['*', k * 0.12, ['max', 0.3, ['-', ['get', 'so'], 3]]],
  8, ['*', k * 0.35, ['max', 0.4, ['-', ['get', 'so'], 2]]],
  12, ['*', k * 0.7, ['max', 0.6, ['-', ['get', 'so'], 1]]],
  16, ['*', k * 1.6, ['max', 1, ['get', 'so']]]];
const flowColor = ['match', ['get', 'fc'], 46006, '#1f6fb2', 46003, '#4f97d1', 46007, '#8db8de', 55800, '#1f6fb2', '#2f80c0'];

const style = {
  version: 8,
  glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
  sources: {
    basemap: {type: 'raster', tileSize: 256, ...BASEMAPS.light},
    hydro: {type: 'vector', url: HYDRO, attribution: '<a href="https://www.usgs.gov/national-hydrography">USGS NHD / WBD</a>'},
    wbd: {type: 'vector', url: WBD},
    gauges: {type: 'geojson', data: 'data/gauges.geojson'},
    hl: {type: 'geojson', data: {type: 'FeatureCollection', features: []}},
  },
  layers: [
    {id: 'basemap', type: 'raster', source: 'basemap', paint: {'raster-opacity': 0.9}},
    {id: 'state-mask', type: 'line', source: 'wbd', 'source-layer': 'state', paint: {'line-color': '#334', 'line-width': 1.5, 'line-opacity': .6}},
    {id: 'counties', type: 'line', source: 'wbd', 'source-layer': 'counties', layout: {visibility: 'none'}, paint: {'line-color': '#555', 'line-width': .7, 'line-dasharray': [3, 2]}},
    {id: 'counties-label', type: 'symbol', source: 'wbd', 'source-layer': 'county_labels', minzoom: 7, layout: {visibility: 'none', 'text-field': ['concat', ['get', 'county'], ' Co.'], 'text-font': FONT_R, 'text-size': 11}, paint: {'text-color': '#555', 'text-halo-color': '#fff', 'text-halo-width': 1.2}},
    ...[2, 4, 6, 8, 10, 12].map(l => ({id: `hu${l}-fill`, type: 'fill', source: 'wbd', 'source-layer': `hu${l}`, layout: {visibility: l === 8 ? 'visible' : 'none'}, paint: {'fill-color': HU_COLORS[l], 'fill-opacity': 0.0}})),
    {id: 'areas', type: 'fill', source: 'hydro', 'source-layer': 'areas', paint: {'fill-color': ['match', ['get', 'ft'], 403, '#d6ecf8', 343, '#c0392b', '#bfe0f5'], 'fill-outline-color': '#7fb5dc', 'fill-opacity': 0.85}},
    {id: 'waterbodies', type: 'fill', source: 'hydro', 'source-layer': 'waterbodies', filter: ['!=', ['get', 'ft'], 466], paint: {'fill-color': ['match', ['get', 'ft'], 436, '#86c0ea', 361, '#e9dfc4', '#9fcdee'], 'fill-outline-color': '#4a90c8'}},
    {id: 'swamps', type: 'fill', source: 'hydro', 'source-layer': 'waterbodies', filter: ['==', ['get', 'ft'], 466], paint: {'fill-color': '#a7d7c5', 'fill-outline-color': '#5aa58a', 'fill-opacity': .8}},
    {id: 'pipes', type: 'line', source: 'hydro', 'source-layer': 'flowlines', filter: ['in', ['get', 'ft'], ['literal', [420, 428]]], layout: {visibility: 'none'}, paint: {'line-color': '#777', 'line-width': 1.2, 'line-dasharray': [2, 2]}},
    {id: 'canals', type: 'line', source: 'hydro', 'source-layer': 'flowlines', filter: ['==', ['get', 'ft'], 336], paint: {'line-color': '#9b3fb5', 'line-width': ['interpolate', ['linear'], ['zoom'], 8, .6, 14, 2.2], 'line-dasharray': [3, 1.5]}},
    {id: 'streams', type: 'line', source: 'hydro', 'source-layer': 'flowlines', filter: ['in', ['get', 'ft'], ['literal', [460, 558, 334, 566]]], layout: {'line-cap': 'round', 'line-join': 'round'}, paint: {'line-color': flowColor, 'line-width': soWidth(1)}},
    {id: 'nhdlines', type: 'line', source: 'hydro', 'source-layer': 'lines', minzoom: 9, paint: {'line-color': ['match', ['get', 'ft'], 343, '#c0392b', 568, '#8e5a2b', 569, '#8e5a2b', '#a04000'], 'line-width': 2}},
    ...[2, 4, 6, 8, 10, 12].map(l => ({id: `hu${l}`, type: 'line', source: 'wbd', 'source-layer': `hu${l}`, layout: {visibility: l === 8 ? 'visible' : 'none', 'line-join': 'round'}, paint: {'line-color': HU_COLORS[l], 'line-width': ['interpolate', ['linear'], ['zoom'], 5, HU_WIDTH[l] * .6, 12, HU_WIDTH[l] * 1.6], 'line-opacity': .85}})),
    {id: 'hl-fill', type: 'fill', source: 'hl', filter: ['==', ['geometry-type'], 'Polygon'], paint: {'fill-color': '#ffeb3b', 'fill-opacity': .35}},
    {id: 'hl-line', type: 'line', source: 'hl', layout: {'line-cap': 'round', 'line-join': 'round'}, paint: {'line-color': '#ff9800', 'line-width': 4, 'line-opacity': .85}},
    {id: 'hl-flow', type: 'line', source: 'hydro', 'source-layer': 'flowlines', filter: ['==', ['get', 'gid'], '__none__'], layout: {'line-cap': 'round'}, paint: {'line-color': '#ff9800', 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 3, 12, 6], 'line-opacity': .8}},
    {id: 'hl-wb', type: 'line', source: 'hydro', 'source-layer': 'waterbodies', filter: ['==', ['get', 'gid'], '__none__'], paint: {'line-color': '#ff9800', 'line-width': 3}},
    {id: 'nhdpoints', type: 'circle', source: 'hydro', 'source-layer': 'points', layout: {visibility: 'none'}, paint: {'circle-radius': 4, 'circle-color': ['match', ['get', 'ft'], 458, '#e67e22', 487, '#2980b9', 431, '#8e44ad', '#7f8c8d'], 'circle-stroke-color': '#fff', 'circle-stroke-width': 1}},
    {id: 'gauges', type: 'circle', source: 'gauges', paint: {'circle-radius': ['interpolate', ['linear'], ['zoom'], 5, 3, 12, 7], 'circle-color': ['case', ['==', ['get', 'act'], 1], '#16a34a', '#9ca3af'], 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.2}},
    // labels
    ...[2, 4, 6, 8, 10, 12].map(l => ({id: `hu${l}-label`, type: 'symbol', source: 'wbd', 'source-layer': `hu${l}_labels`, minzoom: HU_LABELZ[l][0], maxzoom: HU_LABELZ[l][1], layout: {visibility: l === 8 ? 'visible' : 'none', 'text-field': ['concat', ['get', 'n'], '\n', ['get', 'huc']], 'text-font': FONT_B, 'text-size': 11, 'text-max-width': 8}, paint: {'text-color': HU_COLORS[l], 'text-halo-color': 'rgba(255,255,255,.9)', 'text-halo-width': 1.5}})),
    {id: 'stream-label', type: 'symbol', source: 'hydro', 'source-layer': 'flowlines', filter: ['!=', ['get', 'n'], ''], layout: {'symbol-placement': 'line', 'text-field': ['get', 'n'], 'text-font': FONT_I, 'text-size': ['interpolate', ['linear'], ['zoom'], 6, ['+', 8, ['*', .5, ['get', 'so']]], 13, ['+', 10, ['*', .6, ['get', 'so']]]], 'symbol-spacing': 350, 'text-letter-spacing': .05}, paint: {'text-color': '#0d4a7a', 'text-halo-color': 'rgba(255,255,255,.9)', 'text-halo-width': 1.4}},
    {id: 'wb-label', type: 'symbol', source: 'hydro', 'source-layer': 'waterbody_labels', layout: {'text-field': ['get', 'n'], 'text-font': FONT_I, 'text-size': ['interpolate', ['linear'], ['get', 'ac'], 10, 10, 1000, 11, 20000, 14], 'text-max-width': 7}, paint: {'text-color': '#0b3f66', 'text-halo-color': 'rgba(255,255,255,.9)', 'text-halo-width': 1.4}},
    {id: 'gauges-label', type: 'symbol', source: 'gauges', minzoom: 10, layout: {'text-field': ['get', 'site'], 'text-font': FONT_R, 'text-size': 10, 'text-offset': [0, 1.1], 'text-anchor': 'top'}, paint: {'text-color': '#166534', 'text-halo-color': '#fff', 'text-halo-width': 1.2}},
  ],
};

const map = new maplibregl.Map({container: 'map', style, bounds: OK_BOUNDS, fitBoundsOptions: {padding: 20}, maxZoom: 17, hash: true, attributionControl: {compact: false}});
map.addControl(new maplibregl.NavigationControl(), 'top-right');
map.addControl(new maplibregl.ScaleControl({unit: 'imperial'}), 'bottom-right');
map.addControl(new maplibregl.FullscreenControl(), 'top-right');
window._map = map;

// ---------- data ----------
const j = (u) => fetch(u).then(r => { if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); });
Promise.all([j('data/codes.json'), j('data/streams.json'), j('data/lakes.json'), j('data/watersheds.json'), j('data/gauges.geojson'), j('data/stats.json')])
  .then(([codes, s, l, w, g, st]) => {
    CODES = codes; STATS = st;
    T.streams = s; T.lakes = l; T.watersheds = w;
    T.gauges = {cols: ['site', 'name', 'type', 'active', 'drainage_sqmi', 'bbox'], rows: g.features.map(f => { const p = f.properties, c = f.geometry.coordinates; return [p.site, p.n, p.t, p.act ? 'yes' : 'no', p.da >= 0 ? p.da : null, [c[0], c[1], c[0], c[1]]]; })};
    T.hucName = {}; w.rows.forEach(r => T.hucName[r[0]] = r[1]);
    T.streamIdx = {}; s.rows.forEach(r => T.streamIdx[r[6] + '|' + r[0]] = r);
    buildSearch(); renderStats(); renderTable();
  }).catch(e => { console.error(e); document.getElementById('stats').textContent = 'Failed to load data: ' + e.message; });

// ---------- layer toggles ----------
const vis = (id, on) => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
const GROUPS = {streams: ['streams'], canals: ['canals'], pipes: ['pipes'], waterbodies: ['waterbodies'], swamps: ['swamps'], areas: ['areas'], nhdlines: ['nhdlines'], nhdpoints: ['nhdpoints'], gauges: ['gauges', 'gauges-label'], counties: ['counties', 'counties-label'], labels: ['stream-label', 'wb-label']};
document.querySelectorAll('[data-layer]').forEach(cb => cb.addEventListener('change', () => GROUPS[cb.dataset.layer].forEach(id => vis(id, cb.checked))));
document.querySelectorAll('[data-hu]').forEach(cb => cb.addEventListener('change', () => { const l = cb.dataset.hu; [`hu${l}`, `hu${l}-fill`, `hu${l}-label`].forEach(id => vis(id, cb.checked)); }));
function streamFilter() {
  const fl = [...document.querySelectorAll('[data-flow]')].filter(c => c.checked).map(c => c.dataset.flow);
  const known = [46006, 46003, 46007];
  const parts = [];
  fl.forEach(f => { if (f === 'other') parts.push(['!', ['in', ['get', 'fc'], ['literal', known]]]); else parts.push(['==', ['get', 'fc'], +f]); });
  let flt = ['all', ['in', ['get', 'ft'], ['literal', [460, 558, 334, 566]]], ['any', ...parts]];
  if (!parts.length) flt = ['==', 1, 0];
  if (document.getElementById('namedOnly').checked) flt.push(['!=', ['get', 'n'], '']);
  map.setFilter('streams', flt);
}
document.querySelectorAll('[data-flow], #namedOnly').forEach(c => c.addEventListener('change', streamFilter));
document.getElementById('activeOnly').addEventListener('change', e => { const f = e.target.checked ? ['==', ['get', 'act'], 1] : null; map.setFilter('gauges', f); map.setFilter('gauges-label', f); });
document.getElementById('basemap').addEventListener('change', e => {
  const v = e.target.value;
  if (map.getLayer('basemap')) map.removeLayer('basemap');
  if (map.getSource('basemap')) map.removeSource('basemap');
  if (v === 'none') return;
  map.addSource('basemap', {type: 'raster', tileSize: 256, ...BASEMAPS[v]});
  map.addLayer({id: 'basemap', type: 'raster', source: 'basemap', paint: {'raster-opacity': 0.9}}, map.getStyle().layers[0].id);
});

// ---------- tabs ----------
document.querySelectorAll('#tabs button').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('#tabs button').forEach(x => x.classList.toggle('on', x === b));
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('on', t.id === 'tab-' + b.dataset.tab));
  document.body.classList.toggle('wide', b.dataset.tab === 'tables');
  setTimeout(() => map.resize(), 250);
}));

// ---------- helpers ----------
const fmt = (n, d = 0) => n == null || n === '' ? '' : Number(n).toLocaleString('en-US', {maximumFractionDigits: d, minimumFractionDigits: 0});
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
function zoomBbox(b, maxZoom = 14) {
  if (!b) return;
  if (b[0] === b[2] && b[1] === b[3]) map.flyTo({center: [b[0], b[1]], zoom: 13});
  else map.fitBounds([[b[0], b[1]], [b[2], b[3]]], {padding: 50, maxZoom, duration: 900});
}
function clearHL() { map.setFilter('hl-flow', ['==', ['get', 'gid'], '__none__']); map.setFilter('hl-wb', ['==', ['get', 'gid'], '__none__']); map.getSource('hl').setData({type: 'FeatureCollection', features: []}); }
function hlStream(gid, name) { clearHL(); map.setFilter('hl-flow', gid ? ['==', ['get', 'gid'], gid] : ['==', ['get', 'n'], name]); }
function hlLake(gid, name) { clearHL(); map.setFilter('hl-wb', gid ? ['==', ['get', 'gid'], gid] : ['==', ['get', 'n'], name]); }
function hlHuc(huc) {
  clearHL(); const l = huc.length;
  const cb = document.querySelector(`[data-hu="${l}"]`); if (cb && !cb.checked) { cb.checked = true; cb.dispatchEvent(new Event('change')); }
  const once = () => { const fs = map.querySourceFeatures('wbd', {sourceLayer: `hu${l}`, filter: ['==', ['get', 'huc'], huc]}); if (fs.length) map.getSource('hl').setData({type: 'FeatureCollection', features: fs.map(f => ({type: 'Feature', properties: {}, geometry: f.geometry}))}); };
  map.once('idle', once);
}
function hlPoint(c) { clearHL(); map.getSource('hl').setData({type: 'FeatureCollection', features: [{type: 'Feature', properties: {}, geometry: {type: 'Point', coordinates: c}}]}); }
const KIND = {
  streams: {zoom: r => { hlStream(r[6], r[0]); zoomBbox(r[7], 13); }},
  lakes: {zoom: r => { hlLake(r[6], r[0]); zoomBbox(r[7], 15); }},
  watersheds: {zoom: r => { zoomBbox(r[7], 14); hlHuc(r[0]); }},
  gauges: {zoom: r => { zoomBbox(r[5]); }},
};

// ---------- search ----------
let SEARCH = [];
function buildSearch() {
  T.streams.rows.forEach(r => SEARCH.push({k: 'streams', label: r[0], sub: `${r[1]} · ${fmt(r[2], 1)} mi in OK${r[5] ? ' · ' + r[5].split(';').slice(0, 3).join(', ') + (r[5].split(';').length > 3 ? '…' : '') : ''}`, w: r[2], r}));
  T.lakes.rows.forEach(r => SEARCH.push({k: 'lakes', label: r[0], sub: `${r[1]} · ${fmt(r[2], 1)} acres${r[3] ? ' · ' + r[3].replace(/;/g, ', ') + ' Co.' : ''}`, w: r[2] / 50, r}));
  T.watersheds.rows.forEach(r => SEARCH.push({k: 'watersheds', label: r[1] + ' (' + r[2] + ')', sub: `HUC ${r[0]} · ${fmt(r[3], 1)} sq mi`, w: r[3] / 10, r, extra: r[0]}));
  T.gauges.rows.forEach(r => SEARCH.push({k: 'gauges', label: r[1], sub: `USGS ${r[0]} · ${r[3] === 'yes' ? 'active' : 'inactive'} gauge`, w: 0, r, extra: r[0]}));
  SEARCH.forEach(s => s.lc = (s.label + ' ' + (s.extra || '')).toLowerCase());
}
const sIn = document.getElementById('search'), sOut = document.getElementById('results');
let sHits = [], sSel = -1;
sIn.addEventListener('input', () => {
  const q = sIn.value.trim().toLowerCase(); sSel = -1;
  if (q.length < 2) { sOut.innerHTML = ''; return; }
  const terms = q.split(/\s+/);
  sHits = SEARCH.filter(s => terms.every(t => s.lc.includes(t))).map(s => ({s, sc: (s.lc.startsWith(q) ? 1e6 : 0) + (s.w || 0)})).sort((a, b) => b.sc - a.sc).slice(0, 40).map(x => x.s);
  const icon = {streams: '〰️', lakes: '💧', watersheds: '🗺️', gauges: '📍'};
  sOut.innerHTML = sHits.map((s, i) => `<div data-i="${i}">${icon[s.k]} ${esc(s.label)}<small>${esc(s.sub)}</small></div>`).join('') || '<div><small>No matches</small></div>';
});
sOut.addEventListener('click', e => { const d = e.target.closest('[data-i]'); if (d) pick(+d.dataset.i); });
sIn.addEventListener('keydown', e => {
  const n = sOut.children.length;
  if (e.key === 'ArrowDown') { sSel = Math.min(n - 1, sSel + 1); } else if (e.key === 'ArrowUp') { sSel = Math.max(0, sSel - 1); } else if (e.key === 'Enter') { pick(sSel < 0 ? 0 : sSel); return; } else if (e.key === 'Escape') { sOut.innerHTML = ''; return; } else return;
  e.preventDefault(); [...sOut.children].forEach((c, i) => c.classList.toggle('sel', i === sSel));
});
function pick(i) { const s = sHits[i]; if (!s) return; sOut.innerHTML = ''; sIn.value = s.label; KIND[s.k].zoom(s.r); }

// ---------- tables ----------
const TDEF = {
  streams: {cols: [['Name', 0], ['Type', 1], ['Length (mi)', 2, 1], ['Max order', 3, 0], ['Drainage (sq mi)', 8, 0], ['Mean flow (cfs)', 9, 0], ['HUC8', 4], ['Counties', 5]], csv: 'tables/streams.csv', sort: [2, -1]},
  lakes: {cols: [['Name', 0], ['Type', 1], ['Area (acres)', 2, 1], ['County', 3], ['HUC8', 4], ['Elev (ft)', 5, 0]], csv: 'tables/lakes.csv', sort: [2, -1]},
  watersheds: {cols: [['HUC', 0], ['Name', 1], ['Level', 2], ['Area (sq mi)', 3, 1], ['% in OK', 4, 1], ['States', 5], ['Stream mi in OK', 6, 0]], csv: 'tables/watersheds.csv', sort: [0, 1]},
  gauges: {cols: [['Site', 0], ['Name', 1], ['Type', 2], ['Active (real-time)', 3], ['Drainage (sq mi)', 4, 0]], csv: 'tables/gauges.csv', sort: [1, 1]},
};
let curT = 'streams', sortState = {};
const tF = document.getElementById('tfilter'), tL = document.getElementById('tlevel');
document.querySelectorAll('#tblnav button').forEach(b => b.addEventListener('click', () => { curT = b.dataset.t; document.querySelectorAll('#tblnav button').forEach(x => x.classList.toggle('on', x === b)); tF.value = ''; renderTable(); }));
tF.addEventListener('input', () => renderTable()); tL.addEventListener('change', () => renderTable());
function renderTable() {
  if (!T[curT]) return;
  const def = TDEF[curT], st = sortState[curT] || def.sort;
  tL.hidden = curT !== 'watersheds';
  document.getElementById('tcsv').href = def.csv;
  const q = tF.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  let rows = T[curT].rows;
  if (curT === 'watersheds' && tL.value) rows = rows.filter(r => r[2] === tL.value);
  if (q.length) rows = rows.filter(r => { const s = r.filter(x => !Array.isArray(x)).join(' ').toLowerCase(); return q.every(t => s.includes(t)); });
  const [ci, dir] = st;
  rows = rows.slice().sort((a, b) => { const x = a[ci], y = b[ci]; if (x == null) return 1; if (y == null) return -1; return (typeof x === 'number' ? x - y : String(x).localeCompare(String(y))) * dir; });
  const LIM = 2000;
  document.getElementById('tcount').textContent = `${fmt(rows.length)} rows${rows.length > LIM ? ` (showing first ${fmt(LIM)} — filter to narrow)` : ''} · click a row to zoom`;
  const thead = document.querySelector('#tbl thead'), tbody = document.querySelector('#tbl tbody');
  thead.innerHTML = '<tr>' + def.cols.map(([n, i]) => `<th data-c="${i}" class="${i === ci ? (dir > 0 ? 'asc' : 'desc') : ''}">${n}</th>`).join('') + '</tr>';
  thead.querySelectorAll('th').forEach(th => th.addEventListener('click', () => { const c = +th.dataset.c; const cur = sortState[curT] || def.sort; sortState[curT] = [c, cur[0] === c ? -cur[1] : (typeof T[curT].rows[0][c] === 'number' ? -1 : 1)]; renderTable(); }));
  const shown = rows.slice(0, LIM);
  tbody.innerHTML = shown.map((r, k) => '<tr data-k="' + k + '">' + def.cols.map(([n, i, d]) => d != null ? `<td class="num">${fmt(r[i], d)}</td>` : `<td>${esc(typeof r[i] === 'string' ? r[i].replace(/;/g, ', ') : r[i])}</td>`).join('') + '</tr>').join('');
  tbody.onclick = e => { const tr = e.target.closest('tr'); if (tr) KIND[curT].zoom(shown[+tr.dataset.k]); };
}

// ---------- stats ----------
function renderStats() {
  const s = STATS, wb = s.waterbodies;
  const card = (v, l) => `<div class="card"><b>${v}</b>${l}</div>`;
  const tbl = (obj, unit) => '<table>' + Object.entries(obj).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${fmt(v)} ${unit}</td></tr>`).join('') + '</table>';
  document.getElementById('stats').innerHTML =
    '<div class="big">' + card(fmt(s.total_flowline_miles), 'miles of mapped flowlines') + card(fmt(s.flowline_segments), 'NHD flowline segments') +
    card(fmt(s.named_streams), 'named streams/rivers/canals') + card(fmt(s.named_stream_miles), 'miles of named streams') +
    card(fmt(wb.polygons), 'lakes, ponds & reservoirs (polygons)') + card(fmt(wb.acres), 'acres of open water & wetland') +
    card(fmt(wb.named), 'named waterbodies') + card(fmt(wb.over_100_acres), 'waterbodies > 100 acres') +
    card(fmt(s.watersheds.HUC8) + ' / ' + fmt(s.watersheds.HUC12), 'HUC8 subbasins / HUC12s') + card(fmt(s.gauges_active_realtime) + ' / ' + fmt(s.gauges), 'active / total USGS gauges') + '</div>' +
    '<h3>Flowline miles by type</h3>' + tbl(s.miles_by_type, 'mi') +
    '<h3>Flow permanence</h3>' + tbl(s.miles_by_flow, 'mi') +
    '<h3>Miles by Strahler stream order</h3><table>' + Object.entries(s.miles_by_order).map(([k, v]) => `<tr><td>Order ${k === '0' ? '(none)' : k}</td><td class="num">${fmt(v)} mi</td></tr>`).join('') + '</table>' +
    '<h3>Waterbodies by type</h3><table>' + Object.entries(wb.by_type).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${fmt(v.count)}</td><td class="num">${fmt(v.acres)} ac</td></tr>`).join('') + '</table>' +
    '<h3>Watershed units touching Oklahoma</h3>' + tbl(s.watersheds, '') +
    '<h3>Longest named streams (in-state miles)</h3><table>' + s.top_streams.map(([n, v]) => `<tr><td>${esc(n)}</td><td class="num">${fmt(v, 1)} mi</td></tr>`).join('') + '</table>' +
    '<h3>Largest named lakes (in-state acres)</h3><table>' + s.top_lakes.map(([n, v]) => `<tr><td>${esc(n)}</td><td class="num">${fmt(v)} ac</td></tr>`).join('') + '</table>';
}

// ---------- popups ----------
const CLICKABLE = ['gauges', 'nhdpoints', 'streams', 'canals', 'pipes', 'nhdlines', 'waterbodies', 'swamps', 'areas', 'hu12-fill', 'hu10-fill', 'hu8-fill', 'hu6-fill', 'hu4-fill', 'hu2-fill'];
const row = (k, v) => v === '' || v == null ? '' : `<tr><td class="k">${k}</td><td>${v}</td></tr>`;
const fdesc = (fc, ft) => CODES.fcode[fc] || CODES.ftype[ft] || ft;
const hucLink = h => h ? `${h} <span style="color:#6b7a89">${esc(T.hucName && T.hucName[h] || '')}</span>` : '';
map.on('click', e => {
  const layers = CLICKABLE.filter(id => map.getLayer(id) && map.getLayoutProperty(id, 'visibility') !== 'none');
  const fs = map.queryRenderedFeatures([[e.point.x - 4, e.point.y - 4], [e.point.x + 4, e.point.y + 4]], {layers});
  if (!fs.length) return;
  let html = '', seen = new Set(), hus = [];
  for (const f of fs) {
    const p = f.properties, id = f.layer.id;
    const key = id + '|' + (p.gid || p.huc || p.site || p.n || '') + '|' + (p.km || p.ac || '');
    if (seen.has(key)) continue; seen.add(key);
    if (id.startsWith('hu')) { hus.push(p); continue; }
    if (html.split('<hr>').length > 3) continue;
    if (id === 'gauges') {
      html += `<h4>📍 ${esc(p.n)}</h4><table>${row('USGS site', p.site)}${row('Type', p.t)}${row('Status', p.act ? 'Active real-time' : 'Inactive / daily only')}${row('Drainage', p.da >= 0 ? fmt(p.da) + ' sq mi' : '')}</table><a target="_blank" rel="noopener" href="https://waterdata.usgs.gov/monitoring-location/USGS-${p.site}/">Live data on USGS Water Data ↗</a>`;
    } else if (['streams', 'canals', 'pipes'].includes(id)) {
      const tr = T.streamIdx && T.streamIdx[(p.gid || '') + '|' + p.n];
      html += `<h4>${p.n ? esc(p.n) : '<i>Unnamed ' + esc(CODES.ftype[p.ft] || 'flowline').toLowerCase() + '</i>'}</h4><table>` +
        row('Type', esc(fdesc(p.fc, p.ft))) + row('Stream order', p.so > 0 ? p.so : '') + row('Drainage area', p.da != null ? fmt(p.da, 1) + ' sq mi' : '') + row('Mean annual flow', p.q != null ? fmt(p.q, 1) + ' cfs (est.)' : '') + row('This segment', fmt(p.km * 0.621371, 2) + ' mi') +
        (tr ? row('Total in OK', fmt(tr[2], 1) + ' mi') + row('Counties', esc(tr[5].replace(/;/g, ', '))) : '') +
        row('HUC8', hucLink(p.huc8)) + row('GNIS ID', p.gid) + '</table>' +
        (p.n ? `<a href="#" data-hls="${esc(p.gid || '')}" data-n="${esc(p.n)}">Highlight entire ${esc(p.n)}</a>` : '');
    } else if (id === 'waterbodies' || id === 'swamps') {
      html += `<h4>${p.n ? esc(p.n) : '<i>Unnamed ' + esc(CODES.ftype[p.ft] || 'waterbody').toLowerCase() + '</i>'}</h4><table>` +
        row('Type', esc(fdesc(p.fc, p.ft))) + row('Area', fmt(p.ac, 1) + ' acres') + row('Elevation', p.el ? fmt(p.el * 3.28084) + ' ft' : '') + row('HUC8', hucLink(p.huc8)) + row('GNIS ID', p.gid) + '</table>';
    } else {
      html += `<h4>${p.n ? esc(p.n) : '<i>' + esc(fdesc(p.fc, p.ft)) + '</i>'}</h4><table>${row('Type', esc(fdesc(p.fc, p.ft)))}${row('Area', p.ac ? fmt(p.ac, 1) + ' acres' : '')}</table>`;
    }
    html += '<hr>';
  }
  if (hus.length) {
    hus.sort((a, b) => a.huc.length - b.huc.length);
    html += '<b>Watersheds</b><table>' + hus.map(h => row('HUC' + h.huc.length, `${esc(h.n)} <span style="color:#6b7a89">${h.huc}</span>`)).join('') + '</table>';
  }
  const pop = new maplibregl.Popup({maxWidth: '340px'}).setLngLat(e.lngLat).setHTML('<div class="pop">' + html.replace(/<hr>$/, '') + '</div>').addTo(map);
  pop.getElement().addEventListener('click', ev => { const a = ev.target.closest('[data-hls]'); if (a) { ev.preventDefault(); hlStream(a.dataset.hls, a.dataset.n); const r = T.streamIdx[a.dataset.hls + '|' + a.dataset.n]; if (r) zoomBbox(r[7], 13); } });
});
map.on('mousemove', e => {
  const layers = CLICKABLE.filter(id => !id.endsWith('-fill') && map.getLayer(id) && map.getLayoutProperty(id, 'visibility') !== 'none');
  map.getCanvas().style.cursor = map.queryRenderedFeatures([[e.point.x - 3, e.point.y - 3], [e.point.x + 3, e.point.y + 3]], {layers}).length ? 'pointer' : '';
});
})();
