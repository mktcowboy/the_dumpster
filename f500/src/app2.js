function overview(){
  const rev = sum(C, c => c.revenue), prof = sum(C, c => c.profit), emp = sum(C, c => c.employees), mc = sum(C, c => c.mktcap);
  $('#ov-hero').innerHTML = `${fmtM(rev)} in revenue.<br><span style="color:var(--mut)">${fmtN(emp)} people. 500 companies.</span>`;
  const top = C[0], states = new Set(C.map(c => c.state));
  $('#ov-lede').innerHTML = `${link(top)} leads the 2026 list with ${fmtM(top.revenue)} in revenue. Together the 500 earned ${fmtM(prof)} in profit and are worth ${fmtM(mc)} on the stock market. Headquarters span ${states.size} states; the largest sector by revenue is <b>${esc(SECT[0])}</b>.`;
  const pub = C.filter(c => c.type === 'Public').length, loss = C.filter(c => c.profit < 0).length, newc = C.filter(c => c.newcomer).length, fem = C.filter(c => c.femaleCeo).length;
  const k = [['Total revenue', fmtM(rev), `Median ${fmtM(d3.median(C, c => c.revenue))} · cutoff ${fmtM(d3.min(C, c => c.revenue))}`],
    ['Total profit', fmtM(prof), `Aggregate margin ${(prof/rev*100).toFixed(1)}% · ${loss} lost money`],
    ['Employees', fmtN(emp), `Largest employer: ${esc(d3.greatest(C, c => c.employees).name)}`],
    ['Market value', fmtM(mc), `${C.filter(c => c.own === 'public' || c.own === 'gse').length} traded · <a href="#/ownership">${C.filter(c => !['public','gse'].includes(c.own)).length} not traded →</a>`],
    ['Total assets', fmtM(sum(C, c => c.assets)), `${esc(d3.greatest(C, c => c.assets).name)} holds the most`],
    ['Newcomers', newc, 'Companies new to the list in 2026'],
    ['Female CEOs', fem, `${(fem/5).toFixed(1)}% of the list`],
    ['Relationships mapped', E.length.toLocaleString(), Object.keys(ETYPES).map(t => `${E.filter(e => e.type===t).length} ${ETYPES[t].n.split(' ')[0].toLowerCase()}`).join(' · ')]];
  $('#kpis').innerHTML = k.map(d => `<div class="card kpi"><div class="l">${d[0]}</div><div class="v">${d[1]}</div><div class="s">${d[2]}</div></div>`).join('');
  const bySec = SECT.map(s => { const l = C.filter(c => c.sector === s); return {k: s, v: sum(l, c => c.revenue), c: scol(s), n: l.length, p: sum(l, c => c.profit), e: sum(l, c => c.employees)}; });
  hbar('#ch-sector', bySec, {fmt: v => fmtM(v), click: d => { location.hash = '#/industries/' + encodeURIComponent(d.k); }, tip: d => `<b>${esc(d.k)}</b><br>${d.n} companies<br>Revenue ${fmtM(d.v)}<br>Profit ${fmtM(d.p)} (${(d.p/d.v*100).toFixed(1)}%)`});
  hbar('#ch-emp', bySec.slice().sort((a,b) => b.e-a.e).map(d => ({...d, rv: d.v, v: d.e})), {fmt: v => fmtN(v), click: d => { location.hash = '#/industries/' + encodeURIComponent(d.k); }, tip: d => `<b>${esc(d.k)}</b><br>${fmtN(d.e)} employees<br>${fmtRPE(d.rv, d.e)}`});
  (function(){ const el = $('#ch-margin'); el.innerHTML = ''; const W = el.clientWidth || 480, rh = 22, ml = 150, H = SECT.length*rh + 26; const svg = d3.select(el).append('svg').attr('width', W).attr('height', H);
    const x = d3.scaleLinear([-30, 60], [ml, W - 12]).clamp(true); svg.append('g').attr('class','axis').attr('transform', `translate(0,${H-20})`).call(d3.axisBottom(x).ticks(6).tickFormat(d => d + '%'));
    svg.append('line').attr('x1', x(0)).attr('x2', x(0)).attr('y1', 0).attr('y2', H-20).attr('stroke', 'var(--line)');
    SECT.forEach((s,i) => { const l = C.filter(c => c.sector === s && c.margin != null), y = i*rh + rh/2; svg.append('text').attr('x', ml-8).attr('y', y).attr('dy','.35em').attr('text-anchor','end').style('font-size','11.5px').text(s.length>22?s.slice(0,21)+'…':s);
      svg.append('g').selectAll('circle').data(l).join('circle').attr('cx', d => x(d.margin)).attr('cy', d => y + (((d.id*37)%11)-5)*.9).attr('r', 3.2).attr('fill', scol(s)).attr('opacity', .7).style('cursor','pointer').on('mousemove', (e,d) => tip(e, ctip(d) + `<br>Margin ${d.margin.toFixed(1)}%`)).on('mouseleave', untip).on('click', (e,d) => location.hash = href(d));
      const md = d3.median(l, d => d.margin); if (md != null) svg.append('rect').attr('x', x(md)-1.5).attr('y', y-8).attr('width', 3).attr('height', 16).attr('fill', 'var(--ink)'); }); })();
  (function(){ const el = $('#ch-rank'); el.innerHTML = ''; const W = el.clientWidth || 600, H = 250, m = {l: 56, r: 14, t: 10, b: 28}; const svg = d3.select(el).append('svg').attr('width', W).attr('height', H);
    const x = d3.scaleLinear([1, 500], [m.l, W-m.r]), y = d3.scaleLog([d3.min(C, c => c.revenue)*.9, d3.max(C, c => c.revenue)*1.1], [H-m.b, m.t]);
    svg.append('g').attr('class','axis').attr('transform', `translate(0,${H-m.b})`).call(d3.axisBottom(x).ticks(10)); svg.append('g').attr('class','axis').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickFormat(d => fmtM(d, 0)));
    const srt = C.slice().sort((a,b) => a.rank-b.rank); svg.append('path').attr('d', d3.area().x(d => x(d.rank)).y0(H-m.b).y1(d => y(d.revenue))(srt)).attr('fill', 'var(--acc)').attr('opacity', .12);
    svg.selectAll('circle').data(srt).join('circle').attr('cx', d => x(d.rank)).attr('cy', d => y(d.revenue)).attr('r', 2.6).attr('fill', d => scol(d.sector)).style('cursor','pointer').on('mousemove', (e,d) => tip(e, ctip(d))).on('mouseleave', untip).on('click', (e,d) => location.hash = href(d));
    const tot = sum(srt, c => c.revenue), sh = n => (sum(srt.slice(0,n), c => c.revenue)/tot*100).toFixed(1);
    $('#ch-rank-note').innerHTML = `Concentration: the top 10 earn <b>${sh(10)}%</b> of all revenue, the top 50 <b>${sh(50)}%</b>, the top 100 <b>${sh(100)}%</b>. Log scale; colour = sector.`; })();
  const bySt = Array.from(d3.rollup(C, v => ({n: v.length, r: sum(v, c => c.revenue)}), c => c.state)).sort((a,b) => b[1].n - a[1].n).slice(0, 12);
  hbar('#ch-states', bySt.map(([k,v]) => ({k, v: v.n, r: v.r, c: 'var(--acc2)'})), {ml: 120, fmt: (v,d) => `${v} · ${fmtM(d.r,1)}`, click: d => { location.hash = '#/map/' + encodeURIComponent(d.k); }, tip: d => `<b>${esc(d.k)}</b><br>${d.v} HQs · ${fmtM(d.r)} revenue`});
  (function(){ const el = $('#ch-found'); el.innerHTML = ''; const W = el.clientWidth || 400, H = 300, m = {l: 30, r: 8, t: 10, b: 26}; const l = C.filter(c => c.founded); const bins = d3.group(l, c => Math.floor(c.founded/10)*10);
    const keys = d3.range(Math.floor(d3.min(l, c => c.founded)/50)*50, 2030, 10); const x = d3.scaleBand(keys, [m.l, W-m.r]).padding(.15), y = d3.scaleLinear([0, d3.max(keys, k => (bins.get(k)||[]).length)], [H-m.b, m.t]);
    const svg = d3.select(el).append('svg').attr('width', W).attr('height', H); svg.append('g').attr('class','axis').attr('transform', `translate(0,${H-m.b})`).call(d3.axisBottom(x).tickValues(keys.filter(k => k % 50 === 0)).tickFormat(d => d + 's'));
    svg.append('g').attr('class','axis').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(4));
    svg.selectAll('rect').data(keys).join('rect').attr('x', k => x(k)).attr('width', x.bandwidth()).attr('y', k => y((bins.get(k)||[]).length)).attr('height', k => H-m.b-y((bins.get(k)||[]).length)).attr('rx', 2).attr('fill', 'var(--acc)').attr('opacity', .8)
      .on('mousemove', (e,k) => { const b = (bins.get(k)||[]).slice().sort((a,b) => a.founded-b.founded); tip(e, `<b>${k}s · ${b.length} companies</b><br>` + b.slice(0,8).map(c => esc(c.name) + ' (' + c.founded + ')').join('<br>') + (b.length > 8 ? '<br>…' : '')); }).on('mouseleave', untip);
    el.insertAdjacentHTML('beforeend', `<div class="note">${l.length} companies with a known founding year. Oldest: ${l.slice().sort((a,b)=>a.founded-b.founded).slice(0,3).map(c => link(c) + ' (' + c.founded + ')').join(', ')}.</div>`); })();
  const mv = C.filter(c => c.rankChg != null && !c.newcomer); const up = mv.slice().sort((a,b) => b.rankChg-a.rankChg).slice(0,6), dn = mv.slice().sort((a,b) => a.rankChg-b.rankChg).slice(0,6);
  $('#ch-movers').innerHTML = '<ul class="toplist">' + up.map(c => `<li><span class="n">#${c.rank}</span>${link(c)}<span class="x pos">▲${c.rankChg}</span></li>`).join('') + dn.map(c => `<li><span class="n">#${c.rank}</span>${link(c)}<span class="x neg">▼${-c.rankChg}</span></li>`).join('') + '</ul>';
  const lists = [['Most profitable', c => c.profit, fmtM], ['Most valuable', c => c.mktcap, fmtM], ['Largest employers', c => c.employees, fmtN], ['Highest margin (rev > $50B)', c => c.revenue > 50000 ? c.margin : null, v => v.toFixed(1) + '%']];
  $('#toplists').innerHTML = lists.map(([t, f, fm]) => `<div class="card"><h3>${t}</h3><ul class="toplist">${C.filter(c => f(c) != null).sort((a,b) => f(b)-f(a)).slice(0,10).map((c,i) => `<li><span class="n">${i+1}</span><i style="width:8px;height:8px;border-radius:50%;background:${scol(c.sector)};flex:none"></i>${link(c)}<span class="x">${fm(f(c))}</span></li>`).join('')}</ul></div>`).join('');
}
const COLS = [['rank','#',1,c=>c.rank],['name','Company',0,c=>c.name],['ticker','Ticker',0,c=>c.ticker],['sector','Sector',0,c=>c.sector],['industry','Industry',0,c=>c.industry],['hq','HQ',0,c=>c.city+', '+(c.st||'')],
  ['revenue','Revenue',1,c=>c.revenue],['revChg','Rev Δ',1,c=>c.revChg],['profit','Profit',1,c=>c.profit],['margin','Margin',1,c=>c.margin],['assets','Assets',1,c=>c.assets],['mktcap','Mkt value',1,c=>c.mktcap],['employees','Employees',1,c=>c.employees],['trend','Rev. trend (SEC)',0,null],['own','Ownership',0,c=>OWNK.indexOf(c.own)],['ceo','CEO',0,c=>c.ceo],['founded','Founded',1,c=>c.founded]];
let tsort = {k: 'rank', dir: 1}, tstate = {q: '', sector: '', state: '', own: '', nw: false, fem: false, loss: false};
function tableInit(){
  SECT.slice().sort().forEach(s => $('#t-sector').insertAdjacentHTML('beforeend', `<option>${esc(s)}</option>`));
  Array.from(new Set(C.map(c => c.state))).sort().forEach(s => $('#t-state').insertAdjacentHTML('beforeend', `<option>${esc(s)}</option>`));
  $('#tbl thead').innerHTML = '<tr>' + COLS.map(c => `<th data-k="${c[0]}" class="${c[2]?'num':''}">${c[1]}</th>`).join('') + '</tr>';
  $$('#tbl th').forEach(th => th.onclick = () => { const k = th.dataset.k; if (k === 'trend') return; tsort = {k, dir: tsort.k === k ? -tsort.dir : (COLS.find(c=>c[0]===k)[2] && k !== 'rank' ? -1 : 1)}; tableDraw(); });
  $('#t-q').oninput = e => { tstate.q = e.target.value; tableDraw(); }; $('#t-sector').onchange = e => { tstate.sector = e.target.value; tableDraw(); }; $('#t-state').onchange = e => { tstate.state = e.target.value; tableDraw(); };
  OWNK.forEach(k => $('#t-own').insertAdjacentHTML('beforeend', `<option value="${k}">${esc(OWN[k].n)} (${C.filter(c => c.own === k).length})</option>`));
  $('#t-own').onchange = e => { tstate.own = e.target.value; tableDraw(); };
  $('#t-new').onchange = e => { tstate.nw = e.target.checked; tableDraw(); }; $('#t-fem').onchange = e => { tstate.fem = e.target.checked; tableDraw(); }; $('#t-loss').onchange = e => { tstate.loss = e.target.checked; tableDraw(); };
  $('#tbl tbody').onclick = e => { const tr = e.target.closest('tr'); if (tr && !e.target.closest('a')) location.hash = href(byId.get(+tr.dataset.id)); };
  $('#t-csv').onclick = () => { const rows = tableRows(); const keys = ['rank','name','ticker','type','sector','industry','city','state','lat','lon','revenue','revChg','profit','profitChg','margin','assets','equity','mktcap','employees','ceo','founded','website','cik','qid','ownLabel','ownDetail'];
    const csv = [keys.join(',')].concat(rows.map(c => keys.map(k => { const v = c[k]; return v == null ? '' : /[",\n]/.test(String(v)) ? '"' + String(v).replace(/"/g,'""') + '"' : v; }).join(','))).join('\n');
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], {type: 'text/csv'})); a.download = 'fortune500_2026_filtered.csv'; a.click(); };
}
function tableRows(){ const q = tstate.q.trim().toLowerCase();
  const r = C.filter(c => (!q || [c.name,c.ticker,c.ceo,c.city,c.state,c.industry,c.sector].join(' ').toLowerCase().includes(q)) && (!tstate.sector || c.sector === tstate.sector) && (!tstate.state || c.state === tstate.state) && (!tstate.own || c.own === tstate.own) && (!tstate.nw || c.newcomer) && (!tstate.fem || c.femaleCeo) && (!tstate.loss || c.profit < 0));
  const f = COLS.find(c => c[0] === tsort.k)[3]; return r.sort((a,b) => { const x = f(a), y = f(b); if (x == null) return 1; if (y == null) return -1; return (x > y ? 1 : x < y ? -1 : 0) * tsort.dir; }); }
function tableDraw(){ const r = tableRows(); $('#t-count').textContent = `${r.length} of 500`;
  $$('#tbl th').forEach(th => { th.classList.toggle('sorted', th.dataset.k === tsort.k); th.textContent = COLS.find(c => c[0] === th.dataset.k)[1] + (th.dataset.k === tsort.k ? (tsort.dir > 0 ? ' ↑' : ' ↓') : ''); });
  $('#tbl tbody').innerHTML = r.map(c => { const rh = Object.values(c.revHist||{}); return `<tr data-id="${c.id}"><td class="num mono">${c.rank}</td><td class="nm"><a href="${href(c)}" style="text-decoration:none">${esc(c.name)}</a></td><td class="mono">${esc(c.ticker||'—')}</td><td><span class="chip"><i style="background:${scol(c.sector)}"></i>${esc(c.sector)}</span></td><td class="muted" style="max-width:220px;overflow:hidden;text-overflow:ellipsis">${esc(c.industry)}</td><td>${esc(c.city)}, ${esc(c.st||'')}</td>
   <td class="num mono">${fmtM(c.revenue)}</td><td class="num mono ${pctCls(c.revChg)}">${fmtP(c.revChg)}</td><td class="num mono ${c.profit<0?'neg':''}">${fmtM(c.profit)}</td><td class="num mono">${c.margin==null?'n/a':c.margin.toFixed(1)+'%'}</td><td class="num mono">${fmtM(c.assets)}</td><td class="num mono">${fmtM(c.mktcap)}</td><td class="num mono">${fmtN(c.employees)}</td><td>${spark(rh)}</td><td>${ownChip(c)}</td><td>${esc(c.ceo||'n/a')}</td><td class="num mono">${c.founded||'n/a'}</td></tr>`; }).join(''); }
