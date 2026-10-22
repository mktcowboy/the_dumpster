const test   = require('node:test');
const assert = require('node:assert/strict');
const fs     = require('fs');
const os     = require('os');
const path   = require('path');

const { locateAndScore, addDistressScore, normalizeB4A } = require('../server');

const quiet    = () => {};
const tmpCache = () => path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'pipeline-test-')), 'cache.json');

test('Bid4Assets page text is not mistaken for an address', () => {
  // Rows the June 2026 scrape produced from page chrome (party name replaced)
  const junk = [
    '6 days Your Bid Status Log in to view status',
    '1105 Attorney The Mortgage Law Firm Defendant DOE JOHN Plaintiff Midfirst Bank',
    '2026 Show Available Auctions Only Sales Date Select Sales Date',
    '2026 Download Property List',
  ];
  for (const address of junk) assert.equal(normalizeB4A({ address }), null, address);

  for (const address of ['4412 NW 27TH ST', '2801 FIREWHEEL RD', '5136 SE 51ST ST', '3934 N POST RD']) {
    assert.equal(normalizeB4A({ address })?.address, address);
  }
  assert.equal(normalizeB4A({ address: '367 4412 NW 27TH ST' })?.address, '4412 NW 27TH ST', 'leading lot number is stripped');
});

test('sheriff-sale score ignores the statutory 2/3 discount', () => {
  const estimated = addDistressScore(normalizeB4A({ address: '4412 NW 27TH ST', openingBid: '66,667' }));
  assert.equal(estimated.appraisedValueBasis, 'opening-bid-times-1.5');
  assert.equal(estimated.discountPercentage, null);
  assert.equal(estimated.score, 35, 'status + source only');

  const sourced = addDistressScore(normalizeB4A({ address: '4412 NW 27TH ST', openingBid: '66,667', appraised: '100,000' }));
  assert.equal(sourced.discountPercentage, null, 'the 2/3 rule is not shown as a discount');
  assert.equal(sourced.score, 35, 'the 2/3 rule is not a deal signal');

  const reo = addDistressScore({ source: 'Hubzu', status: 'reo', openingBid: 60000, appraisedValue: 100000 });
  assert.equal(reo.discountPercentage, 40);
  assert.equal(reo.score, 83, '48 discount + 25 status + 10 source');
});

test('locateAndScore drops confirmed out-of-area listings and keeps ones it cannot place', async () => {
  const geocode = async rows => new Map(rows.map(r => [r.id,
    r.street === '4412 NW 27TH ST'
      ? { status: 'match', exact: true, lat: 35.49735, lon: -97.59983, countyFips: '40109', matchedAddress: '4412 NW 27TH ST, OKLAHOMA CITY, OK, 73107' }
      : r.street === '1 Main St'
        ? { status: 'match', exact: true, lat: 36.1156, lon: -97.0584, countyFips: '40119', matchedAddress: '1 MAIN ST, STILLWATER, OK, 74074' }
        : { status: 'no_match' },
  ]));

  const out = await locateAndScore([
    normalizeB4A({ address: '4412 NW 27TH ST' }),
    { id: 'a', source: 'Hubzu', status: 'reo', address: '1 Main St, Stillwater, OK 74074', scrapedAt: 'x' },
    { id: 'b', source: 'Hubzu', status: 'reo', address: '77 Unknown Ln', scrapedAt: 'x' },
    { id: 'c', source: 'Hubzu', status: 'reo', address: '', scrapedAt: 'x' },
  ], { geocode, cacheFile: tmpCache(), log: quiet });

  assert.deepEqual(out.map(l => l.address), ['4412 NW 27TH ST', '77 Unknown Ln']);
  assert.equal(out[0].county, 'Oklahoma County');
  assert.equal(out[0].city, 'Oklahoma City');
  assert.equal(out[0].geoApprox, true, 'Bid4Assets gives a street only');
  assert.equal(out[1].inArea, null);
  assert.ok(out.every(l => 'score' in l));
});
