/* Cleveland County (OK) Land Map — an onX-style public-data map. Leaflet + vanilla JS, no API keys. */
(function () {
  'use strict';
  const $ = s => document.querySelector(s);
  const esc = Geo.esc;
  const LS = { get: (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } }, set: (k, v) => localStorage.setItem(k, JSON.stringify(v)) };

  const SRC = {
    normanParcels: 'https://services.arcgis.com/rt1leD4Hj3sLGHNL/arcgis/rest/services/Parcels/FeatureServer/1',
    assessor: 'https://property.spatialest.com/ok/cleveland/',
    epqs: 'https://epqs.nationalmap.gov/v1/json',
    nominatim: 'https://nominatim.openstreetmap.org/search',
  };
  const COUNTY_BBOX = [-97.6815, 34.9174, -97.1316, 35.3874];
  const ATTR_USGS = '<a href="https://www.usgs.gov/programs/national-geospatial-program/national-map" target="_blank">USGS The National Map</a>';

  // ---------- Map ----------
  const saved = LS.get('ccmap.view', null);
  const map = L.map('map', { zoomControl: false, maxZoom: 20, worldCopyJump: false, preferCanvas: false });
  L.control.zoom({ position: 'topright' }).addTo(map);
  L.control.scale({ imperial: true, metric: true, position: 'bottomleft' }).addTo(map);
  const fromHash = () => { const m = location.hash.match(/^#(\d+(?:\.\d+)?)\/(-?\d+\.\d+)\/(-?\d+\.\d+)/); return m ? { z: +m[1], c: [+m[2], +m[3]] } : null; };
  const h = fromHash();
  if (h) map.setView(h.c, h.z); else if (saved) map.setView(saved.c, saved.z);
  else map.fitBounds([[COUNTY_BBOX[1], COUNTY_BBOX[0]], [COUNTY_BBOX[3], COUNTY_BBOX[2]]]);
  map.on('moveend', () => {
    const c = map.getCenter(), z = map.getZoom();
    LS.set('ccmap.view', { c: [c.lat, c.lng], z });
    history.replaceState(null, '', `#${z}/${c.lat.toFixed(5)}/${c.lng.toFixed(5)}`);
  });

  // Panes for draw order
  [['publand', 410], ['parcels', 420], ['lines', 430], ['plss', 440], ['pts', 600]].forEach(([n, z]) => { map.createPane(n).style.zIndex = z; });

  // ArcGIS MapServer "export" as 256px tiles (works for any dynamic MapServer, no CORS needed for <img>)
  const ExportLayer = L.TileLayer.extend({
    getTileUrl(c) {
      const ts = this.getTileSize(), nw = c.scaleBy(ts), se = nw.add(ts), crs = L.CRS.EPSG3857;
      const a = crs.project(this._map.unproject(nw, c.z)), b = crs.project(this._map.unproject(se, c.z));
      const lyr = this.options.layers ? `&layers=show:${this.options.layers}` : '';
      return `${this._url}/export?bbox=${a.x},${b.y},${b.x},${a.y}&bboxSR=3857&imageSR=3857&size=${ts.x},${ts.y}&format=png32&transparent=true&dpi=96${lyr}&f=image`;
    },
  });

  const t = (url, o) => L.tileLayer(url, { maxNativeZoom: 16, maxZoom: 20, ...o });
  const BASEMAPS = {
    'USGS Imagery': t('https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}', { attribution: `Imagery: ${ATTR_USGS} (NAIP/orthoimagery)` }),
    'USGS Imagery + Topo': t('https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryTopo/MapServer/tile/{z}/{y}/{x}', { attribution: ATTR_USGS }),
    'USGS Topo': t('https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}', { attribution: ATTR_USGS }),
    'Esri World Imagery': t('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxNativeZoom: 19, attribution: 'Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community' }),
    'OpenStreetMap': t('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxNativeZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors' }),
  };

  // ---------- Reference dictionaries (PAD-US 4.x codes) ----------
  const MANG = { CITY: 'City', CNTY: 'County', SFW: 'State Fish & Wildlife (ODWC)', SPR: 'State Parks & Recreation', SLB: 'State Land Board (Commissioners of the Land Office)', SDC: 'State Dept. of Conservation', OTHS: 'Other State', BLM: 'Bureau of Land Management', BOR: 'Bureau of Reclamation', USACE: 'Army Corps of Engineers', FWS: 'US Fish & Wildlife Service', NPS: 'National Park Service', USFS: 'US Forest Service', DOD: 'Dept. of Defense', NRCS: 'Natural Resources Conservation Service', NGO: 'Non-profit (NGO)', PVT: 'Private', TRIB: 'Tribal', UNK: 'Unknown', REG: 'Regional Agency', JNT: 'Joint', OTHF: 'Other Federal', OTHR: 'Other' };
  const ACCESS = { OA: 'Open access', RA: 'Restricted access', XA: 'Closed / no public access', UK: 'Access unknown' };
  const DES = { LP: 'Local Park', LREC: 'Local Recreation Area', LRMA: 'Local Resource Mgmt Area', LCA: 'Local Conservation Area', SP: 'State Park', SCA: 'State Conservation Area', SRMA: 'State Resource Mgmt Area', SREC: 'State Recreation Area', SW: 'State Wilderness', MIL: 'Military Land', AGRE: 'Agricultural Easement', CONE: 'Conservation Easement', RECE: 'Recreation Easement', PUB: 'Public Land (unclassified)', WPA: 'Watershed Protection Area', PPRK: 'Private Park', PREC: 'Private Recreation', PCON: 'Private Conservation', NWR: 'National Wildlife Refuge', NF: 'National Forest', NG: 'National Grassland', REA: 'Research/Educational Area', HCA: 'Historic/Cultural Area', FOTH: 'Federal Other', UNK: 'Unknown' };
  const PADCOLOR = { FED: '#e8b923', STAT: '#3a7bd5', LOC: '#3fae5a', NGO: '#9b59b6', PVT: '#9e9e9e', JNT: '#f2994a', DIST: '#26a69a', TRIB: '#8d6e63', UNK: '#cfcfcf' };
  const isEasement = p => /E$/.test(p.Des_Tp || '') && p.Des_Tp !== 'PUB' || p.Category === 'Easement';

  // ---------- Overlays ----------
  const data = {}; // name -> FeatureCollection
  async function loadJSON(name) { if (!data[name]) { const r = await fetch(`data/${name}.geojson`); data[name] = await r.json(); } return data[name]; }
  function lazyGeo(name, opts) { // GeoJSON layer that loads its file on first add
    const g = L.geoJSON(null, opts); let loaded = false;
    g.on('add', async () => { if (loaded) return; loaded = true; const fc = await loadJSON(name); g.addData(fc); opts.after && opts.after(g, fc); });
    return g;
  }
  function labelsLayer(name, minZoom, labelFn, cls) {
    const grp = L.layerGroup(); let built = false;
    const refresh = () => { if (!map.hasLayer(grp)) return; const show = map.getZoom() >= minZoom; grp.eachLayer(l => l.setOpacity(show ? 1 : 0)); };
    grp.on('add', async () => {
      if (!built) { built = true; const fc = await loadJSON(name);
        fc.features.forEach(f => { const c = L.geoJSON(f).getBounds().getCenter();
          L.marker(c, { pane: 'plss', interactive: false, keyboard: false, icon: L.divIcon({ className: 'plss-label ' + (cls || ''), html: labelFn(f.properties), iconSize: null }) }).addTo(grp); }); }
      refresh();
    });
    map.on('zoomend', refresh);
    return grp;
  }

  // Live City of Norman parcels (only drawn at z>=15)
  const parcels = L.geoJSON(null, { pane: 'parcels', interactive: false, style: { color: '#ffd400', weight: 1.4, fill: false, opacity: .95 } });
  const parcelHi = L.geoJSON(null, { pane: 'lines', interactive: false, style: { color: '#ff3b30', weight: 3, fillColor: '#ff3b30', fillOpacity: .12 } }).addTo(map);
  let parcelReq = 0;
  async function refreshParcels() {
    if (!map.hasLayer(parcels)) return;
    if (map.getZoom() < 15) { parcels.clearLayers(); return; }
    const b = map.getBounds(), id = ++parcelReq;
    const u = `${SRC.normanParcels}/query?geometry=${b.getWest()},${b.getSouth()},${b.getEast()},${b.getNorth()}&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=OBJECTID&returnGeometry=true&outSR=4326&geometryPrecision=6&resultRecordCount=4000&f=geojson`;
    try { const j = await (await fetch(u)).json(); if (id !== parcelReq) return; parcels.clearLayers(); parcels.addData(j); }
    catch (e) { console.warn('parcels', e); }
  }
  let pTimer; map.on('moveend', () => { clearTimeout(pTimer); pTimer = setTimeout(refreshParcels, 250); });
  parcels.on('add', refreshParcels);

  const wilmaIcon = { 'Parking': '🅿️', 'Entrance': '🚪', 'Shooting Range': '🎯', 'Camping Area': '⛺', 'Boat Ramp': '🚤', 'Department Office': '🏢', 'Toilet': '🚻', 'Water': '💧', 'Pond': '💧', 'Food Plot': '🌾' };

  const OVERLAYS = [
    { id: 'hillshade', name: 'Hillshade (USGS 3DEP)', sw: '#999', layer: t('https://basemap.nationalmap.gov/arcgis/rest/services/USGSShadedReliefOnly/MapServer/tile/{z}/{y}/{x}', { opacity: .35, attribution: ATTR_USGS }), opacity: true },
    { id: 'contours', name: 'Contours (USGS)', sw: '#a0522d', layer: new ExportLayer('https://carto.nationalmap.gov/arcgis/rest/services/contours/MapServer', { minZoom: 12, attribution: ATTR_USGS }) },
    { id: 'nhd', name: 'Hydrography (USGS NHD)', sw: '#1e88e5', layer: new ExportLayer('https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer', { minZoom: 11, opacity: .85, attribution: ATTR_USGS }) },
    { id: 'roads', name: 'Road labels (Esri reference)', sw: '#fff', layer: t('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}', { maxNativeZoom: 19, attribution: 'Roads © Esri' }) },
    { id: 'places', name: 'Place labels (Esri reference)', sw: '#fff', layer: t('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', { maxNativeZoom: 19, attribution: 'Labels © Esri' }) },
    { id: 'padus', name: 'Public & protected land (PAD-US)', sw: '#3a7bd5', legend: 'padus', layer: lazyGeo('padus', { pane: 'publand', interactive: false, style: f => { const p = f.properties, c = PADCOLOR[p.Mang_Type] || '#ccc'; return { color: c, weight: 1.5, fillColor: c, fillOpacity: isEasement(p) ? .12 : (p.Pub_Access === 'XA' ? .2 : .38), dashArray: isEasement(p) ? '5 4' : null }; } }) },
    { id: 'wma', name: 'ODWC Wildlife Mgmt Areas', sw: '#e65100', layer: lazyGeo('odwc_wma', { pane: 'publand', interactive: false, style: { color: '#e65100', weight: 2.5, fillColor: '#ff9800', fillOpacity: .3 } }) },
    { id: 'wilma', name: 'WMA facilities (parking, ranges, camps, roads)', sw: '#6d4c41', layer: lazyGeo('odwc_wilma', { pane: 'pts', interactive: false, after: () => wilmaZoom(),
      style: { color: '#6d4c41', weight: 2, dashArray: '4 3', fillOpacity: .2 },
      pointToLayer: (f, ll) => L.marker(ll, { pane: 'pts', title: `${f.properties.kind}`, icon: L.divIcon({ className: 'wp-icon', html: wilmaIcon[f.properties.kind] || '•', iconSize: [22, 22], iconAnchor: [11, 11] }) }) }) },
    { id: 'stpark', name: 'State parks', sw: '#00897b', layer: lazyGeo('state_parks', { pane: 'publand', interactive: false, style: { color: '#00695c', weight: 2, fillColor: '#26a69a', fillOpacity: .25 } }) },
    { id: 'bor', name: 'Lake Thunderbird BOR flowage easements', sw: '#7e57c2', layer: lazyGeo('bor_flowage_easements', { pane: 'publand', interactive: false, style: { color: '#5e35b1', weight: 1, dashArray: '3 3', fillColor: '#7e57c2', fillOpacity: .15 } }) },
    { id: 'parcels', name: 'Parcels — City of Norman (z≥15)', sw: '#ffd400', layer: parcels },
    { id: 'twp', name: 'PLSS townships (BLM)', sw: '#b3261e', layer: L.layerGroup([lazyGeo('plss_townships', { pane: 'plss', interactive: false, style: { color: '#b3261e', weight: 2.2, fill: false } }), labelsLayer('plss_townships', 9, p => esc(p.TWNSHPLAB), 'twp')]) },
    { id: 'sec', name: 'PLSS sections (BLM)', sw: '#e57373', layer: L.layerGroup([lazyGeo('plss_sections', { pane: 'plss', interactive: false, style: { color: '#d32f2f', weight: 1, opacity: .8, fill: false } }), labelsLayer('plss_sections', 13, p => esc(String(+p.FRSTDIVLAB || p.FRSTDIVLAB)))]) },
    { id: 'county', name: 'County boundary', sw: '#000', layer: lazyGeo('county', { pane: 'lines', interactive: false, style: { color: '#111', weight: 3, dashArray: '10 6', fill: false } }) },
  ];
  // WMA facility icons only at z>=13 to avoid clutter
  const wilmaOv = OVERLAYS.find(o => o.id === 'wilma');
  const wilmaZoom = () => { const show = map.getZoom() >= 13; wilmaOv.layer.eachLayer(l => { if (l.setOpacity) l.setOpacity(show ? 1 : 0); else if (l.setStyle) l.setStyle({ opacity: show ? 1 : 0, fillOpacity: show ? .2 : 0 }); }); };
  map.on('zoomend', wilmaZoom);
  const DEFAULT_ON = ['padus', 'wma', 'wilma', 'stpark', 'parcels', 'twp', 'sec', 'county'];

  // State
  const state = LS.get('ccmap.layers', { base: 'USGS Imagery + Topo', on: DEFAULT_ON, op: {} });
  let base = BASEMAPS[state.base] || BASEMAPS['USGS Imagery + Topo']; base.addTo(map);
  OVERLAYS.forEach(o => { if (state.op[o.id] != null && o.layer.setOpacity) o.layer.setOpacity(state.op[o.id]); if (state.on.includes(o.id)) o.layer.addTo(map); });
  const saveLayers = () => LS.set('ccmap.layers', state);

  // ---------- Panels ----------
  const panel = $('#panel');
  function openPanel(title, html, kind) {
    $('#panel-title').textContent = title; const b = $('#panel-body');
    if (typeof html === 'string') b.innerHTML = html; else { b.innerHTML = ''; b.appendChild(html); }
    panel.hidden = false; panel.dataset.kind = kind || '';
    document.querySelectorAll('#toolbar [data-panel]').forEach(x => x.classList.toggle('active', x.dataset.panel === kind));
    return b;
  }
  function closePanel() { panel.hidden = true; panel.dataset.kind = ''; parcelHi.clearLayers(); document.querySelectorAll('#toolbar [data-panel]').forEach(x => x.classList.remove('active')); }
  $('#panel-close').onclick = closePanel;
  const tpl = id => document.getElementById(id).content.cloneNode(true);

  function showLayers() {
    const b = openPanel('Layers', tpl('tpl-layers'), 'layers');
    const bm = b.querySelector('#basemaps');
    Object.keys(BASEMAPS).forEach(n => {
      const l = document.createElement('label');
      l.innerHTML = `<input type="radio" name="bm" ${state.base === n ? 'checked' : ''}> ${esc(n)}`;
      l.querySelector('input').onchange = () => { map.removeLayer(base); base = BASEMAPS[n]; base.addTo(map); base.bringToBack(); state.base = n; saveLayers(); };
      bm.appendChild(l);
    });
    const ov = b.querySelector('#overlays');
    OVERLAYS.forEach(o => {
      const l = document.createElement('label');
      const op = o.layer.setOpacity && o.opacity ? `<input type="range" min="0" max="1" step="0.05" value="${state.op[o.id] ?? o.layer.options.opacity ?? 1}" title="Opacity">` : '';
      l.innerHTML = `<input type="checkbox" ${map.hasLayer(o.layer) ? 'checked' : ''}><span class="sw" style="background:${o.sw}"></span>${esc(o.name)}${op}`;
      l.querySelector('input[type=checkbox]').onchange = e => {
        if (e.target.checked) { o.layer.addTo(map); state.on = [...new Set([...state.on, o.id])]; } else { map.removeLayer(o.layer); state.on = state.on.filter(x => x !== o.id); }
        saveLayers();
      };
      const r = l.querySelector('input[type=range]'); if (r) r.oninput = e => { o.layer.setOpacity(+e.target.value); state.op[o.id] = +e.target.value; saveLayers(); };
      ov.appendChild(l);
    });
  }
  function showLegend() {
    const b = openPanel('Legend', tpl('tpl-legend'), 'legend'), lg = b.querySelector('#legend');
    const item = (sw, txt, extra = '') => `<div class="legend-item"><span class="sw" style="${sw}"></span>${txt}${extra}</div>`;
    lg.innerHTML = `<h3>Public & protected land (PAD-US) — by manager type</h3>` +
      [['FED', 'Federal'], ['STAT', 'State (incl. ODWC, State Parks, CLO trust land)'], ['LOC', 'Local (city/county)'], ['NGO', 'Non-profit'], ['PVT', 'Private (protected/easement)'], ['TRIB', 'Tribal']].map(([k, v]) => item(`background:${PADCOLOR[k]};opacity:.75`, v)).join('') +
      item('background:transparent;border:2px dashed #888', 'Dashed outline = easement (land stays private)') +
      `<p class="small">Click any spot to see the unit name, manager and PAD-US public-access code (Open / Restricted / Closed / Unknown). “Open” in PAD-US does <b>not</b> automatically mean hunting is allowed.</p>` +
      `<h3>Hunting</h3>` + item('background:#ff9800;border-color:#e65100', 'ODWC Wildlife Management Area') +
      Object.entries(wilmaIcon).slice(0, 6).map(([k, v]) => `<div class="legend-item"><span style="width:22px;text-align:center">${v}</span>WMA ${esc(k.toLowerCase())}</div>`).join('') +
      item('background:transparent;border:2px dashed #6d4c41', 'WMA road / trail') +
      `<h3>Other</h3>` + item('background:#26a69a', 'State park') + item('background:#7e57c2;opacity:.6', 'Lake Thunderbird BOR flowage easement (City of Norman data)') +
      item('background:transparent;border:2px solid #ffd400', 'Parcel boundary (City of Norman, z≥15)') + item('background:transparent;border:2px solid #ff3b30', 'Selected parcel') +
      item('background:transparent;border:2px solid #b3261e', 'PLSS township (label: T R)') + item('background:transparent;border:1px solid #d32f2f', 'PLSS section (label: section #)') +
      item('background:transparent;border:2px dashed #111', 'Cleveland County boundary') + item('background:#1e88e5', 'NHD streams / waterbodies (USGS)') + item('background:#a0522d', 'Contours (USGS, z≥12)');
  }
  function showAbout() { openPanel('About & sources', tpl('tpl-about'), 'about'); }

  // ---------- Coordinates ----------
  const coordsEl = $('#coords'); let cfmt = LS.get('ccmap.cfmt', 0), lastLL = null;
  const fmtLL = (ll, f = cfmt) => {
    if (f === 1) return `${Geo.dms(ll.lat, 'N', 'S')} ${Geo.dms(ll.lng, 'E', 'W')}`;
    if (f === 2) { try { return 'MGRS ' + mgrs.forward([ll.lng, ll.lat], 5).replace(/^(\d+\w)(\w\w)(\d{5})(\d{5})$/, '$1 $2 $3 $4'); } catch { return '—'; } }
    return `${ll.lat.toFixed(5)}, ${ll.lng.toFixed(5)}`;
  };
  const showCoords = ll => { lastLL = ll; coordsEl.textContent = fmtLL(ll); };
  map.on('mousemove', e => showCoords(e.latlng));
  map.on('move', () => { if (!matchMedia('(hover: hover)').matches) showCoords(map.getCenter()); });
  coordsEl.onclick = () => { cfmt = (cfmt + 1) % 3; LS.set('ccmap.cfmt', cfmt); showCoords(lastLL || map.getCenter()); };
  showCoords(map.getCenter());

  // ---------- Identify (click on map) ----------
  const kv = rows => `<table class="kv">${rows.filter(r => r[1] !== undefined && r[1] !== null && String(r[1]).trim() !== '').map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v}</td></tr>`).join('')}</table>`;
  const idMarker = L.circleMarker([0, 0], { radius: 7, color: '#fff', weight: 3, fillColor: '#ff3b30', fillOpacity: 1, pane: 'pts' });

  async function identify(ll) {
    const pt = [ll.lng, ll.lat];
    idMarker.setLatLng(ll).addTo(map); parcelHi.clearLayers();
    const gmaps = `https://www.google.com/maps/dir/?api=1&destination=${ll.lat.toFixed(6)},${ll.lng.toFixed(6)}`;
    const b = openPanel('Location info', `<div class="card"><h4>📌 Point</h4>${kv([
      ['Lat, Lon', `${ll.lat.toFixed(6)}, ${ll.lng.toFixed(6)}`], ['DMS', fmtLL(ll, 1)], ['MGRS', fmtLL(ll, 2).replace('MGRS ', '')],
      ['Elevation', '<span id="id-elev">…</span>'], ['PLSS', '<span id="id-plss">…</span>']])}
      <div class="row" style="margin-top:6px"><button id="id-save">Save waypoint</button><a class="btn" href="${gmaps}" target="_blank" rel="noopener">Directions ↗</a></div></div>
      <div id="id-parcel"></div><div id="id-pub"></div>`, 'identify');
    b.querySelector('#id-save').onclick = () => addSaved({ type: 'Feature', properties: { name: prompt('Waypoint name', 'Waypoint') || 'Waypoint', created: new Date().toISOString() }, geometry: { type: 'Point', coordinates: pt.map(n => +n.toFixed(6)) } });

    // Elevation (USGS EPQS)
    fetch(`${SRC.epqs}?x=${pt[0]}&y=${pt[1]}&units=Feet&wkid=4326`).then(r => r.json()).then(j => {
      const v = +j.value; const el = b.querySelector('#id-elev'); if (el) el.textContent = isFinite(v) && v > -1000 ? `${Math.round(v)} ft (${Math.round(v * 0.3048)} m) · USGS 3DEP` : 'n/a';
    }).catch(() => { const el = b.querySelector('#id-elev'); if (el) el.textContent = 'n/a'; });

    // PLSS (local data)
    loadJSON('plss_sections').then(fc => {
      const s = fc.features.find(f => Geo.inPolygon(pt, f.geometry)); const el = b.querySelector('#id-plss');
      if (el) el.textContent = s ? `Sec ${+s.properties.FRSTDIVLAB}, ${(s.properties.TWNSHPLAB || '').replace(/(\d+[NS]) (\d+[EW])/, 'T$1 R$2')}, Indian Meridian` : 'outside loaded PLSS';
    });

    // Public lands (local data)
    const hits = [];
    const [pad, wma, park, bor] = await Promise.all(['padus', 'odwc_wma', 'state_parks', 'bor_flowage_easements'].map(loadJSON));
    wma.features.filter(f => Geo.inPolygon(pt, f.geometry)).forEach(f => hits.push(`<div class="card"><h4>🦌 ${esc(f.properties.NAME)}</h4>${kv([['Type', 'ODWC Wildlife Management Area'], ['Rules', '<a href="https://www.wildlifedepartment.com/hunting/wma/all" target="_blank" rel="noopener">Check ODWC WMA regulations ↗</a>']])}</div>`));
    park.features.filter(f => Geo.inPolygon(pt, f.geometry)).forEach(f => hits.push(`<div class="card"><h4>🏞️ ${esc(f.properties.PARK_NAME)}</h4>${kv([['Type', 'Oklahoma State Park']])}</div>`));
    pad.features.filter(f => Geo.inPolygon(pt, f.geometry)).sort((a, b) => (a.properties.GIS_Acres || 0) - (b.properties.GIS_Acres || 0)).forEach(f => {
      const p = f.properties;
      hits.push(`<div class="card"><h4><span class="sw" style="width:12px;height:12px;background:${PADCOLOR[p.Mang_Type] || '#ccc'};display:inline-block;border-radius:2px"></span>${esc(p.Unit_Nm || p.Loc_Nm || 'Protected area')} <span class="tag ${esc(p.Pub_Access)}">${esc(ACCESS[p.Pub_Access] || p.Pub_Access)}</span></h4>${kv([
        ['Manager', esc(MANG[p.Mang_Name] || p.Mang_Name)], ['Owner', esc(p.Own_Name ? (MANG[p.Own_Name] || p.Own_Name) : '')], ['Designation', esc(DES[p.Des_Tp] || p.Loc_Ds || p.Des_Tp)],
        ['Category', esc(p.Category)], ['GIS acres', p.GIS_Acres != null ? Number(p.GIS_Acres).toLocaleString() : ''], ['GAP status', esc(p.GAP_Sts)], ['Source', 'USGS PAD-US 4.1']])}</div>`);
    });
    bor.features.filter(f => Geo.inPolygon(pt, f.geometry)).forEach(f => hits.push(`<div class="card"><h4>🌊 BOR flowage easement</h4>${kv(Object.entries(f.properties).slice(0, 8).map(([k, v]) => [k, esc(v)]))}<p class="small">Bureau of Reclamation flowage easement around Lake Thunderbird (City of Norman GIS). Underlying land is generally private.</p></div>`));
    const pubEl = b.querySelector('#id-pub');
    if (pubEl) pubEl.innerHTML = hits.length ? `<h3>Public / protected land here</h3>${hits.join('')}` : `<p class="small">No PAD-US public/protected land, WMA or state park at this point — <b>assume private land</b>.</p>`;

    // Parcel (live, City of Norman)
    const pEl = b.querySelector('#id-parcel'); if (pEl) pEl.innerHTML = '<p class="small">Looking up parcel…</p>';
    try {
      const u = `${SRC.normanParcels}/query?geometry=${pt[0]},${pt[1]}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&returnGeometry=true&outSR=4326&f=geojson`;
      const j = await (await fetch(u)).json();
      const el = b.querySelector('#id-parcel'); if (!el) return;
      if (j.features && j.features.length) {
        const f = j.features[0], p = f.properties; parcelHi.clearLayers().addData(f);
        el.innerHTML = parcelCard(p, f);
      } else el.innerHTML = `<div class="card"><h4>🏠 Parcel</h4><p class="small">No parcel polygon here in the City of Norman dataset (it only covers Norman city limits). Countywide owner records: <a href="${SRC.assessor}" target="_blank" rel="noopener">Cleveland County Assessor ↗</a></p></div>`;
    } catch (e) { const el = b.querySelector('#id-parcel'); if (el) el.innerHTML = `<p class="small">Parcel service unavailable (${esc(e.message)}).</p>`; }
  }
  function parcelAddr(p) { const n = p.F_ADD && p.F_ADD !== p.T_ADD && p.T_ADD ? `${p.F_ADD}-${p.T_ADD}` : (p.F_ADD || ''); return [n, p.PRE_DIR, p.STREET_NAME, p.STREET_TYPE, p.SUF_DIR].map(s => String(s ?? '').trim()).filter(s => s && s !== '0').join(' '); }
  function parcelCard(p, f) {
    let area = '';
    if (f && f.geometry) { const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates; area = Geo.fmtArea(polys.reduce((s, pl) => s + Geo.ringArea(pl[0]) - pl.slice(1).reduce((h, r) => h + Geo.ringArea(r), 0), 0)); }
    const addr = parcelAddr(p);
    return `<div class="card"><h4>🏠 Parcel ${esc((p.GEONUMBER || '').replace(/\s+/g, ' ').trim())}</h4>${kv([
      ['Situs address', esc(addr ? addr + ', Norman OK' : '')], ['Owner', '<i>Not published in the public GIS layer</i> — <a href="' + SRC.assessor + '" target="_blank" rel="noopener">search Assessor ↗</a>'],
      ['Acreage (record)', p.ACREAGE != null ? (+p.ACREAGE).toFixed(2) + ' ac' : ''], ['Area (computed)', area], ['Land use', esc((p.USECODE || '').trim())],
      ['Geo number', esc((p.GEONUMBER || '').trim())], ['School district', esc((p.SCHDIST || '').trim())], ['Addition / Block / Lot', esc([p.ADDT, p.BLOCK, p.LOT].map(s => String(s ?? '').trim()).filter(Boolean).join(' / '))],
      ['FEMA LOMC', esc([(p.LOMC || '').trim(), (p.LOMC_CASE || '').trim()].filter(Boolean).join(' '))], ['Source', 'City of Norman GIS (Parcels)']])}
      <p class="small">Tip: copy the address and paste it into the Assessor search for owner, value and legal description.</p></div>`;
  }

  // ---------- Saved items (waypoints / lines / areas) ----------
  let store = LS.get('ccmap.saved.v1', { type: 'FeatureCollection', features: [] });
  const savedLayer = L.featureGroup().addTo(map);
  const persist = () => { LS.set('ccmap.saved.v1', store); renderSaved(); };
  function describe(f) {
    const g = f.geometry;
    if (g.type === 'Point') return `${g.coordinates[1].toFixed(5)}, ${g.coordinates[0].toFixed(5)}`;
    if (g.type === 'LineString') return Geo.fmtDist(Geo.length(g.coordinates));
    if (g.type === 'Polygon') return `${Geo.fmtArea(Geo.ringArea(g.coordinates[0]))} · perimeter ${Geo.fmtDist(Geo.length(g.coordinates[0]))}`;
    return g.type;
  }
  function renderSaved() {
    savedLayer.clearLayers();
    store.features.forEach((f, i) => {
      const l = L.geoJSON(f, {
        pane: 'pts', style: { color: '#ff6d00', weight: 3, fillOpacity: .15 },
        pointToLayer: (_, ll) => L.marker(ll, { pane: 'pts', icon: L.divIcon({ className: 'wp-icon', html: '📍', iconSize: [22, 22], iconAnchor: [11, 21] }) }),
      }).bindPopup(`<b>${esc(f.properties.name)}</b><br><small>${esc(describe(f))}</small>${f.properties.notes ? `<br>${esc(f.properties.notes)}` : ''}`);
      l.featureIndex = i; savedLayer.addLayer(l);
    });
    const ul = document.getElementById('saved-list'); if (!ul) return;
    ul.innerHTML = store.features.length ? '' : '<li class="small">Nothing saved yet. Use 📍 Waypoint, 〰️ Line or ⬠ Area.</li>';
    store.features.forEach((f, i) => {
      const li = document.createElement('li'); const ic = { Point: '📍', LineString: '〰️', Polygon: '⬠' }[f.geometry.type] || '•';
      li.innerHTML = `<span>${ic}</span><span class="nm">${esc(f.properties.name)}<span class="meta">${esc(describe(f))}</span></span><button title="Rename">✏️</button><button title="Delete">🗑️</button>`;
      li.querySelector('.nm').onclick = () => { const g = L.geoJSON(f); f.geometry.type === 'Point' ? map.setView(g.getBounds().getCenter(), Math.max(map.getZoom(), 16)) : map.fitBounds(g.getBounds(), { padding: [40, 40] }); };
      const [ren, del] = li.querySelectorAll('button');
      ren.onclick = () => { const n = prompt('Name', f.properties.name); if (n != null) { f.properties.name = n; const notes = prompt('Notes (optional)', f.properties.notes || ''); if (notes != null) f.properties.notes = notes; persist(); } };
      del.onclick = () => { if (confirm(`Delete "${f.properties.name}"?`)) { store.features.splice(i, 1); persist(); } };
      ul.appendChild(li);
    });
  }
  function addSaved(f) { store.features.push(f); persist(); toast(`Saved “${f.properties.name}”`); }
  function download(name, text, type) { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500); }
  function showSaved() {
    const b = openPanel('My saved items', tpl('tpl-saved'), 'saved'); renderSaved();
    const stamp = new Date().toISOString().slice(0, 10);
    b.querySelector('#exp-gpx').onclick = () => download(`cleveland-county-${stamp}.gpx`, Geo.toGPX(store.features), 'application/gpx+xml');
    b.querySelector('#exp-geojson').onclick = () => download(`cleveland-county-${stamp}.geojson`, JSON.stringify(store, null, 1), 'application/geo+json');
    b.querySelector('#imp').onchange = async e => {
      const file = e.target.files[0]; if (!file) return; const txt = await file.text(); let feats = [];
      try { feats = /\.gpx$/i.test(file.name) || txt.trim().startsWith('<') ? Geo.fromGPX(txt) : (JSON.parse(txt).features || []); } catch (err) { alert('Could not read file: ' + err.message); return; }
      feats = feats.filter(f => f.geometry && ['Point', 'LineString', 'Polygon'].includes(f.geometry.type)).map(f => ({ type: 'Feature', properties: { name: f.properties?.name || f.geometry.type, notes: f.properties?.notes || '' }, geometry: f.geometry }));
      store.features.push(...feats); persist(); toast(`Imported ${feats.length} item(s)`);
    };
  }
  renderSaved();

  // ---------- Drawing & measuring ----------
  let tool = null, pts = [], sketch = L.layerGroup().addTo(map);
  const hint = $('#drawhint');
  function setTool(name) {
    tool = name; pts = []; sketch.clearLayers();
    document.querySelectorAll('#toolbar [data-tool]').forEach(b => b.classList.toggle('active', b.dataset.tool === name));
    map.getContainer().style.cursor = name ? 'crosshair' : '';
    hint.hidden = !name || name === 'waypoint' && false; updateHint();
  }
  function updateHint() {
    if (!tool) { hint.hidden = true; return; }
    hint.hidden = false;
    const ll = pts.map(p => [p.lng, p.lat]);
    let msg = { waypoint: 'Tap the map to drop a waypoint', line: 'Tap to add points', area: 'Tap to add corners', measure: 'Tap to measure' }[tool];
    if (pts.length > 1) msg = `Distance ${Geo.fmtDist(Geo.length(tool === 'area' ? [...ll, ll[0]] : ll))}`;
    if (pts.length > 2 && (tool === 'area' || tool === 'measure')) msg += ` · Area ${Geo.fmtArea(Geo.ringArea(ll))}`;
    $('#drawmsg').textContent = msg;
    $('#drawfinish').hidden = tool === 'waypoint' || tool === 'measure'; $('#drawundo').hidden = tool === 'waypoint';
    $('#drawcancel').textContent = tool === 'measure' ? 'Done' : 'Cancel';
  }
  function redrawSketch() {
    sketch.clearLayers(); if (!pts.length) return;
    const style = { color: tool === 'measure' ? '#00e5ff' : '#ff6d00', weight: 3, dashArray: tool === 'measure' ? '6 4' : null, pane: 'pts' };
    if (pts.length > 2 && (tool === 'area' || tool === 'measure')) L.polygon(pts, { ...style, fillOpacity: .15 }).addTo(sketch); else L.polyline(pts, style).addTo(sketch);
    pts.forEach(p => L.circleMarker(p, { radius: 4, color: '#fff', weight: 2, fillColor: style.color, fillOpacity: 1, pane: 'pts' }).addTo(sketch));
  }
  map.on('click', e => {
    if (!tool) { identify(e.latlng); return; }
    if (tool === 'waypoint') {
      const n = prompt('Waypoint name', `Waypoint ${store.features.filter(f => f.geometry.type === 'Point').length + 1}`);
      if (n !== null) addSaved({ type: 'Feature', properties: { name: n || 'Waypoint', created: new Date().toISOString() }, geometry: { type: 'Point', coordinates: [+e.latlng.lng.toFixed(6), +e.latlng.lat.toFixed(6)] } });
      setTool(null); return;
    }
    pts.push(e.latlng); redrawSketch(); updateHint();
  });
  $('#drawundo').onclick = () => { pts.pop(); redrawSketch(); updateHint(); };
  $('#drawcancel').onclick = () => setTool(null);
  $('#drawfinish').onclick = () => {
    const need = tool === 'area' ? 3 : 2; if (pts.length < need) { toast(`Add at least ${need} points`); return; }
    const c = pts.map(p => [+p.lng.toFixed(6), +p.lat.toFixed(6)]);
    const geom = tool === 'area' ? { type: 'Polygon', coordinates: [[...c, c[0]]] } : { type: 'LineString', coordinates: c };
    const n = prompt('Name', tool === 'area' ? 'Area' : 'Line');
    if (n !== null) addSaved({ type: 'Feature', properties: { name: n || tool, created: new Date().toISOString() }, geometry: geom });
    setTool(null);
  };
  document.querySelectorAll('#toolbar [data-tool]').forEach(b => b.onclick = () => setTool(tool === b.dataset.tool ? null : b.dataset.tool));
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { if (tool) setTool(null); else closePanel(); } if (e.key === 'Enter' && tool && (tool === 'line' || tool === 'area') && document.activeElement === document.body) $('#drawfinish').click(); });

  // ---------- Geolocation ----------
  let locOn = false; const locLayer = L.layerGroup().addTo(map); let firstFix = true;
  $('#locate').onclick = () => {
    locOn = !locOn; $('#locate').classList.toggle('active', locOn);
    if (locOn) { firstFix = true; map.locate({ watch: true, enableHighAccuracy: true, setView: false, maxZoom: 16 }); }
    else { map.stopLocate(); locLayer.clearLayers(); }
  };
  map.on('locationfound', e => {
    locLayer.clearLayers();
    L.circle(e.latlng, { radius: e.accuracy, color: '#2979ff', weight: 1, fillOpacity: .12, interactive: false }).addTo(locLayer);
    L.circleMarker(e.latlng, { radius: 8, color: '#fff', weight: 3, fillColor: '#2979ff', fillOpacity: 1, pane: 'pts' }).bindTooltip(`You (±${Math.round(e.accuracy)} m)`).addTo(locLayer);
    if (firstFix) { map.setView(e.latlng, Math.max(map.getZoom(), 15)); firstFix = false; }
  });
  map.on('locationerror', e => { toast('Location unavailable: ' + e.message); locOn = false; $('#locate').classList.remove('active'); });

  // ---------- Search ----------
  const resEl = $('#results');
  function showResults(items) {
    resEl.innerHTML = ''; resEl.hidden = !items.length;
    items.forEach(it => { const li = document.createElement('li'); li.tabIndex = 0; li.innerHTML = `${esc(it.label)}<small>${esc(it.sub || '')}</small>`;
      li.onclick = li.onkeydown = ev => { if (ev.type === 'keydown' && ev.key !== 'Enter') return; resEl.hidden = true; it.go(); }; resEl.appendChild(li); });
  }
  const goBounds = (geo, then) => { const b = L.geoJSON(geo).getBounds(); map.fitBounds(b, { maxZoom: 17, padding: [40, 40] }); then && setTimeout(then, 400); };
  async function search(q) {
    q = q.trim(); if (!q) return; const out = [];
    // Coordinates
    const m = q.match(/^\s*(-?\d{1,2}\.\d+)\s*[, ]\s*(-?\d{1,3}\.\d+)\s*$/);
    if (m) { const ll = L.latLng(+m[1], +m[2]); map.setView(ll, 16); identify(ll); resEl.hidden = true; return; }
    try { const p = mgrs.toPoint(q.replace(/\s+/g, '').toUpperCase()); if (p && isFinite(p[0])) { const ll = L.latLng(p[1], p[0]); map.setView(ll, 16); identify(ll); resEl.hidden = true; return; } } catch { }
    // PLSS: "T9N R2W S15", "9N 2W 15", "Sec 15 T9N R2W"
    const s = q.toUpperCase();
    const pm = s.match(/T?\s*(\d{1,2})\s*([NS])\W*R?\s*(\d{1,2})\s*([EW])/);
    if (pm) {
      const sec = (s.match(/S(?:EC(?:TION)?)?\.?\s*(\d{1,2})\b/) || s.match(/[EW]\W+(\d{1,2})\s*$/) || [])[1];
      const id = `OK17${pm[1].padStart(3, '0')}0${pm[2]}${pm[3].padStart(3, '0')}0${pm[4]}0`;
      if (sec) { const fc = await loadJSON('plss_sections'); const f = fc.features.find(f => f.properties.PLSSID === id && +f.properties.FRSTDIVLAB === +sec); if (f) out.push({ label: `Section ${+sec}, T${pm[1]}${pm[2]} R${pm[3]}${pm[4]}`, sub: 'PLSS section (BLM)', go: () => goBounds(f) }); }
      const tf = (await loadJSON('plss_townships')).features.find(f => f.properties.PLSSID === id);
      if (tf) out.push({ label: `Township T${pm[1]}${pm[2]} R${pm[3]}${pm[4]}`, sub: 'PLSS township (BLM)', go: () => goBounds(tf) });
    }
    // Public land by name
    const ql = q.toLowerCase();
    if (ql.length >= 3) {
      const [pad, wma] = await Promise.all([loadJSON('padus'), loadJSON('odwc_wma')]);
      const seen = new Set();
      [...wma.features.map(f => [f.properties.NAME, 'ODWC WMA', f]), ...pad.features.map(f => [f.properties.Unit_Nm, `PAD-US · ${MANG[f.properties.Mang_Name] || f.properties.Mang_Name}`, f])]
        .filter(([n]) => n && n.toLowerCase().includes(ql)).forEach(([n, sub, f]) => { if (seen.has(n + sub) || seen.size >= 6) return; seen.add(n + sub); out.push({ label: n, sub, go: () => goBounds(f) }); });
    }
    showResults(out.length ? out : [{ label: 'Searching…', sub: '', go: () => { } }]);
    // Norman parcels: geo number or "123 Main"
    const parcelQs = [];
    const am = q.match(/^(\d+)\s+(?:([NSEW])\.?\s+)?([A-Za-z0-9 ]+?)(?:\s+(ST|AVE|RD|DR|LN|CT|BLVD|CIR|PL|TER|WAY|PKWY|TRL|HWY))?\.?(?:,.*)?$/i);
    if (am) { const n = +am[1], street = am[3].trim().toUpperCase().replace(/'/g, "''");
      parcelQs.push(`F_ADD <= ${n} AND T_ADD >= ${n} AND STREET_NAME LIKE '${street}%'` + (am[2] ? ` AND PRE_DIR = '${am[2].toUpperCase()}'` : '')); }
    if (/^[A-Z]{0,2}\d[\d\sA-Z]{4,}$/i.test(q) && !am) parcelQs.push(`GEONUMBER LIKE '%${q.toUpperCase().replace(/'/g, "''").replace(/\s+/g, '%')}%'`);
    const parcelP = Promise.all(parcelQs.map(w => fetch(`${SRC.normanParcels}/query?where=${encodeURIComponent(w)}&outFields=*&returnGeometry=true&outSR=4326&resultRecordCount=8&f=geojson`).then(r => r.json()).catch(() => ({ features: [] }))))
      .then(rs => rs.flatMap(r => r.features || []).map(f => ({ label: parcelAddr(f.properties) || f.properties.GEONUMBER, sub: `Norman parcel ${f.properties.GEONUMBER} · ${(+f.properties.ACREAGE || 0).toFixed(2)} ac`, go: () => { goBounds(f, () => identify(L.geoJSON(f).getBounds().getCenter())); } })));
    // Nominatim (OSM) limited to the county
    const nomP = fetch(`${SRC.nominatim}?format=jsonv2&limit=6&countrycodes=us&bounded=1&viewbox=${COUNTY_BBOX[0]},${COUNTY_BBOX[3]},${COUNTY_BBOX[2]},${COUNTY_BBOX[1]}&q=${encodeURIComponent(q)}`, { headers: { 'Accept-Language': 'en' } })
      .then(r => r.json()).then(js => js.map(j => ({ label: j.display_name.split(',').slice(0, 3).join(','), sub: `OpenStreetMap · ${j.type}`, go: () => { const ll = L.latLng(+j.lat, +j.lon); map.setView(ll, 17); identify(ll); } }))).catch(() => []);
    const [pr, nr] = await Promise.all([parcelP, nomP]);
    const all = [...out, ...pr, ...nr];
    showResults(all.length ? all : [{ label: 'No results in Cleveland County', sub: 'Try an address, a place, “T9N R2W S15”, lat,lon or MGRS. Owner-name search is not available (owners are not in public GIS).', go: () => { } }]);
  }
  $('#search').onsubmit = e => { e.preventDefault(); search($('#q').value); };
  document.addEventListener('click', e => { if (!e.target.closest('#search')) resEl.hidden = true; });

  // ---------- Misc ----------
  function toast(msg) { const d = document.createElement('div'); d.textContent = msg; Object.assign(d.style, { position: 'fixed', left: '50%', bottom: '90px', transform: 'translateX(-50%)', background: '#222', color: '#fff', padding: '8px 14px', borderRadius: '8px', zIndex: 6000 }); document.body.appendChild(d); setTimeout(() => d.remove(), 2200); }
  const PANELS = { layers: showLayers, legend: showLegend, saved: showSaved, about: showAbout };
  document.querySelectorAll('#toolbar [data-panel]').forEach(b => b.onclick = () => panel.dataset.kind === b.dataset.panel ? closePanel() : PANELS[b.dataset.panel]());
  if (!LS.get('ccmap.ack', false)) { $('#modal').hidden = false; $('#modal-ok').onclick = () => { LS.set('ccmap.ack', true); $('#modal').hidden = true; }; } else $('#modal').hidden = true;
  window.ccmap = { map, identify, search, OVERLAYS, BASEMAPS }; // for debugging / tests
})();
