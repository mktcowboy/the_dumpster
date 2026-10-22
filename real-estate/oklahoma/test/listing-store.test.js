const test   = require('node:test');
const assert = require('node:assert/strict');

const { mergeRun } = require('../listing-store');

const DAY  = 24 * 60 * 60 * 1000;
const T0   = new Date('2026-09-15T12:00:00Z');
const T1   = new Date(T0.getTime() + DAY);
const T2   = new Date(T0.getTime() + 2 * DAY);
const sale = (id, extra = {}) => ({ id, sourceName: 'Canadian Sheriff', source: 'County Sheriff', scrapedAt: 'x', status: 'scheduled', openingBid: 100000, appraisedValue: 150000, auctionDate: '2026-10-05', address: `${id} Main St`, ...extra });

test('first sync: everything is new', () => {
  const { listings, summary } = mergeRun({ fresh: [sale('a'), sale('b')], now: T0 });
  assert.deepEqual(summary, { added: 2, updated: 0, removed: 0, relisted: 0 });
  assert.equal(listings[0].firstSeen, T0.toISOString());
  assert.equal(listings[0].lastSeen, T0.toISOString());
  assert.deepEqual(listings[0].changes, []);
});

test('later sync: keeps firstSeen, logs changes, marks what disappeared', () => {
  const first = mergeRun({ fresh: [sale('a'), sale('b'), sale('c')], now: T0 }).listings;
  const { listings, summary } = mergeRun({
    previous: first,
    fresh: [sale('a'), sale('b', { openingBid: 90000, auctionDate: '2026-10-19' }), sale('d')],
    now: T1,
  });
  const byId = Object.fromEntries(listings.map(l => [l.id, l]));

  assert.deepEqual(summary, { added: 1, updated: 1, removed: 1, relisted: 0 });
  assert.equal(byId.a.firstSeen, T0.toISOString(), 'first found date survives');
  assert.equal(byId.a.lastSeen, T1.toISOString());
  assert.deepEqual(byId.b.changes.map(c => [c.field, c.from, c.to]), [['openingBid', 100000, 90000], ['auctionDate', '2026-10-05', '2026-10-19']]);
  assert.equal(byId.c.removedAt, T1.toISOString(), 'no longer listed, but kept');
  assert.equal(byId.d.firstSeen, T1.toISOString());
});

test('a listing that comes back is logged as relisted', () => {
  const s0 = mergeRun({ fresh: [sale('a')], now: T0 }).listings;
  const s1 = mergeRun({ previous: s0, fresh: [], now: T1 }).listings;
  const { listings, summary } = mergeRun({ previous: s1, fresh: [sale('a')], now: T2 });
  assert.equal(summary.relisted, 1);
  assert.equal(listings[0].removedAt, null);
  assert.equal(listings[0].firstSeen, T0.toISOString());
  assert.equal(listings[0].changes.at(-1).field, 'relisted');
});

test('a failed source keeps its listings as they were', () => {
  const s0 = mergeRun({ fresh: [sale('a')], now: T0 }).listings;
  const { listings, summary } = mergeRun({ previous: s0, fresh: [], failedSources: ['Canadian Sheriff'], now: T1 });
  assert.equal(summary.removed, 0);
  assert.equal(listings[0].removedAt, null);
  assert.equal(listings[0].stale, true);
  assert.equal(listings[0].lastSeen, T0.toISOString());
});

test('user-added listings pass through; old off-market and pre-history listings are pruned', () => {
  const tracked = { id: 'mine', address: '1 My Deal St', notes: 'call owner' };
  const legacy  = { id: 'old-oscn', source: 'OSCN', scrapedAt: 'x', address: 'CF-1992-2237' };
  const gone    = sale('gone', { removedAt: new Date(T2.getTime() - 200 * DAY).toISOString(), firstSeen: 'x' });
  const recent  = sale('recent', { removedAt: new Date(T2.getTime() - 10 * DAY).toISOString(), firstSeen: 'x' });
  const { listings } = mergeRun({ previous: [tracked, legacy, gone, recent], fresh: [], now: T2 });
  assert.deepEqual(listings.map(l => l.id), ['mine', 'recent']);
});
