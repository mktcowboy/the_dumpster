/**
 * Restricted market-data proxy for the local drawdown.html page.
 *
 * Routes:
 *   GET /chart/TICKER     Yahoo v8 daily adjusted-close history
 *   GET /iv/TICKER        30-day constant-maturity IV from the CBOE delayed chain
 *   GET /volindex/INDEX   Official CBOE vol-index daily history (allow-listed)
 *
 * Yahoo range=max&interval=1d currently returns monthly bars, so /chart uses
 * period1=0&period2=<now>&interval=1d&events=div,split&includeAdjustedClose=true.
 */

const YAHOO_HOSTS = [
  "https://query1.finance.yahoo.com/v8/finance/chart",
  "https://query2.finance.yahoo.com/v8/finance/chart",
];
const CBOE_OPTIONS = "https://cdn.cboe.com/api/global/delayed_quotes/options/";
const CBOE_VOL_CSV = "https://cdn.cboe.com/api/global/us_indices/daily_prices/";
const BROWSER_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

const TICKER_RE = /^[A-Za-z0-9^][A-Za-z0-9._=^-]{0,31}$/;
const OCC_RE = /^([A-Z0-9]+)(\d{6})([CP])(\d{8})$/;
const YEAR_DAYS = 365;
const TARGET_DAYS = 30;

const VOL_INDEXES = {
  VIX: "S&P 500 30-day IV (VIX)",
  VXN: "Nasdaq-100 30-day IV (VXN)",
  RVX: "Russell 2000 30-day IV (RVX)",
  VXAPL: "CBOE Equity VIX on Apple",
  VXAZN: "CBOE Equity VIX on Amazon",
  VXGOG: "CBOE Equity VIX on Google",
  VXGS: "CBOE Equity VIX on Goldman Sachs",
  VXIBM: "CBOE Equity VIX on IBM",
};

const TICKER_TO_VOLINDEX = {
  SPY: "VIX", SPX: "VIX", "^SPX": "VIX", "^GSPC": "VIX", IVV: "VIX", VOO: "VIX",
  QQQ: "VXN", QQQM: "VXN", NDX: "VXN", "^NDX": "VXN",
  IWM: "RVX", RUT: "RVX", "^RUT": "RVX",
  AAPL: "VXAPL", AMZN: "VXAZN", GOOG: "VXGOG", GOOGL: "VXGOG", GS: "VXGS", IBM: "VXIBM",
};

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age": "86400",
};

function json(body, status = 200, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      ...CORS_HEADERS,
      "Content-Type": "application/json; charset=utf-8",
      ...extra,
    },
  });
}

function yahooQuery() {
  const period2 = Math.floor(Date.now() / 1000);
  return `period1=0&period2=${period2}&interval=1d&events=div,split&includeAdjustedClose=true`;
}

function route(url) {
  const parts = url.pathname.split("/").filter(Boolean);
  const q = (url.searchParams.get("ticker") || url.searchParams.get("index") || "").trim();
  const head = (parts[0] || "").toLowerCase();
  if (head === "iv") return { kind: "iv", symbol: (parts[1] || q).toUpperCase() };
  if (head === "volindex") return { kind: "volindex", symbol: (parts[1] || q).toUpperCase() };
  if (head === "chart") return { kind: "chart", symbol: (parts[1] || q).toUpperCase() };
  if (parts.length === 1 && head !== "health") return { kind: "chart", symbol: parts[0].toUpperCase() };
  return { kind: "health", symbol: q.toUpperCase() };
}

function erf(x) {
  const sign = x < 0 ? -1 : 1;
  x = Math.abs(x);
  const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741, a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
  const t = 1 / (1 + p * x);
  return sign * (1 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x));
}
function normCdf(x) { return 0.5 * (1 + erf(x / Math.SQRT2)); }

function yearFraction(expiryDate, asofMs) {
  const end = Date.UTC(expiryDate.getUTCFullYear(), expiryDate.getUTCMonth(), expiryDate.getUTCDate(), 21, 0, 0); // 16:00 ET = 21:00 UTC (EST)
  // Use 16:00 America/New_York properly via offset: Nov is EST (UTC-5) so 21:00 UTC is correct for late year.
  return Math.max(end - asofMs, 0) / (YEAR_DAYS * 24 * 3600 * 1000);
}

function parseOcc(symbol) {
  const m = OCC_RE.exec(String(symbol || "").replace(/\s+/g, ""));
  if (!m) return null;
  const yy = m[2].slice(0, 2), mo = m[2].slice(2, 4), dd = m[2].slice(4, 6);
  const expiry = new Date(Date.UTC(2000 + Number(yy), Number(mo) - 1, Number(dd)));
  return { root: m[1], expiry, kind: m[3] === "C" ? "call" : "put", strike: Number(m[4]) / 1000 };
}

function bsDelta(spot, strike, t, r, q, sigma, kind) {
  if (spot <= 0 || strike <= 0 || t <= 1e-8 || sigma <= 1e-8) return null;
  const d1 = (Math.log(spot / strike) + (r - q + 0.5 * sigma * sigma) * t) / (sigma * Math.sqrt(t));
  const dq = Math.exp(-q * t);
  return kind === "call" ? dq * normCdf(d1) : dq * (normCdf(d1) - 1);
}

function usable(c) {
  if (!(c.iv > 0.01 && c.iv <= 5)) return false;
  if (c.bid > 0 && c.ask > 0 && c.ask >= c.bid) return true;
  return c.last > 0;
}

function interpolateY(xs, ys, x0) {
  if (!xs.length || xs.length !== ys.length) return null;
  const pairs = xs.map((x, i) => [x, ys[i]]).sort((a, b) => a[0] - b[0]);
  const X = pairs.map((p) => p[0]), Y = pairs.map((p) => p[1]);
  const span = X[X.length - 1] - X[0];
  const pad = Math.max(0.03, 0.15 * (span || 0));
  if (x0 < X[0] - pad || x0 > X[X.length - 1] + pad) return null;
  if (x0 <= X[0]) return Y[0];
  if (x0 >= X[X.length - 1]) return Y[Y.length - 1];
  for (let i = 1; i < X.length; i++) {
    if (X[i] >= x0) {
      if (X[i] === X[i - 1]) return Y[i];
      const w = (x0 - X[i - 1]) / (X[i] - X[i - 1]);
      return Y[i - 1] * (1 - w) + Y[i] * w;
    }
  }
  return Y[Y.length - 1];
}

function ivAtDelta(contracts, t, spot, r, q, target) {
  const xs = [], ys = [];
  for (const c of contracts) {
    if (!usable(c)) continue;
    const d = bsDelta(spot, c.strike, t, r, q, c.iv, c.kind);
    if (d == null) continue;
    xs.push(d); ys.push(c.iv);
  }
  return interpolateY(xs, ys, target);
}

function ivAtStrike(contracts, k0) {
  const xs = [], ys = [];
  for (const c of contracts) {
    if (!usable(c)) continue;
    xs.push(c.strike); ys.push(c.iv);
  }
  return interpolateY(xs, ys, k0);
}

function interpolateMaturity(slices, key, targetT) {
  const usableSlices = slices.filter((s) => s[key] != null);
  if (!usableSlices.length) return { value: null, near: null, far: null };
  const exact = usableSlices.reduce((a, b) => Math.abs(a.t - targetT) < Math.abs(b.t - targetT) ? a : b);
  if (Math.abs(exact.t - targetT) * YEAR_DAYS < 0.6) return { value: exact[key], near: exact, far: exact };
  const below = usableSlices.filter((s) => s.t <= targetT);
  const above = usableSlices.filter((s) => s.t >= targetT);
  if (!below.length || !above.length) {
    if (Math.abs(exact.t - targetT) * YEAR_DAYS <= 7) return { value: exact[key], near: exact, far: exact };
    return { value: null, near: null, far: null };
  }
  const s1 = below.reduce((a, b) => (a.t > b.t ? a : b));
  const s2 = above.reduce((a, b) => (a.t < b.t ? a : b));
  if (s1.expiry === s2.expiry) return { value: s1[key], near: s1, far: s2 };
  const varT =
    s1[key] * s1[key] * s1.t * (s2.t - targetT) / (s2.t - s1.t) +
    s2[key] * s2[key] * s2.t * (targetT - s1.t) / (s2.t - s1.t);
  if (varT <= 0) return { value: null, near: s1, far: s2 };
  return { value: Math.sqrt(varT / targetT), near: s1, far: s2 };
}

async function upstreamJson(url) {
  const resp = await fetch(url, { headers: { Accept: "application/json", "User-Agent": BROWSER_UA } });
  const text = await resp.text();
  let body;
  try { body = JSON.parse(text); } catch { body = { error: text.slice(0, 200) }; }
  return { ok: resp.ok, status: resp.status, body };
}

async function handleChart(ticker) {
  const encoded = encodeURIComponent(ticker);
  let upstreamResp, lastError;
  for (const host of YAHOO_HOSTS) {
    try {
      upstreamResp = await fetch(`${host}/${encoded}?${yahooQuery()}`, {
        method: "GET",
        headers: { Accept: "application/json", "User-Agent": BROWSER_UA },
      });
    } catch (err) {
      lastError = err;
      continue;
    }
    if (upstreamResp.ok || (upstreamResp.status < 500 && upstreamResp.status !== 429)) break;
  }
  if (!upstreamResp) return json({ error: "upstream fetch failed", detail: String(lastError) }, 502);
  const body = await upstreamResp.arrayBuffer();
  return new Response(body, {
    status: upstreamResp.status,
    headers: {
      ...CORS_HEADERS,
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": upstreamResp.ok ? "public, max-age=300" : "no-store",
    },
  });
}

async function fetchRate() {
  try {
    const { ok, body } = await upstreamJson(`${YAHOO_HOSTS[0]}/%5EIRX?${yahooQuery()}`);
    if (!ok || !body.chart || !body.chart.result) return 0.04;
    const closes = (((body.chart.result[0].indicators || {}).quote || [{}])[0].close || []);
    for (let i = closes.length - 1; i >= 0; i--) {
      if (closes[i] != null) return Number(closes[i]) / 100;
    }
  } catch { /* default */ }
  return 0.04;
}

async function handleIv(ticker) {
  const { ok, status, body } = await upstreamJson(CBOE_OPTIONS + encodeURIComponent(ticker) + ".json");
  if (!ok) return json({ error: "CBOE options fetch failed", status, detail: body }, 502);
  const data = body.data || {};
  const spot = Number(data.close || data.current_price || 0);
  if (!spot) return json({ error: "no underlying price on CBOE payload" }, 502);
  const cboeIv30 = data.iv30 != null ? Number(data.iv30) / 100 : null;
  let asofMs = Date.now();
  if (data.last_trade_time) {
    const parsed = Date.parse(data.last_trade_time);
    if (!Number.isNaN(parsed)) asofMs = parsed;
  }
  const r = await fetchRate();
  const q = 0;
  const byExp = new Map();
  for (const raw of data.options || []) {
    const parsed = parseOcc(raw.option);
    if (!parsed || parsed.root !== ticker) continue;
    const iv = Number(raw.iv);
    if (!Number.isFinite(iv)) continue;
    const key = parsed.expiry.toISOString().slice(0, 10);
    if (!byExp.has(key)) byExp.set(key, { expiry: parsed.expiry, contracts: [] });
    byExp.get(key).contracts.push({
      kind: parsed.kind,
      strike: parsed.strike,
      bid: Number(raw.bid) || 0,
      ask: Number(raw.ask) || 0,
      iv,
      last: Number(raw.last_trade_price) || 0,
    });
  }
  const slices = [];
  for (const { expiry, contracts } of byExp.values()) {
    const t = yearFraction(expiry, asofMs);
    if (t <= 3 / YEAR_DAYS) continue;
    const calls = contracts.filter((c) => c.kind === "call");
    const puts = contracts.filter((c) => c.kind === "put");
    const fwd = spot * Math.exp((r - q) * t);
    let atm = ivAtStrike(calls.concat(puts), fwd) ?? ivAtStrike(calls.concat(puts), spot);
    if (atm == null) {
      const c50 = ivAtDelta(calls, t, spot, r, q, 0.5);
      const p50 = ivAtDelta(puts, t, spot, r, q, -0.5);
      atm = c50 != null && p50 != null ? 0.5 * (c50 + p50) : (c50 ?? p50);
    }
    slices.push({
      expiry: expiry.toISOString().slice(0, 10),
      t,
      atm_iv: atm,
      put25_iv: ivAtDelta(puts, t, spot, r, q, -0.25),
      call25_iv: ivAtDelta(calls, t, spot, r, q, 0.25),
    });
  }
  const targetT = TARGET_DAYS / YEAR_DAYS;
  const atm = interpolateMaturity(slices, "atm_iv", targetT);
  const put25 = interpolateMaturity(slices, "put25_iv", targetT);
  const call25 = interpolateMaturity(slices, "call25_iv", targetT);
  const near = (atm.near || put25.near || call25.near);
  const far = (atm.far || put25.far || call25.far);
  const notes = [`CBOE chain timestamp ${body.timestamp || ""}`];
  if (data.current_price && data.close && Math.abs(Number(data.current_price) - Number(data.close)) / Number(data.close) > 0.02) {
    notes.push(`Using regular-session close ${Number(data.close).toFixed(2)} (feed current_price ${Number(data.current_price).toFixed(2)} ignored as off-session)`);
  }
  const volindex = TICKER_TO_VOLINDEX[ticker] || null;
  return json({
    ticker,
    asof: new Date(asofMs).toISOString(),
    source: "cboe",
    spot,
    r, q,
    atm_iv_30d: atm.value,
    put25_iv_30d: put25.value,
    call25_iv_30d: call25.value,
    skew_25d: put25.value != null && call25.value != null ? put25.value - call25.value : null,
    cboe_iv30: cboeIv30,
    near_expiry: near && near.expiry,
    far_expiry: far && far.expiry,
    volindex,
    volindex_label: volindex ? VOL_INDEXES[volindex] : null,
    notes,
  }, 200, { "Cache-Control": "public, max-age=120" });
}

async function handleVolindex(index) {
  if (!VOL_INDEXES[index]) {
    return json({ error: "unsupported vol index", allowed: Object.keys(VOL_INDEXES) }, 400);
  }
  const resp = await fetch(CBOE_VOL_CSV + index + "_History.csv", {
    headers: { Accept: "text/csv", "User-Agent": BROWSER_UA },
  });
  if (!resp.ok) return json({ error: "CBOE vol-index fetch failed", status: resp.status }, 502);
  const text = await resp.text();
  const lines = text.trim().split(/\r?\n/);
  const points = [];
  for (let i = 1; i < lines.length; i++) {
    const [d, , , , close] = lines[i].split(",");
    if (!d || !close) continue;
    const [m, day, y] = d.split("/");
    if (!y) continue;
    const iso = `${y.padStart(4, "0")}-${m.padStart(2, "0")}-${day.padStart(2, "0")}`;
    const px = Number(close);
    if (Number.isFinite(px)) points.push({ date: iso, close: px });
  }
  return json({
    index,
    label: VOL_INDEXES[index],
    n: points.length,
    first: points[0] || null,
    last: points[points.length - 1] || null,
    points,
  }, 200, { "Cache-Control": "public, max-age=300" });
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }
    if (request.method !== "GET") return json({ error: "method not allowed" }, 405);

    const url = new URL(request.url);
    let r;
    try { r = route(url); r.symbol = decodeURIComponent(r.symbol || "").trim().toUpperCase(); }
    catch { return json({ error: "invalid symbol" }, 400); }

    if (r.kind === "health" && !r.symbol) {
      return json({
        ok: true,
        service: "drawdown-check",
        usage: ["GET /chart/TICKER", "GET /iv/TICKER", "GET /volindex/INDEX"],
      });
    }
    if (!r.symbol || !TICKER_RE.test(r.symbol)) return json({ error: "invalid symbol" }, 400);
    if (r.kind === "iv") return handleIv(r.symbol);
    if (r.kind === "volindex") return handleVolindex(r.symbol);
    return handleChart(r.symbol);
  },
};
