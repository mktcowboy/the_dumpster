#!/usr/bin/env node
/**
 * Builds config/area.json — the counties and towns around the center point — from
 * Census TIGERweb 2020 boundaries and 2020 population. Counties are those touching the
 * radius; towns reach PLACE_BUFFER_MI past it so geo.js can rule out addresses in
 * nearby towns that are just outside. Re-run after changing the center or radius:
 *   node scripts/build-area.mjs                        # downtown OKC, 50 mi
 *   node scripts/build-area.mjs --radius 75
 *   node scripts/build-area.mjs --lat 35.22 --lon -97.44 --radius 40
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT  = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT   = path.join(ROOT, 'config', 'area.json');
const TIGER = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer';
const PLACE_BUFFER_MI = 30;

const arg = (name, dflt) => { const i = process.argv.indexOf(`--${name}`); return i > -1 ? Number(process.argv[i + 1]) : dflt; };
const custom = process.argv.includes('--lat') || process.argv.includes('--lon');
const center = { lat: arg('lat', 35.4676), lon: arg('lon', -97.5164), label: custom ? 'Custom center' : 'Downtown Oklahoma City' };
const RADIUS = arg('radius', 50);

// Flat projection in miles around the center — well under 1% error at this scale.
const MI_LAT = 69.0;
const MI_LON = 69.172 * Math.cos(center.lat * Math.PI / 180);
const toXY  = ([lon, lat]) => [(lon - center.lon) * MI_LON, (lat - center.lat) * MI_LAT];
const round1 = n => Math.round(n * 10) / 10;

function haversineMi(lat1, lon1, lat2, lon2) {
  const d = Math.PI / 180;
  const a = Math.sin((lat2 - lat1) * d / 2) ** 2 + Math.cos(lat1 * d) * Math.cos(lat2 * d) * Math.sin((lon2 - lon1) * d / 2) ** 2;
  return 2 * 3958.8 * Math.asin(Math.sqrt(a));
}

function pointInRings([px, py], rings) {
  let inside = false;
  for (const ring of rings) {
    for (let i = 0, k = ring.length - 1; i < ring.length; k = i++) {
      const [xi, yi] = ring[i], [xk, yk] = ring[k];
      if ((yi > py) !== (yk > py) && px < (xk - xi) * (py - yi) / (yk - yi) + xi) inside = !inside;
    }
  }
  return inside;
}

function segmentDist([px, py], [ax, ay], [bx, by]) {
  const dx = bx - ax, dy = by - ay;
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy || 1)));
  return Math.hypot(px - ax - t * dx, py - ay - t * dy);
}

// Miles from the center to the closest part of a polygon (0 if the center is inside it).
function distanceToPolygonMi(rings) {
  if (!rings.length) return Infinity;
  if (pointInRings([0, 0], rings)) return 0;
  let min = Infinity;
  for (const r of rings) for (let i = 1; i < r.length; i++) min = Math.min(min, segmentDist([0, 0], r[i - 1], r[i]));
  return min;
}

// Share of a polygon's area inside the radius, sampled on a 1-mile grid.
function shareInside(rings) {
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const r of rings) for (const [x, y] of r) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
  let total = 0, inside = 0;
  for (let x = x0; x <= x1; x += 1) for (let y = y0; y <= y1; y += 1) {
    if (!pointInRings([x, y], rings)) continue;
    total++;
    if (Math.hypot(x, y) <= RADIUS) inside++;
  }
  return total ? inside / total : 0;
}

async function getJson(url) {
  const res = await fetch(url);
  const text = await res.text();
  let json;
  try { json = JSON.parse(text); } catch { throw new Error(`${res.status} non-JSON from ${url.slice(0, 100)}`); }
  if (json.error) throw new Error(`TIGERweb error: ${JSON.stringify(json.error)}`);
  return json;
}

async function queryLayer(layers, name, reach) {
  const layer = layers.find(l => l.name === name);
  if (!layer) throw new Error(`TIGERweb layer "${name}" not found`);
  const bbox = {
    xmin: center.lon - reach / MI_LON, ymin: center.lat - reach / MI_LAT,
    xmax: center.lon + reach / MI_LON, ymax: center.lat + reach / MI_LAT,
    spatialReference: { wkid: 4326 },
  };
  const params = new URLSearchParams({
    where: '1=1', geometry: JSON.stringify(bbox), geometryType: 'esriGeometryEnvelope', inSR: '4326',
    spatialRel: 'esriSpatialRelIntersects', outFields: '*', returnGeometry: 'true', outSR: '4326',
    maxAllowableOffset: '0.002', f: 'json',
  });
  const { features } = await getJson(`${TIGER}/${layer.id}/query?${params}`);
  return features.map(f => ({ a: f.attributes, rings: (f.geometry?.rings || []).map(r => r.map(toXY)) }));
}

const tierOf = share => share >= 0.8 ? 'core' : share >= 0.05 ? 'partial' : 'sliver';

const { layers } = await getJson(`${TIGER}?f=json`);

const counties = (await queryLayer(layers, 'Counties', RADIUS))
  .map(({ a, rings }) => ({ name: a.NAME, fips: a.GEOID, rings, nearMi: distanceToPolygonMi(rings), share: shareInside(rings), pop2020: a.POP100 ?? null }))
  .filter(c => c.nearMi <= RADIUS)
  .sort((x, y) => y.share - x.share || (y.pop2020 ?? 0) - (x.pop2020 ?? 0));

const places = [];
const placeReach = RADIUS + PLACE_BUFFER_MI;
for (const [layerName, kind] of [['Incorporated Places', 'city/town'], ['Census Designated Places', 'CDP']]) {
  for (const { a, rings } of await queryLayer(layers, layerName, placeReach)) {
    const lat = Number(a.INTPTLAT ?? a.CENTLAT), lon = Number(a.INTPTLON ?? a.CENTLON);
    const nearMi = rings.length ? distanceToPolygonMi(rings) : haversineMi(center.lat, center.lon, lat, lon);
    if (nearMi > placeReach) continue;
    const county = counties.find(c => pointInRings(toXY([lon, lat]), c.rings));
    places.push({
      name: a.BASENAME ?? a.NAME, fips: a.GEOID, kind, county: county?.name ?? null, lat, lon,
      centerMi: round1(haversineMi(center.lat, center.lon, lat, lon)), nearestMi: round1(nearMi),
      touchesRadius: nearMi <= RADIUS, pop2020: a.POP100 ?? null,
    });
  }
}
places.sort((x, y) => (y.pop2020 ?? -1) - (x.pop2020 ?? -1));

const area = {
  generatedAt: new Date().toISOString().slice(0, 10),
  source: 'US Census TIGERweb 2020 boundaries and 2020 population (POP100); built by scripts/build-area.mjs',
  center,
  radiusMi: RADIUS,
  placeBufferMi: PLACE_BUFFER_MI,
  tiers: { core: '80%+ of county land inside radius', partial: '5-80%', sliver: 'under 5%' },
  counties: counties.map(c => ({ name: c.name, fips: c.fips, tier: tierOf(c.share), shareInside: Math.round(c.share * 100) / 100, nearestMi: round1(c.nearMi), pop2020: c.pop2020 })),
  places,
};

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(area, null, 2) + '\n');

const touching = places.filter(p => p.touchesRadius);
console.log(`Wrote ${path.relative(ROOT, OUT)}: ${RADIUS} mi around ${center.label} (${center.lat}, ${center.lon})`);
for (const t of ['core', 'partial', 'sliver']) {
  console.log(`  ${t.padEnd(8)} ${area.counties.filter(c => c.tier === t).map(c => `${c.name.replace(' County', '')} ${Math.round(c.shareInside * 100)}%`).join(', ')}`);
}
console.log(`  ${touching.length} towns/CDPs touch the radius (largest: ${touching.slice(0, 6).map(p => `${p.name} ${p.centerMi} mi`).join(', ')})`);
console.log(`  ${places.length - touching.length} more within ${PLACE_BUFFER_MI} mi past it, kept to rule addresses out`);
