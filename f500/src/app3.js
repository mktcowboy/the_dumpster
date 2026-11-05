let map, clusterLayer, plainLayer, stateLayer, stateGeo, mstate = {mode: 'cluster', metric: 'count', sector: ''}, mapReady = false, tileLayer, mapAgg, mapSel = null;
const TILE = () => 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/' + (root.dataset.theme === 'dark' ? 'World_Dark_Gray_Base' : 'World_Light_Gray_Base') + '/MapServer/tile/{z}/{y}/{x}';
const rScale = d3.scaleSqrt([0, d3.max(C, c => c.revenue)], [5, 34]);
const nk = s => (s||'').toLowerCase();
function mapInit(){
  map = L.map('map', {zoomSnap: .25}).setView([38.5, -96], 4.25);
  tileLayer = L.tileLayer(TILE(), {attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors', maxZoom: 16}).addTo(map);
  window._tiles.push(() => tileLayer && tileLayer.setUrl(TILE()));
  stateGeo = topojson.feature(DATA.states, DATA.states.objects.states);
  SECT.forEach(s => $('#m-sector').insertAdjacentHTML('beforeend', `<option>${esc(s)}</option>`));
  $$('#m-mode button').forEach(b => b.onclick = () => { $$('#m-mode button').forEach(x => x.classList.remove('on')); b.classList.add('on'); mstate.mode = b.dataset.v; mapDraw(); });
  $('#m-metric').onchange = e => { mstate.metric = e.target.value; mapDraw(); }; $('#m-sector').onchange = e => { mstate.sector = e.target.value; mapDraw(); };
  $('#m-legend').innerHTML = SECT.map(s => `<span class="chip" data-s="${esc(s)}"><i style="background:${scol(s)}"></i>${esc(s)}</span>`).join('');
  $$('#m-legend .chip').forEach(ch => ch.onclick = () => { mstate.sector = mstate.sector === ch.dataset.s ? '' : ch.dataset.s; $('#m-sector').value = mstate.sector; mapDraw(); });
  mapReady = true; mapDraw();
}
function marker(c){ const r = Math.round(rScale(c.revenue)); const m = L.marker([c.lat, c.lon], {icon: L.divIcon({className: '', html: `<div class="hqdot" style="width:${r}px;height:${r}px;background:${scol(c.sector)}"></div>`, iconSize: [r, r], iconAnchor: [r/2, r/2]}), riseOnHover: true, title: c.name});
  m._c = c; m.bindPopup(`<b style="font-size:14px">#${c.rank} ${esc(c.name)}</b><br>${esc(c.industry)}<br>${esc(c.city)}, ${esc(c.st||'')}<br>Revenue <b>${fmtM(c.revenue)}</b> · Profit ${fmtM(c.profit)}<br>Employees ${fmtN(c.employees)}<br><a href="${href(c)}">Open full profile →</a>`); return m; }
function mapDraw(){ if (!mapReady) return; [clusterLayer, plainLayer, stateLayer].forEach(l => l && map.removeLayer(l)); clusterLayer = plainLayer = stateLayer = null;
  const list = C.filter(c => c.lat != null && (!mstate.sector || c.sector === mstate.sector));
  $$('#m-legend .chip').forEach(ch => ch.classList.toggle('off', !!mstate.sector && ch.dataset.s !== mstate.sector));
  const agg = d3.rollup(list, v => ({count: v.length, revenue: sum(v, c => c.revenue), profit: sum(v, c => c.profit), employees: sum(v, c => c.employees), mktcap: sum(v, c => c.mktcap), list: v}), c => nk(c.state));
  mapAgg = agg;
  if (mstate.metric !== 'off') { const vals = Array.from(agg.values()).map(a => a[mstate.metric]); const dark = root.dataset.theme === 'dark'; const cs = d3.scaleSequentialSqrt([0, d3.max(vals) || 1], d3.interpolateRgb(dark ? '#232838' : '#fbe9e3', '#d6332c'));
    stateLayer = L.geoJSON(stateGeo, {style: f => { const a = agg.get(nk(f.properties.name)); return {fillColor: a ? cs(Math.max(0, a[mstate.metric])) : 'transparent', fillOpacity: a ? .55 : 0, color: dark ? '#3a3f4e' : '#c9c3b6', weight: .8}; },
      onEachFeature: (f, l) => { const a = agg.get(nk(f.properties.name)); l.bindTooltip(`<b>${esc(f.properties.name)}</b><br>${a ? a.count + ' HQs · ' + fmtM(a.revenue) + ' revenue<br>' + fmtN(a.employees) + ' employees' : 'No Fortune 500 HQ'}`, {sticky: true});
        l.on('click', () => mapSide(f.properties.name)); l.on('mouseover', () => l.setStyle({weight: 2})); l.on('mouseout', () => l.setStyle({weight: .8})); }}).addTo(map); }
  if (mstate.mode === 'cluster') { clusterLayer = L.markerClusterGroup({maxClusterRadius: 45, showCoverageOnHover: false, iconCreateFunction: cl => { const ms = cl.getAllChildMarkers(), n = ms.length, rv = sum(ms, m => m._c.revenue), s = Math.round(30 + Math.sqrt(n)*6);
      return L.divIcon({className: '', html: `<div class="cl" style="width:${s}px;height:${s}px"><div>${n}<small>${fmtM(rv, 1)}</small></div></div>`, iconSize: [s, s]}); }});
    list.forEach(c => clusterLayer.addLayer(marker(c))); map.addLayer(clusterLayer); }
  else if (mstate.mode === 'bubble') { plainLayer = L.layerGroup(list.slice().sort((a,b) => b.revenue-a.revenue).map(marker)).addTo(map); }
  mapSide(mapSel, true); }
function mapSide(st, nofit){ mapSel = st; const el = $('#m-side'); if (!mapAgg) return;
  if (!st) { const rows = Array.from(mapAgg.values()).map(v => ({k: v.list[0].state, ...v})).sort((a,b) => b.revenue - a.revenue);
    el.innerHTML = `<h3>States${mstate.sector ? ' · ' + esc(mstate.sector) : ''}</h3><div class="note" style="margin-bottom:8px">${rows.length} states / DC · click a state on the map or below.</div><table class="data"><thead><tr><th>State</th><th class="num">HQs</th><th class="num">Revenue</th><th class="num">Employees</th></tr></thead><tbody>${rows.map(r => `<tr data-st="${esc(r.k)}"><td>${esc(r.k)}</td><td class="num mono">${r.count}</td><td class="num mono">${fmtM(r.revenue)}</td><td class="num mono">${fmtN(r.employees)}</td></tr>`).join('')}</tbody></table>`;
    el.querySelectorAll('tr[data-st]').forEach(tr => tr.onclick = () => mapSide(tr.dataset.st)); return; }
  const a = mapAgg.get(nk(st)); const list = a ? a.list.slice().sort((x,y) => x.rank-y.rank) : [];
  el.innerHTML = `<a class="chip" id="m-back">← All states</a><h2 style="margin-top:10px">${esc(st)}</h2>` + (a ? `<div class="grid g2" style="margin:10px 0"><div class="kpi"><div class="l">HQs</div><div class="v">${a.count}</div></div><div class="kpi"><div class="l">Revenue</div><div class="v">${fmtM(a.revenue,1)}</div></div><div class="kpi"><div class="l">Profit</div><div class="v">${fmtM(a.profit,1)}</div></div><div class="kpi"><div class="l">Employees</div><div class="v">${fmtN(a.employees)}</div></div></div>
    <h3>Sector mix</h3><div class="legend" style="margin-bottom:12px">${Array.from(d3.rollup(list, v => v.length, c => c.sector)).sort((x,y) => y[1]-x[1]).map(([s,n]) => `<span class="chip"><i style="background:${scol(s)}"></i>${esc(s)} ${n}</span>`).join('')}</div>
    <ul class="toplist">${list.map(c => `<li><span class="n">${c.rank}</span><i style="width:8px;height:8px;border-radius:50%;background:${scol(c.sector)};flex:none"></i>${link(c)}<span class="x muted" style="font-size:11px">${esc(c.city)}</span><span class="x">${fmtM(c.revenue,0)}</span></li>`).join('')}</ul>` : '<p class="muted">No Fortune 500 headquarters here with the current filter.</p>');
  $('#m-back').onclick = () => { mapSide(null); map.setView([38.5, -96], 4.25); };
  if (a && map && !nofit) { const f = stateGeo.features.find(f => nk(f.properties.name) === nk(st)); if (f) map.fitBounds(L.geoJSON(f).getBounds(), {maxZoom: 7, padding: [20,20]}); } }
let istate = {chart: 'treemap', metric: 'revenue', focus: null};
const mval = (c, m) => m === 'count' ? 1 : Math.max(0, c[m] || 0);
function hierarchy(m){ const r = {name: 'Fortune 500', children: SECT.map(s => ({name: s, sector: s, children: Array.from(d3.group(C.filter(c => c.sector === s), c => c.industry)).map(([ind, l]) => ({name: ind, sector: s, children: l.map(c => ({name: c.name, c, sector: s, value: mval(c, m)}))}))}))};
  return d3.hierarchy(r).sum(d => d.value || 0).sort((a,b) => b.value - a.value); }
const fmtMetric = (v, m) => m === 'employees' ? fmtN(v) : m === 'count' ? v + ' cos.' : fmtM(v);
function indInit(){ $$('#i-chart button').forEach(b => b.onclick = () => { $$('#i-chart button').forEach(x => x.classList.remove('on')); b.classList.add('on'); istate.chart = b.dataset.v; indDraw(); });
  $$('#i-metric button').forEach(b => b.onclick = () => { $$('#i-metric button').forEach(x => x.classList.remove('on')); b.classList.add('on'); istate.metric = b.dataset.v; indDraw(); }); sectorTable(); }
function indDraw(){ $('#treemap').style.display = istate.chart === 'treemap' ? 'block' : 'none'; $('#sunburst').style.display = istate.chart === 'sunburst' ? 'block' : 'none';
  const cr = $('#i-crumbs'); cr.innerHTML = `<a data-f="">All sectors</a>` + (istate.focus ? ` › <b>${esc(istate.focus)}</b>` : '') + `<span class="spacer"></span><span class="muted">${istate.chart === 'treemap' ? 'Click a sector to drill in; click a company to open it.' : 'Click a sector or industry to zoom; click the centre to zoom out.'}</span>`;
  cr.querySelector('a').onclick = () => { location.hash = '#/industries'; };
  if (istate.chart === 'treemap') treemap(); else sunburst(); indList(); scatter(); }
function treemap(){ const el = $('#treemap'); el.innerHTML = ''; const W = el.clientWidth || 1000, H = 640; let h = hierarchy(istate.metric); if (istate.focus) { const n = h.children.find(d => d.data.name === istate.focus); if (n) h = n.copy ? d3.hierarchy(n.data).sum(d => d.value || 0).sort((a,b) => b.value - a.value) : n; }
  const leafDepth = istate.focus ? 2 : 3;
  d3.treemap().size([W, H]).paddingOuter(3).paddingTop(d => d.depth > 0 && d.depth < leafDepth ? 19 : 3).paddingInner(1.5).round(true)(h);
  const svg = d3.select(el).append('svg').attr('width', W).attr('height', H).attr('class', 'tm');
  const nodes = h.descendants().filter(d => d.depth > 0 && d.value > 0);
  const g = svg.selectAll('g').data(nodes).join('g').attr('transform', d => `translate(${d.x0},${d.y0})`);
  g.append('rect').attr('width', d => d.x1-d.x0).attr('height', d => d.y1-d.y0).attr('rx', 3).attr('fill', d => { const c = d3.color(scol(d.data.sector)); return d.depth === leafDepth ? c.brighter((((d.data.c ? d.data.c.id : 0) % 5) * .12) - .1).formatHex() : d.depth === leafDepth - 1 ? c.darker(.45).formatHex() : c.darker(1.1).formatHex(); })
    .on('mousemove', (e,d) => tip(e, d.data.c ? ctip(d.data.c) : `<b>${esc(d.data.name)}</b><br>${fmtMetric(d.value, istate.metric)} · ${d.leaves().length} companies`)).on('mouseleave', untip)
    .on('click', (e,d) => { if (d.data.c) location.hash = href(d.data.c); else if (!istate.focus) location.hash = '#/industries/' + encodeURIComponent(d.data.sector); });
  g.filter(d => (d.x1-d.x0) > 44 && (d.y1-d.y0) > 16).append('text').attr('x', 5).attr('y', 13).style('font-size', d => d.depth === leafDepth ? '11px' : '12px').style('font-weight', d => d.depth < leafDepth ? 700 : 500)
    .text(d => { const w = Math.floor((d.x1-d.x0)/6.6); const t = d.data.name; return t.length > w ? t.slice(0, Math.max(0, w-1)) + '…' : t; });
  g.filter(d => d.depth === leafDepth && (d.x1-d.x0) > 56 && (d.y1-d.y0) > 32).append('text').attr('x', 5).attr('y', 27).style('font-size', '10.5px').style('opacity', .85).text(d => fmtMetric(d.value, istate.metric)); }
function sunburst(){ const el = $('#sunburst'); el.innerHTML = ''; const W = el.clientWidth || 900, H = 640, R = Math.min(W, H)/2 - 6; const h = hierarchy(istate.metric); d3.partition().size([2*Math.PI, h.height + 1])(h); h.each(d => d.current = d);
  const arc = d3.arc().startAngle(d => d.x0).endAngle(d => d.x1).padAngle(d => Math.min((d.x1-d.x0)/2, .004)).padRadius(R/1.5).innerRadius(d => d.y0 * R/4).outerRadius(d => Math.max(d.y0 * R/4, d.y1 * R/4 - 1));
  const svg = d3.select(el).append('svg').attr('width', W).attr('height', H).append('g').attr('transform', `translate(${W/2},${H/2})`);
  const vis = d => d.y1 <= 4 && d.y0 >= 1 && d.x1 > d.x0;
  const path = svg.append('g').selectAll('path').data(h.descendants().slice(1)).join('path').attr('fill', d => { const c = d3.color(scol(d.data.sector)); return (d.depth === 1 ? c : d.depth === 2 ? c.brighter(.35) : c.brighter(.75)).formatHex(); }).attr('fill-opacity', d => vis(d.current) ? 1 : 0).attr('d', d => arc(d.current)).style('cursor', 'pointer')
    .on('mousemove', (e,d) => tip(e, d.data.c ? ctip(d.data.c) : `<b>${esc(d.data.name)}</b><br>${fmtMetric(d.value, istate.metric)} · ${d.leaves().length} companies`)).on('mouseleave', untip)
    .on('click', (e,p) => { if (p.data.c) { location.hash = href(p.data.c); return; } zoom(p); });
  function lv(d){ return d.y1 <= 4 && d.y0 >= 1 && (d.y1-d.y0)*(d.x1-d.x0) > .06; }
  function lt(d){ const x = (d.x0+d.x1)/2*180/Math.PI, y = (d.y0+d.y1)/2*R/4; return `rotate(${x-90}) translate(${y},0) rotate(${x < 180 ? 0 : 180})`; }
  const label = svg.append('g').attr('pointer-events', 'none').attr('text-anchor', 'middle').selectAll('text').data(h.descendants().slice(1)).join('text').attr('dy', '.35em').style('font-size', '10.5px').style('fill', '#fff')
    .attr('fill-opacity', d => +lv(d.current)).attr('transform', d => lt(d.current)).text(d => d.data.name.length > 18 ? d.data.name.slice(0,17) + '…' : d.data.name);
  let cur = h;
  svg.append('circle').attr('r', R/4).attr('fill', 'var(--card)').style('cursor', 'pointer').on('click', () => zoom(cur.parent || h));
  const ctext = svg.append('text').attr('text-anchor', 'middle').attr('dy', '.35em').attr('pointer-events', 'none').style('font-family', 'var(--serif)').style('font-size', '15px').style('fill', 'var(--ink)').text('Fortune 500');
  function zoom(p){ cur = p; ctext.text(p.depth ? (p.data.name.length > 22 ? p.data.name.slice(0,21)+'…' : p.data.name) : 'Fortune 500');
    h.each(d => d.target = {x0: Math.max(0, Math.min(1, (d.x0 - p.x0)/(p.x1 - p.x0))) * 2*Math.PI, x1: Math.max(0, Math.min(1, (d.x1 - p.x0)/(p.x1 - p.x0))) * 2*Math.PI, y0: Math.max(0, d.y0 - p.depth), y1: Math.max(0, d.y1 - p.depth)});
    const t = svg.transition().duration(650);
    path.transition(t).tween('data', d => { const i = d3.interpolate(d.current, d.target); return tt_ => d.current = i(tt_); }).attr('fill-opacity', d => vis(d.target) ? 1 : 0).attrTween('d', d => () => arc(d.current));
    label.transition(t).attr('fill-opacity', d => +lv(d.target)).attrTween('transform', d => () => lt(d.current)); }
  if (istate.focus) { const n = h.children.find(d => d.data.name === istate.focus); if (n) setTimeout(() => zoom(n), 50); } }
function indList(){ const s = istate.focus; const l = s ? C.filter(c => c.sector === s) : C; $('#i-indtitle').textContent = s ? `Industries in ${s}` : `All ${new Set(C.map(c => c.industry)).size} industries`;
  const g = Array.from(d3.group(l, c => c.industry)).map(([k, v]) => ({k, v, r: sum(v, c => c.revenue), p: sum(v, c => c.profit)})).sort((a,b) => b.r-a.r);
  $('#i-indlist').innerHTML = g.map(d => `<details style="border-bottom:1px solid var(--line);padding:8px 0"><summary style="cursor:pointer;display:flex;gap:8px;align-items:center"><i style="width:8px;height:8px;border-radius:50%;background:${scol(d.v[0].sector)};flex:none;display:inline-block"></i><b style="flex:1">${esc(d.k)}</b><span class="mono muted">${d.v.length}</span><span class="mono">${fmtM(d.r,0)}</span></summary><div class="note" style="margin:6px 0">Profit ${fmtM(d.p)} · margin ${(d.p/d.r*100).toFixed(1)}% · median revenue ${fmtM(d3.median(d.v, c => c.revenue))}</div><ul class="toplist">${d.v.slice().sort((a,b) => a.rank-b.rank).map(c => `<li><span class="n">${c.rank}</span>${link(c)}<span class="x">${fmtM(c.revenue,0)}</span></li>`).join('')}</ul></details>`).join(''); }
let secSort = {k: 'revenue', dir: -1};
function sectorTable(){ const rows = SECT.map(s => { const l = C.filter(c => c.sector === s); const r = sum(l, c => c.revenue), p = sum(l, c => c.profit), e = sum(l, c => c.employees);
    return {s, n: l.length, revenue: r, profit: p, margin: p/r*100, medMargin: d3.median(l, c => c.margin), employees: e, rpe: r*1e6/e, mktcap: sum(l, c => c.mktcap), assets: sum(l, c => c.assets), top: d3.least(l, c => c.rank), ind: new Set(l.map(c => c.industry)).size}; });
  const cols = [['s','Sector'],['n','Cos.'],['ind','Industries'],['revenue','Revenue'],['profit','Profit'],['margin','Agg. margin'],['medMargin','Median margin'],['employees','Employees'],['rpe','Rev / employee'],['mktcap','Market value'],['assets','Assets'],['top','Largest']];
  rows.sort((a,b) => { const x = a[secSort.k], y = b[secSort.k]; return (typeof x === 'string' ? x.localeCompare(y) : (x||0) - (y||0)) * secSort.dir; });
  const pc = v => v == null ? 'n/a' : v.toFixed(1)+'%';
  $('#sectbl thead').innerHTML = '<tr>' + cols.map(c => `<th data-k="${c[0]}" class="${c[0]==='s'||c[0]==='top'?'':'num'} ${secSort.k===c[0]?'sorted':''}">${c[1]}</th>`).join('') + '</tr>';
  const maxR = d3.max(rows, r => r.revenue);
  $('#sectbl tbody').innerHTML = rows.map(r => `<tr data-s="${esc(r.s)}"><td><span class="chip"><i style="background:${scol(r.s)}"></i>${esc(r.s)}</span></td><td class="num mono">${r.n}</td><td class="num mono">${r.ind}</td><td class="num mono"><span style="display:inline-block;height:6px;border-radius:3px;background:${scol(r.s)};width:${Math.round(r.revenue/maxR*80)}px;margin-right:6px;vertical-align:middle"></span>${fmtM(r.revenue)}</td><td class="num mono">${fmtM(r.profit)}</td><td class="num mono">${pc(r.margin)}</td><td class="num mono">${pc(r.medMargin)}</td><td class="num mono">${fmtN(r.employees)}</td><td class="num mono">$${Math.round(r.rpe/1000).toLocaleString()}K</td><td class="num mono">${fmtM(r.mktcap)}</td><td class="num mono">${fmtM(r.assets)}</td><td>${link(r.top)}</td></tr>`).join('');
  $$('#sectbl th').forEach(th => th.onclick = () => { const k = th.dataset.k; if (k === 'top') return; secSort = {k, dir: secSort.k === k ? -secSort.dir : (k === 's' ? 1 : -1)}; sectorTable(); });
  $$('#sectbl tbody tr').forEach(tr => tr.onclick = e => { if (!e.target.closest('a')) location.hash = '#/industries/' + encodeURIComponent(tr.dataset.s); }); }
function scatter(){ const el = $('#ch-scatter'); el.innerHTML = ''; const W = el.clientWidth || 700, H = 460, m = {l: 50, r: 14, t: 10, b: 34}; const l = C.filter(c => c.margin != null && c.revenue > 0);
  const x = d3.scaleLog(d3.extent(l, c => c.revenue), [m.l, W-m.r]).nice(), y = d3.scaleLinear([-30, 60], [H-m.b, m.t]).clamp(true);
  const svg = d3.select(el).append('svg').attr('width', W).attr('height', H); svg.append('g').attr('class','axis').attr('transform', `translate(0,${H-m.b})`).call(d3.axisBottom(x).ticks(6).tickFormat(d => [1e4,2e4,5e4,1e5,2e5,5e5].includes(d) ? fmtM(d, 0) : ''));
  svg.append('g').attr('class','axis').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(8).tickFormat(d => d + '%')); svg.append('line').attr('x1', m.l).attr('x2', W-m.r).attr('y1', y(0)).attr('y2', y(0)).attr('stroke', 'var(--mut)').attr('stroke-dasharray', '3 3');
  svg.append('g').selectAll('circle').data(l.slice().sort((a,b) => (a.sector === istate.focus) - (b.sector === istate.focus))).join('circle').attr('cx', d => x(d.revenue)).attr('cy', d => y(d.margin)).attr('r', d => 2.5 + Math.sqrt(d.employees||0)/220).attr('fill', d => scol(d.sector)).attr('opacity', d => !istate.focus || d.sector === istate.focus ? .8 : .08).attr('stroke', 'var(--card)').attr('stroke-width', .6).style('cursor', 'pointer')
    .on('mousemove', (e,d) => tip(e, ctip(d) + `<br>Margin ${d.margin.toFixed(1)}%`)).on('mouseleave', untip).on('click', (e,d) => location.hash = href(d)); }
