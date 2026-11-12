// Cloudflare Worker: serves the static site from Workers Static Assets and exposes
// /tiles/<name>.pmtiles as a single byte-range-addressable file, reassembled from
// 512 KiB chunk assets (Workers Static Assets has a 25 MiB per-file limit).
import MANIFEST from './manifest.json';

const CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Range, If-Match', 'Access-Control-Expose-Headers': 'Content-Range, Content-Length, ETag, Accept-Ranges'};

async function chunkRange(env, origin, name, i, lo, hi) {
  const r = await env.ASSETS.fetch(new Request(`${origin}/tiles/${name}/${String(i).padStart(3, '0')}.bin`, {headers: {Range: `bytes=${lo}-${hi}`}}));
  if (r.status === 206) return new Uint8Array(await r.arrayBuffer());
  if (r.status === 200) return new Uint8Array(await r.arrayBuffer()).subarray(lo, hi + 1);
  throw new Error('chunk ' + i + ' status ' + r.status);
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const m = url.pathname.match(/^\/tiles\/([\w-]+)\.pmtiles$/);
    if (!m || !MANIFEST[m[1]]) return env.ASSETS.fetch(req);
    if (req.method === 'OPTIONS') return new Response(null, {headers: CORS});
    const f = MANIFEST[m[1]], size = f.size, C = f.chunk;
    const base = {...CORS, 'Accept-Ranges': 'bytes', 'Content-Type': 'application/octet-stream', 'Cache-Control': 'public, max-age=86400', ETag: `"${f.etag}"`};
    if (req.method === 'HEAD') return new Response(null, {headers: {...base, 'Content-Length': String(size)}});
    const rh = req.headers.get('Range');
    let a = 0, b = Math.min(size - 1, 16383);
    if (rh) {
      const mm = rh.match(/bytes=(\d*)-(\d*)/);
      if (!mm) return new Response('bad range', {status: 416, headers: base});
      if (mm[1] === '') { a = Math.max(0, size - Number(mm[2])); b = size - 1; }
      else { a = Number(mm[1]); b = mm[2] === '' ? size - 1 : Math.min(Number(mm[2]), size - 1); }
      if (a > b || a >= size) return new Response('range not satisfiable', {status: 416, headers: {...base, 'Content-Range': `bytes */${size}`}});
    } else {
      return new Response('Use HTTP Range requests (PMTiles).', {status: 200, headers: {...base, 'Content-Type': 'text/plain'}});
    }
    const parts = [];
    for (let i = Math.floor(a / C); i <= Math.floor(b / C); i++) {
      const lo = Math.max(a, i * C) - i * C, hi = Math.min(b, (i + 1) * C - 1) - i * C;
      parts.push(chunkRange(env, url.origin, m[1], i, lo, hi));
    }
    const bufs = await Promise.all(parts);
    let body;
    if (bufs.length === 1) body = bufs[0];
    else { body = new Uint8Array(b - a + 1); let o = 0; for (const x of bufs) { body.set(x, o); o += x.length; } }
    return new Response(body, {status: 206, headers: {...base, 'Content-Range': `bytes ${a}-${b}/${size}`, 'Content-Length': String(body.length)}});
  },
};
