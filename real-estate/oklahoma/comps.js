/**
 * Nearby comparable listings. Asking-price comps come from other active,
 * pending, or auction rows already in the tracker. A sold comp is included
 * only when that row carries a source-provided recorded sale amount.
 * Assessor values, when a comp has them, are passed through under their own
 * fields and are not treated as sale prices.
 */

const { haversineMi } = require('./geo');

const num = v => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const round1 = n => Math.round(n * 10) / 10;
const round2 = n => Math.round(n * 100) / 100;

function asking(listing) {
  const n = num(listing.price) ?? num(listing.openingBid);
  return n != null && n > 0 ? n : null;
}

function acresOf(listing) {
  const acres = num(listing.acres);
  if (acres != null && acres > 0) return acres;
  const lot = num(listing.lotSqft);
  return lot != null && lot > 0 ? lot / 43560 : null;
}

function perUnit(listing) {
  const price = asking(listing);
  if (price == null) return null;
  const sqft = num(listing.sqft);
  if (sqft != null && sqft > 0) return { unit: 'sqft', value: price / sqft };
  const acres = acresOf(listing);
  if (acres != null && acres > 0) return { unit: 'acre', value: price / acres };
  return null;
}

function radiusFor(listing) {
  if (listing.propertyCategory === 'land') return 15;
  if (listing.propertyCategory === 'commercial') return 10;
  if (listing.distressed) return 8;
  return 3;
}

function sameFamily(a, b) {
  const ac = a.propertyCategory;
  const bc = b.propertyCategory;
  if (ac && bc && ac !== 'unknown' && bc !== 'unknown') return ac === bc;
  if (a.distressed && b.distressed) return true;
  return false;
}

function sizeOk(a, b) {
  const as = num(a.sqft);
  const bs = num(b.sqft);
  if (as > 0 && bs > 0) {
    const ratio = bs / as;
    return ratio >= 0.6 && ratio <= 1.67;
  }
  const aa = acresOf(a);
  const ba = acresOf(b);
  if (aa > 0 && ba > 0) {
    const ratio = ba / aa;
    return ratio >= 0.5 && ratio <= 2;
  }
  return true;
}

function basisFor(listing) {
  if (listing.status === 'pending') return 'pending-listing';
  if (listing.status === 'scheduled') return 'distress-auction';
  if (listing.status === 'reo') return 'reo-listing';
  return 'active-listing';
}

function shapeComp(subject, subjectUnit, other, dist, loose) {
  const unit = perUnit(other);
  let deltaPct = null;
  let comparison = 'none';
  if (subjectUnit && unit && subjectUnit.unit === unit.unit) {
    comparison = subjectUnit.unit;
    deltaPct = round1(((unit.value - subjectUnit.value) / subjectUnit.value) * 100);
  } else if (asking(subject) && asking(other)) {
    comparison = 'price';
    deltaPct = round1(((asking(other) - asking(subject)) / asking(subject)) * 100);
  }
  return {
    id: other.id,
    address: other.address,
    city: other.city || null,
    county: other.county || null,
    status: other.status || null,
    propertyType: other.propertyType || null,
    price: asking(other),
    distanceMi: round1(dist),
    unit: unit ? unit.unit : null,
    compPerUnit: unit ? round2(unit.value) : null,
    subjectPerUnit: subjectUnit && unit && subjectUnit.unit === unit.unit ? round2(subjectUnit.value) : null,
    deltaPct,
    comparison,
    loose: !!loose,
    basis: basisFor(other),
    assessorValue: other.assessor?.totalValue ?? null,
    assessorAssessed: other.assessor?.totalAssessed ?? null,
    url: other.url || null,
  };
}

function attachComps(listings, { limit = 5 } = {}) {
  const pool = listings.filter(l => !l.removedAt && num(l.lat) != null && num(l.lon) != null);
  return listings.map(subject => {
    if (subject.removedAt || num(subject.lat) == null || num(subject.lon) == null) {
      return { ...subject, comps: [], soldComps: [] };
    }
    const subjectUnit = perUnit(subject);
    const ranked = pool
      .filter(other => other.id !== subject.id && sameFamily(subject, other))
      .map(other => ({ other, dist: haversineMi(subject.lat, subject.lon, other.lat, other.lon) }))
      .filter(row => row.dist <= radiusFor(subject))
      .sort((a, b) => a.dist - b.dist);
    const tight = ranked.filter(row => sizeOk(subject, row.other));
    const loose = tight.length === 0 && ranked.length > 0;
    const chosen = (tight.length ? tight : ranked).slice(0, limit);
    const comps = chosen.map(row => shapeComp(subject, subjectUnit, row.other, row.dist, loose));
    const soldComps = ranked
      .filter(row => num(row.other.recordedSale?.price) > 0)
      .slice(0, limit)
      .map(row => ({
        id: row.other.id,
        address: row.other.address,
        city: row.other.city || null,
        distanceMi: round1(row.dist),
        price: row.other.recordedSale.price,
        date: row.other.recordedSale.date || null,
        basis: 'recorded-sale',
        source: row.other.recordedSale.source || row.other.source,
        note: row.other.recordedSale.note || 'Recorded sale amount from the source. Not an asking price.',
      }));
    return { ...subject, comps, soldComps };
  });
}

module.exports = { attachComps, perUnit, asking };
