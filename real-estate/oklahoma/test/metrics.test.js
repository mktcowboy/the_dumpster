const test = require('node:test');
const assert = require('node:assert/strict');
const { annotate, applyMetrics } = require('../metrics');

const NOW = Date.parse('2026-10-22T15:00:00Z');

test('cap rate is copied from the source and not rescaled', () => {
  const out = applyMetrics({ price: 200000, capRate: 7.5, noi: 999 }, NOW);
  assert.equal(out.capRate, 7.5);
  assert.equal(out.capRateBasis, 'source');
  assert.equal(out.noi, 999);
  assert.equal(out.noiBasis, 'source');
});

test('cap rate is computed from source NOI and from source income minus expenses', () => {
  const fromNoi = applyMetrics({ price: 200000, noi: 10000 }, NOW);
  assert.equal(fromNoi.capRate, 5);
  assert.equal(fromNoi.capRateBasis, 'computed-from-source-noi');

  const fromIncome = applyMetrics({ openingBid: 200000, grossIncome: 20000, operatingExpenses: 8000 }, NOW);
  assert.equal(fromIncome.noi, 12000);
  assert.equal(fromIncome.noiBasis, 'computed-from-source-income-and-expenses');
  assert.equal(fromIncome.capRate, 6);
  assert.equal(fromIncome.capRateBasis, 'computed-from-source-income-and-expenses');
});

test('income without expenses does not produce a cap rate or NOI', () => {
  const out = applyMetrics({ price: 200000, grossIncome: 24000 }, NOW);
  assert.equal(out.noi, null);
  assert.equal(out.capRate, null);
  assert.equal(out.grossIncome, 24000);
});

test('occupancy, tenants, and lease terms pass through only when provided', () => {
  const present = applyMetrics({ price: 100000, occupancyPct: 92, tenants: 'Example Retail LLC', leaseTerms: '5 years' }, NOW);
  assert.equal(present.occupancyPct, 92);
  assert.equal(present.occupancyBasis, 'source');
  assert.equal(present.tenants, 'Example Retail LLC');
  assert.equal(present.leaseTerms, '5 years');

  const absent = applyMetrics({ price: 100000 }, NOW);
  assert.equal(absent.occupancyPct, null);
  assert.equal(absent.tenants, null);
  assert.equal(absent.leaseTerms, null);
  assert.equal(absent.capRate, null);
});

test('price per square foot and per acre are unit conversions', () => {
  const house = annotate({ propertyType: 'SFR', openingBid: 150000, sqft: 1500, lotSqft: 87120 }, NOW);
  assert.equal(house.propertyCategory, 'residential');
  assert.equal(house.propertyType, 'single-family');
  assert.equal(house.price, 150000);
  assert.equal(house.pricePerSqft, 100);
  assert.equal(house.pricePerSqftBasis, 'computed');
  assert.equal(house.acres, 2);
  assert.equal(house.acresBasis, 'computed-from-lot-sqft');
  assert.equal(house.pricePerAcre, 75000);

  const land = annotate({ propertyType: 'Land', price: 87000, acres: 10 }, NOW);
  assert.equal(land.propertyCategory, 'land');
  assert.equal(land.pricePerAcre, 8700);
  assert.equal(land.acresBasis, 'source');
  assert.equal(land.pricePerSqft, null);
});

test('days on market prefer the source value, otherwise the list date', () => {
  const sourced = applyMetrics({ daysOnMarket: 12, listedDate: '2020-01-01' }, NOW);
  assert.equal(sourced.daysOnMarket, 12);
  assert.equal(sourced.daysOnMarketBasis, 'source');

  const computed = applyMetrics({ listedDate: '2026-10-12T00:00:00Z' }, NOW);
  assert.equal(computed.daysOnMarket, 10);
  assert.equal(computed.daysOnMarketBasis, 'computed-from-list-date');

  const none = applyMetrics({ auctionDate: '2026-11-01' }, NOW);
  assert.equal(none.daysOnMarket, null);
});

test('an ordinary for-sale listing is not marked distressed', () => {
  const sale = annotate({ source: 'RentCast', propertyType: 'Condo', status: 'Active', price: 100 }, NOW);
  assert.equal(sale.propertyType, 'condo');
  assert.equal(sale.status, 'for_sale');
  assert.equal(sale.distressed, false);

  const sheriff = annotate({ source: 'County Sheriff', saleType: 'sheriff', propertyType: 'unknown', status: 'scheduled' }, NOW);
  assert.equal(sheriff.distressed, true);
  assert.equal(sheriff.propertyCategory, 'unknown');
});
