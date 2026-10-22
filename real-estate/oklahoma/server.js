/**
 * OKC Distressed Property Tracker — Local Scraper Backend
 * Runs Playwright (real Chrome) against each source, caches results,
 * auto-refreshes every 6 hours. API served on port 4083.
 */

const express = require('express');
const fs      = require('fs');
const path    = require('path');
const crypto  = require('crypto');

const app       = express();
const PORT      = 4083;
const DATA_DIR  = path.join(__dirname, 'data');
const CACHE     = path.join(DATA_DIR, 'listings.json');
const LOG_FILE  = path.join(DATA_DIR, 'sync.log');
const INTERVAL  = 6 * 60 * 60 * 1000; // 6 hours

// Search area (center, radius, counties) lives in config/area.json — rebuild with `npm run build-area`.
// geo.js geocodes each listing and measures its distance from the center.
const { AREA, locate } = require('./geo');
const { FEEDS: SHERIFF_FEEDS, fetchSheriffSales } = require('./sheriff-feeds');
const { fetchVrm } = require('./vrm');
const { mergeRun } = require('./listing-store');
const { addDistressScore } = require('./score');
const { annotate } = require('./metrics');
const { attachComps } = require('./comps');
const { summarize } = require('./summary');
const { publicListing, textBlocked } = require('./privacy');
const { CATALOG } = require('./sources/catalog');
const { fetchPayneSales } = require('./sources/payne-sheriff');
const { fetchMcclainSales } = require('./sources/mcclain-sheriff');
const { fetchRentCast } = require('./sources/rentcast');
const { fetchMashvisor } = require('./sources/mashvisor');
const { enrichAttom } = require('./sources/attom');
const { enrichCanadian } = require('./sources/canadian-assessor');

// OSCN is switched off in runSync (Sep 2026): its searches sit behind a
// human-verification check and robots.txt disallows crawling. Several of these
// counties (McClain, Grady, Lincoln, Pottawatomie, Kingfisher) are on ODCR, not OSCN.
const OSCN_COURTS = Object.freeze([
  { database: 'oklahoma', county: 'Oklahoma' },
  { database: 'canadian', county: 'Canadian' },
  { database: 'cleveland', county: 'Cleveland' },
  { database: 'mcclain', county: 'McClain' },
  { database: 'logan', county: 'Logan' },
  { database: 'grady', county: 'Grady' },
  { database: 'lincoln', county: 'Lincoln' },
  { database: 'pottawatomie', county: 'Pottawatomie' },
  { database: 'kingfisher', county: 'Kingfisher' },
]);

// No CORS and no static folder: the dashboard is same-origin, and serving the project
// folder would let any website read data/ and research/ from localhost.
app.use(express.json());

// ─── Cache ──────────────────────────────────────────────────────────────────

function readCache() {
  try { return JSON.parse(fs.readFileSync(CACHE, 'utf8')); }
  catch { return { listings: [], lastSync: null, sourceStatus: {}, syncing: false }; }
}
// listings.json holds the listing history, so write a temp file and rename it into place:
// a crash mid-write can't leave a half-written file that reads back as empty.
function writeCache(data) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  const tmp = `${CACHE}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
  fs.renameSync(tmp, CACHE);
}
function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}`;
  console.log(line);
  try { fs.mkdirSync(DATA_DIR, { recursive: true }); fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
}
function uid(url) {
  return crypto.createHash('md5').update(url || Math.random().toString()).digest('hex').slice(0, 12);
}

// ─── Browser ─────────────────────────────────────────────────────────────────

async function launchBrowser() {
  let chromium;
  try {
    ({ chromium } = require('playwright'));
  } catch {
    throw new Error('playwright is not installed; the disabled browser scrapers need it');
  }
  // Try system Chrome first (already installed, less detectable)
  for (const channel of ['chrome', 'msedge', null]) {
    try {
      const opts = {
        headless: true,
        args: [
          '--disable-blink-features=AutomationControlled',
          '--no-sandbox',
          '--disable-dev-shm-usage',
          '--disable-infobars',
          '--window-size=1280,900',
        ],
      };
      if (channel) opts.channel = channel;
      const b = await chromium.launch(opts);
      log(`Browser launched via ${channel || 'bundled chromium'}`);
      return b;
    } catch {}
  }
  throw new Error('Could not launch any browser');
}

async function newPage(browser) {
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 900 },
    locale: 'en-US',
    timezoneId: 'America/Chicago',
    extraHTTPHeaders: {
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    },
  });
  const page = await ctx.newPage();
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
    window.chrome = { runtime: {} };
  });
  return page;
}

async function safeGoto(page, url, timeout = 30000) {
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout });
    await page.waitForTimeout(2500 + Math.random() * 1500); // human-like delay
  } catch (e) {
    log(`  goto timeout/error for ${url}: ${e.message}`);
  }
}

// ─── Scrapers ─────────────────────────────────────────────────────────────────

async function scrapeBid4Assets(browser) {
  log('  Scraping Bid4Assets OKC Sheriff...');
  const page = await newPage(browser);
  const allListings = [];

  try {
    // Capture any JSON API responses with property data
    const apiCandidates = [];
    page.on('response', async resp => {
      try {
        const ct = resp.headers()['content-type'] || '';
        if (!ct.includes('json')) return;
        const json = await resp.json().catch(() => null);
        if (!json) return;
        // Look for arrays that might be property listings
        const arrays = [json, json.data, json.results, json.listings, json.assets, json.items]
          .filter(x => Array.isArray(x) && x.length > 0);
        for (const arr of arrays) {
          if (arr[0] && (arr[0].address || arr[0].propertyAddress || arr[0].street)) {
            apiCandidates.push(...arr);
          }
        }
      } catch {}
    });

    await safeGoto(page, 'https://www.bid4assets.com/okcsheriff', 45000);
    await page.waitForTimeout(4000);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(2000);

    // If API gave us structured data, use it
    if (apiCandidates.length > 0) {
      log(`  Bid4Assets API candidates: ${apiCandidates.length}`);
      return apiCandidates
        .map(i => normalizeB4A({ ...i, url: i.url || i.listingUrl || 'https://www.bid4assets.com/okcsheriff' }))
        .filter(Boolean);
    }

    // Find auction batch links from the main page then scrape each batch
    const batchLinks = await page.evaluate(() => {
      const links = [...document.querySelectorAll('a[href]')]
        .map(a => a.href)
        .filter(h => h.includes('bid4assets.com') && (h.includes('/auction') || h.match(/\/\d{4,}/)));
      return [...new Set(links)].slice(0, 10);
    });

    log(`  Bid4Assets batch links found: ${batchLinks.length}`);

    // Scrape each batch page for individual properties
    for (const batchUrl of batchLinks.slice(0, 5)) {
      const bPage = await newPage(browser);
      try {
        await safeGoto(bPage, batchUrl, 30000);
        await bPage.waitForTimeout(3000);

        const props = await bPage.evaluate(() => {
          const results = [];
          const selectors = [
            '[data-lot-id]', '[data-asset-id]', '[data-auction-id]',
            '.auction-lot', '.lot-item', '.property-lot',
            '[class*="lot-card"]', '[class*="property-card"]', '[class*="asset-card"]',
            '.asset-listing li', '.asset-item',
          ];
          let cards = [];
          for (const sel of selectors) {
            const found = [...document.querySelectorAll(sel)];
            if (found.length > 0) { cards = found; break; }
          }
          // Smart fallback: look for elements that have both a dollar amount AND an address pattern
          if (cards.length === 0) {
            const candidates = [...document.querySelectorAll('div, li, article')].filter(el => {
              const t = el.innerText || '';
              return t.match(/\$[\d,]+/) && t.match(/\d+\s+\w+\s+(?:St|Ave|Blvd|Dr|Rd|Ln|Way|Ct|Pl|Trl|Cir)\b/i);
            });
            cards = candidates.slice(0, 50);
          }

          for (const card of cards) {
            const text = card.innerText || '';
            if (text.length < 20) continue;
            const link = card.querySelector('a');
            const url  = link ? link.href : window.location.href;
            const addrMatch  = text.match(/\d+\s+[\w\s.]+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Rd|Road|Ln|Lane|Way|Ct|Court|Pl|Place|Trl|Trail|Cir|Circle)[^,\n]*/i);
            const priceMatch = text.match(/(?:Opening Bid|Starting Bid)[:\s]*\$?([\d,]+)/i);
            const dateMatch  = text.match(/\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}\/\d{1,2}\/\d{4}/i);
            const caseMatch  = text.match(/(?:CJ|MF|CF)[-\s]?\d{4}[-\s]?\d+/i);
            const apprMatch  = text.match(/(?:Appraised?|Market Value|Assessed)[:\s]*\$?([\d,]+)/i);
            if (addrMatch) {
              results.push({
                address:  addrMatch[0].trim(),
                openingBid: priceMatch ? priceMatch[1] : '',
                dateText: dateMatch  ? dateMatch[0]  : '',
                caseNum:  caseMatch  ? caseMatch[0]  : '',
                appraised: apprMatch ? apprMatch[1]  : '',
                url,
              });
            }
          }
          return results;
        });
        allListings.push(...props);
        log(`  Bid4Assets batch ${batchUrl.slice(-20)}: ${props.length} properties`);
      } catch (e) {
        log(`  Bid4Assets batch error: ${e.message}`);
      } finally {
        await bPage.context().close();
      }
    }

    // Also try the main page directly for any property cards
    const mainProps = await page.evaluate(() => {
      const results = [];
      const candidates = [...document.querySelectorAll('div, li, article, section')].filter(el => {
        const t = el.innerText || '';
        return t.match(/\d+\s+\w+\s+(?:St|Ave|Blvd|Dr|Rd|Ln|Way|Ct|Pl|Trl)\b/i) &&
               (t.match(/\$[\d,]+/) || t.match(/bid|opening|appraised/i));
      });
      for (const el of candidates.slice(0, 30)) {
        const text = el.innerText || '';
        const addrMatch  = text.match(/\d+\s+[\w\s.]+(?:St|Street|Ave|Avenue|Blvd|Dr|Drive|Rd|Road|Ln|Lane|Way|Ct|Court|Pl|Place|Trl|Cir)[^,\n]*/i);
        const priceMatch = text.match(/(?:Opening Bid|Starting Bid)[:\s]*\$?([\d,]+)/i);
        const link = el.querySelector('a');
        if (addrMatch) {
          results.push({
            address: addrMatch[0].trim(),
            openingBid: priceMatch ? priceMatch[1] : '',
            dateText: '',
            caseNum: '',
            appraised: '',
            url: link ? link.href : window.location.href,
          });
        }
      }
      return results;
    });
    allListings.push(...mainProps);

    log(`  Bid4Assets: found ${allListings.length} items total`);
    // Normalize first (strips lot numbers, drops page text), then deduplicate by address
    const seen = new Set();
    return allListings
      .map(l => normalizeB4A(l))
      .filter(l => { const k = l?.address.toLowerCase(); if (!k || seen.has(k)) return false; seen.add(k); return true; });
  } finally {
    await page.context().close();
  }
}

function normalizeB4A(l) {
  // A lot number sometimes precedes the house number ("367 4412 NW 27TH ST").
  const addr = cleanAddress(l.address || l.propertyAddress || l.street || '').replace(/^\d{1,4}\s+(?=\d+\s+\S)/, '');
  if (isGarbageB4AAddress(addr)) return null;

  // Structured/labeled opening bids come first. A generic API price is accepted
  // only as a last resort and still must clear the tiny-noise floor.
  const openingBid = parseOpeningBid(
    l.openingBid || l.opening_bid || l.labeledOpeningBid || l.startingBid || l.price || '',
  );
  const sourceAppraisal = parsePrice(String(l.appraised || l.appraisedValue || l.assessedValue || ''));
  const appraisedValue = sourceAppraisal || (openingBid ? Math.round(openingBid * 1.5) : null);

  return {
    id: uid((l.url || '') + addr),
    source: 'Bid4Assets',
    address: addr,
    city: l.city || l.propertyCity || '',
    county: l.county || l.propertyCounty || 'Oklahoma',
    state: l.state || l.propertyState || 'OK',
    zip: l.zip || l.zipCode || l.postalCode || '',
    latitude: l.latitude ?? l.lat ?? null,
    longitude: l.longitude ?? l.lng ?? l.lon ?? null,
    status: 'scheduled',
    auctionDate: parseDate(l.dateText || l.auctionDate || ''),
    openingBid,
    appraisedValue,
    appraisedValueBasis: sourceAppraisal ? 'source' : appraisedValue ? 'opening-bid-times-1.5' : null,
    caseNumber: String(l.caseNum || l.caseNumber || '').replace(/case\s*#?\s*/i, '').trim(),
    url: l.url || 'https://www.bid4assets.com/okcsheriff',
    beds: null, baths: null, sqft: null,
    propertyType: 'SFR',
    scrapedAt: new Date().toISOString(),
  };
}

// Bid4Assets pages mix property rows with page text ("2026 Download Property List",
// "6 days Your Bid Status ..."), so require something shaped like a street address.
const STREET_RE    = /\b(?:st|street|ave|avenue|blvd|boulevard|dr|drive|rd|road|ln|lane|way|ct|court|pl|place|ter|terrace|trl|trail|cir|circle|pkwy|parkway|hwy|highway|expy|loop|broadway)\b|\b[NSEW]{1,2}\s+\d+(?:st|nd|rd|th)\b/i;
const PAGE_TEXT_RE = /\b(?:opening bid|deposit|auction date|case number|property details|buyer premium|attorney|plaintiff|defendant|log in|download|select|status|available auctions|sales date)\b/i;

function isGarbageB4AAddress(address) {
  if (!address || address.length < 8 || address.length > 150) return true;
  if (!/^\d+[A-Z]?\s+\S/i.test(address)) return true;   // starts with a house number
  if (!STREET_RE.test(address)) return true;
  if (PAGE_TEXT_RE.test(address)) return true;
  return false;
}

function parseOpeningBid(value) {
  const amount = parsePrice(String(value || ''));
  return amount && amount >= 1000 ? amount : null;
}

// ─────────────────────────────────────────────────────────────────────────────

async function scrapeAuctionCom(browser) {
  log('  Scraping Auction.com...');
  const page = await newPage(browser);
  try {
    // Intercept their internal search API — look for the assets/search XHR
    let apiResponse = null;
    page.on('response', async resp => {
      try {
        const u = resp.url();
        if (apiResponse) return;
        if (!u.includes('auction.com')) return;
        const ct = resp.headers()['content-type'] || '';
        if (!ct.includes('json')) return;
        const json = await resp.json().catch(() => null);
        if (!json) return;
        const candidates = [json.results, json.assets, json.listings, json.data, json.properties]
          .find(x => Array.isArray(x) && x.length > 0);
        if (candidates) apiResponse = candidates;
      } catch {}
    });

    // Use the Oklahoma state-level page for broadest coverage
    await safeGoto(page, 'https://www.auction.com/residential/oklahoma--ok/', 45000);
    await page.waitForTimeout(5000);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(2000);

    if (apiResponse) {
      log(`  Auction.com API: ${apiResponse.length} items`);
      return apiResponse.map(i => normalizeAuction(i));
    }

    // DOM fallback — extract only OK state properties
    const listings = await page.evaluate(() => {
      const ADDR_RE = /\d+\s+[\w\s.#-]+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Rd|Road|Ln|Lane|Way|Ct|Court|Pl|Place|Trl|Trail|Cir|Circle|Pkwy)[^,\n]*/i;
      const results = [];

      const selectors = [
        '[class*="property-card"]', '[class*="listing-card"]',
        '[class*="asset-card"]', '[data-testid*="property"]',
        '[class*="PropertyCard"]', '[class*="ListingCard"]',
        '.tile', 'article',
      ];
      let cards = [];
      for (const sel of selectors) {
        const found = [...document.querySelectorAll(sel)];
        if (found.length > 2) { cards = found; break; }
      }

      for (const card of cards.slice(0, 150)) {
        const text = card.innerText || '';
        if (text.length < 20) continue;

        // Only keep Oklahoma properties
        if (!text.match(/,\s*OK\b/) && !text.match(/Oklahoma/i)) continue;

        const link      = card.querySelector('a[href*="auction.com"]') || card.querySelector('a');
        const url       = link ? link.href : '';
        // Price: look for explicit labels first
        const priceMatch = text.match(/(?:Opening Bid|Current Bid|Starting Bid|List Price)[:\s]*\$?([\d,]+)/i)
                        || text.match(/\$\s*([\d,]+)/);
        // Address: find actual street address in text
        const addrMatch  = text.match(ADDR_RE);
        // Date
        const dateMatch  = text.match(/(?:Starts?|Auction|Bid).*?(\w+ \d{1,2},?\s*\d{4}|\d{1,2}\/\d{1,2}\/\d{4})/i)
                        || text.match(/\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2},?\s+\d{4}/i);
        const bedsMatch  = text.match(/(\d+)\s*(?:bed|bd)\b/i);
        const bathsMatch = text.match(/(\d+(?:\.\d)?)\s*(?:bath|ba)\b/i);
        const sqftMatch  = text.match(/([\d,]+)\s*(?:sq\.?\s*ft|sqft)/i);

        if (addrMatch) {
          results.push({
            address:  addrMatch[0].trim(),
            price:    priceMatch ? (priceMatch[1] || priceMatch[0]).replace(/[,$]/g,'').trim() : '',
            dateText: dateMatch  ? dateMatch[1] || dateMatch[0] : '',
            beds:     bedsMatch  ? parseInt(bedsMatch[1])         : null,
            baths:    bathsMatch ? parseFloat(bathsMatch[1])       : null,
            sqft:     sqftMatch  ? parseInt(sqftMatch[1].replace(',','')) : null,
            url: url || window.location.href,
          });
        }
      }
      return results;
    });

    // Deduplicate by address
    const seen = new Set();
    const unique = listings.filter(l => {
      const k = l.address?.toLowerCase().slice(0, 30);
      if (!k || seen.has(k)) return false;
      seen.add(k); return true;
    });

    log(`  Auction.com DOM: ${unique.length} OK-state items`);
    return unique.map(l => ({
      id: uid(l.url + l.address),
      source: 'Auction.com',
      address: cleanAddress(l.address),
      status: 'scheduled',
      auctionDate: parseDate(l.dateText),
      openingBid: parsePrice(l.price),
      appraisedValue: null,
      caseNumber: '',
      url: l.url,
      beds: l.beds, baths: l.baths, sqft: l.sqft,
      propertyType: 'SFR',
      scrapedAt: new Date().toISOString(),
    }));
  } finally {
    await page.context().close();
  }
}

function normalizeAuction(i) {
  const addr = [i.address, i.street, i.streetAddress, i.propertyAddress]
    .filter(Boolean).find(a => a.length > 5) || '';
  return {
    id: uid(i.id || i.assetId || i.listingId || addr),
    source: 'Auction.com',
    address: cleanAddress(addr),
    status: 'scheduled',
    auctionDate: parseDate(i.auctionDate || i.saleDate || i.eventDate || ''),
    openingBid: parsePrice(String(i.openingBid || i.startingBid || i.price || '')),
    appraisedValue: parsePrice(String(i.appraisedValue || i.assessedValue || '')),
    caseNumber: i.caseNumber || i.caseNum || '',
    url: i.listingUrl || i.url || i.link || `https://www.auction.com`,
    beds: i.bedrooms || i.beds || null,
    baths: i.bathrooms || i.baths || null,
    sqft: i.squareFeet || i.sqft || null,
    propertyType: i.propertyType || 'SFR',
    scrapedAt: new Date().toISOString(),
  };
}

// ─────────────────────────────────────────────────────────────────────────────

async function scrapeHubzu(browser) {
  log('  Scraping Hubzu...');
  const page = await newPage(browser);
  try {
    // Try multiple Hubzu URL patterns for Oklahoma City
    const urls = [
      'https://www.hubzu.com/real-estate/OK/oklahoma-city/',
      'https://www.hubzu.com/real-estate/OK/',
      'https://www.hubzu.com/?search=Oklahoma+City+OK',
    ];
    let landed = false;
    for (const u of urls) {
      await safeGoto(page, u, 35000);
      await page.waitForTimeout(3500);
      const hasContent = await page.evaluate(() => {
        const cards = document.querySelectorAll('[class*="property"], [class*="listing"], [class*="card"], article');
        return cards.length > 2;
      });
      if (hasContent) { landed = true; log(`  Hubzu: loaded ${u}`); break; }
    }
    if (!landed) { log('  Hubzu: no content found'); return []; }

    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(2000);

    const listings = await page.evaluate(() => {
      const ADDR_RE = /\d+\s+[\w\s.#-]+(?:St|Street|Ave|Avenue|Blvd|Dr|Drive|Rd|Road|Ln|Lane|Way|Ct|Court|Pl|Place|Trl|Cir)[^,\n]*/i;
      const results = [];
      const selectors = [
        '[class*="property-card"]', '[class*="propertyCard"]',
        '[class*="listing-card"]', '[class*="home-card"]',
        '[data-testid*="property"]', 'article', '.card',
      ];
      let cards = [];
      for (const sel of selectors) {
        const found = [...document.querySelectorAll(sel)];
        if (found.length > 2) { cards = found; break; }
      }
      for (const card of cards.slice(0, 100)) {
        const text = card.innerText || '';
        if (text.length < 20 || !text.match(/,\s*OK\b/)) continue;
        const link      = card.querySelector('a[href*="hubzu"]') || card.querySelector('a');
        const url       = link ? link.href : '';
        const priceMatch = text.match(/\$\s*([\d,]+)/);
        const addrMatch  = text.match(ADDR_RE);
        const bedsMatch  = text.match(/(\d+)\s*(?:bed|bd)\b/i);
        const bathsMatch = text.match(/(\d+(?:\.\d)?)\s*(?:bath|ba)\b/i);
        const sqftMatch  = text.match(/([\d,]+)\s*(?:sq\.?\s*ft|sqft)/i);
        const dateMatch  = text.match(/\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2},?\s+\d{4}/i);
        if (addrMatch) {
          results.push({
            address:  addrMatch[0].trim(),
            price:    priceMatch ? priceMatch[1] : '',
            dateText: dateMatch  ? dateMatch[0]  : '',
            beds:     bedsMatch  ? parseInt(bedsMatch[1])         : null,
            baths:    bathsMatch ? parseFloat(bathsMatch[1])       : null,
            sqft:     sqftMatch  ? parseInt(sqftMatch[1].replace(',','')) : null,
            url: url || 'https://www.hubzu.com',
          });
        }
      }
      return results;
    });

    const seen = new Set();
    const unique = listings.filter(l => {
      const k = l.address?.toLowerCase().slice(0, 30);
      if (!k || seen.has(k)) return false;
      seen.add(k); return true;
    });
    log(`  Hubzu: ${unique.length} items`);
    return unique.map(l => ({
      id: uid(l.url + l.address),
      source: 'Hubzu',
      address: cleanAddress(l.address),
      status: 'reo',
      auctionDate: parseDate(l.dateText),
      openingBid: parsePrice(l.price),
      appraisedValue: null,
      caseNumber: '',
      url: l.url,
      beds: l.beds, baths: l.baths, sqft: l.sqft,
      propertyType: 'SFR',
      scrapedAt: new Date().toISOString(),
    }));
  } finally {
    await page.context().close();
  }
}

// ─────────────────────────────────────────────────────────────────────────────

async function scrapeHUD(browser) {
  log('  Scraping HUD Home Store...');
  const page = await newPage(browser);
  try {
    // Use direct URL with query params to skip the JS form
    const searchUrl = 'https://www.hudhomestore.gov/Listing/Listing.aspx?' +
      'sState=OK&sCity=&sZip=&sBed=0&sBath=0&sStatus=&sType=0' +
      '&sMinPrc=0&sMaxPrc=10000000&sOrder=1&sPPP=50&sCaseName=';
    await safeGoto(page, searchUrl, 45000);
    await page.waitForTimeout(4000);

    // Also try intercepting any JSON API call HUD makes
    let apiHits = [];
    page.on('response', async resp => {
      try {
        const ct = resp.headers()['content-type'] || '';
        if (!ct.includes('json')) return;
        const json = await resp.json().catch(() => null);
        if (!json) return;
        const arr = [json, json.data, json.results, json.listings]
          .find(x => Array.isArray(x) && x.length > 0 && (x[0].address || x[0].caseNum || x[0].price));
        if (arr) apiHits.push(...arr);
      } catch {}
    });

    // Scroll to trigger lazy loading
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(2000);

    if (apiHits.length > 0) {
      log(`  HUD API hits: ${apiHits.length}`);
      return apiHits.map(i => ({
        id: uid(String(i.caseNum || i.address || Math.random())),
        source: 'HUD Home Store',
        address: cleanAddress(i.address || i.streetAddress || ''),
        status: 'reo',
        auctionDate: null,
        openingBid: parsePrice(String(i.listPrice || i.price || '')),
        appraisedValue: null,
        caseNumber: String(i.caseNum || ''),
        url: i.url || searchUrl,
        beds: i.beds || i.bedrooms || null,
        baths: i.baths || i.bathrooms || null,
        sqft: i.sqft || i.squareFeet || null,
        propertyType: 'SFR',
        scrapedAt: new Date().toISOString(),
      }));
    }

    const listings = await page.evaluate(() => {
      const ADDR_RE = /\d+\s+[\w\s.#-]+(?:St|Street|Ave|Avenue|Blvd|Dr|Drive|Rd|Road|Ln|Lane|Way|Ct|Court|Pl|Place)[^,\n]*/i;
      const results = [];
      const rows = [
        ...document.querySelectorAll('.property-listing, .listing-item, [class*="property-row"]'),
        ...document.querySelectorAll('tbody tr'),
        ...document.querySelectorAll('[class*="hud"], [class*="listing"]'),
      ].filter(r => r.innerText && r.innerText.length > 20);

      for (const row of rows.slice(0, 100)) {
        const text = row.innerText || '';
        if (!text.match(/OK\b|Oklahoma/)) continue;
        const link      = row.querySelector('a');
        const url       = link ? link.href : '';
        const priceMatch = text.match(/\$\s*([\d,]+)/);
        const addrMatch  = text.match(ADDR_RE);
        const caseMatch  = text.match(/\d{3}-\d{6,}/);
        const bedsMatch  = text.match(/(\d+)\s*(?:bed|bd)\b/i);
        const bathsMatch = text.match(/(\d+(?:\.\d)?)\s*(?:bath|ba)\b/i);
        if (addrMatch) {
          results.push({
            address: addrMatch[0].trim(),
            price:   priceMatch ? priceMatch[1] : '',
            caseNum: caseMatch  ? caseMatch[0]  : '',
            beds:    bedsMatch  ? parseInt(bedsMatch[1])    : null,
            baths:   bathsMatch ? parseFloat(bathsMatch[1]) : null,
            url: url || 'https://www.hudhomestore.gov',
          });
        }
      }
      return results;
    });

    log(`  HUD: ${listings.length} items`);
    return listings.map(l => ({
      id: uid(l.url + l.address),
      source: 'HUD Home Store',
      address: cleanAddress(l.address),
      status: 'reo',
      auctionDate: null,
      openingBid: parsePrice(l.price),
      appraisedValue: null,
      caseNumber: l.caseNum,
      url: l.url,
      beds: l.beds, baths: l.baths, sqft: null,
      propertyType: 'SFR',
      scrapedAt: new Date().toISOString(),
    }));
  } finally {
    await page.context().close();
  }
}

// ─────────────────────────────────────────────────────────────────────────────

async function scrapeFannieMae(browser) {
  log('  Scraping Fannie Mae HomePath...');
  const page = await newPage(browser);
  try {
    await safeGoto(page, 'https://www.homepath.fanniemae.com/path/buy-a-home/find-a-home?search=Oklahoma%2C+OK', 45000);
    await page.waitForTimeout(5000);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(2000);

    const listings = await page.evaluate(() => {
      const results = [];
      const selectors = [
        '[class*="property-card"]', '[class*="listing-card"]',
        '[class*="home-card"]', '[class*="result-card"]',
        '.card', 'article', '[data-property-id]',
      ];
      let cards = [];
      for (const sel of selectors) {
        const found = [...document.querySelectorAll(sel)];
        if (found.length > 1) { cards = found; break; }
      }
      for (const card of cards.slice(0, 100)) {
        const text = card.innerText || '';
        if (text.length < 15) continue;
        const link = card.querySelector('a');
        const url  = link ? link.href : '';
        const priceMatch = text.match(/\$[\d,]+/);
        const bedsMatch  = text.match(/(\d+)\s*(?:bed|br)/i);
        const bathsMatch = text.match(/(\d+(?:\.\d)?)\s*(?:bath|ba)\b/i);
        const sqftMatch  = text.match(/([\d,]+)\s*(?:sq\.?\s*ft|sqft)/i);
        const addrLine   = text.split('\n')[0].trim();
        results.push({
          address: addrLine,
          price:   priceMatch ? priceMatch[0] : '',
          beds:    bedsMatch  ? parseInt(bedsMatch[1])       : null,
          baths:   bathsMatch ? parseFloat(bathsMatch[1])    : null,
          sqft:    sqftMatch  ? parseInt(sqftMatch[1].replace(',','')) : null,
          url,
        });
      }
      return results;
    });
    log(`  Fannie Mae: ${listings.length} items`);
    return listings.map(l => ({
      id: uid(l.url || l.address),
      source: 'Fannie Mae HomePath',
      address: cleanAddress(l.address),
      status: 'reo',
      auctionDate: null,
      openingBid: parsePrice(l.price),
      appraisedValue: null,
      caseNumber: '',
      url: l.url,
      beds: l.beds, baths: l.baths, sqft: l.sqft,
      propertyType: 'SFR',
      scrapedAt: new Date().toISOString(),
    }));
  } finally {
    await page.context().close();
  }
}

// ─────────────────────────────────────────────────────────────────────────────

async function scrapeOSCN(browser) {
  log(`  Scraping OSCN (pre-foreclosures) across ${OSCN_COURTS.length} court databases...`);
  const page = await newPage(browser);
  try {
    const today = new Date();
    const d90   = new Date(); d90.setDate(today.getDate() - 90);
    const fmt   = d => `${d.getMonth()+1}/${d.getDate()}/${d.getFullYear()}`;
    const cases = [];

    for (const court of OSCN_COURTS) {
      const url = `https://www.oscn.net/dockets/Results.aspx?db=${court.database}` +
        `&number=&casetype=MF&partyname=&partytype=0&accounttype=0&id=` +
        `&offensive=0&begindate=${encodeURIComponent(fmt(d90))}` +
        `&enddate=${encodeURIComponent(fmt(today))}` +
        `&court=&resultcount=200&format=4&demeanor=B`;
      try {
        await safeGoto(page, url, 40000);
        await page.waitForTimeout(1800);
        const found = await page.evaluate(() => {
          const results = [];
          const rows = [...document.querySelectorAll('table tr, .result-row, [class*="result"]')];
          for (const row of rows) {
            const cells = [...row.querySelectorAll('td, .cell')];
            const text  = row.innerText || '';
            if (text.length < 10) continue;
            const link = row.querySelector('a[href*="dockets"]') || row.querySelector('a');
            const caseMatch = text.match(/(?:CJ|MF|CF|FJ|CM)-?\d{4}-?\d+/i);
            if (!caseMatch) continue;
            const dateMatch  = text.match(/\d{1,2}\/\d{1,2}\/\d{4}/);
            const partyNames = cells.slice(0, 5).map(c => c.innerText.trim())
              .filter(x => x && x.length > 1 && !x.match(/^\d/));
            results.push({
              caseNum: caseMatch[0], parties: partyNames.join(' vs '),
              date: dateMatch ? dateMatch[0] : '', url: link ? link.href : '',
            });
          }
          return results.slice(0, 200);
        });
        cases.push(...found.map(c => ({ ...c, county: court.county, database: court.database,
          url: c.url || `https://www.oscn.net/dockets/Results.aspx?db=${court.database}&casetype=MF` })));
        log(`  OSCN ${court.county}: ${found.length} MF cases`);
      } catch (e) {
        log(`  OSCN ${court.county}: ${e.message}`);
      }
    }

    const unique = [...new Map(cases.map(c => [`${c.database}:${c.caseNum}`, c])).values()];
    log(`  OSCN: ${unique.length} MF cases across configured counties`);
    return unique.map(c => ({
      id: uid(`${c.database}:${c.caseNum}`), source: 'OSCN',
      address: c.parties || c.caseNum, county: c.county, state: 'OK',
      status: 'preforeclosure', auctionDate: null, openingBid: null,
      appraisedValue: null, caseNumber: c.caseNum, url: c.url,
      beds: null, baths: null, sqft: null, propertyType: 'Unknown',
      scrapedAt: new Date().toISOString(), notes: `Filed: ${c.date}`,
    }));
  } finally {
    await page.context().close();
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function cleanAddress(raw) {
  if (!raw) return '';
  return raw.replace(/\s+/g, ' ').replace(/[^\w\s,#.-]/g, '').trim().slice(0, 150);
}
function parsePrice(s) {
  if (!s) return null;
  const n = parseInt(String(s).replace(/[^\d]/g, ''));
  return isNaN(n) || n === 0 ? null : n;
}
function parseDate(s) {
  if (!s) return null;
  try {
    const d = new Date(s);
    if (!isNaN(d)) return d.toISOString().split('T')[0];
  } catch {}
  return null;
}


// Cleans addresses, geocodes, drops listings confirmed outside the radius (ones we
// can't place stay for review), then scores. geoOptions lets tests swap the geocoder.
// The statewide tracker uses prepareStatewide, which keeps out-of-area rows.
async function locateAndScore(listings, geoOptions = {}) {
  const say = geoOptions.log || log;
  const cleaned = listings
    .map(listing => ({ ...listing, address: cleanAddress(listing.address || '') }))
    .filter(listing => listing.address.length > 3);
  try {
    const geo = await locate(cleaned, { log: say, ...geoOptions });
    say(`  Location: ${geo.inArea} inside ${AREA.radiusMi} mi, ${geo.outOfArea} outside (dropped), ${geo.unknown} not placed — ${JSON.stringify(geo.byStatus)}`);
  } catch (e) {
    say(`  Location step failed, keeping all listings: ${e.message}`);
  }
  return cleaned.filter(listing => listing.inArea !== false).map(listing => addDistressScore(annotate(listing, geoOptions.now)));
}

// Same cleaning and geocoding as locateAndScore, but every Oklahoma listing is kept.
// inArea remains the 50-mile flag the dashboard filters on. geoOptions.enrich may
// attach assessor or recorded-sale fields before metrics are computed.
async function prepareStatewide(listings, geoOptions = {}) {
  const say = geoOptions.log || log;
  const cleaned = listings
    .map(listing => ({ ...listing, address: cleanAddress(listing.address || '') }))
    .filter(listing => listing.address.length > 3);
  try {
    const geo = await locate(cleaned, { log: say, ...geoOptions });
    say(`  Location: ${geo.inArea} inside ${AREA.radiusMi} mi, ${geo.outOfArea} outside (kept), ${geo.unknown} not placed — ${JSON.stringify(geo.byStatus)}`);
  } catch (e) {
    say(`  Location step failed, keeping all listings: ${e.message}`);
  }
  if (geoOptions.enrich) await geoOptions.enrich(cleaned);
  return cleaned.map(listing => addDistressScore(annotate(listing, geoOptions.now)));
}

// ─── Sync Orchestrator ───────────────────────────────────────────────────────

let syncInProgress = false;

async function syncAll() {
  if (syncInProgress) { log('Sync already in progress, skipping'); return; }
  syncInProgress = true;
  try {
    return await runSync();
  } finally {
    syncInProgress = false;
  }
}

async function runSync() {
  log('=== Starting full sync ===');

  const cache = readCache();
  cache.syncing = true;
  cache.syncStarted = new Date().toISOString();
  writeCache(cache);

  // Switched off Sep 2026 because each site blocks automated access; they're weekly manual
  // checks now (see research/source-review-2026-09-15.md): OSCN (Turnstile), Bid4Assets
  // (Akamai), Auction.com (Imperva), HUD Home Store (robots.txt Disallow: /), HomePath
  // (browser check). Their scrape functions are kept for reference only.
  const scrapers = [
    // Plain JSON requests, cached to about one a day per county
    ...SHERIFF_FEEDS.map(feed => ({
      name: `${feed.county.replace(/ County$/, '')} Sheriff`,
      fn: () => fetchSheriffSales(feed, { log }),
    })),
    { name: 'Payne Sheriff', fn: () => fetchPayneSales({ log }) },
    { name: 'McClain Sheriff', fn: () => fetchMcclainSales({ log }) },
    { name: 'VRM', fn: () => fetchVrm({ log, statewide: true }) },
    { name: 'RentCast', fn: () => fetchRentCast({ log }) },
    { name: 'Mashvisor', fn: () => fetchMashvisor({ log }) },
    // Hubzu (scrapeHubzu, headless browser) removed Sep 2026: it returned nothing on every run.
  ];

  let browser = null;
  const allNew = [];
  const sourceStatus = {};

  try {
    for (const { name, fn, needsBrowser } of scrapers) {
      try {
        // Launched only when a browser scraper runs, so a launch failure can't block the feeds
        if (needsBrowser && !browser) browser = await launchBrowser();
        const results = await fn(browser);
        results.forEach(r => { r.sourceName = name; });
        allNew.push(...results);
        const stale = results.find(r => r.staleSince)?.staleSince || null;
        sourceStatus[name] = { ok: true, count: results.length, stale, at: new Date().toISOString() };
        log(`  ${name}: ${results.length} listings OK${stale ? ` (cached copy from ${stale})` : ''}`);
      } catch (e) {
        if (e.skip) {
          sourceStatus[name] = { ok: true, skipped: true, count: 0, reason: e.message, at: new Date().toISOString() };
          log(`  ${name}: skipped (${e.message})`);
        } else {
          log(`  ${name}: ERROR — ${e.message}`);
          sourceStatus[name] = { ok: false, error: e.message, at: new Date().toISOString() };
        }
      }
      // Polite pause between sources
      await new Promise(r => setTimeout(r, 1500));
    }
  } finally {
    if (browser) await browser.close().catch(() => {});
  }

  // Statewide: out-of-area listings stay, tagged with inArea for the radius filter.
  const scraped = await prepareStatewide(allNew, {
    log,
    enrich: async rows => {
      try {
        const n = await enrichCanadian(rows, { log });
        sourceStatus['Canadian Assessor'] = { ok: true, count: n, at: new Date().toISOString() };
        log(`  Canadian Assessor: ${n} situs matches`);
      } catch (e) {
        sourceStatus['Canadian Assessor'] = { ok: false, error: e.message, at: new Date().toISOString() };
        log(`  Canadian Assessor: ERROR — ${e.message}`);
      }
      try {
        const attom = await enrichAttom(rows, { log });
        sourceStatus.ATTOM = attom.skipped
          ? { ok: true, skipped: true, count: 0, reason: 'ATTOM_API_KEY is not set', at: new Date().toISOString() }
          : { ok: true, count: attom.enriched, at: new Date().toISOString() };
        log(attom.skipped ? '  ATTOM: skipped (no API key)' : `  ATTOM: ${attom.enriched} recorded sales`);
      } catch (e) {
        sourceStatus.ATTOM = { ok: false, error: e.message, at: new Date().toISOString() };
        log(`  ATTOM: ERROR — ${e.message}`);
      }
    },
  });
  const { listings: merged, summary } = mergeRun({
    previous: cache.listings || [],
    fresh: scraped,
    failedSources: Object.keys(sourceStatus).filter(n => sourceStatus[n].ok === false),
  });
  const listings = [];
  let privacyDrops = 0;
  for (const listing of merged) {
    const safe = publicListing(listing);
    if (textBlocked(safe)) { privacyDrops++; continue; }
    listings.push(safe);
  }
  if (privacyDrops) log(`  Privacy filter dropped ${privacyDrops} listings`);
  log(`  History: ${summary.added} new, ${summary.updated} changed, ${summary.removed} no longer listed, ${summary.relisted} back on the market`);

  const result = {
    listings,
    lastSync: new Date().toISOString(),
    lastRun: summary,
    area: { center: AREA.center, radiusMi: AREA.radiusMi, statewide: true },
    sourceStatus,
    syncing: false,
  };
  writeCache(result);
  log(`=== Sync complete: ${scraped.length} current listings, ${listings.filter(l => !l.removedAt).length} active, ${listings.length} saved ===`);
  return result;
}

// ─── API Routes ───────────────────────────────────────────────────────────────

app.get('/api/status', (req, res) => {
  const cache = readCache();
  res.json({
    syncing: syncInProgress,
    lastSync: cache.lastSync,
    sourceStatus: cache.sourceStatus || {},
    count: (cache.listings || []).filter(l => !l.removedAt).length,
    lastRun: cache.lastRun || null,
  });
});

app.get('/api/listings', (req, res) => {
  const cache = readCache();
  const rows = cache.listings || [];
  const active = rows.filter(l => !l.removedAt);
  const withComps = attachComps(active);
  const byId = new Map(withComps.map(l => [l.id, l]));
  res.json(rows.map(l => byId.get(l.id) || l));
});

app.get('/api/summary', (req, res) => {
  const cache = readCache();
  res.json(summarize(cache.listings || []));
});

app.get('/api/sources', (req, res) => {
  const cache = readCache();
  res.json({
    catalog: CATALOG,
    live: cache.sourceStatus || {},
    area: { center: AREA.center, radiusMi: AREA.radiusMi },
  });
});

app.post('/api/sync', (req, res) => {
  // Browsers send Origin on cross-site POSTs; only the dashboard itself may start a sync
  const origin = req.get('origin');
  if (origin && origin !== `http://localhost:${PORT}` && origin !== `http://127.0.0.1:${PORT}`) {
    return res.status(403).json({ ok: false, message: 'Sync can only be started from the dashboard' });
  }
  if (syncInProgress) {
    return res.json({ ok: false, message: 'Sync already running' });
  }
  res.json({ ok: true, message: 'Sync started' });
  syncAll().catch(e => log('Sync failed: ' + e.message));
});

// ─── Static + boot ───────────────────────────────────────────────────────────

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'oklahoma.html'));
});

// Listen only when run directly (node server.js); tests require() the pipeline functions.
if (require.main === module) {
  if (process.argv.includes('--sync-once')) {
    syncAll().then(() => process.exit(0)).catch(e => { log('Sync failed: ' + e.message); process.exit(1); });
  } else {
    // Sync only when the saved listings are older than INTERVAL — checked at startup and every
    // 15 minutes — so a restart reuses what's saved. "Sync Now" on the dashboard forces a check.
    const syncIfDue = () => {
      const sinceLast = Date.now() - (Date.parse(readCache().lastSync) || 0);
      if (sinceLast >= INTERVAL) syncAll().catch(e => log('Sync failed: ' + e.message));
    };
    app.listen(PORT, () => {
      const last = readCache().lastSync;
      log(`Server running on http://localhost:${PORT} (last sync: ${last || 'never'})`);
      syncIfDue();
      setInterval(syncIfDue, 15 * 60 * 1000);
    });
  }
}

module.exports = { locateAndScore, prepareStatewide, addDistressScore, normalizeB4A };
