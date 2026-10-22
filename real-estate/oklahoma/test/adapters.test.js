const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');

const { parsePayne, normalizePayne, fetchPayneSales } = require('../sources/payne-sheriff');
const { parseMcclain, normalizeMcclain, fetchMcclainSales } = require('../sources/mcclain-sheriff');
const { normalizeRentCast, fetchRentCast } = require('../sources/rentcast');
const { normalizeMashvisor, fetchMashvisor } = require('../sources/mashvisor');
const { extractSale, enrichAttom } = require('../sources/attom');
const { fromAttributes, enrichCanadian, FIELDS } = require('../sources/canadian-assessor');
const { publicListing, textBlocked } = require('../privacy');
const { summarize } = require('../summary');
const crypto = require('crypto');

const tmpCache = () => path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'ok-adapter-')), 'cache.json');
const NOW = Date.parse('2026-10-22T15:00:00Z');

const PAYNE_HTML = `
<table><thead><tr><th>Date</th><th>Case</th><th>Appraisal</th><th>Bid</th><th>Address</th></tr></thead>
<tbody>
<tr><td>11/10/2026</td><td>CJ-2026-1</td><td>$120,000.00</td><td>$80,000.00</td><td>100 Example Ave, Cushing OK 74023</td></tr>
<tr><td>09/01/2026</td><td>CJ-2020-9</td><td>$10,000.00</td><td>$6,667.00</td><td>9 Past Rd, Yale OK 74085</td></tr>
</tbody></table>`;

test('Payne table rows become sheriff listings and past sales drop', () => {
  const rows = parsePayne(PAYNE_HTML);
  assert.equal(rows.length, 2);
  const kept = rows.map(r => normalizePayne(r, '2026-10-22')).filter(Boolean);
  assert.equal(kept.length, 1);
  assert.equal(kept[0].city, 'Cushing');
  assert.equal(kept[0].zip, '74023');
  assert.equal(kept[0].auctionDate, '2026-11-10');
  assert.equal(kept[0].appraisedValue, 120000);
  assert.equal(kept[0].openingBid, 80000);
  assert.equal(kept[0].saleType, 'sheriff');
  assert.equal(kept[0].county, 'Payne County');
});

test('McClain blocks keep the bank plaintiff and drop party names', async () => {
  const html = 'CASE #: CJ-26-1 STATUS: ACTIVE SALE DATE: 12/01/2026 10 AM DESCRIPTION/ADDRESS: 100 Example Ave, Exampletown, OK 73010 APPRAISAL AMOUNT: 120,000.00 PLAINTIFF: Example Bank DEFENDANT: NOTKEPT PERSON ATTORNEY: NOTKEPT LAW';
  const [row] = parseMcclain(html);
  const listing = normalizeMcclain(row, '2026-10-22');
  assert.equal(listing.caseNumber, 'CJ-26-1');
  assert.equal(listing.plaintiff, 'Example Bank');
  assert.equal(listing.appraisedValue, 120000);
  assert.equal(listing.openingBid, 80000);
  assert.equal(listing.city, 'Exampletown');
  const cacheFile = tmpCache();
  const fetchImpl = async () => ({ ok: true, status: 200, text: async () => html });
  const listings = await fetchMcclainSales({ fetchImpl, cacheFile, now: NOW });
  const stored = fs.readFileSync(cacheFile, 'utf8') + JSON.stringify(listings);
  assert.ok(!stored.includes('NOTKEPT'), 'party names were stored');
  assert.equal(listings.length, 1);

  assert.throws(
    () => parseMcclain('<html><meta http-equiv="refresh" content="0;/.well-known/sgcaptcha/?r="></html>'),
    /captcha/,
  );
});

test('Payne fetch is cached for about a day', async () => {
  const cacheFile = tmpCache();
  let calls = 0;
  const fetchImpl = async () => { calls++; return { ok: true, status: 200, text: async () => PAYNE_HTML }; };
  assert.equal((await fetchPayneSales({ fetchImpl, cacheFile, now: NOW })).length, 1);
  await fetchPayneSales({ fetchImpl, cacheFile, now: NOW + 6 * 3600e3 });
  assert.equal(calls, 1);
});

test('RentCast normalizes a sale listing and skips without a key', async () => {
  const listing = normalizeRentCast({
    id: 'abc',
    formattedAddress: '10 Example St, Norman, OK 73069',
    addressLine1: '10 Example St',
    city: 'Norman',
    state: 'OK',
    zipCode: '73069',
    county: 'Cleveland',
    propertyType: 'Single Family',
    bedrooms: 3,
    bathrooms: 2,
    squareFootage: 1800,
    lotSize: 9000,
    yearBuilt: 1998,
    status: 'Active',
    price: 250000,
    listedDate: '2026-10-01T00:00:00.000Z',
    daysOnMarket: 21,
    latitude: 35.22,
    longitude: -97.44,
    listingAgent: { name: 'Agent Name', email: 'agent@example.com' },
  });
  assert.equal(listing.city, 'Norman');
  assert.equal(listing.county, 'Cleveland County');
  assert.equal(listing.sqft, 1800);
  assert.equal(listing.lon, -97.44);
  assert.equal(listing.daysOnMarket, 21);
  const blob = JSON.stringify(listing);
  assert.ok(!blob.includes('Agent Name'));
  assert.ok(!blob.includes('agent@example.com'));

  await assert.rejects(fetchRentCast({ env: {} }), err => err.skip === true);
});

test('Mashvisor keeps a source cap rate and a source last sale, and skips without a key', async () => {
  const withIncome = normalizeMashvisor({
    id: 5,
    address: '5 Example Ave',
    city: 'Tulsa',
    state: 'OK',
    zip_code: '74103',
    county: 'Tulsa',
    type: 'Single Family Residential',
    status: 'active',
    list_price: 300000,
    beds: 3,
    baths: 2,
    sqft: 1600,
    latitude: 36.15,
    longitude: -95.99,
    cap_rate: 6.25,
    occupancy: 95,
    last_sale_price: 210000,
  });
  assert.equal(withIncome.capRate, 6.25);
  assert.equal(withIncome.capRateBasis, 'source');
  assert.equal(withIncome.occupancyPct, 95);
  assert.equal(withIncome.recordedSale.price, 210000);
  assert.equal(withIncome.recordedSale.basis, 'source');

  const bare = normalizeMashvisor({ id: 6, address: '6 Example Ave', city: 'Tulsa', state: 'OK', list_price: 10, type: 'Condo', status: 'active' });
  assert.equal(bare.capRate, null);
  assert.equal(bare.recordedSale, null);
  await assert.rejects(fetchMashvisor({ env: {} }), err => err.skip === true);
});

test('ATTOM stores a sale amount only when the payload has one', async () => {
  assert.equal(extractSale({ property: [{ sale: { saleTransDate: '2024-04-01' } }] }), null);
  const sale = extractSale({ property: [{ sale: { saleAmt: 250000, saleTransDate: '2024-04-01' } }] });
  assert.equal(sale.price, 250000);
  assert.equal(sale.basis, 'source');
  assert.match(sale.note, /Not an MLS close/);

  const listings = [{ address: '10 Example St', city: 'Norman', state: 'OK', zip: '73069' }];
  const skipped = await enrichAttom(listings, { env: {} });
  assert.equal(skipped.skipped, true);
  assert.equal(listings[0].recordedSale, undefined);

  const fetchImpl = async () => ({ ok: true, status: 200, json: async () => ({ property: [{ sale: { saleAmt: 180000, saleTransDate: '2023-01-02' } }] }) });
  const result = await enrichAttom(listings, { env: { ATTOM_API_KEY: 'test-key' }, fetchImpl, sleep: async () => {} });
  assert.equal(result.enriched, 1);
  assert.equal(listings[0].recordedSale.price, 180000);
});

test('Canadian assessor values are assessments, and owner fields are not requested', async () => {
  assert.equal(fromAttributes({ total_assess: 0, total_val: 0, situs: '1 MAIN' }), null);
  const hit = fromAttributes({ situs: '100 EXAMPLE AVE', situs_city: 'YUKON', total_assess: 20000, total_val: 180000, land_val: 40000, parcel_size: 0.2 });
  assert.equal(hit.totalAssessed, 20000);
  assert.equal(hit.totalValue, 180000);
  assert.match(hit.note, /not a sale price/i);
  assert.ok(!FIELDS.toLowerCase().includes('owner'));
  assert.ok(!FIELDS.toLowerCase().includes('mail'));

  const listings = [
    { county: 'Canadian County', address: '100 Example Ave', city: 'Yukon' },
    { county: 'Tulsa County', address: '1 Main St', city: 'Tulsa' },
  ];
  const fetchImpl = async url => {
    fetchImpl.urls.push(String(url));
    return { ok: true, status: 200, json: async () => ({ features: [{ attributes: { situs: '100 EXAMPLE AVE', situs_city: 'YUKON', total_assess: 15000, total_val: 140000 } }] }) };
  };
  fetchImpl.urls = [];
  const n = await enrichCanadian(listings, { fetchImpl, cacheFile: tmpCache(), sleep: async () => {} });
  assert.equal(n, 1);
  assert.equal(listings[0].assessor.totalValue, 140000);
  assert.equal(listings[1].assessor, undefined);
  assert.ok(fetchImpl.urls[0].includes('outFields='));
  assert.ok(!decodeURIComponent(fetchImpl.urls[0]).toLowerCase().includes('owners_name'));
});

test('privacy filter removes party keys and can drop a blocked token without printing it', () => {
  const out = publicListing({ address: '1 Example St', defendant: 'X', attorney: 'Y', plaintiff: 'Example Bank', county: 'Payne County' });
  assert.equal(out.defendant, undefined);
  assert.equal(out.attorney, undefined);
  assert.equal(out.plaintiff, 'Example Bank');
  assert.equal(out.county, 'Payne County');

  const word = 'exampletoken';
  const hash = crypto.createHash('sha256').update(word).digest('hex');
  assert.equal(textBlocked({ address: `1 ${word} st` }, new Set([hash])), true);
  assert.equal(textBlocked({ address: '1 Example St' }, new Set([hash])), false);
});

test('summary medians ignore missing prices and count categories separately from distress', () => {
  const summary = summarize([
    { price: 100000, propertyCategory: 'residential', propertyType: 'single-family', county: 'Tulsa County', city: 'Tulsa', source: 'VRM', distressed: true },
    { price: 300000, propertyCategory: 'residential', propertyType: 'single-family', county: 'Tulsa County', city: 'Tulsa', source: 'VRM', distressed: true },
    { openingBid: 80000, propertyCategory: 'unknown', propertyType: 'unknown', county: 'Payne County', city: 'Cushing', source: 'County Sheriff', distressed: true },
    { propertyCategory: 'land', propertyType: 'land', county: 'Payne County', city: 'Yale', source: 'RentCast', capRate: 8 },
    { removedAt: '2026-01-01', price: 1, propertyCategory: 'residential' },
  ]);
  assert.equal(summary.count, 4);
  assert.equal(summary.offMarket, 1);
  assert.equal(summary.medianPrice, 100000);
  assert.equal(summary.distressed, 3);
  assert.equal(summary.withCapRate, 1);
  assert.equal(summary.byPropertyCategory.find(r => r.key === 'residential').count, 2);
  assert.equal(summary.byCounty.find(r => r.key === 'Payne County').count, 2);
});
