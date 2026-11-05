(function(){
'use strict';
const C = DATA.companies, E = DATA.edges, META = DATA.meta;
const byId = new Map(C.map(c => [c.id, c]));
const $ = s => document.querySelector(s), $$ = s => Array.from(document.querySelectorAll(s));
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const NA = '<span class="muted">n/a</span>';
const slug = c => c.id + '-' + c.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const href = c => '#/company/' + slug(c);
const link = (c, cls) => `<a href="${href(c)}" class="${cls||''}">${esc(c.name)}</a>`;
function fmtM(v, d){ if (v == null || isNaN(v)) return 'n/a'; const a = Math.abs(v), s = v < 0 ? '−' : '';
  if (a >= 1e6) return s + '$' + (a/1e6).toFixed(d==null?2:d) + 'T'; if (a >= 1e3) return s + '$' + (a/1e3).toFixed(d==null?1:d) + 'B'; return s + '$' + Math.round(a).toLocaleString() + 'M'; }
const fmtN = v => v == null ? 'n/a' : (v >= 1e6 ? (v/1e6).toFixed(2) + 'M' : v >= 1e4 ? Math.round(v/1e3) + 'K' : Math.round(v).toLocaleString());
const fmtP = (v, d=1) => v == null ? 'n/a' : (v > 0 ? '+' : '') + v.toFixed(d) + '%';
const fmtRPE = (rev, emp) => { if (!rev || !emp) return ''; const d = rev*1e6/emp; return (d >= 1e6 ? '$' + (d/1e6).toFixed(2) + 'M' : '$' + Math.round(d/1e3).toLocaleString() + 'K') + ' revenue / employee'; };
const pctCls = v => v == null ? 'muted' : v >= 0 ? 'pos' : 'neg';
const sum = (a, f) => a.reduce((s, x) => s + (f(x) || 0), 0);
const SECT = Array.from(d3.rollup(C, v => sum(v, d => d.revenue), d => d.sector)).sort((a,b)=>b[1]-a[1]).map(d=>d[0]);
const PAL = ['#e4572e','#2e86de','#17a589','#f1a208','#8e44ad','#c0392b','#16a085','#d35400','#34495e','#27ae60','#e84393','#0984e3','#b8860b','#6c5ce7','#00b894','#fd79a8','#7f8c8d','#a0522d','#00cec9','#e17055','#5f27cd'];
const scol = d3.scaleOrdinal(SECT, PAL);
const ETYPES = {peer:{n:'Industry peers',c:'#9aa0ad',d:'Same Fortune industry; each company linked to its 3 nearest peers by revenue (Fortune 2026 classification).'},
  customer:{n:'Major customer (10-K)',c:'#e4572e',d:'Customer named alongside a % of revenue/sales in the supplier\'s latest 10-K (SEC EDGAR); evidence sentence kept.'},
  owner:{n:'Ownership stake',c:'#2e86de',d:'"Owned by" (P127) / "owner of" (P1830) statements on Wikidata, e.g. institutional or strategic shareholders.'},
  board:{n:'Shared board member',c:'#8e44ad',d:'A person listed as board member (P3320) of both companies on Wikidata (statements without an end date).'},
  spinoff:{n:'Spin-off / succession',c:'#17a589',d:'Wikidata "separated from" (P807), "replaces" (P1365), "replaced by" (P1366).'},
  parent:{n:'Parent / subsidiary',c:'#f1a208',d:'Wikidata parent organization (P749) / has subsidiary (P355).'}};
const adj = new Map(C.map(c => [c.id, []]));
E.forEach(e => { if (adj.has(e.s) && adj.has(e.t)) { adj.get(e.s).push({e, o: e.t, dir: 'out'}); adj.get(e.t).push({e, o: e.s, dir: 'in'}); } });
const tt = $('#tt');
function tip(ev, html){ tt.innerHTML = html; tt.style.opacity = 1; const w = tt.offsetWidth, h = tt.offsetHeight; let x = ev.clientX + 14, y = ev.clientY + 14; if (x + w > innerWidth - 8) x = ev.clientX - w - 14; if (y + h > innerHeight - 8) y = ev.clientY - h - 14; tt.style.left = x + 'px'; tt.style.top = y + 'px'; }
function untip(){ tt.style.opacity = 0; }
const ctip = c => `<b>#${c.rank} ${esc(c.name)}</b><br>${esc(c.sector)} · ${esc(c.industry)}<br>Revenue ${fmtM(c.revenue)} · Profit ${fmtM(c.profit)}<br>${esc(c.city)}, ${esc(c.st||c.state)}`;
const root = document.documentElement;
window._tiles = [];
function setTheme(t){ root.dataset.theme = t; try { localStorage.setItem('f500theme', t); } catch(e) {} window._tiles.forEach(f => f()); }
let saved = null; try { saved = localStorage.getItem('f500theme'); } catch(e) {}
setTheme(saved || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
$('#theme').onclick = () => { setTheme(root.dataset.theme === 'dark' ? 'light' : 'dark'); if (typeof mapDraw === 'function') mapDraw(); };
const gq = $('#gq'), sugg = $('#sugg'); let selIdx = 0, sres = [];
function searchC(q){ q = q.trim().toLowerCase(); if (!q) return [];
  const sc = c => { const n = c.name.toLowerCase(); if ((c.ticker||'').toLowerCase() === q) return 0; if (n.startsWith(q)) return 1; if (n.includes(q)) return 2; if ((c.ceo||'').toLowerCase().includes(q)) return 3; if ((c.industry||'').toLowerCase().includes(q) || (c.city||'').toLowerCase().includes(q)) return 4; return 9; };
  return C.map(c => [sc(c), c]).filter(d => d[0] < 9).sort((a,b) => a[0]-b[0] || a[1].rank-b[1].rank).slice(0, 12).map(d => d[1]); }
function drawSugg(){ sugg.innerHTML = sres.map((c,i) => `<a href="${href(c)}" class="${i===selIdx?'sel':''}"><span class="rk">#${c.rank}</span><i style="width:8px;height:8px;border-radius:50%;background:${scol(c.sector)};flex:none"></i><span style="flex:1"><b>${esc(c.name)}</b><br><span class="muted" style="font-size:12px">${esc(c.ticker||c.type||'')} · ${esc(c.industry)}${c.ceo ? ' · ' + esc(c.ceo) : ''}</span></span></a>`).join('') || '<div style="padding:12px" class="muted">No match</div>'; sugg.style.display = 'block'; }
gq.addEventListener('input', () => { sres = searchC(gq.value); selIdx = 0; if (gq.value) drawSugg(); else sugg.style.display = 'none'; });
gq.addEventListener('keydown', e => { if (e.key === 'ArrowDown') { selIdx = Math.min(selIdx+1, sres.length-1); drawSugg(); e.preventDefault(); } else if (e.key === 'ArrowUp') { selIdx = Math.max(selIdx-1, 0); drawSugg(); e.preventDefault(); } else if (e.key === 'Enter' && sres[selIdx]) { location.hash = href(sres[selIdx]); gq.value = ''; gq.blur(); } else if (e.key === 'Escape') gq.blur(); });
gq.addEventListener('blur', () => setTimeout(() => { sugg.style.display = 'none'; }, 180));
sugg.addEventListener('mousedown', e => e.preventDefault()); sugg.addEventListener('click', () => { gq.value = ''; sugg.style.display = 'none'; gq.blur(); });
document.addEventListener('keydown', e => { if (e.key === '/' && document.activeElement.tagName !== 'INPUT') { e.preventDefault(); gq.focus(); } });
function hbar(el, data, o){
  el = typeof el === 'string' ? $(el) : el; el.innerHTML = ''; const W = el.clientWidth || 500, rh = o.rh || 22, m = {l: o.ml || 170, r: 74, t: 4, b: 4}, H = data.length * rh + m.t + m.b;
  const svg = d3.select(el).append('svg').attr('width', W).attr('height', H); const x = d3.scaleLinear([0, d3.max(data, d => d.v) || 1], [0, Math.max(10, W - m.l - m.r)]);
  const g = svg.selectAll('g').data(data).join('g').attr('transform', (d,i) => `translate(0,${m.t + i*rh})`).style('cursor', o.click ? 'pointer' : null).on('click', (e,d) => o.click && o.click(d)).on('mousemove', (e,d) => o.tip && tip(e, o.tip(d))).on('mouseleave', untip);
  g.append('text').attr('x', m.l - 8).attr('y', rh/2).attr('dy', '.35em').attr('text-anchor', 'end').style('font-size', '12px').text(d => d.k.length > 26 ? d.k.slice(0,25)+'…' : d.k);
  g.append('rect').attr('x', m.l).attr('y', 3).attr('height', rh - 6).attr('rx', 4).attr('fill', d => d.c || 'var(--acc)').attr('width', 0).transition().duration(600).attr('width', d => Math.max(1, x(d.v)));
  g.append('text').attr('x', d => m.l + x(d.v) + 6).attr('y', rh/2).attr('dy', '.35em').style('font-size', '11.5px').style('font-family', 'var(--mono)').text(d => o.fmt(d.v, d));
}
function spark(vals, w=90, h=22, col='var(--acc2)'){ if (!vals || vals.length < 2) return ''; const x = d3.scaleLinear([0, vals.length-1], [1, w-1]), y = d3.scaleLinear(d3.extent(vals), [h-2, 2]);
  return `<svg class="spark" width="${w}" height="${h}"><path d="${d3.line().x((d,i)=>x(i)).y(d=>y(d))(vals)}" fill="none" stroke="${col}" stroke-width="1.6"/></svg>`; }
