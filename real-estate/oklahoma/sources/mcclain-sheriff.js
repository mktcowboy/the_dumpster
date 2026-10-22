/**
 * McClain County sheriff sales. The September 2026 review found a plain HTML
 * list at mcclaincountysheriff.com/sheriff-sales (robots disallowed only
 * /wp-admin/). On 2026-10-22 that URL returned a SiteGround captcha, so live
 * sync fails closed and the page is a manual check until the captcha is gone.
 * The parser still accepts the labeled-block format. Defendant and attorney
 * text is never stored.
 */

const path = require('path');
const crypto = require('crypto');
const { cachedRows } = require('../feed-cache');

const PAGE_URL = 'https://mcclaincountysheriff.com/sheriff-sales/';
const CACHE_FILE = path.join(__dirname, '..', 'data', 'mcclain-sheriff.json');
const MIN_REFETCH_MS = 20 * 60 * 60 * 1000;
const HEADERS = { 'User-Agent': 'oklahoma-listing-tracker/1.0 (personal use; about one request a day)', Accept: 'text/html' };

const textOf = html => String(html || '')
  .replace(/<script[\s\S]*?<\/script>/gi, ' ')
  .replace(/<style[\s\S]*?<\/style>/gi, ' ')
  .replace(/<[^>]*>/g, ' ')
  .replace(/&nbsp;/g, ' ')
  .replace(/&amp;/g, '&')
  .replace(/\s+/g, ' ')
  .trim();
const money = s => { const n = Number(String(s ?? '').replace(/[^\d.]/g, '')); return n > 0 ? Math.round(n) : null; };
const okToday = now => new Date(now).toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });
const titleCase = s => String(s || '').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());

function isoDate(mdy) {
  const m = String(mdy || '').match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!m) return null;
  return `${m[3]}-${m[1].padStart(2, '0')}-${m[2].padStart(2, '0')}`;
}

function parseCity(address) {
  const m = String(address).match(/,\s*([A-Za-z .'-]+?)(?:,\s*OK|\s+OK\b|\s*$)/);
  return m ? titleCase(m[1].trim()) : '';
}

function parseMcclain(html) {
  const raw = String(html || '');
  if (/sgcaptcha|captcha challenge/i.test(raw) && !/CASE\s*#/i.test(raw)) {
    throw new Error('captcha challenge; manual check');
  }
  const text = textOf(raw);
  const chunks = text.split(/CASE\s*#:\s*/i).slice(1);
  const rows = chunks.map(chunk => {
    const caseNumber = (chunk.match(/^([A-Z]{1,4}-[\d-]+)/i) || [])[1] || '';
    const status = (chunk.match(/STATUS:\s*([A-Za-z]+)/i) || [])[1] || '';
    const date = (chunk.match(/SALE DATE:\s*(\d{1,2}\/\d{1,2}\/\d{4})/i) || [])[1] || '';
    const address = (chunk.match(/(?:DESCRIPTION\/ADDRESS|ADDRESS):\s*(.*?)\s*(?:APPRAISAL|PRINCIPAL|PLAINTIFF|DEFENDANT|ATTORNEY|$)/i) || [])[1] || '';
    const appraisal = (chunk.match(/APPRAISAL(?:\s+AMOUNT)?:\s*\$?\s*([\d,.]+)/i) || [])[1] || '';
    const plaintiff = (chunk.match(/PLAINTIFF:\s*(.*?)\s*(?:DEFENDANT|ATTORNEY|CASE\s*#|$)/i) || [])[1] || '';
    return { caseNumber, status, date, address: address.trim(), appraisal, plaintiff: plaintiff.trim() };
  }).filter(row => row.caseNumber && row.address);
  if (!rows.length) throw new Error('no sheriff-sale blocks parsed; the page layout may have changed');
  return rows;
}

function normalizeMcclain(row, today) {
  if (String(row.status || 'active').trim().toLowerCase() !== 'active') return null;
  const date = isoDate(row.date);
  if (!date || date < today) return null;
  const address = String(row.address || '').replace(/\s+/g, ' ').trim();
  if (!address) return null;
  const appraisal = money(row.appraisal);
  const key = `${row.caseNumber}|${address}`;
  return {
    id: `mcclain-${crypto.createHash('md5').update(key).digest('hex').slice(0, 12)}`,
    source: 'County Sheriff',
    saleType: 'sheriff',
    address,
    city: parseCity(address),
    zip: (address.match(/\b(\d{5})(?:-\d{4})?\b/) || [])[1] || '',
    state: 'OK',
    county: 'McClain County',
    status: 'scheduled',
    auctionDate: date,
    appraisedValue: appraisal,
    appraisedValueBasis: appraisal ? 'source' : null,
    openingBid: appraisal ? Math.ceil(appraisal * 2 / 3) : null,
    caseNumber: row.caseNumber,
    plaintiff: row.plaintiff,
    url: PAGE_URL,
    beds: null,
    baths: null,
    sqft: null,
    propertyType: 'unknown',
    distressed: true,
    scrapedAt: new Date().toISOString(),
    notes: `McClain County sheriff sale ${date}`,
  };
}

async function fetchMcclainSales({ fetchImpl = fetch, cacheFile = CACHE_FILE, now = Date.now(), log = () => {} } = {}) {
  const today = okToday(now);
  const { rows, staleSince } = await cachedRows('mcclain-sheriff', {
    cacheFile, now, log,
    label: 'McClain sheriff sales',
    minIntervalMs: MIN_REFETCH_MS,
    fetchRows: async () => {
      const res = await fetchImpl(PAGE_URL, { headers: HEADERS, signal: AbortSignal.timeout(30000) });
      if (res.status === 202) throw new Error('captcha challenge; manual check');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return parseMcclain(await res.text());
    },
  });
  return rows
    .map(row => normalizeMcclain(row, today))
    .filter(Boolean)
    .map(listing => (staleSince ? { ...listing, staleSince } : listing));
}

module.exports = { fetchMcclainSales, parseMcclain, normalizeMcclain, PAGE_URL };
