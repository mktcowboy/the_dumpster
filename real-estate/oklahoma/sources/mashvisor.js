/**
 * Mashvisor city listing search. Official API, skipped unless MASHVISOR_API_KEY
 * is set. The listings payload used here has price, size, type, and sometimes
 * last_sale_price. It does not include cap rate or NOI; those stay empty
 * unless a record actually carries them. City-level investment stats are not
 * copied onto individual listings.
 *
 * Docs: https://www.mashvisor.com/api-doc-v2/search
 * Default is one page (100 rows) for each city in MASHVISOR_CITIES, or a
 * short list of larger Oklahoma cities. Header: x-api-key.
 */

const DEFAULT_CITIES = [
  'Oklahoma City', 'Tulsa', 'Norman', 'Edmond', 'Broken Arrow', 'Lawton',
  'Moore', 'Midwest City', 'Enid', 'Stillwater', 'Muskogee', 'Bartlesville',
];

const num = v => {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : null;
};

function normalizeMashvisor(row) {
  if (!row || !row.address) return null;
  if (row.state && String(row.state).toUpperCase() !== 'OK') return null;
  const price = num(row.list_price ?? row.price);
  const cap = row.cap_rate != null ? Number(row.cap_rate) : (row.traditional?.cap_rate != null ? Number(row.traditional.cap_rate) : null);
  const occupancy = row.occupancy != null ? Number(row.occupancy) : (row.traditional?.occupancy != null ? Number(row.traditional.occupancy) : null);
  const lastSale = num(row.last_sale_price);
  return {
    id: `mashvisor-${row.id}`,
    source: 'Mashvisor',
    address: row.address,
    city: row.city || '',
    zip: String(row.zip_code || '').slice(0, 5),
    state: 'OK',
    county: row.county ? (/\bcounty\b/i.test(row.county) ? row.county : `${row.county} County`) : null,
    status: row.status || 'active',
    price,
    openingBid: price,
    beds: row.beds ?? null,
    baths: row.baths ?? null,
    sqft: num(row.sqft),
    lotSqft: num(row.lot_size),
    propertyType: row.type || row.property_type || 'unknown',
    lat: Number.isFinite(Number(row.latitude)) ? Number(row.latitude) : null,
    lon: Number.isFinite(Number(row.longitude)) ? Number(row.longitude) : null,
    distressed: row.is_foreclosure === 1 || row.is_foreclosure === true,
    capRate: Number.isFinite(cap) ? cap : null,
    capRateBasis: Number.isFinite(cap) ? 'source' : null,
    occupancyPct: Number.isFinite(occupancy) ? occupancy : null,
    occupancyBasis: Number.isFinite(occupancy) ? 'source' : null,
    recordedSale: lastSale ? {
      price: lastSale,
      date: null,
      basis: 'source',
      source: 'Mashvisor',
      note: 'Last sale price on the Mashvisor listing record. Not a nearby comparable and not computed by this tracker.',
    } : null,
    url: null,
    scrapedAt: new Date().toISOString(),
    notes: 'Mashvisor listing search',
  };
}

async function fetchMashvisor({ fetchImpl = fetch, env = process.env, log = () => {}, sleep = async () => {} } = {}) {
  const key = env.MASHVISOR_API_KEY;
  if (!key) {
    const err = new Error('MASHVISOR_API_KEY is not set');
    err.skip = true;
    throw err;
  }
  const cities = String(env.MASHVISOR_CITIES || DEFAULT_CITIES.join(','))
    .split(',')
    .map(s => s.trim())
    .filter(Boolean);
  const maxPages = Math.max(1, Number(env.MASHVISOR_MAX_PAGES || 1));
  const pageLimit = Math.min(100, Number(env.MASHVISOR_PAGE_LIMIT || 100));
  const headers = { Accept: 'application/json', 'x-api-key': key };
  const byId = new Map();
  let requests = 0;

  for (const city of cities) {
    for (let page = 1; page <= maxPages; page++) {
      const url = new URL('https://api.mashvisor.com/v1.1/client/city/listings');
      url.searchParams.set('state', 'OK');
      url.searchParams.set('city', city);
      url.searchParams.set('page', String(page));
      url.searchParams.set('page_limit', String(pageLimit));
      if (requests) await sleep(400);
      const res = await fetchImpl(url, { headers, signal: AbortSignal.timeout(30000) });
      requests++;
      if (!res.ok) throw new Error(`Mashvisor HTTP ${res.status} for ${city}`);
      const json = await res.json();
      const rows = json?.content?.properties || json?.properties || [];
      for (const row of rows) {
        const listing = normalizeMashvisor(row);
        if (listing) byId.set(listing.id, listing);
      }
      const totalPages = Number(json?.content?.total_pages || 1);
      if (page >= totalPages || rows.length < pageLimit) break;
    }
  }
  log(`  Mashvisor requests: ${requests}`);
  return [...byId.values()];
}

module.exports = { fetchMashvisor, normalizeMashvisor, DEFAULT_CITIES };
