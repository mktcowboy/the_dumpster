/**
 * Maps source property-type strings onto the tracker's categories.
 * A listing is distressed only when the source says so (sheriff sale, REO, pre-foreclosure).
 * An ordinary for-sale house is not marked distressed just because it has a price.
 */

const DISTRESS_SOURCES = new Set([
  'County Sheriff', 'VRM', 'OSCN', 'Bid4Assets', 'Auction.com', 'Hubzu',
  'HUD Home Store', 'Fannie Mae HomePath',
]);

const TYPE_MAP = {
  sfr: ['residential', 'single-family'],
  'single family': ['residential', 'single-family'],
  'single-family': ['residential', 'single-family'],
  'single family residential': ['residential', 'single-family'],
  condo: ['residential', 'condo'],
  condominium: ['residential', 'condo'],
  townhouse: ['residential', 'townhouse'],
  townhome: ['residential', 'townhouse'],
  manufactured: ['residential', 'manufactured'],
  mobile: ['residential', 'manufactured'],
  'mobile home': ['residential', 'manufactured'],
  'multi-family': ['residential', 'multifamily'],
  multifamily: ['residential', 'multifamily'],
  'multi family': ['residential', 'multifamily'],
  duplex: ['residential', 'multifamily'],
  triplex: ['residential', 'multifamily'],
  fourplex: ['residential', 'multifamily'],
  apartment: ['residential', 'multifamily'],
  apartments: ['residential', 'multifamily'],
  retail: ['commercial', 'retail'],
  office: ['commercial', 'office'],
  industrial: ['commercial', 'industrial'],
  warehouse: ['commercial', 'industrial'],
  'mixed-use': ['commercial', 'mixed-use'],
  'mixed use': ['commercial', 'mixed-use'],
  land: ['land', 'land'],
  lot: ['land', 'land'],
  'vacant land': ['land', 'land'],
  farm: ['land', 'farm'],
  ranch: ['land', 'ranch'],
  'farm/ranch': ['land', 'farm'],
  unknown: ['unknown', 'unknown'],
};

const STATUS_MAP = {
  active: 'for_sale',
  'for sale': 'for_sale',
  for_sale: 'for_sale',
  pending: 'pending',
  'under contract': 'pending',
  contingent: 'pending',
  reo: 'reo',
  scheduled: 'scheduled',
  preforeclosure: 'preforeclosure',
};

function classifyListing(listing) {
  const raw = String(listing.propertyType || 'unknown').trim().toLowerCase();
  const mapped = TYPE_MAP[raw];
  const propertyCategory = listing.propertyCategory || (mapped ? mapped[0] : 'unknown');
  const propertyType = mapped ? mapped[1] : (String(listing.propertyType || 'unknown').trim().toLowerCase() || 'unknown');
  const statusKey = String(listing.status || '').trim().toLowerCase();
  const status = STATUS_MAP[statusKey] || listing.status || 'unknown';
  const distressed = listing.distressed === true
    || listing.saleType === 'sheriff'
    || (DISTRESS_SOURCES.has(listing.source) && ['reo', 'scheduled', 'preforeclosure'].includes(String(status).toLowerCase()));
  return { ...listing, propertyCategory, propertyType, status, distressed: !!distressed };
}

module.exports = { classifyListing, TYPE_MAP };
