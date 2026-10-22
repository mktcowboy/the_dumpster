/**
 * County sheriff-sale lists. Several in-area sheriffs (Canadian, Grady, Lincoln, Logan,
 * Caddo, Seminole) run the same website template, whose /sheriff-sales page loads its
 * list as JSON from one endpoint. The sites' terms allow copying for personal,
 * non-commercial use. That covers this private tracker (Sep 2026).
 * Budget: about one request per county per day, cached in data/sheriff-feeds.json.
 */

const path   = require('path');
const crypto = require('crypto');
const { cachedRows } = require('./feed-cache');

const CACHE_FILE     = path.join(__dirname, 'data', 'sheriff-feeds.json');
const API_PATH       = '/dmxConnect/api/SheriffSales/Read.php';
const MIN_REFETCH_MS = 20 * 60 * 60 * 1000;

const FEEDS = [
  { county: 'Canadian County', site: 'https://www.ccsheriff.net' },
  { county: 'Grady County',    site: 'https://gradycosheriff.com' },
  { county: 'Lincoln County',  site: 'https://lincolncountysheriffok.gov' },
  { county: 'Logan County',    site: 'https://www.logancountyso.org' },
  { county: 'Caddo County',    site: 'https://caddocountysheriff.com' },
  { county: 'Seminole County', site: 'https://www.seminolecosheriff.com' },
];

const titleCase = s => String(s || '').trim().toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
const money     = s => { const n = parseInt(String(s ?? '').replace(/[^\d.]/g, ''), 10); return n > 0 ? n : null; };
const okToday   = now => new Date(now).toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });   // YYYY-MM-DD

// Only the fields the tracker uses. Defendant and attorney details are never stored.
function pickFields(row) {
  return {
    sale_id:   row.sale_id ?? null,
    date:      row.date ?? '',
    status:    row.status ?? '',
    case:      row.case ?? '',
    address:   row.address ?? '',
    city:      row.city ?? '',
    zip:       row.zip ?? '',
    appraisal: row.appraisal ?? '',
    plaintiff: row.plaintiff ?? row.plantiff ?? '',   // the feed spells it "plantiff"
  };
}

/** One feed row → tracker listing, or null unless it's an active sale on or after `today`. */
function normalizeSale(row, feed, today) {
  if (String(row.status).trim().toLowerCase() !== 'active') return null;
  const date = String(row.date).slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || date < today) return null;
  const address = String(row.address || '').replace(/\s+/g, ' ').trim();
  if (!address) return null;
  const appraisal = money(row.appraisal);
  const key = row.sale_id != null ? row.sale_id : `${row.case}|${address}`;
  return {
    id: crypto.createHash('md5').update(`${feed.site}|${key}`).digest('hex').slice(0, 12),
    source: 'County Sheriff',
    saleType: 'sheriff',
    address,
    city: titleCase(row.city),
    zip: String(row.zip || '').trim().slice(0, 5),
    state: 'OK',
    county: feed.county,
    status: 'scheduled',
    auctionDate: date,
    appraisedValue: appraisal,
    appraisedValueBasis: appraisal ? 'source' : null,
    openingBid: appraisal ? Math.ceil(appraisal * 2 / 3) : null,   // statutory minimum bid: 2/3 of appraisal
    caseNumber: String(row.case || '').trim(),
    plaintiff: String(row.plaintiff || '').trim(),
    url: `${feed.site}/sheriff-sales`,
    beds: null, baths: null, sqft: null,
    propertyType: 'Unknown',
    scrapedAt: new Date().toISOString(),
    notes: `${feed.county} sheriff sale ${date}`,
  };
}

/**
 * Upcoming active sales for one county, fetched at most about once a day. A failed request,
 * or an empty list while sales were still upcoming, falls back to the last good copy and
 * marks each listing with `staleSince`.
 */
async function fetchSheriffSales(feed, { fetchImpl = fetch, cacheFile = CACHE_FILE, now = Date.now(), log = () => {} } = {}) {
  const today    = okToday(now);
  const upcoming = rows => rows.map(row => normalizeSale(row, feed, today)).filter(Boolean);

  const { rows, staleSince } = await cachedRows(feed.site, {
    cacheFile, now, log,
    label: `${feed.county} sheriff feed`,
    minIntervalMs: MIN_REFETCH_MS,
    keepOldIfEmpty: old => upcoming(old).length > 0,
    fetchRows: async () => {
      const res = await fetchImpl(feed.site + API_PATH, {
        headers: { Accept: 'application/json', 'User-Agent': 'okc-deal-tracker/1.0 (personal use; about one request a day)' },
        signal: AbortSignal.timeout(30000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (!Array.isArray(json?.allSales)) throw new Error('unexpected response: no allSales list');
      return json.allSales.map(pickFields);
    },
  });

  return upcoming(rows).map(listing => (staleSince ? { ...listing, staleSince } : listing));
}

module.exports = { FEEDS, fetchSheriffSales, normalizeSale, pickFields };
