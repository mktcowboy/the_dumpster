/** Counts and medians from listings that are still on the market. Prices of $0 are ignored. */

function priceOf(listing) {
  const n = Number(listing.price ?? listing.openingBid);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function median(values) {
  const xs = values.filter(n => n != null).sort((a, b) => a - b);
  if (!xs.length) return null;
  const mid = Math.floor(xs.length / 2);
  return xs.length % 2 ? xs[mid] : Math.round((xs[mid - 1] + xs[mid]) / 2);
}

function group(rows, keyFn) {
  const buckets = new Map();
  for (const row of rows) {
    const key = keyFn(row) || 'Unknown';
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(row);
  }
  return [...buckets.entries()]
    .map(([key, items]) => {
      const prices = items.map(priceOf);
      return {
        key,
        count: items.length,
        withPrice: prices.filter(n => n != null).length,
        medianPrice: median(prices),
      };
    })
    .sort((a, b) => b.count - a.count || String(a.key).localeCompare(String(b.key)));
}

function summarize(listings) {
  const rows = (listings || []).filter(l => !l.removedAt);
  const prices = rows.map(priceOf);
  return {
    count: rows.length,
    offMarket: (listings || []).length - rows.length,
    withPrice: prices.filter(n => n != null).length,
    medianPrice: median(prices),
    distressed: rows.filter(l => l.distressed).length,
    withCapRate: rows.filter(l => l.capRate != null).length,
    withOccupancy: rows.filter(l => l.occupancyPct != null).length,
    withRecordedSale: rows.filter(l => Number(l.recordedSale?.price) > 0).length,
    withAssessor: rows.filter(l => l.assessor && (l.assessor.totalValue != null || l.assessor.totalAssessed != null)).length,
    byPropertyCategory: group(rows, l => l.propertyCategory),
    byPropertyType: group(rows, l => l.propertyType),
    byCounty: group(rows, l => l.county),
    byCity: group(rows, l => l.city),
    bySource: group(rows, l => l.source),
  };
}

module.exports = { summarize, median, priceOf };
