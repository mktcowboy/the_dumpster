const test   = require('node:test');
const assert = require('node:assert/strict');
const fs     = require('fs');
const os     = require('os');
const path   = require('path');

const { FEEDS, fetchSheriffSales, normalizeSale } = require('../sheriff-feeds');
const { addDistressScore } = require('../server');

const CANADIAN = FEEDS.find(f => f.county === 'Canadian County');
const tmpCache = () => path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'sheriff-test-')), 'cache.json');
const HOUR     = 3600e3;
const NOW      = Date.parse('2026-09-16T15:00:00Z');   // 10:00 in Oklahoma

// Shaped like the live feed; people, firms and addresses are made up.
const ROWS = [
  { sale_id: 101, date: '2026-10-05', status: 'Active',   case: 'CJ-2026-148', address: '123 N Example Ave', city: 'YUKON',   zip: '73099',      appraisal: '150000',     value: '', plantiff: 'Example Bank', defendant: 'DOE, JANE', attorney: 'Example Law', attyPhone: '555-0100', details: 'Lot 1' },
  { sale_id: 102, date: '2026-10-05', status: 'Recalled', case: 'CJ-2026-149', address: '9 W Recalled St',   city: 'El Reno', zip: '73036',      appraisal: '90000',      plantiff: 'Example Bank', defendant: 'DOE, JOHN' },
  { sale_id: 103, date: '2026-09-14', status: 'Active',   case: 'CJ-2026-150', address: '7 S Past Rd',       city: 'Yukon',   zip: '73099',      appraisal: '$80,000.00', plantiff: 'Example Bank', defendant: 'ROE, RICHARD' },
  { sale_id: 104, date: '2026-09-16', status: 'Active',   case: 'CJ-2026-151', address: '5 E Today Dr',      city: 'okarche', zip: '73762-1234', appraisal: '$80,000.00', plantiff: 'Example Credit Union', defendant: 'ROE, RICHARD' },
];

function fakeFetch(body = { allSales: ROWS }, status = 200) {
  const fn = async url => { fn.calls.push(url); return { ok: status === 200, status, json: async () => body }; };
  fn.calls = [];
  return fn;
}

test('keeps active upcoming sales and maps their fields', () => {
  const out = ROWS.map(r => normalizeSale(r, CANADIAN, '2026-09-16'));
  assert.equal(out[1], null, 'recalled');
  assert.equal(out[2], null, 'already held');

  const sale = out[0];
  assert.equal(sale.source, 'County Sheriff');
  assert.equal(sale.saleType, 'sheriff');
  assert.equal(sale.county, 'Canadian County');
  assert.equal(sale.city, 'Yukon');
  assert.equal(sale.zip, '73099');
  assert.equal(sale.auctionDate, '2026-10-05');
  assert.equal(sale.appraisedValue, 150000);
  assert.equal(sale.openingBid, 100000);
  assert.equal(sale.caseNumber, 'CJ-2026-148');
  assert.equal(sale.url, 'https://www.ccsheriff.net/sheriff-sales');

  assert.equal(out[3].auctionDate, '2026-09-16', 'a sale today still shows');
  assert.equal(out[3].zip, '73762');
  assert.equal(out[3].appraisedValue, 80000);
  assert.equal(out[3].openingBid, 53334);
  assert.equal(out[3].city, 'Okarche');
});

test('never stores defendant or attorney details', async () => {
  const cacheFile = tmpCache();
  const listings  = await fetchSheriffSales(CANADIAN, { fetchImpl: fakeFetch(), cacheFile, now: NOW });
  const stored    = fs.readFileSync(cacheFile, 'utf8') + JSON.stringify(listings);
  for (const secret of ['DOE', 'ROE', 'Example Law', '555-0100', 'defendant', 'attorney', 'Lot 1']) {
    assert.ok(!stored.includes(secret), `${secret} was stored`);
  }
});

test('fetches each county at most about once a day', async () => {
  const cacheFile = tmpCache();

  const first = fakeFetch();
  assert.equal((await fetchSheriffSales(CANADIAN, { fetchImpl: first, cacheFile, now: NOW })).length, 2);
  assert.deepEqual(first.calls, ['https://www.ccsheriff.net/dmxConnect/api/SheriffSales/Read.php']);

  const sixHoursLater = fakeFetch();
  assert.equal((await fetchSheriffSales(CANADIAN, { fetchImpl: sixHoursLater, cacheFile, now: NOW + 6 * HOUR })).length, 2);
  assert.equal(sixHoursLater.calls.length, 0);

  const nextDay = fakeFetch({ allSales: ROWS.slice(0, 1) });
  assert.equal((await fetchSheriffSales(CANADIAN, { fetchImpl: nextDay, cacheFile, now: NOW + 21 * HOUR })).length, 1);
  assert.equal(nextDay.calls.length, 1);
});

test('a failing site is retried only after the same ~20 hour wait', async () => {
  const cacheFile = tmpCache();
  await fetchSheriffSales(CANADIAN, { fetchImpl: fakeFetch(), cacheFile, now: NOW });

  const down = fakeFetch({}, 503);
  await fetchSheriffSales(CANADIAN, { fetchImpl: down, cacheFile, now: NOW + 21 * HOUR });
  await fetchSheriffSales(CANADIAN, { fetchImpl: down, cacheFile, now: NOW + 27 * HOUR });
  await fetchSheriffSales(CANADIAN, { fetchImpl: down, cacheFile, now: NOW + 33 * HOUR });
  assert.equal(down.calls.length, 1, 'syncs at +27h and +33h reuse the copy');
  await fetchSheriffSales(CANADIAN, { fetchImpl: down, cacheFile, now: NOW + 42 * HOUR });
  assert.equal(down.calls.length, 2);

  // Cold start: no copy at all, so it errors — but still doesn't retry on the next sync
  const coldCache = tmpCache();
  const cold = fakeFetch({}, 503);
  await assert.rejects(fetchSheriffSales(CANADIAN, { fetchImpl: cold, cacheFile: coldCache, now: NOW }), /no data yet.*HTTP 503/);
  await assert.rejects(fetchSheriffSales(CANADIAN, { fetchImpl: cold, cacheFile: coldCache, now: NOW + HOUR }), /no data yet/);
  assert.equal(cold.calls.length, 1);
});

test('a failed or suspiciously empty response falls back to the last good copy', async () => {
  const twoDaysLater = NOW + 48 * HOUR;   // the 9/16 sale has passed by then

  const failCache = tmpCache();
  await fetchSheriffSales(CANADIAN, { fetchImpl: fakeFetch(), cacheFile: failCache, now: NOW });
  const logs = [];
  const failed = await fetchSheriffSales(CANADIAN, { fetchImpl: fakeFetch({}, 503), cacheFile: failCache, now: twoDaysLater, log: m => logs.push(m) });
  assert.deepEqual(failed.map(l => l.caseNumber), ['CJ-2026-148']);
  assert.ok(failed[0].staleSince, 'marked as a cached copy');
  assert.ok(logs.some(m => m.includes('HTTP 503')));

  const emptyCache = tmpCache();
  await fetchSheriffSales(CANADIAN, { fetchImpl: fakeFetch(), cacheFile: emptyCache, now: NOW });
  const glitch = await fetchSheriffSales(CANADIAN, { fetchImpl: fakeFetch({ allSales: [] }), cacheFile: emptyCache, now: twoDaysLater });
  assert.deepEqual(glitch.map(l => l.caseNumber), ['CJ-2026-148'], 'upcoming sale kept');
  assert.ok(glitch[0].staleSince);

  // Once every cached sale is in the past, an empty list is believed
  const monthLater = NOW + 30 * 24 * HOUR;
  const cleared = await fetchSheriffSales(CANADIAN, { fetchImpl: fakeFetch({ allSales: [] }), cacheFile: emptyCache, now: monthLater });
  assert.equal(cleared.length, 0);
  assert.equal(JSON.parse(fs.readFileSync(emptyCache, 'utf8'))[CANADIAN.site].rows.length, 0);

  await assert.rejects(
    fetchSheriffSales(CANADIAN, { fetchImpl: fakeFetch({ nope: 1 }), cacheFile: tmpCache(), now: NOW }),
    /allSales/,
  );
});

test('sheriff sales are scored without the statutory 2/3 discount', () => {
  const sale = addDistressScore(normalizeSale(ROWS[0], CANADIAN, '2026-09-16'));
  assert.equal(sale.discountPercentage, null);
  assert.equal(sale.score, 35);
});
