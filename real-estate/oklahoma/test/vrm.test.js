const test   = require('node:test');
const assert = require('node:assert/strict');
const fs     = require('fs');
const os     = require('os');
const path   = require('path');

const { fetchVrm, parseListingsPage, normalizeVrm } = require('../vrm');

const tmpCache = () => path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'vrm-test-')), 'cache.json');
const NOW      = Date.parse('2026-09-16T15:00:00Z');
const noSleep  = async () => {};

// Card markup as served by vrmproperties.com (Sep 2026); addresses are made up.
function card({ id, street, city, zip, price = '79,750', status = 'For Sale', beds = '3', baths = '2', sqft = '1,999', vendee = true }) {
  return `
<div class="col col-xl-3 col-lg-4 col-md-6 col-sm-6 col-xs-12 mb-4 prop-card-container">
<div class="card">
<a href="/Property-For-Sale/${id}/${street.replace(/ /g, '-')}-${city}-ok-${zip}">
<div class="img-ratio img-fallback"><img class="img-fit" alt="Photo" src="https://media.vrmproperties.com/media/x"></div>
</a>
<div class="card-body">
${vendee ? '<img class="special-fin" src="/css/images/vendee_horz_white.png" alt="Property May Be Eligible for Vendee Financing">' : ''}
<div class="row"><div class="col-12">
<div class="d-flex align-items-center property-status"><i class="fa text-xs fa-circle color-active mr-1"></i> ${status}</div>
<h6 class="card-subtitle">$${price} <span class="price-suffix"><i class="fa text-xs  color-active mr-1"></i></span></h6>
<div class="d-flex justify-content-between">
<p class="card-text specs">
<span class="font-weight-bold d-inline-block mr-4">${beds}&nbsp;<i class="fas fa-bed" title="Beds"></i></span>
<span class="font-weight-bold d-inline-block mr-2">
${baths}&nbsp;<i class="fas fa-bath" title="Baths"></i>
</span>
<span class="font-weight-bold d-inline-block mr-4">
${sqft}&nbsp;<i class="fas fa-ruler-triangle" title="Sqr. Feet"></i>
</span>
</p>
</div>
<p class="card-text properCase">${street}  <br />${city}, OK  ${zip}</p>
</div></div>
</div>
</div>
</div>`;
}
const page = cards => `<html><body><div id="listings" class="row">${cards.join('')}</div><footer>…</footer></body></html>`;

test('parses VRM property cards', () => {
  const [a, b] = parseListingsPage(page([
    card({ id: '30175', street: '8541 sw 107th st', city: 'oklahoma city', zip: '73173' }),
    card({ id: '29914', street: '2109 e winston st', city: 'broken arrow', zip: '74011', price: '215,000', status: 'Under Contract', beds: '4', baths: '2.5', sqft: '2,410', vendee: false }),
  ]));
  assert.deepEqual(a, { id: '30175', path: '/Property-For-Sale/30175/8541-sw-107th-st-oklahoma city-ok-73173', street: '8541 sw 107th st', city: 'oklahoma city', zip: '73173', price: '79750', status: 'For Sale', beds: 3, baths: 2, sqft: 1999, vendee: true });
  assert.equal(b.status, 'Under Contract');
  assert.equal(b.baths, 2.5);
  assert.equal(b.vendee, false);

  const listing = normalizeVrm(a, NOW);
  assert.equal(listing.id, 'vrm-30175');
  assert.equal(listing.address, '8541 SW 107th St');
  assert.equal(listing.city, 'Oklahoma City');
  assert.equal(listing.openingBid, 79750);
  assert.equal(listing.status, 'reo');
  assert.equal(listing.url, 'https://vrmproperties.com/Property-For-Sale/30175/8541-sw-107th-st-oklahoma city-ok-73173');
  assert.match(listing.notes, /Vendee/);

  const glued = street => normalizeVrm({ ...a, street }).address;
  assert.equal(glued('4012 nw33rd st'), '4012 NW 33rd St');
  assert.equal(glued('1004s 11th st'), '1004 S 11th St');
  assert.equal(glued('8418n 116th east ave'), '8418 N 116th East Ave');
  assert.equal(glued('125 w midland st'), '125 W Midland St');
  assert.equal(glued('900 sweetwater dr'), '900 Sweetwater Dr', 'words starting with a direction are left alone');
});

test('pages until a short page, and skips towns far outside the area', async () => {
  const full = Array.from({ length: 3 }, (_, i) => card({ id: `1${i}`, street: `${i + 1} main st`, city: i === 0 ? 'tulsa' : 'norman', zip: '73069' }));
  const pages = {
    1: page(full),
    2: page([card({ id: '20', street: '5 elm st', city: 'yukon', zip: '73099' }), card({ id: '21', street: '6 oak st', city: 'moore', zip: '73160', status: 'Sold' })]),
  };
  const calls = [];
  const fetchImpl = async url => {
    calls.push(url);
    const n = Number(new URL(url).searchParams.get('currentPage'));
    return { ok: true, status: 200, text: async () => pages[n] || page([]) };
  };

  const listings = await fetchVrm({ fetchImpl, sleep: noSleep, cacheFile: tmpCache(), now: NOW });
  assert.equal(calls.length, 2, 'page 2 had fewer cards than page 1, so it was the last');
  assert.deepEqual(listings.map(l => l.city).sort(), ['Norman', 'Norman', 'Yukon'], 'Tulsa skipped, sold home skipped');
});

test('uses the cached pass for about a day and keeps it if the site fails', async () => {
  const cacheFile = tmpCache();
  let calls = 0;
  const ok   = async () => { calls++; return { ok: true, status: 200, text: async () => page([card({ id: '1', street: '1 main st', city: 'norman', zip: '73069' })]) }; };
  const down = async () => { calls++; return { ok: false, status: 503, text: async () => '' }; };

  await fetchVrm({ fetchImpl: ok, sleep: noSleep, cacheFile, now: NOW });
  const firstPass = calls;   // page 1, then page 2 repeats it and ends the pass
  await fetchVrm({ fetchImpl: ok, sleep: noSleep, cacheFile, now: NOW + 6 * 3600e3 });
  assert.equal(calls, firstPass, 'six hours later: served from cache');

  const stale = await fetchVrm({ fetchImpl: down, sleep: noSleep, cacheFile, now: NOW + 21 * 3600e3 });
  assert.equal(calls, firstPass + 1, 'next day: one failed request, no retry loop');
  assert.equal(stale.length, 1);
  assert.ok(stale[0].staleSince);

  await assert.rejects(fetchVrm({ fetchImpl: async () => ({ ok: true, status: 200, text: async () => '<html>redesigned</html>' }), sleep: noSleep, cacheFile: tmpCache(), now: NOW }), /layout may have changed/);
});
