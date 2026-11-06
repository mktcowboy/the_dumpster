const test = require('node:test');
const assert = require('node:assert/strict');
const { attachComps } = require('../comps');

const house = (id, extra) => ({
  id,
  propertyCategory: 'residential',
  propertyType: 'single-family',
  status: 'for_sale',
  price: 150000,
  sqft: 1500,
  lat: 35.47,
  lon: -97.52,
  address: `${id} Example St`,
  city: 'Oklahoma City',
  ...extra,
});

test('comps compare price per square foot for similar nearby houses', () => {
  const [subject] = attachComps([
    house('a', { price: 150000, sqft: 1500 }),
    house('b', { price: 200000, sqft: 1600, lat: 35.477, status: 'pending' }),
    house('c', { propertyCategory: 'land', propertyType: 'land', sqft: null, acres: 20, price: 80000, lat: 35.477 }),
  ]);
  assert.equal(subject.comps.length, 1);
  assert.equal(subject.comps[0].id, 'b');
  assert.equal(subject.comps[0].comparison, 'sqft');
  assert.equal(subject.comps[0].subjectPerUnit, 100);
  assert.equal(subject.comps[0].compPerUnit, 125);
  assert.equal(subject.comps[0].deltaPct, 25);
  assert.equal(subject.comps[0].basis, 'pending-listing');
  assert.equal(subject.comps[0].loose, false);
  assert.ok(subject.comps[0].distanceMi < 1);
});

test('a recorded sale is a sold comp and an asking price is not', () => {
  const [subject] = attachComps([
    house('a'),
    house('b', { lat: 35.477, recordedSale: { price: 140000, date: '2025-06-01', source: 'ATTOM', note: 'from the source' } }),
  ]);
  assert.equal(subject.soldComps.length, 1);
  assert.equal(subject.soldComps[0].price, 140000);
  assert.equal(subject.soldComps[0].basis, 'recorded-sale');
  assert.equal(subject.soldComps[0].source, 'ATTOM');
  assert.notEqual(subject.comps[0].basis, 'recorded-sale');
});

test('no coordinates means no comps, and a size mismatch is labeled loose', () => {
  const rows = attachComps([
    house('a', { lat: null, lon: null }),
    house('b', { sqft: 1500 }),
    house('c', { sqft: 8000, price: 400000, lat: 35.477 }),
  ]);
  assert.deepEqual(rows[0].comps, []);
  assert.equal(rows[1].comps.length, 1);
  assert.equal(rows[1].comps[0].loose, true);
  assert.equal(rows[1].comps[0].id, 'c');
});

test('assessor values on a comp stay labeled as assessor values', () => {
  const [subject] = attachComps([
    house('a'),
    house('b', { lat: 35.477, assessor: { totalValue: 180000, totalAssessed: 20000, basis: 'Canadian County assessor' } }),
  ]);
  assert.equal(subject.comps[0].assessorValue, 180000);
  assert.equal(subject.comps[0].assessorAssessed, 20000);
  assert.equal(subject.comps[0].basis, 'active-listing');
});

test('land comps use price per acre', () => {
  const [subject] = attachComps([
    house('a', { propertyCategory: 'land', propertyType: 'land', sqft: null, acres: 40, price: 80000 }),
    house('b', { propertyCategory: 'land', propertyType: 'ranch', sqft: null, acres: 50, price: 150000, lat: 35.5 }),
  ]);
  assert.equal(subject.comps.length, 1);
  assert.equal(subject.comps[0].comparison, 'acre');
  assert.equal(subject.comps[0].subjectPerUnit, 2000);
  assert.equal(subject.comps[0].compPerUnit, 3000);
  assert.equal(subject.comps[0].deltaPct, 50);
});
