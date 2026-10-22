/**
 * Payne County sheriff sales. The public page at paynecountyok.gov/sheriff-sale
 * is server-rendered HTML (robots.txt Allow: /). Checked 2026-10-22.
 * One request a day. The table has date, case, appraisal, starting bid, and
 * address. Party names are not on the page and are not stored.
 */

const path = require('path');
const crypto = require('crypto');
const { cachedRows } = require('../feed-cache');

const PAGE_URL = 'https://www.paynecountyok.gov/sheriff-sale';
const CACHE_FILE = path.join(__dirname, '..', 'data', 'payne-sheriff.json');
const MIN_REFETCH_MS = 20 * 60 * 60 * 1000;
const HEADERS = { 'User-Agent': 'oklahoma-listing-tracker/1.0 (personal use; about one request a day)', Accept: 'text/html' };

const text = html => String(html || '').replace(/<[^>]*>/g, ' ').replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();
const money = s => { const n = Number(String(s ?? '').replace(/[^\d.]/g, '')); return n > 0 ? Math.round(n) : null; };
const okToday = now => new Date(now).toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });
const titleCase = s => String(s || '').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());

function isoDate(mdy) {
  const m = String(mdy || '').match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!m) return null;
  return `${m[3]}-${m[1].padStart(2, '0')}-${m[2].padStart(2, '0')}`;
}

function splitAddress(raw) {
  const m = String(raw || '').trim().match(/^(.*?),\s*([A-Za-z .'-]+?)\s+OK\s+(\d{5})(?:-\d{4})?$/i);
  if (!m) return { street: String(raw || '').trim(), city: '', zip: '' };
  return { street: m[1].trim(), city: titleCase(m[2].trim()), zip: m[3] };
}

function parsePayne(html) {
  const body = String(html).split(/<tbody>/i)[1] || '';
  const rows = [];
  for (const tr of body.split(/<tr\b/i).slice(1)) {
    const cells = [...tr.matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/gi)].map(m => text(m[1]));
    if (cells.length < 5) continue;
    rows.push({
      date: cells[0],
      caseNumber: cells[1],
      appraisal: cells[2],
      openingBid: cells[3],
      address: cells[4],
    });
  }
  if (!rows.length) throw new Error('no sale table parsed; the page layout may have changed');
  return rows;
}

function normalizePayne(row, today) {
  const date = isoDate(row.date);
  if (!date || date < today) return null;
  const address = splitAddress(row.address);
  if (!address.street) return null;
  const appraisal = money(row.appraisal);
  const bid = money(row.openingBid) || (appraisal ? Math.ceil(appraisal * 2 / 3) : null);
  const key = `${row.caseNumber}|${address.street}`;
  return {
    id: `payne-${crypto.createHash('md5').update(key).digest('hex').slice(0, 12)}`,
    source: 'County Sheriff',
    saleType: 'sheriff',
    address: address.street,
    city: address.city,
    zip: address.zip,
    state: 'OK',
    county: 'Payne County',
    status: 'scheduled',
    auctionDate: date,
    appraisedValue: appraisal,
    appraisedValueBasis: appraisal ? 'source' : null,
    openingBid: bid,
    price: bid,
    caseNumber: String(row.caseNumber || '').trim(),
    url: PAGE_URL,
    beds: null,
    baths: null,
    sqft: null,
    propertyType: 'unknown',
    distressed: true,
    scrapedAt: new Date().toISOString(),
    notes: `Payne County sheriff sale ${date}`,
  };
}

async function fetchPayneSales({ fetchImpl = fetch, cacheFile = CACHE_FILE, now = Date.now(), log = () => {} } = {}) {
  const today = okToday(now);
  const { rows, staleSince } = await cachedRows('payne-sheriff', {
    cacheFile, now, log,
    label: 'Payne sheriff sales',
    minIntervalMs: MIN_REFETCH_MS,
    keepOldIfEmpty: old => old.some(row => {
      const date = isoDate(row.date);
      return date && date >= today;
    }),
    fetchRows: async () => {
      const res = await fetchImpl(PAGE_URL, { headers: HEADERS, signal: AbortSignal.timeout(30000) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return parsePayne(await res.text());
    },
  });
  return rows
    .map(row => normalizePayne(row, today))
    .filter(Boolean)
    .map(listing => (staleSince ? { ...listing, staleSince } : listing));
}

module.exports = { fetchPayneSales, parsePayne, normalizePayne, PAGE_URL };
