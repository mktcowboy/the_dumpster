/**
 * Shared politeness + resilience for scraped sources. Each source is requested at most once
 * per `minIntervalMs`, counted from the last attempt (so a failing site isn't retried every
 * sync), and a failure falls back to the last good rows, reported through `staleSince`.
 */

const fs   = require('fs');
const path = require('path');

function readJson(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return {}; }
}

/**
 * Returns { rows, staleSince } for `key` from `cacheFile`, calling `fetchRows()` when the
 * interval has passed. `keepOldIfEmpty(oldRows)` returning true treats an empty fetch as a
 * glitch. Throws only when there's no good copy at all.
 */
async function cachedRows(key, { cacheFile, minIntervalMs, fetchRows, keepOldIfEmpty = () => false, now = Date.now(), log = () => {}, label = key }) {
  const cache = readJson(cacheFile);
  const entry = cache[key] || (cache[key] = {});

  if (now - (entry.attemptedAt ?? entry.fetchedAt ?? 0) >= minIntervalMs) {
    entry.attemptedAt = now;
    try {
      const rows = await fetchRows();
      if (!rows.length && entry.rows && keepOldIfEmpty(entry.rows)) {
        throw new Error('returned nothing while the last copy still had current listings');
      }
      Object.assign(entry, { fetchedAt: now, rows, lastError: null });
    } catch (e) {
      entry.lastError = e.message;
      log(`  ${label} failed (${e.message})` +
        (entry.rows ? `; using the copy from ${new Date(entry.fetchedAt).toISOString()}` : ''));
    }
    fs.mkdirSync(path.dirname(cacheFile), { recursive: true });
    fs.writeFileSync(cacheFile, JSON.stringify(cache, null, 2));
  }

  if (!entry.rows) throw new Error(`no data yet (${entry.lastError || 'never fetched'})`);
  return { rows: entry.rows, staleSince: entry.lastError ? new Date(entry.fetchedAt).toISOString() : null };
}

module.exports = { cachedRows };
