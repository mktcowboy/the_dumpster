/**
 * Location filter — geocodes listings with the free Census batch geocoder,
 * measures miles from the center point in config/area.json, and tags each
 * listing with lat/lon, county, distance, and whether it's inside the radius.
 */

const fs   = require('fs');
const path = require('path');

const AREA_FILE        = path.join(__dirname, 'config', 'area.json');
const CACHE_FILE       = path.join(__dirname, 'data', 'geocode-cache.json');
const CENSUS_BATCH_URL = 'https://geocoding.geo.census.gov/geocoder/geographies/addressbatch';
const BATCH_SIZE       = 1000;                       // Census allows up to 10,000 rows per request
const RETRY_MISS_MS    = 7 * 24 * 60 * 60 * 1000;    // re-try unmatched addresses after a week
const FAR_TOWN_MARGIN_MI = 10;                       // an unpinned address in a town this far past the radius is out

let AREA;
try { AREA = JSON.parse(fs.readFileSync(AREA_FILE, 'utf8')); }
catch (e) { throw new Error(`Can't read config/area.json (${e.message}). Build it with: npm run build-area`); }

// Sources name counties either way ("Oklahoma" or "Oklahoma County") and write towns in any case.
const countyKey      = name => String(name || '').toLowerCase().replace(/\s+county$/, '').trim();
const placeKey       = name => String(name || '').toLowerCase().replace(/[^a-z]/g, '');
const COUNTY_BY_FIPS = new Map(AREA.counties.map(c => [c.fips, c]));
const COUNTY_BY_NAME = new Map(AREA.counties.map(c => [countyKey(c.name), c]));
const OK_COUNTIES    = JSON.parse(fs.readFileSync(path.join(__dirname, 'config', 'ok-counties.json'), 'utf8'));

// Area counties keep their tier. Any other Oklahoma county is named from the statewide
// FIPS table and treated as outside the radius (tier "outside"), so a Tulsa pin is kept
// and labeled rather than left with a blank county.
function countyRecord(fips) {
  if (!fips) return null;
  const known = COUNTY_BY_FIPS.get(fips);
  if (known) return known;
  const name = OK_COUNTIES[fips];
  return name ? { name, fips, tier: 'outside' } : null;
}
const PLACE_BY_NAME  = new Map();
for (const p of AREA.places || []) {   // sorted largest first, so the bigger town wins a shared name
  if (!PLACE_BY_NAME.has(placeKey(p.name))) PLACE_BY_NAME.set(placeKey(p.name), p);
}

// ─── Distance ────────────────────────────────────────────────────────────────

function haversineMi(lat1, lon1, lat2, lon2) {
  const d = Math.PI / 180;
  const a = Math.sin((lat2 - lat1) * d / 2) ** 2 +
            Math.cos(lat1 * d) * Math.cos(lat2 * d) * Math.sin((lon2 - lon1) * d / 2) ** 2;
  return 2 * 3958.8 * Math.asin(Math.sqrt(a));
}

function milesFromCenter(lat, lon) {
  return haversineMi(AREA.center.lat, AREA.center.lon, lat, lon);
}

// ─── Address parsing ─────────────────────────────────────────────────────────

const ZIP_RE      = /\b(7[34]\d{3})(?:-\d{4})?\b/;
const STATE_END   = /\b(?:OK|OKLA\.?|OKLAHOMA)$/i;
const UNIT_RE     = /^(?:apt|unit|suite|ste|lot|#)/i;
const HOUSE_NO_RE = /^\d+[A-Z]?\s+\S/i;

/**
 * Street / city / state / ZIP for a listing. Explicit fields from a scraper win;
 * otherwise parses strings like "4412 NW 27th St, Oklahoma City, OK 73107".
 */
function addressParts(listing) {
  const parts = String(listing.address || '').replace(/\s+/g, ' ').split(',').map(s => s.trim()).filter(Boolean);
  let street = parts.join(', '), city = '', zip = '';
  if (parts.length > 1) {
    const tail     = parts[parts.length - 1];
    const tailCity = tail.replace(ZIP_RE, '').trim().replace(STATE_END, '').trim();
    zip = (tail.match(ZIP_RE) || [])[1] || '';
    if (tailCity && !UNIT_RE.test(tailCity)) {
      city   = tailCity;
      street = parts.slice(0, -1).join(', ');
    } else if (!tailCity) {
      const prev = parts.length > 2 ? parts[parts.length - 2] : '';
      city   = UNIT_RE.test(prev) ? '' : prev;
      street = parts.slice(0, city ? -2 : -1).join(', ');
    }
  }
  return {
    street: listing.street || street,
    city:   listing.city   || city,
    state:  listing.state  || 'OK',
    zip:    listing.zip    || zip,
  };
}

const norm      = s => String(s || '').toUpperCase().replace(/[^\w# ]+/g, ' ').replace(/\s+/g, ' ').trim();
const cacheKey  = p => [p.street, p.city, p.state, p.zip].map(norm).join('|');
const titleCase = s => s.toLowerCase().replace(/\b\w/g, c => c.toUpperCase());

// ─── Census batch geocoder ───────────────────────────────────────────────────

const csvField = s => `"${String(s ?? '').replace(/"/g, '""')}"`;

function parseCsvLine(line) {
  const fields = [];
  let cur = '', quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (ch === '"') quoted = false;
      else cur += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { fields.push(cur); cur = ''; }
    else cur += ch;
  }
  fields.push(cur);
  return fields;
}

/**
 * Geocodes rows [{ id, street, city, state, zip }] in one request. Returns
 * Map(id → { status: 'match' | 'no_match' | 'tie', lat, lon, exact, matchedAddress, countyFips }).
 * Rows missing from the response are left out so callers don't cache them.
 */
async function censusBatch(rows) {
  const csv  = rows.map(r => [r.id, r.street, r.city, r.state, r.zip].map(csvField).join(',')).join('\n');
  const form = new FormData();
  form.append('addressFile', new Blob([csv], { type: 'text/csv' }), 'addresses.csv');
  form.append('benchmark', 'Public_AR_Current');
  form.append('vintage', 'Current_Current');

  const res = await fetch(CENSUS_BATCH_URL, { method: 'POST', body: form, signal: AbortSignal.timeout(180000) });
  if (!res.ok) throw new Error(`Census geocoder HTTP ${res.status}`);

  const results = new Map();
  for (const line of (await res.text()).split(/\r?\n/)) {
    if (!line.trim()) continue;
    // id, input, Match|No_Match|Tie, Exact|Non_Exact, matched address, "lon,lat", tiger id, side, state, county, tract, block
    const [id, , status, matchType, matchedAddress, coords = '', , , stateFips, countyFips] = parseCsvLine(line);
    if (status === 'No_Match' || status === 'Tie') { results.set(id, { status: status === 'Tie' ? 'tie' : 'no_match' }); continue; }
    if (status !== 'Match') continue;
    const [lon, lat] = coords.split(',').map(Number);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
    results.set(id, { status: 'match', lat, lon, exact: matchType === 'Exact', matchedAddress, countyFips: `${stateFips}${countyFips}` });
  }
  if (rows.length && !results.size) throw new Error('Census geocoder returned no readable rows');
  return results;
}

// ─── Locate listings ─────────────────────────────────────────────────────────

function readJson(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return {}; }
}

/**
 * Tags each listing in place with lat, lon, county, distanceMi, inArea, areaBasis,
 * geoStatus, and geoApprox, and fills city/zip from the geocoder match.
 * areaBasis says how inArea was decided: 'distance' (pinned address), 'town' (address
 * not pinned; distance to its town's center, and in-area if the town touches the
 * radius), or 'county' (no town either; core counties count as in, slivers as out).
 * inArea is null when we can't tell — callers should drop only inArea === false so
 * unplaced listings stay visible for review.
 */
async function locate(listings, { geocode = censusBatch, cacheFile = CACHE_FILE, log = () => {} } = {}) {
  const cache   = readJson(cacheFile);
  const now     = Date.now();
  const pending = new Map();

  const jobs = listings.map(listing => {
    const srcLat = listing.lat ?? listing.latitude, srcLon = listing.lon ?? listing.longitude;
    if (Number.isFinite(srcLat) && Number.isFinite(srcLon)) {
      return { listing, geo: { status: 'match', lat: srcLat, lon: srcLon } };
    }
    const parts = addressParts(listing);
    // A bare street with no city, ZIP, or known county could match that street anywhere in the state.
    const anchored = parts.city || parts.zip || COUNTY_BY_NAME.has(countyKey(listing.county));
    if (!HOUSE_NO_RE.test(parts.street) || !anchored) return { listing, parts, geo: { status: 'no_address' } };
    const key   = cacheKey(parts) + (parts.city || parts.zip ? '' : `|${countyKey(listing.county)}`);
    const hit   = cache[key];
    const stale = hit && hit.status !== 'match' && now - hit.at > RETRY_MISS_MS;
    if (!hit || stale) pending.set(key, parts);
    return { listing, parts, key };
  });

  const keys = [...pending.keys()];
  let dirty = false;
  for (let i = 0; i < keys.length; i += BATCH_SIZE) {
    const chunk = keys.slice(i, i + BATCH_SIZE);
    try {
      const results = await geocode(chunk.map((key, n) => ({ id: String(n), ...pending.get(key) })));
      chunk.forEach((key, n) => {
        const r = results.get(String(n));
        if (r) { cache[key] = { ...r, at: now }; dirty = true; }
      });
    } catch (e) {
      log(`  Geocoder failed for ${chunk.length} addresses: ${e.message}`);
    }
  }
  if (dirty) {
    fs.mkdirSync(path.dirname(cacheFile), { recursive: true });
    fs.writeFileSync(cacheFile, JSON.stringify(cache));
  }

  const summary = { total: listings.length, inArea: 0, outOfArea: 0, unknown: 0, byStatus: {} };
  for (const job of jobs) {
    const { listing, parts } = job;
    const geo          = job.geo || cache[job.key] || { status: 'error' };
    const sourceCounty = COUNTY_BY_NAME.get(countyKey(listing.county)) || null;
    let status = geo.status, lat = null, lon = null, county = sourceCounty;

    if (geo.status === 'match') {
      if (sourceCounty && geo.countyFips && geo.countyFips !== sourceCounty.fips) {
        status = 'wrong_county';   // same street name in another county — trust the source's county, not the pin
      } else {
        lat = geo.lat;
        lon = geo.lon;
        county = countyRecord(geo.countyFips) || sourceCounty;
      }
    }

    let distanceMi = lat == null ? null : Math.round(milesFromCenter(lat, lon) * 10) / 10;
    let inArea = null, areaBasis = null;
    const town = distanceMi == null ? PLACE_BY_NAME.get(placeKey(listing.city || parts?.city)) : null;
    if (distanceMi != null) {
      inArea = distanceMi <= AREA.radiusMi;
      areaBasis = 'distance';
    } else if (town) {
      // Not pinned, so only rule it out when the whole town is well past the radius
      // (e.g. Lawton); edge towns stay unknown for review.
      distanceMi = town.centerMi;
      inArea = town.centerMi <= AREA.radiusMi ? true
             : town.nearestMi > AREA.radiusMi + FAR_TOWN_MARGIN_MI ? false
             : null;
      areaBasis = 'town';
    } else if (county) {
      inArea = county.tier === 'core' ? true : null;
      areaBasis = 'county';
    }

    if (status === 'match' && geo.matchedAddress) {
      const m = geo.matchedAddress.split(',').map(s => s.trim());   // "STREET, CITY, OK, ZIP"
      if (!listing.city && m.length >= 4) listing.city = titleCase(m[m.length - 3]);
      if (!listing.zip && m.length >= 4)  listing.zip  = m[m.length - 1];
    }

    Object.assign(listing, {
      lat, lon, distanceMi, inArea, areaBasis,
      // Where to draw it on the map: the pin, or the town center when only the town is known
      mapLat: lat ?? (areaBasis === 'town' ? town.lat : null),
      mapLon: lon ?? (areaBasis === 'town' ? town.lon : null),
      county:    county ? county.name : (listing.county || null),
      geoStatus: status,
      geoApprox: areaBasis === 'town' ||
                 (status === 'match' && !!job.key && (geo.exact === false || !(parts.city || parts.zip))),
    });

    summary.byStatus[status] = (summary.byStatus[status] || 0) + 1;
    if (inArea === true) summary.inArea++;
    else if (inArea === false) summary.outOfArea++;
    else summary.unknown++;
  }
  return summary;
}

/** A town from config/area.json by name (towns reach 30 mi past the radius), or null. */
const townFor = name => PLACE_BY_NAME.get(placeKey(name)) || null;

module.exports = { AREA, locate, townFor, addressParts, parseCsvLine, censusBatch, haversineMi, milesFromCenter };
