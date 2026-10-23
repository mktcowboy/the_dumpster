/**
 * RentCast sale listings. Official API, skipped unless RENTCAST_API_KEY is set.
 * Coverage is residential, small multifamily, apartments, and land. It does not
 * include office, retail, or industrial, and the sale-listing schema has no
 * cap rate or NOI. Agent and office contact fields are not stored.
 *
 * Docs: https://developers.rentcast.io/reference/sale-listings
 * Each property type is one request (limit 500). RENTCAST_MAX_REQUESTS caps
 * the run (default 7, one per type). A free tier can be exhausted by a
 * statewide pull; raise the cap only when the key's quota allows it.
 */

const crypto = require('crypto');

const TYPES = ['Single Family', 'Condo', 'Townhouse', 'Manufactured', 'Multi-Family', 'Apartment', 'Land'];
const ENDPOINT = 'https://api.rentcast.io/v1/listings/sale';

const hid = value => crypto.createHash('md5').update(String(value)).digest('hex').slice(0, 12);
const num = v => {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : null;
};

function normalizeRentCast(row) {
  if (!row || String(row.state || '').toUpperCase() !== 'OK') return null;
  const street = row.addressLine1 || row.formattedAddress || '';
  if (!street) return null;
  const county = row.county ? (/\bcounty\b/i.test(row.county) ? row.county : `${row.county} County`) : null;
  return {
    id: `rentcast-${hid(row.id || street)}`,
    source: 'RentCast',
    address: street,
    city: row.city || '',
    zip: String(row.zipCode || '').slice(0, 5),
    state: 'OK',
    county,
    status: row.status || 'Active',
    price: num(row.price),
    openingBid: num(row.price),
    beds: row.bedrooms ?? null,
    baths: row.bathrooms ?? null,
    sqft: num(row.squareFootage),
    lotSqft: num(row.lotSize),
    yearBuilt: num(row.yearBuilt),
    daysOnMarket: row.daysOnMarket ?? null,
    listedDate: row.listedDate || null,
    propertyType: row.propertyType || 'unknown',
    lat: Number.isFinite(Number(row.latitude)) ? Number(row.latitude) : null,
    lon: Number.isFinite(Number(row.longitude)) ? Number(row.longitude) : null,
    url: row.url || null,
    scrapedAt: new Date().toISOString(),
    notes: 'RentCast sale listing',
  };
}

async function fetchRentCast({ fetchImpl = fetch, env = process.env, log = () => {}, sleep = async () => {} } = {}) {
  const key = env.RENTCAST_API_KEY;
  if (!key) {
    const err = new Error('RENTCAST_API_KEY is not set');
    err.skip = true;
    throw err;
  }
  const max = Number(env.RENTCAST_MAX_REQUESTS || TYPES.length);
  const limit = Math.min(500, Number(env.RENTCAST_PAGE_LIMIT || 500));
  const headers = { Accept: 'application/json', 'X-Api-Key': key };
  const byId = new Map();
  let requests = 0;

  for (const propertyType of TYPES) {
    if (requests >= max) break;
    let offset = 0;
    for (;;) {
      if (requests >= max) break;
      const url = new URL(ENDPOINT);
      url.searchParams.set('state', 'OK');
      url.searchParams.set('propertyType', propertyType);
      url.searchParams.set('status', 'Active');
      url.searchParams.set('limit', String(limit));
      url.searchParams.set('offset', String(offset));
      if (requests) await sleep(400);
      const res = await fetchImpl(url, { headers, signal: AbortSignal.timeout(30000) });
      requests++;
      if (!res.ok) throw new Error(`RentCast HTTP ${res.status} for ${propertyType}`);
      const json = await res.json();
      const rows = Array.isArray(json) ? json : (json.listings || json.data || []);
      for (const row of rows) {
        const listing = normalizeRentCast(row);
        if (listing) byId.set(listing.id, listing);
      }
      if (rows.length < limit) break;
      offset += rows.length;
    }
  }
  log(`  RentCast requests: ${requests}`);
  return [...byId.values()];
}

module.exports = { fetchRentCast, normalizeRentCast, TYPES };
