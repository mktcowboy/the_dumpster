/**
 * Price-per-unit and income metrics. Computed figures are labeled.
 * Cap rate and occupancy are filled only from source-provided numbers:
 * a cap rate the source states, or NOI the source states, or NOI computed
 * as source gross income minus source operating expenses. Missing expenses
 * are not assumed, and nothing is filled with a market guess.
 */

const { classifyListing } = require('./classify');

const SQFT_PER_ACRE = 43560;
const num = v => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const positive = v => {
  const n = num(v);
  return n != null && n > 0 ? n : null;
};
const round = (n, d = 2) => Math.round(n * 10 ** d) / 10 ** d;

function incomeMetrics(listing, price) {
  const sourceCap = num(listing.capRate);
  let noi = num(listing.noi);
  let noiBasis = noi != null ? (listing.noiBasis || 'source') : null;
  const grossIncome = num(listing.grossIncome);
  const operatingExpenses = num(listing.operatingExpenses);
  if (noi == null && grossIncome != null && operatingExpenses != null) {
    noi = grossIncome - operatingExpenses;
    noiBasis = 'computed-from-source-income-and-expenses';
  }

  let capRate = null;
  let capRateBasis = null;
  if (sourceCap != null) {
    capRate = sourceCap;
    capRateBasis = listing.capRateBasis || 'source';
  } else if (noi != null && price != null && price > 0) {
    capRate = round((noi / price) * 100, 2);
    capRateBasis = noiBasis === 'source' ? 'computed-from-source-noi' : 'computed-from-source-income-and-expenses';
  }

  const occupancyPct = num(listing.occupancyPct);
  const tenants = listing.tenants == null || listing.tenants === '' ? null : listing.tenants;
  const leaseTerms = listing.leaseTerms == null || listing.leaseTerms === '' ? null : listing.leaseTerms;
  return {
    noi: noi != null ? round(noi, 2) : null,
    noiBasis,
    capRate,
    capRateBasis,
    grossIncome,
    operatingExpenses,
    occupancyPct,
    occupancyBasis: occupancyPct != null ? (listing.occupancyBasis || 'source') : null,
    tenants,
    leaseTerms,
  };
}

function daysOnMarket(listing, now) {
  const given = num(listing.daysOnMarket);
  if (given != null && given >= 0) return { daysOnMarket: given, daysOnMarketBasis: 'source' };
  const listed = Date.parse(listing.listedDate || '');
  if (!Number.isFinite(listed)) return { daysOnMarket: null, daysOnMarketBasis: null };
  const days = Math.floor((now - listed) / 86400000);
  if (days < 0 || days > 4000) return { daysOnMarket: null, daysOnMarketBasis: null };
  return { daysOnMarket: days, daysOnMarketBasis: 'computed-from-list-date' };
}

function applyMetrics(listing, now = Date.now()) {
  const price = positive(listing.price) ?? positive(listing.openingBid);
  const sqft = positive(listing.sqft);
  const sourceAcres = positive(listing.acres);
  const sourceLot = positive(listing.lotSqft);
  let acres = sourceAcres;
  let lotSqft = sourceLot;
  let acresBasis = null;
  if (acres != null) acresBasis = 'source';
  else if (lotSqft != null) {
    acres = lotSqft / SQFT_PER_ACRE;
    acresBasis = 'computed-from-lot-sqft';
  }
  if (lotSqft == null && sourceAcres != null) lotSqft = Math.round(sourceAcres * SQFT_PER_ACRE);

  const pricePerSqft = price != null && sqft != null ? round(price / sqft, 2) : null;
  const pricePerAcre = price != null && acres != null ? round(price / acres, 2) : null;
  return {
    ...listing,
    price,
    sqft,
    acres: acres != null ? round(acres, 4) : null,
    acresBasis,
    lotSqft,
    pricePerSqft,
    pricePerSqftBasis: pricePerSqft != null ? 'computed' : null,
    pricePerAcre,
    pricePerAcreBasis: pricePerAcre != null ? 'computed' : null,
    yearBuilt: positive(listing.yearBuilt),
    ...daysOnMarket(listing, now),
    ...incomeMetrics(listing, price),
  };
}

function annotate(listing, now = Date.now()) {
  return applyMetrics(classifyListing(listing), now);
}

module.exports = { annotate, applyMetrics, incomeMetrics, SQFT_PER_ACRE };
