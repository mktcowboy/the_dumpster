/**
 * VRM (Vendor Resource Management) — VA-owned and Mr. Cooper bank-owned homes for sale.
 * Server-rendered results pages at vrmproperties.com; robots.txt allows the listing path and
 * the terms have no automated-access clause (checked Sep 2026). One pass a day at most
 * (about 5 page requests, 1.5 s apart), cached in data/vrm.json.
 */

const path = require('path');
const { cachedRows } = require('./feed-cache');
const { townFor }    = require('./geo');

const BASE           = 'https://vrmproperties.com';
const CACHE_FILE     = path.join(__dirname, 'data', 'vrm.json');
const MIN_REFETCH_MS = 20 * 60 * 60 * 1000;
const PAGE_DELAY_MS  = 1500;
const MAX_PAGES      = 12;
const HEADERS        = { 'User-Agent': 'okc-deal-tracker/1.0 (personal use; about one pass a day)' };

const listUrl = page => `${BASE}/Properties-For-Sale?state=OK&currentPage=${page}&orderBy=default+desc&orderByText=Default`;

const text = html => String(html || '')
  .replace(/<[^>]*>/g, ' ')
  .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/&quot;/g, '"')
  .replace(/&[a-z]+;/g, '')
  .replace(/\s+/g, ' ').trim();

// VRM sometimes glues directions to numbers: "1004s 11th st", "4012 nw33rd st".
const tidyStreet = s => String(s || '')
  .replace(/^(\d+)(n|s|e|w|ne|nw|se|sw)\b/i, '$1 $2')
  .replace(/\b(n|s|e|w|ne|nw|se|sw)(\d)/gi, '$1 $2');

const titleCase = s => String(s || '').toLowerCase()
  .replace(/\b\w/g, c => c.toUpperCase())
  .replace(/\b(Ne|Nw|Se|Sw)\b/g, d => d.toUpperCase());

/** Property cards on one results page → [{ id, path, street, city, zip, price, status, beds, baths, sqft, vendee }]. */
function parseListingsPage(html) {
  return String(html).split('prop-card-container').slice(1).map(card => {
    const link = card.match(/href="(\/Property-For-Sale\/(\d+)\/[^"]*)"/);
    if (!link) return null;
    const [streetHtml, cityHtml = ''] = (card.match(/<p class="card-text properCase">([\s\S]*?)<\/p>/)?.[1] || '').split(/<br\s*\/?>/i);
    const cityZip = text(cityHtml).match(/^(.*?),\s*OK\s+(\d{5})/i);
    const spec = title => {
      const m = card.match(new RegExp(`([\\d,.]+)&nbsp;<i[^>]*title="${title}"`));
      return m ? Number(m[1].replace(/,/g, '')) : null;
    };
    return {
      id:     link[2],
      path:   link[1],
      street: text(streetHtml),
      city:   cityZip ? cityZip[1] : '',
      zip:    cityZip ? cityZip[2] : '',
      price:  (card.match(/class="card-subtitle">\s*\$([\d,]+)/)?.[1] || '').replace(/,/g, ''),
      status: text(card.match(/property-status[^"]*">([\s\S]*?)<\/div>/)?.[1]),
      beds:   spec('Beds'),
      baths:  spec('Baths'),
      sqft:   spec('Sqr. Feet'),
      vendee: /vendee_horz/i.test(card),
    };
  }).filter(Boolean);
}

function normalizeVrm(card, now = Date.now()) {
  return {
    id: `vrm-${card.id}`,
    source: 'VRM',
    address: titleCase(tidyStreet(card.street)),
    city: titleCase(card.city),
    zip: card.zip,
    state: 'OK',
    status: 'reo',
    auctionDate: null,
    openingBid: Number(card.price) || null,   // list price
    appraisedValue: null,
    caseNumber: '',
    url: `${BASE}${card.path}`,
    beds: card.beds, baths: card.baths, sqft: card.sqft,
    propertyType: 'SFR',
    scrapedAt: new Date(now).toISOString(),
    notes: `VRM: ${card.status || 'listed'}${card.vendee ? ' · may qualify for Vendee financing' : ''}`,
  };
}

/**
 * Oklahoma VRM listings in towns near the search area (statewide towns further out are
 * skipped before geocoding). Pages through results until a short or repeated page.
 */
async function fetchVrm({ fetchImpl = fetch, sleep = ms => new Promise(r => setTimeout(r, ms)), cacheFile = CACHE_FILE, now = Date.now(), log = () => {}, statewide = false } = {}) {
  const { rows, staleSince } = await cachedRows('vrm-ok', {
    cacheFile, now, log,
    label: 'VRM',
    minIntervalMs: MIN_REFETCH_MS,
    fetchRows: async () => {
      const byId = new Map();
      let pageSize = 0;
      for (let page = 1; page <= MAX_PAGES; page++) {
        if (page > 1) await sleep(PAGE_DELAY_MS);
        const res = await fetchImpl(listUrl(page), { headers: HEADERS, signal: AbortSignal.timeout(30000) });
        if (!res.ok) throw new Error(`HTTP ${res.status} on page ${page}`);
        const cards = parseListingsPage(await res.text());
        if (page === 1) pageSize = cards.length;
        const fresh = cards.filter(c => !byId.has(c.id));
        fresh.forEach(c => byId.set(c.id, c));
        if (!fresh.length || cards.length < pageSize) break;
      }
      if (!byId.size) throw new Error('no listings parsed; the page layout may have changed');
      return [...byId.values()];
    },
  });

  const listings = rows
    .filter(card => !/\bsold\b/i.test(card.status) && (statewide || townFor(card.city)))
    .map(card => normalizeVrm(card, now));
  return staleSince ? listings.map(l => ({ ...l, staleSince })) : listings;
}

module.exports = { fetchVrm, parseListingsPage, normalizeVrm };
