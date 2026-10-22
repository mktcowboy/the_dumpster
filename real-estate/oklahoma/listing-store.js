/**
 * Keeps every listing the tracker has found, across syncs. Each sync is merged into the saved
 * list: new listings get firstSeen, existing ones get lastSeen and a change log (price, sale
 * date, status), and listings a source stops showing get removedAt instead of vanishing.
 */

const TRACKED_FIELDS    = ['openingBid', 'price', 'appraisedValue', 'auctionDate', 'status'];
const MAX_CHANGES       = 20;
const KEEP_REMOVED_DAYS = 180;
const DAY_MS            = 24 * 60 * 60 * 1000;

/**
 * previous: the saved listings (user-added ones have no scrapedAt and pass through untouched).
 * fresh: this sync's listings. failedSources: source names that errored this sync — their
 * saved listings are kept as they were and marked stale rather than treated as removed.
 * Returns { listings, summary: { added, updated, removed, relisted } }.
 */
function mergeRun({ previous = [], fresh = [], failedSources = [], now = new Date() }) {
  const at       = now.toISOString();
  const failed   = new Set(failedSources);
  const userAdded = previous.filter(l => !l.scrapedAt);
  const prevById = new Map(previous.filter(l => l.scrapedAt).map(l => [l.id, l]));
  const summary  = { added: 0, updated: 0, removed: 0, relisted: 0 };
  const out      = [];
  const seen     = new Set();

  for (const listing of fresh) {
    if (seen.has(listing.id)) continue;
    seen.add(listing.id);
    const prev = prevById.get(listing.id);

    if (!prev) {
      out.push({ ...listing, firstSeen: at, lastSeen: at, removedAt: null, stale: !!listing.staleSince, changes: [] });
      summary.added++;
      continue;
    }

    const changes = [...(prev.changes || [])];
    if (prev.removedAt) {
      changes.push({ at, field: 'relisted', from: prev.removedAt, to: null });
      summary.relisted++;
    }
    const fieldChanges = TRACKED_FIELDS
      .filter(field => String(prev[field] ?? null) !== String(listing[field] ?? null))
      .map(field => ({ at, field, from: prev[field] ?? null, to: listing[field] ?? null }));
    if (fieldChanges.length) summary.updated++;

    out.push({
      ...listing,
      firstSeen: prev.firstSeen || prev.scrapedAt || at,
      lastSeen: at,
      removedAt: null,
      stale: !!listing.staleSince,
      changes: [...changes, ...fieldChanges].slice(-MAX_CHANGES),
    });
  }

  const keepRemovedSince = now.getTime() - KEEP_REMOVED_DAYS * DAY_MS;
  for (const prev of prevById.values()) {
    if (seen.has(prev.id)) continue;
    if (!prev.sourceName) continue;   // saved before history tracking, from retired scrapers
    if (failed.has(prev.sourceName)) {
      out.push({ ...prev, stale: true });
    } else if (prev.removedAt) {
      if (Date.parse(prev.removedAt) >= keepRemovedSince) out.push(prev);
    } else {
      out.push({ ...prev, removedAt: at, stale: false });
      summary.removed++;
    }
  }

  return { listings: [...userAdded, ...out], summary };
}

module.exports = { mergeRun, TRACKED_FIELDS };
