/**
 * ATTOM sale snapshot, used only as enrichment. Skipped unless ATTOM_API_KEY
 * is set. This is not a for-sale feed: the property API returns assessment and
 * deed history, not statewide MLS inventory. A sale amount is stored only when
 * the response includes one. Documentary-stamp math is not applied.
 *
 * Endpoint: GET https://api.gateway.attomdata.com/propertyapi/v1.0.0/sale/snapshot
 * Header: APIKey. ATTOM_MAX caps address lookups per sync (default 25).
 */

const num = v => {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : null;
};

function extractSale(json) {
  const property = Array.isArray(json?.property) ? json.property[0] : json?.property;
  const sale = property?.sale || (Array.isArray(property?.saleHistory) ? property.saleHistory[0] : null);
  const price = num(sale?.saleAmt ?? sale?.amount?.saleamt ?? sale?.saleAmount);
  if (price == null) return null;
  return {
    price,
    date: sale.saleTransDate || sale.saleSearchDate || sale.saleRecDate || null,
    basis: 'source',
    source: 'ATTOM',
    note: 'Sale amount returned by ATTOM for this address. Not an MLS close, and not derived from documentary stamps by this tracker.',
  };
}

async function enrichAttom(listings, { fetchImpl = fetch, env = process.env, log = () => {}, sleep = async () => {}, max } = {}) {
  const key = env.ATTOM_API_KEY;
  if (!key) return { skipped: true, enriched: 0, calls: 0 };
  const cap = max ?? Number(env.ATTOM_MAX || 25);
  let enriched = 0;
  let calls = 0;
  for (const listing of listings) {
    if (calls >= cap) break;
    if (num(listing.recordedSale?.price)) continue;
    const address1 = String(listing.address || '').split(',')[0].trim();
    const city = listing.city || '';
    if (!address1 || !city) continue;
    const url = new URL('https://api.gateway.attomdata.com/propertyapi/v1.0.0/sale/snapshot');
    url.searchParams.set('address1', address1);
    url.searchParams.set('address2', [city, listing.state || 'OK', listing.zip || ''].filter(Boolean).join(', '));
    if (calls) await sleep(250);
    const res = await fetchImpl(url, {
      headers: { Accept: 'application/json', APIKey: key },
      signal: AbortSignal.timeout(30000),
    });
    calls++;
    if (res.status === 401 || res.status === 403) throw new Error(`ATTOM HTTP ${res.status}`);
    if (!res.ok) continue;
    const sale = extractSale(await res.json());
    if (sale) {
      listing.recordedSale = sale;
      enriched++;
    }
  }
  log(`  ATTOM lookups: ${calls}`);
  return { skipped: false, enriched, calls };
}

module.exports = { enrichAttom, extractSale };
