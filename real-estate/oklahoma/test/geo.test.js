const test   = require('node:test');
const assert = require('node:assert/strict');
const fs     = require('fs');
const os     = require('os');
const path   = require('path');

const { AREA, locate, addressParts, parseCsvLine, censusBatch, haversineMi, milesFromCenter } = require('../geo');

const tmpCache = () => path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'geo-test-')), 'cache.json');

// Stands in for the Census geocoder: answers by street, records every call.
function fakeGeocoder(answers) {
  const fn = async rows => {
    fn.calls.push(rows);
    return new Map(rows.map(r => [r.id, answers[r.street] || { status: 'no_match' }]));
  };
  fn.calls = [];
  return fn;
}

const OKC_HOUSE = { status: 'match', exact: true, lat: 35.49735, lon: -97.59983, countyFips: '40109', matchedAddress: '4412 NW 27TH ST, OKLAHOMA CITY, OK, 73107' };

test('area config is the 50-mile circle around downtown OKC', () => {
  assert.equal(AREA.radiusMi, 50);
  assert.ok(Math.abs(AREA.center.lat - 35.4676) < 0.01 && Math.abs(AREA.center.lon + 97.5164) < 0.01);
  const tier = name => AREA.counties.find(c => c.name === name)?.tier;
  assert.equal(tier('Oklahoma County'), 'core');
  assert.equal(tier('Cleveland County'), 'core');
  assert.equal(tier('Payne County'), 'partial');
  assert.equal(tier('Tulsa County'), undefined);
  assert.ok(AREA.places.some(p => p.name === 'Norman' && p.touchesRadius));
  assert.ok(AREA.places.some(p => p.name === 'Eakly' && !p.touchesRadius), 'towns just outside are kept to rule addresses out');
});

test('distances from downtown OKC', () => {
  assert.ok(milesFromCenter(35.46862, -97.52120) < 0.5, 'OKC City Hall');
  const norman = milesFromCenter(35.22102, -97.44321);
  assert.ok(norman > 16 && norman < 19, `Norman ${norman}`);
  const stillwater = milesFromCenter(36.1156, -97.0584);
  assert.ok(stillwater > AREA.radiusMi && stillwater < 55, `Stillwater ${stillwater}`);
  assert.equal(haversineMi(35, -97, 35, -97), 0);
});

test('addressParts splits common address formats', () => {
  const cases = [
    ['4412 NW 27th St, Oklahoma City, OK 73107', { street: '4412 NW 27th St', city: 'Oklahoma City', zip: '73107' }],
    ['4412 NW 27th St, Oklahoma City OK 73107',  { street: '4412 NW 27th St', city: 'Oklahoma City', zip: '73107' }],
    ['101 E Main St, Suite 2, Norman, OK 73069',  { street: '101 E Main St, Suite 2', city: 'Norman', zip: '73069' }],
    ['4412 NW 27th St, OK 73107',                { street: '4412 NW 27th St', city: '', zip: '73107' }],
    ['123 Main St, Apt 4, OK 73107',             { street: '123 Main St, Apt 4', city: '', zip: '73107' }],
    ['123 Main St, Apt 4',                       { street: '123 Main St, Apt 4', city: '', zip: '' }],
    ['4412 NW 27TH ST',                          { street: '4412 NW 27TH ST', city: '', zip: '' }],
    ['73107 N County Line Rd',                   { street: '73107 N County Line Rd', city: '', zip: '' }],
  ];
  for (const [address, want] of cases) {
    const got = addressParts({ address });
    assert.deepEqual({ street: got.street, city: got.city, zip: got.zip }, want, address);
    assert.equal(got.state, 'OK');
  }
  assert.deepEqual(
    addressParts({ address: 'junk', street: '1 A St', city: 'Moore', zip: '73160' }),
    { street: '1 A St', city: 'Moore', state: 'OK', zip: '73160' },
  );
});

test('parseCsvLine handles the Census response format', () => {
  const f = parseCsvLine('"6","101 E Main St, Suite 2, Norman, OK, 73069","Match","Exact","101 E MAIN ST, NORMAN, OK, 73069","-97.443211999974,35.221021499282","99911348","L","40","027","200100","1014"');
  assert.equal(f.length, 12);
  assert.equal(f[4], '101 E MAIN ST, NORMAN, OK, 73069');
  assert.equal(f[5], '-97.443211999974,35.221021499282');
  assert.equal(f[8] + f[9], '40027');
  assert.deepEqual(parseCsvLine('"4","99999 Nowhere, Norman, OK, 73069","No_Match"'), ['4', '99999 Nowhere, Norman, OK, 73069', 'No_Match']);
  assert.deepEqual(parseCsvLine('"a ""quoted"" b",c'), ['a "quoted" b', 'c']);
});

test('locate tags distance, county, and in-area status', async () => {
  const geocode = fakeGeocoder({
    '4412 NW 27th St': OKC_HOUSE,
    '1 Main St':       { status: 'match', exact: true, lat: 36.1156, lon: -97.0584, countyFips: '40119', matchedAddress: '1 MAIN ST, STILLWATER, OK, 74074' },
    '500 W Main St':   { status: 'match', exact: true, lat: 35.2210, lon: -97.4432, countyFips: '40027', matchedAddress: '500 W MAIN ST, NORMAN, OK, 73069' },
  });
  const L = {
    okc:        { address: '4412 NW 27th St, Oklahoma City, OK', county: 'Oklahoma County' },
    stillwater: { address: '1 Main St, Stillwater, OK 74074' },
    courtCase:  { address: 'CJ-2026-1234', county: 'Oklahoma County' },
    wrongPin:   { address: '500 W Main St', county: 'Oklahoma County' },
    nowhere:    { address: '999 Nowhere Rd, Norman, OK' },
    hasCoords:  { address: 'from an API', lat: 35.3273, lon: -96.9253 },
  };
  const summary = await locate(Object.values(L), { geocode, cacheFile: tmpCache() });

  assert.equal(L.okc.geoStatus, 'match');
  assert.equal(L.okc.inArea, true);
  assert.equal(L.okc.county, 'Oklahoma County');
  assert.equal(L.okc.city, 'Oklahoma City');
  assert.equal(L.okc.zip, '73107');
  assert.equal(L.okc.geoApprox, false);
  assert.ok(L.okc.distanceMi > 3 && L.okc.distanceMi < 7, `okc ${L.okc.distanceMi}`);

  assert.equal(L.stillwater.inArea, false);
  assert.equal(L.stillwater.county, 'Payne County');
  assert.ok(L.stillwater.distanceMi > 50);

  assert.equal(L.courtCase.geoStatus, 'no_address');
  assert.equal(L.courtCase.inArea, true, 'Oklahoma County is a core county');
  assert.equal(L.courtCase.areaBasis, 'county');

  assert.equal(L.wrongPin.geoStatus, 'wrong_county');
  assert.equal(L.wrongPin.lat, null);
  assert.equal(L.wrongPin.inArea, true);
  assert.equal(L.wrongPin.county, 'Oklahoma County');

  assert.equal(L.nowhere.geoStatus, 'no_match');
  assert.equal(L.nowhere.areaBasis, 'town', 'unpinned, but Norman is known');
  assert.equal(L.nowhere.inArea, true);

  assert.equal(L.hasCoords.areaBasis, 'distance');
  assert.equal(L.hasCoords.inArea, true);
  assert.equal(L.hasCoords.geoApprox, false);

  assert.equal(geocode.calls.length, 1);
  assert.equal(geocode.calls[0].length, 4, 'court case and pre-located listing are not sent');
  assert.deepEqual(summary, { total: 6, inArea: 5, outOfArea: 1, unknown: 0, byStatus: { match: 3, no_address: 1, wrong_county: 1, no_match: 1 } });
});

test('unplaced addresses fall back to their town, which can rule them out', async () => {
  const listings = [
    { address: '2389 County Road 1262', city: 'Blanchard', county: 'Grady County' },
    { address: '224 S Church St', city: 'EAKLY', county: 'Caddo County' },
    { address: '12 Rural Rd', city: 'Not A Real Town', county: 'Caddo County' },
    { address: '1301 SW C Ave', city: 'Lawton' },
  ];
  await locate(listings, { geocode: fakeGeocoder({}), cacheFile: tmpCache() });
  const [blanchard, eakly, unknownTown, lawton] = listings;

  assert.equal(lawton.areaBasis, 'town');
  assert.equal(lawton.inArea, false, 'all of Lawton is well past the radius');

  assert.equal(blanchard.areaBasis, 'town');
  assert.equal(blanchard.inArea, true);
  assert.equal(blanchard.geoApprox, true);
  assert.equal(blanchard.lat, null, 'not pinned');
  assert.ok(Number.isFinite(blanchard.mapLat) && Number.isFinite(blanchard.mapLon), 'drawn at the town center');
  assert.ok(blanchard.distanceMi > 15 && blanchard.distanceMi < 30, `Blanchard ${blanchard.distanceMi}`);

  assert.equal(eakly.areaBasis, 'town');
  assert.equal(eakly.inArea, null, 'Eakly is ~60 mi out, but an unpinned address is never dropped');
  assert.ok(eakly.distanceMi > 50);

  assert.equal(unknownTown.areaBasis, 'county');
  assert.equal(unknownTown.inArea, null, 'Caddo is a partial county');
});

test('a bare street is geocoded only when its county is known, and flagged approximate', async () => {
  const geocode  = fakeGeocoder({ '4412 NW 27th St': OKC_HOUSE });
  const withCounty = { address: '4412 NW 27th St', county: 'Oklahoma County' };
  const bare       = { address: '100 N Main St' };
  await locate([withCounty, bare], { geocode, cacheFile: tmpCache() });

  assert.equal(withCounty.geoStatus, 'match');
  assert.equal(withCounty.geoApprox, true);
  assert.equal(bare.geoStatus, 'no_address', 'a Main St with no town could be anywhere in Oklahoma');
  assert.equal(bare.inArea, null);
  assert.equal(geocode.calls[0].length, 1);
});

test('locate reuses cached answers and never caches failures', async () => {
  const cacheFile = tmpCache();
  await locate(
    [{ address: '4412 NW 27th St, Oklahoma City, OK' }, { address: '999 Nowhere Rd, Norman, OK' }],
    { geocode: fakeGeocoder({ '4412 NW 27th St': OKC_HOUSE }), cacheFile },
  );

  const second = fakeGeocoder({});
  const again  = [{ address: '4412 NW 27TH ST,  Oklahoma City, OK' }, { address: '999 Nowhere Rd, Norman, OK' }];
  await locate(again, { geocode: second, cacheFile });
  assert.equal(second.calls.length, 0, 'match and recent miss both come from cache');
  assert.equal(again[0].inArea, true);

  const logs  = [];
  const fresh = [{ address: '7 New St, Moore, OK', county: 'Cleveland County' }, { address: '8 New St' }];
  await locate(fresh, { geocode: async () => { throw new Error('HTTP 503'); }, cacheFile, log: m => logs.push(m) });
  assert.equal(fresh[0].geoStatus, 'error');
  assert.equal(fresh[0].inArea, true, 'falls back to its town');
  assert.equal(fresh[1].inArea, null, 'no town or county to fall back on');
  assert.ok(logs.some(m => m.includes('HTTP 503')));
  const keys = Object.keys(JSON.parse(fs.readFileSync(cacheFile, 'utf8')));
  assert.ok(!keys.some(k => k.startsWith('7 NEW ST') || k.startsWith('8 NEW ST')), 'failures must not be cached');
});

test('unmatched addresses are retried after a week', async () => {
  const cacheFile = tmpCache();
  const listing = () => [{ address: '999 Nowhere Rd, Norman, OK' }];
  await locate(listing(), { geocode: fakeGeocoder({}), cacheFile });

  const cache = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
  for (const v of Object.values(cache)) v.at -= 8 * 24 * 60 * 60 * 1000;
  fs.writeFileSync(cacheFile, JSON.stringify(cache));

  const retry = fakeGeocoder({});
  await locate(listing(), { geocode: retry, cacheFile });
  assert.equal(retry.calls.length, 1);
});

test('county names match with or without "County"; latitude/longitude fields count', async () => {
  const listings = [
    { address: 'CJ-2026-1', county: 'Canadian' },
    { address: '4412 NW 27th St, Oklahoma City, OK', county: 'oklahoma county' },
    { address: 'from an API', latitude: 35.3273, longitude: -96.9253 },
  ];
  const geocode = fakeGeocoder({ '4412 NW 27th St': OKC_HOUSE });
  await locate(listings, { geocode, cacheFile: tmpCache() });
  assert.equal(listings[0].county, 'Canadian County');
  assert.equal(listings[0].inArea, true);
  assert.equal(listings[1].geoStatus, 'match');
  assert.equal(listings[1].county, 'Oklahoma County');
  assert.equal(listings[2].areaBasis, 'distance');
  assert.equal(geocode.calls[0].length, 1);
});

test('live: Census batch geocoder (run with GEO_LIVE=1)', { skip: !process.env.GEO_LIVE }, async () => {
  const r = await censusBatch([
    { id: '1', street: '200 N Walker Ave', city: 'Oklahoma City', state: 'OK', zip: '73102' },
    { id: '2', street: '99999 Nowhere Fake Blvd', city: 'Norman', state: 'OK', zip: '73069' },
  ]);
  assert.equal(r.get('1').status, 'match');
  assert.equal(r.get('1').countyFips, '40109');
  assert.ok(milesFromCenter(r.get('1').lat, r.get('1').lon) < 1);
  assert.equal(r.get('2').status, 'no_match');
});
