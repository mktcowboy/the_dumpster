/**
 * Drops party-contact fields and any listing whose text matches the repository
 * privacy blocklist. Matched values are never printed.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const PRIVACY_PY = path.join(__dirname, '..', '..', 'scripts', 'check_privacy.py');

function loadBlocked() {
  try {
    const text = fs.readFileSync(PRIVACY_PY, 'utf8');
    return new Set([...text.matchAll(/'([a-f0-9]{64})'/g)].map(m => m[1]));
  } catch {
    return new Set();
  }
}

const BLOCKED = loadBlocked();

const DROP_KEY = /defendant|attorney|atty|owner|owners_name|ownername|mail_info|listingagent|listingoffice|email|phone|broker/i;

function publicListing(listing) {
  const out = {};
  for (const [key, value] of Object.entries(listing || {})) {
    if (DROP_KEY.test(key)) continue;
    out[key] = value;
  }
  return out;
}

function textBlocked(listing, blocked = BLOCKED) {
  const blob = JSON.stringify(listing ?? '').toLowerCase();
  for (const token of blob.match(/[a-z0-9]+/g) || []) {
    if (blocked.has(crypto.createHash('sha256').update(token).digest('hex'))) return true;
  }
  return false;
}

module.exports = { publicListing, textBlocked, BLOCKED };
