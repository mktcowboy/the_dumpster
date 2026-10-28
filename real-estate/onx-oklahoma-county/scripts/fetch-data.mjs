// Downloads and pre-bakes small public GeoJSON layers for Oklahoma County, OK (FIPS 40109).
// Usage: npm install && npm run fetch-data
// Everything comes from public ArcGIS REST services; see README for source details.
import { createHash } from 'node:crypto';
import fs from 'node:fs/promises';
import bboxClip from '@turf/bbox-clip';
import booleanIntersects from '@turf/boolean-intersects';
import intersect from '@turf/intersect';
import { featureCollection } from '@turf/helpers';

const OUT = new URL('../data/', import.meta.url);
const FIPS = '40109';
const UA = { 'User-Agent': 'onx-oklahoma-county data refresh (open-source public-land map)' };

// Same fingerprints as the repository privacy check. A refresh must not write them back.
const BLOCKED = new Set([
  '8802b69f05738c4ed94b86a0fa4cee921db823e62d47a70d9034a1abcaa3bb9b',
  '9fbb8412cdc93b8c5919da05fe115ab04af1b15acc0e14c91d025b249a88f268',
  '614e8e1f4c3876db53f8d40288168711fa77930b5ccbf0b9626c9b01aa42d5f2',
  'e016ef65bf37def457ab09faa9d48effdf0186a7dab671318b6d39de1a4f551c',
]);

function scrubValue(value) {
  if (typeof value !== 'string' || !value) return value;
  return value.replace(/[A-Za-z0-9]+/g, (token) => {
    const digest = createHash('sha256').update(token.toLowerCase()).digest('hex');
    return BLOCKED.has(digest) ? '' : token;
  }).replace(/-{2,}/g, '-').replace(/\s{2,}/g, ' ').replace(/-\s+/g, ' ').replace(/\s+-/g, ' ').trim();
}

function scrubProps(props) {
  if (!props || typeof props !== 'object') return props;
  return Object.fromEntries(Object.entries(props).map(([k, v]) => [k, scrubValue(v)]));
}

async function getJSON(url, params) {
  const u = new URL(url);
  for (const [k, v] of Object.entries(params || {})) u.searchParams.set(k, v);
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const r = await fetch(u, { headers: UA });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      if (j.error) throw new Error(JSON.stringify(j.error));
      return j;
    } catch (e) {
      if (attempt === 3) throw new Error(`${u.toString().slice(0, 200)} -> ${e.message}`);
      await new Promise(res => setTimeout(res, 1500 * attempt));
    }
  }
}

// Page through an ArcGIS layer query returning GeoJSON.
async function queryAll(layerUrl, params, pageSize = 1000) {
  const feats = [];
  for (let offset = 0; ; offset += pageSize) {
    const j = await getJSON(`${layerUrl}/query`, {
      outSR: 4326, f: 'geojson', resultOffset: offset, resultRecordCount: pageSize, ...params,
    });
    feats.push(...(j.features || []));
    const more = j.exceededTransferLimit || j.properties?.exceededTransferLimit;
    if (!more || !(j.features || []).length) break;
  }
  return feats;
}

const round = (geom, p = 6) => {
  const f = c => Array.isArray(c[0]) ? c.map(f) : c.map(n => +n.toFixed(p));
  if (!geom) return geom;
  if (geom.type === 'GeometryCollection') return { ...geom, geometries: geom.geometries.map(g => round(g, p)) };
  return { ...geom, coordinates: f(geom.coordinates) };
};

async function save(name, features, meta) {
  const fc = { type: 'FeatureCollection', metadata: { ...meta, retrieved: new Date().toISOString() },
    features: features.map(f => ({ type: 'Feature', properties: scrubProps(f.properties), geometry: round(f.geometry) })) };
  await fs.writeFile(new URL(name, OUT), JSON.stringify(fc));
  console.log(`  ${name}: ${features.length} features`);
}

const pick = (props, keys) => Object.fromEntries(keys.filter(k => k in props).map(k => [k, props[k]]));

async function main() {
  await fs.mkdir(OUT, { recursive: true });

  console.log('County boundary (Census TIGERweb)');
  const TIGER = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1';
  const county = await queryAll(TIGER, { where: `GEOID='${FIPS}'`, outFields: 'GEOID,NAME,BASENAME' });
  if (!county.length) throw new Error('county not found');
  await save('county.geojson', county, { source: TIGER });
  const cgeom = county[0];
  const ring = cgeom.geometry.type === 'Polygon' ? cgeom.geometry.coordinates : cgeom.geometry.coordinates.flat();
  const xs = ring.flat().map(c => c[0]), ys = ring.flat().map(c => c[1]);
  const pad = 0.01;
  const bbox = [Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad];
  console.log('  bbox', bbox.map(n => n.toFixed(4)).join(','));
  await fs.writeFile(new URL('bbox.json', OUT), JSON.stringify(bbox));
  const env = { geometry: bbox.join(','), geometryType: 'esriGeometryEnvelope', inSR: 4326, spatialRel: 'esriSpatialRelIntersects' };
  const inCounty = f => { try { return booleanIntersects(f, cgeom); } catch { return true; } };
  const clip = f => {
    if (!f.geometry || !/Polygon|LineString/.test(f.geometry.type)) return f;
    const c = bboxClip(f, bbox), g = c.geometry;
    if (!g) return null;
    // drop degenerate rings/parts produced by clipping
    if (g.type === 'Polygon') g.coordinates = g.coordinates.filter(r => r.length >= 4);
    if (g.type === 'MultiPolygon') g.coordinates = g.coordinates.map(p => p.filter(r => r.length >= 4)).filter(p => p.length);
    if (g.type === 'MultiPolygon' && g.coordinates.length === 1) { g.type = 'Polygon'; g.coordinates = g.coordinates[0]; }
    return g.coordinates.length ? c : null;
  };

  console.log('PAD-US 4.1 (USGS) - public/protected lands');
  const PADUS = 'https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/Manager_Name_PADUS/FeatureServer/0';
  let pad_ = await queryAll(PADUS, { ...env, where: "Des_Tp <> 'TRIBL'", outFields: 'Unit_Nm,Loc_Nm,Mang_Name,Mang_Type,Own_Name,Own_Type,Des_Tp,Loc_Ds,Pub_Access,GAP_Sts,GIS_Acres,Category,FeatClass,Date_Est,Src_Date', geometryPrecision: 6, maxAllowableOffset: 0.00002 }, 500);
  // Clip each PAD-US polygon to the county outline (some units, e.g. CLO trust lands, are statewide multipolygons)
  pad_ = pad_.map(clip).filter(Boolean).filter(inCounty).map(f => {
    try { const x = intersect(featureCollection([f, cgeom])); return x ? { ...f, geometry: x.geometry } : null; } catch { return f; }
  }).filter(Boolean);
  await save('padus.geojson', pad_, { source: PADUS, note: 'Tribal statistical areas (Des_Tp=TRIBL) excluded: they are Census statistical areas, not land ownership.' });

  console.log('ODWC areas (OklahomaRecreationalAreas)');
  const REC = 'https://services6.arcgis.com/RBtoEUQ2lmN0K3GY/arcgis/rest/services/OklahomaRecreationalAreas/FeatureServer';
  const wma = (await queryAll(`${REC}/0`, { ...env, where: '1=1', outFields: 'NAME,SHORTNAME' })).filter(inCounty);
  await save('odwc_wma.geojson', wma, { source: `${REC}/0` });
  // (layer 3 = state parks: none intersect Oklahoma County as of 2026-10, so not baked)

  console.log('ODWC WILMA public WMA features');
  const WILMA = 'https://www.wildlifedepartment.com/server/rest/services/PublicWILMA/WILMAFeatures/MapServer';
  const wilmaLayers = { 0: 'Department Office', 1: 'Entrance', 2: 'Parking', 3: 'Shooting Range', 4: 'Camping Area', 5: 'Boat Ramp', 6: 'Special Use Area', 7: 'Food Plot', 8: 'Water', 9: 'WMA Road', 10: 'Wetland Development Unit', 11: 'Toilet', 12: 'Pond' };
  const wilma = [];
  for (const [id, kind] of Object.entries(wilmaLayers)) {
    try {
      const fs_ = await queryAll(`${WILMA}/${id}`, { ...env, where: '1=1', outFields: '*' }, 1000);
      for (const f of fs_) {
        const p = Object.fromEntries(Object.entries(f.properties).filter(([k, v]) => v !== null && String(v).trim() !== '' && !/^(OBJECTID|GlobalID|last_edited|created_|Shape)/i.test(k)));
        wilma.push({ ...f, properties: { kind, ...p } });
      }
    } catch (e) { console.warn(`  WILMA layer ${id} failed: ${e.message}`); }
  }
  await save('odwc_wilma.geojson', wilma.filter(inCounty), { source: WILMA });

  console.log('BLM PLSS CadNSDI townships + sections');
  const PLSS = 'https://gis.blm.gov/arcgis/rest/services/Cadastral/BLM_Natl_PLSS_CadNSDI/MapServer';
  const twp = (await queryAll(`${PLSS}/1`, { ...env, where: '1=1', outFields: 'PLSSID,TWNSHPLAB,PRINMER,TWNSHPNO,TWNSHPDIR,RANGENO,RANGEDIR' })).filter(inCounty);
  await save('plss_townships.geojson', twp, { source: `${PLSS}/1` });
  const twpLab = Object.fromEntries(twp.map(f => [f.properties.PLSSID, f.properties.TWNSHPLAB]));
  const sec = (await queryAll(`${PLSS}/2`, { ...env, where: '1=1', outFields: 'PLSSID,FRSTDIVID,FRSTDIVLAB,FRSTDIVTXT' }))
    .filter(inCounty)
    .map(f => ({ ...f, properties: { ...f.properties, TWNSHPLAB: twpLab[f.properties.PLSSID] || null } }));
  await save('plss_sections.geojson', sec, { source: `${PLSS}/2` });

  console.log('City of Oklahoma City open data: parks, trails, trailheads, trail parking');
  const OKC = 'https://utility.arcgis.com/usrsvcs/servers/1e65b61d07f5458a90d4cfa01e882044/rest/services/OpenData/Recreation_Parks/FeatureServer';
  const okcParks = await queryAll(`${OKC}/4`, { where: '1=1', outFields: 'Name,Address,ParkType,Park_Acres' });
  await save('okc_parks.geojson', okcParks, { source: `${OKC}/4` });
  const okcTrails = await queryAll(`${OKC}/3`, { where: '1=1', outFields: 'TrailName,Status,Rating,DesignUse,Accessible,Motorized,Hike,RoadBike,Mtnbike,Equestrian' });
  const heads = (await queryAll(`${OKC}/1`, { where: '1=1', outFields: 'PointType,Trail' })).map(f => ({ ...f, properties: { kind: 'Trailhead', ...f.properties } }));
  const tpark = (await queryAll(`${OKC}/2`, { where: '1=1', outFields: 'Name,Address' })).map(f => ({ ...f, properties: { kind: 'Trail parking', ...f.properties } }));
  await save('okc_trails.geojson', [...okcTrails.map(f => ({ ...f, properties: { kind: 'Trail', ...f.properties } })), ...heads, ...tpark], { source: `${OKC}/1,2,3` });

  console.log('Done.');
}
main().catch(e => { console.error(e); process.exit(1); });
