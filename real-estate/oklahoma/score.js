/**
 * Distress score from observed fields only. No market value, repair cost, or ARV is guessed.
 * Sheriff-sale opening bids are set by law at 2/3 of appraisal, so that gap is not a discount.
 */

function addDistressScore(listing) {
  const openingBid = Number(listing.openingBid);
  const appraisedValue = Number(listing.appraisedValue);
  const statutoryBid = listing.saleType === 'sheriff' || listing.source === 'Bid4Assets';
  const hasFinancials = !statutoryBid && Number.isFinite(openingBid) && openingBid > 0 &&
    Number.isFinite(appraisedValue) && appraisedValue > 0 &&
    listing.appraisedValueBasis !== 'opening-bid-times-1.5';
  const discountPercentage = hasFinancials
    ? Math.round(((appraisedValue - openingBid) / appraisedValue) * 1000) / 10
    : null;

  const distressStatus = ['preforeclosure', 'scheduled', 'reo'].includes(String(listing.status).toLowerCase());
  const distressSource = ['County Sheriff', 'VRM', 'OSCN', 'Bid4Assets', 'Auction.com', 'Hubzu', 'HUD Home Store', 'Fannie Mae HomePath']
    .includes(listing.source);
  const hasPropertyFacts = listing.beds != null || listing.baths != null || listing.sqft != null;
  const enoughInformation = hasFinancials || (distressStatus && (distressSource || hasPropertyFacts));
  if (!enoughInformation) {
    return { ...listing, discountPercentage, distressValueScore: null, score: null, scoreBasis: [] };
  }

  const scoreBasis = [];
  let score = 0;
  if (hasFinancials && !statutoryBid) {
    const discountPoints = Math.max(0, Math.min(60, discountPercentage * 1.2));
    score += discountPoints;
    scoreBasis.push('opening-bid-vs-appraised');
  }
  if (distressStatus) { score += 25; scoreBasis.push(`status:${listing.status}`); }
  if (distressSource) { score += 10; scoreBasis.push(`source:${listing.source}`); }
  if (hasPropertyFacts) { score += 5; scoreBasis.push('property-facts'); }
  return {
    ...listing,
    discountPercentage,
    distressValueScore: Math.round(Math.max(0, Math.min(100, score))),
    score: Math.round(Math.max(0, Math.min(100, score))),
    scoreBasis,
  };
}

module.exports = { addDistressScore };
