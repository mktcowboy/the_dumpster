/**
 * Canadian County public parcel layer. Query + Extract on
 * ParcelDataService_2_view layer 3. Used to attach assessed value and the
 * assessor's total value to listings already in Canadian County.
 * Owner and mailing fields are not requested and not stored.
 * These figures are assessments, not sale prices. There is no sale-price column.
 */

const fs = require('fs');
const path = require('path');

const QUERY = 'https://services2.arcgis.com/0NjdXxmJp53hZWPd/arcgis/rest/services/ParcelDataService_2_view/FeatureServer/3/query';
const FIELDS = 'situs,situs_city,situs_zip,total_assess,total_val,land_val,bldg_val,parcel_size,parcel_size_units,prop_class';
const CACHE_FILE = path.join(__dirname, '..', 'data', 'assessor-cache.json');

const num = v => {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : null;
};

function streetKey(address) {
  const street = String(address || '').split(',')[0];
  const norm = street.toUpperCase().replace(/[^A-Z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
  return norm.split(' ').slice(0, 3).join(' ');
}

function fromAttributes(attrs) {
  if (!attrs) return null;
  const totalAssessed = num(attrs.total_assess);
  const totalValue = num(attrs.total_val);
  if (totalAssessed == null && totalValue == null) return null;
  return {
    situs: attrs.situs || null,
    city: attrs.situs_city || null,
    zip: attrs.situs_zip || null,
    totalAssessed,
    totalValue,
    landValue: num(attrs.land_val),
    buildingValue: num(attrs.bldg_val),
    parcelSize: attrs.parcel_size ?? null,
    parcelSizeUnits: attrs.parcel_size_units || null,
    propertyClass: attrs.prop_class || null,
    basis: 'Canadian County assessor',
    note: 'County assessment, not a sale price. totalValue is the assessor total value; totalAssessed is the assessed figure. Neither is an arm\'s-length close.',
  };
}

function readCache(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return {}; }
}

async function lookupCanadian(listing, { fetchImpl = fetch, cache, cacheFile = CACHE_FILE } = {}) {
  const city = String(listing.city || '').toUpperCase().replace(/'/g, '');
  const key = streetKey(listing.address);
  if (!city || !/^\d/.test(key)) return null;
  const cacheKey = `${city}|${key}`;
  if (cache && Object.prototype.hasOwnProperty.call(cache, cacheKey)) return cache[cacheKey];
  const where = `situs_city='${city}' AND situs LIKE '${key.replace(/'/g, '')}%'`;
  const url = new URL(QUERY);
  url.searchParams.set('where', where);
  url.searchParams.set('outFields', FIELDS);
  url.searchParams.set('returnGeometry', 'false');
  url.searchParams.set('resultRecordCount', '5');
  url.searchParams.set('f', 'json');
  const res = await fetchImpl(url, { signal: AbortSignal.timeout(30000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json = await res.json();
  if (json.error) throw new Error(json.error.message || 'assessor query failed');
  const features = json.features || [];
  const hit = features.map(f => fromAttributes(f.attributes)).find(Boolean) || null;
  if (cache) {
    cache[cacheKey] = hit;
    fs.mkdirSync(path.dirname(cacheFile), { recursive: true });
    fs.writeFileSync(cacheFile, JSON.stringify(cache));
  }
  return hit;
}

async function enrichCanadian(listings, { fetchImpl = fetch, cacheFile = CACHE_FILE, log = () => {}, sleep = async () => {} } = {}) {
  const cache = readCache(cacheFile);
  let matched = 0;
  let calls = 0;
  for (const listing of listings) {
    if (!/canadian/i.test(listing.county || '')) continue;
    try {
      if (calls) await sleep(200);
      const before = Object.keys(cache).length;
      const hit = await lookupCanadian(listing, { fetchImpl, cache, cacheFile });
      if (Object.keys(cache).length !== before) calls++;
      if (hit) {
        listing.assessor = hit;
        matched++;
      }
    } catch (e) {
      log(`  Canadian assessor lookup failed: ${e.message}`);
    }
  }
  return matched;
}

module.exports = { enrichCanadian, lookupCanadian, fromAttributes, streetKey, FIELDS, QUERY };
