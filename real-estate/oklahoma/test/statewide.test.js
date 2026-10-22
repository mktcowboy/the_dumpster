const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { prepareStatewide } = require('../server');
const { fetchVrm } = require('../vrm');

const tmpCache = () => path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'ok-state-')), 'cache.json');

test('prepareStatewide keeps a Tulsa listing and names the county', async () => {
  const geocode = async rows => new Map(rows.map(r => [r.id, {
    status: 'match',
    exact: true,
    lat: 36.154,
    lon: -95.9928,
    countyFips: '40143',
    matchedAddress: '1 MAIN ST, TULSA, OK, 74103',
  }]));
  const out = await prepareStatewide([
    {
      id: 't',
      source: 'VRM',
      status: 'reo',
      address: '1 Main St, Tulsa, OK 74103',
      scrapedAt: 'x',
      beds: 3,
      sqft: 1500,
      openingBid: 200000,
      propertyType: 'SFR',
    },
  ], { geocode, cacheFile: tmpCache(), log: () => {}, now: Date.parse('2026-10-22T15:00:00Z') });

  assert.equal(out.length, 1);
  assert.equal(out[0].inArea, false);
  assert.equal(out[0].county, 'Tulsa County');
  assert.equal(out[0].propertyCategory, 'residential');
  assert.equal(out[0].propertyType, 'single-family');
  assert.equal(out[0].distressed, true);
  assert.equal(out[0].price, 200000);
  assert.equal(out[0].pricePerSqft, 133.33);
  assert.equal(out[0].capRate, null);
});

test('VRM statewide keeps towns outside the Oklahoma City radius', async () => {
  const { parseListingsPage } = require('../vrm');
  assert.equal(typeof parseListingsPage, 'function');
  const card = city => `
<div class="prop-card-container">
<a href="/Property-For-Sale/9/1-main-${city}-ok-74103"></a>
<div class="property-status">For Sale</div>
<h6 class="card-subtitle">$100,000</h6>
<p class="card-text specs"><span>3&nbsp;<i title="Beds"></i></span><span>2&nbsp;<i title="Baths"></i></span><span>1,200&nbsp;<i title="Sqr. Feet"></i></span></p>
<p class="card-text properCase">1 main st<br>${city}, OK 74103</p>
</div>`;
  const html = `<html><body>${card('tulsa')}</body></html>`;
  const fetchImpl = async () => ({ ok: true, status: 200, text: async () => html });
  const areaOnly = await fetchVrm({ fetchImpl, sleep: async () => {}, cacheFile: tmpCache(), now: Date.parse('2026-10-22T15:00:00Z') });
  const statewide = await fetchVrm({ fetchImpl, sleep: async () => {}, cacheFile: tmpCache(), now: Date.parse('2026-10-22T15:00:00Z'), statewide: true });
  assert.equal(areaOnly.length, 0);
  assert.equal(statewide.length, 1);
  assert.equal(statewide[0].city, 'Tulsa');
});
