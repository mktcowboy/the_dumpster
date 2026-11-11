/**
 * Restricted Yahoo Finance chart proxy for the local drawdown.html page.
 *
 * Only forwards GET requests for a single ticker to the Yahoo v8 chart API
 * (query1, then query2). range=max&interval=1d currently returns monthly bars,
 * so this worker uses period1=0&period2=<now>&interval=1d&events=div,split
 * &includeAdjustedClose=true to get the full daily adjusted-close history.
 *
 * Usage: GET /chart/QQQ   (also accepts /QQQ or ?ticker=QQQ)
 */

const YAHOO_HOSTS = [
  "https://query1.finance.yahoo.com/v8/finance/chart",
  "https://query2.finance.yahoo.com/v8/finance/chart",
];
const BROWSER_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

function yahooQuery() {
  const period2 = Math.floor(Date.now() / 1000);
  return `period1=0&period2=${period2}&interval=1d&events=div,split&includeAdjustedClose=true`;
}
// Letters, digits, and the symbols Yahoo uses for share classes, indices, futures, and crypto.
const TICKER_RE = /^[A-Za-z0-9^][A-Za-z0-9._=^-]{0,31}$/;

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

function parseTicker(url) {
  const fromQuery = (url.searchParams.get("ticker") || "").trim();
  if (fromQuery) return fromQuery;
  const parts = url.pathname.split("/").filter(Boolean);
  if (parts.length === 2 && parts[0].toLowerCase() === "chart") return parts[1];
  if (parts.length === 1 && parts[0].toLowerCase() !== "health") return parts[0];
  return "";
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }
    if (request.method !== "GET") {
      return json({ error: "method not allowed" }, 405);
    }

    const url = new URL(request.url);
    let ticker;
    try {
      ticker = decodeURIComponent(parseTicker(url)).trim().toUpperCase();
    } catch {
      return json({ error: "invalid ticker" }, 400);
    }

    if (!ticker) {
      return json({
        ok: true,
        service: "drawdown-check",
        usage: "GET /chart/TICKER",
        upstream: `${YAHOO_HOSTS[0]}/<TICKER>?${yahooQuery()}`,
      });
    }

    if (!TICKER_RE.test(ticker)) {
      return json({ error: "invalid ticker" }, 400);
    }

    const encoded = encodeURIComponent(ticker);
    let upstreamResp;
    let lastError;
    for (const host of YAHOO_HOSTS) {
      const upstream = `${host}/${encoded}?${yahooQuery()}`;
      try {
        upstreamResp = await fetch(upstream, {
          method: "GET",
          headers: {
            Accept: "application/json",
            "User-Agent": BROWSER_UA,
          },
        });
      } catch (err) {
        lastError = err;
        continue;
      }
      if (upstreamResp.ok || (upstreamResp.status < 500 && upstreamResp.status !== 429)) {
        break;
      }
    }
    if (!upstreamResp) {
      return json({ error: "upstream fetch failed", detail: String(lastError) }, 502);
    }

    const body = await upstreamResp.arrayBuffer();
    const cache = upstreamResp.ok ? "public, max-age=300" : "no-store";
    return new Response(body, {
      status: upstreamResp.status,
      headers: {
        ...CORS_HEADERS,
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": cache,
      },
    });
  },
};
