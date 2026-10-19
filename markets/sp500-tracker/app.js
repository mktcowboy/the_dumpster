(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const WIKI = 'https://en.wikipedia.org/wiki/Historical_components_of_the_S%26P_500';
  const COLORS = ['#14324f', '#1f8b82', '#9460b2', '#da8734', '#929ba7'];
  const month = date => date.slice(0, 7);
  const monthIndex = key => Number(key.slice(0, 4)) * 12 + Number(key.slice(5, 7)) - 1;
  const time = date => Date.parse(date.length === 7 ? date + '-01T12:00:00Z' : date + 'T12:00:00Z');
  const fmtDate = date => new Date(time(date)).toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric', timeZone:'UTC'});
  const fmtMonth = key => new Date(time(key)).toLocaleDateString('en-US', {month:'short', year:'numeric', timeZone:'UTC'});
  const pct = (value, unit = '%') => value == null || !Number.isFinite(value) ? '—' : '<span class="' + (value >= 0 ? 'pos' : 'neg') + '">' + (value >= 0 ? '+' : '') + value.toFixed(1) + unit + '</span>';
  const source = event => {
    const url = event.src || WIKI;
    let title;
    try { title = new URL(url).hostname.replace(/^www\./, ''); } catch { return '—'; }
    return '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer" title="' + esc(event.src_note || '') + '">' + esc(title) + '</a>';
  };
  const byDate = new Map(), stocks = new Map();
  DATA.events.forEach((event, index) => {
    event.id = index;
    if (!byDate.has(event.date)) byDate.set(event.date, []);
    byDate.get(event.date).push(event);
    for (const action of ['added', 'removed']) {
      const ticker = event[action + '_t'];
      if (!ticker) continue;
      if (!stocks.has(ticker)) stocks.set(ticker, {ticker, name:event[action + '_n'], events:[]});
      const stock = stocks.get(ticker);
      stock.name = event[action + '_n'] || stock.name;
      stock.events.push({event, action});
    }
  });
  stocks.forEach(stock => {
    stock.events.sort((a,b) => a.event.date.localeCompare(b.event.date));
    const first = stock.events[0].event.date;
    const raw = DATA.prices[stock.ticker]?.px || [];
    stock.reused = raw.length > 0 && time(raw[0][0]) - time(first) > 365 * 86400000;
    // Yahoo may include both a completed monthly bar and a live bar in one month.
    // Use the last observation per month in tables and comparisons alike.
    stock.prices = stock.reused ? [] : [...new Map(raw.map(p => [month(p[0]), p])).values()].sort((a,b)=>a[0].localeCompare(b[0]));
  });
  const state = {view:'changes', returnView:'changes', detail:null, comparisons:[], historyPlot:null, detailPlot:null};
  const years = [...new Set(DATA.events.map(e => e.date.slice(0,4)))].sort();
  $('year').innerHTML += years.map(y => '<option>' + y + '</option>').join('');
  const tickerButton = (ticker, name, id, action) => '<button class="ticker-link ' + action + '" data-ticker="' + esc(ticker) + '" data-event="' + id + '" data-action="' + action + '">' + esc(ticker) + '</button>' + (name ? '<span class="company">' + esc(name) + '</span>' : '');
  const bindTickers = container => container.querySelectorAll('[data-ticker]').forEach(button => button.addEventListener('click', () => openDetail(button.dataset.ticker, Number(button.dataset.event), button.dataset.action)));
  function statistics(items) {
    $('stats').innerHTML = items.map(([value,label]) => '<div class="stat"><div class="value">' + value + '</div><div class="label">' + label + '</div></div>').join('');
  }
  function chosenRows() {
    const q = $('search').value.trim().toLowerCase(), year = $('year').value, coverage = $('coverage').value;
    let rows;
    if (state.view === 'changes') {
      rows = DATA.events.filter(e => (year === 'all' || e.date.startsWith(year)) && (!q || [e.date,e.added_t,e.added_n,e.removed_t,e.removed_n,e.reason].join(' ').toLowerCase().includes(q))).map(e => ({date:e.date, ticker:e.added_t || e.removed_t, event:e}));
    } else {
      rows = [...stocks.values()].filter(s => state.view !== 'removed' || s.events.some(e => e.action === 'removed')).map(s => {
        const events = s.events.filter(e => state.view !== 'removed' || e.action === 'removed');
        const latest = events[events.length - 1];
        return {date:latest.event.date, ticker:s.ticker, stock:s, event:latest.event, action:latest.action};
      }).filter(r => (year === 'all' || r.date.startsWith(year)) && (!q || [r.ticker,r.stock.name,r.date,r.event.reason].join(' ').toLowerCase().includes(q)) && (coverage === 'all' || (coverage === 'available' ? r.stock.prices.length > 0 : !r.stock.prices.length)));
    }
    const sort=$('sort').value;
    rows.sort((a,b) => {
      if(sort==='ticker')return a.ticker.localeCompare(b.ticker);
      if(a.stock && ['return-high','return-low','excess'].includes(sort)) {
        const key=sort==='excess'?'excess':'total', av=stockMetrics(a.stock,a.event)[key], bv=stockMetrics(b.stock,b.event)[key];
        if(av==null)return bv==null?0:1;if(bv==null)return -1;
        return sort==='return-low'?av-bv:bv-av;
      }
      return sort==='oldest'?a.date.localeCompare(b.date):b.date.localeCompare(a.date);
    });
    return rows;
  }
  const spyMonths=new Map(DATA.prices.SPY.px.map(p=>[month(p[0]),p[1]]));
  function stockMetrics(stock, event) {
    stock.metrics=stock.metrics||new Map();
    if(stock.metrics.has(event.date))return stock.metrics.get(event.date);
    const points=stock.prices.filter(p=>month(p[0])>=month(event.date)&&spyMonths.has(month(p[0])));
    const total=points.length>1?(points.at(-1)[1]/points[0][1]-1)*100:null;
    const spy=points.length>1?(spyMonths.get(month(points.at(-1)[0]))/spyMonths.get(month(points[0][0]))-1)*100:null;
    const metrics={total,excess:total!=null?total-spy:null};stock.metrics.set(event.date,metrics);return metrics;
  }
  function renderOverview() {
    const changes = state.view === 'changes';
    $('history').hidden = !changes;
    $('coverage').hidden = changes;
    document.querySelectorAll('[data-stock-sort]').forEach(option=>{option.disabled=changes;option.hidden=changes;});
    if(changes&&['return-high','return-low','excess'].includes($('sort').value))$('sort').value='newest';
    $('table-title').textContent = changes ? 'Constituent change log' : state.view === 'removed' ? 'Removed stocks' : 'All tickers in the change log';
    $('table-hint').textContent = changes ? 'Click an added or removed ticker to open its chart and comparison tools.' : 'Click a ticker for its performance, membership events, and stock comparisons. Year filters use the most recent relevant event.';
    if (changes) statistics([[DATA.events.length,'Change events'],[DATA.events.filter(e=>e.added_t).length,'Additions'],[DATA.events.filter(e=>e.removed_t).length,'Removals'],[stocks.size,'Distinct tickers in log']]);
    else {
      const all = [...stocks.values()].filter(s => state.view !== 'removed' || s.events.some(e=>e.action==='removed'));
      statistics([[all.length,state.view==='removed'?'Removed tickers':'Tickers in log'],[all.filter(s=>s.prices.length).length,'With usable price history'],[all.filter(s=>s.reused).length,'Possible ticker reuse'],[all.filter(s=>!s.prices.length&&!s.reused).length,'Price history unavailable']]);
    }
    $('table-head').innerHTML = changes ? '<tr><th>Effective date</th><th>Added</th><th>Removed</th><th>Reason</th><th>Source</th></tr>' : '<tr><th>Ticker / company</th><th>' + (state.view === 'removed' ? 'Last removal' : 'Last index event') + '</th><th>Action</th><th>Price return since event</th><th>vs SPY</th><th>Price history</th><th>Source</th></tr>';
    const rows = chosenRows();
    $('rows').innerHTML = rows.map(r => {
      const e = r.event;
      if (changes) return '<tr><td class="date">' + fmtDate(e.date) + '</td><td>' + (e.added_t ? tickerButton(e.added_t,e.added_n,e.id,'added') : '—') + '</td><td>' + (e.removed_t ? tickerButton(e.removed_t,e.removed_n,e.id,'removed') : '—') + '</td><td>' + esc(e.reason) + '</td><td class="source">' + source(e) + '</td></tr>';
      const s = r.stock;
      const coverage = s.reused ? 'Possible ticker reuse' : s.prices.length ? 'Through ' + fmtMonth(month(s.prices.at(-1)[0])) : 'Unavailable';
      const metrics=stockMetrics(s,e);
      return '<tr><td>' + tickerButton(s.ticker,s.name,e.id,r.action) + '</td><td class="date">' + fmtDate(r.date) + '</td><td>' + esc(r.action) + '</td><td>' + pct(metrics.total) + '</td><td>' + pct(metrics.excess,' pp') + '</td><td><span class="pill ' + (s.prices.length?'available':'') + '">' + coverage + '</span></td><td class="source">' + source(e) + '</td></tr>';
    }).join('') || '<tr><td colspan="7" class="empty">No matching records.</td></tr>';
    const total = changes ? DATA.events.length : [...stocks.values()].filter(s=>state.view!=='removed'||s.events.some(e=>e.action==='removed')).length;
    $('count').textContent = rows.length + ' of ' + total + (changes ? ' events' : ' tickers');
    bindTickers($('rows'));
    if (changes) drawHistory();
  }
  function showView(view) {
    state.view = view;
    $('overview').hidden = false;
    $('detail').hidden = true;
    document.querySelectorAll('[data-view]').forEach(button => {
      const active = button.dataset.view === view;
      button.classList.toggle('active',active);
      button.setAttribute('aria-pressed',String(active));
    });
    renderOverview();
  }
  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => {
    if (state.view !== button.dataset.view) { $('search').value = ''; $('year').value = 'all'; $('coverage').value = 'all'; }
    showView(button.dataset.view);
  }));
  ['search','year','coverage','sort'].forEach(id => $(id).addEventListener(id==='search'?'input':'change',renderOverview));
  $('csv').addEventListener('click', () => {
    const rows = chosenRows(), changes = state.view === 'changes';
    const fields = changes ? ['date','added_ticker','added_name','removed_ticker','removed_name','reason','source_url'] : ['ticker','company','event_date','action','price_return_since_event_pct','excess_vs_spy_pp','price_coverage','source_url'];
    const quoteCSV = value => '"' + String(value ?? '').replace(/"/g,'""') + '"';
    const lines = [fields.join(',')];
    rows.forEach(r => {
      const e = r.event;
      const values = changes ? [e.date,e.added_t,e.added_n,e.removed_t,e.removed_n,e.reason,e.src||WIKI] : [r.ticker,r.stock.name,r.date,r.action,stockMetrics(r.stock,e).total,stockMetrics(r.stock,e).excess,r.stock.reused?'possible ticker reuse':r.stock.prices.length?'available':'unavailable',e.src||WIKI];
      lines.push(values.map(quoteCSV).join(','));
    });
    const url = URL.createObjectURL(new Blob([lines.join('\r\n')],{type:'text/csv;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = 'sp500-' + state.view + '.csv'; link.click();
    setTimeout(()=>URL.revokeObjectURL(url),4000);
  });
  // A shared canvas renderer keeps both views responsive without external libraries.
  function chart(canvas, series, markers = [], empty = 'No price history available') {
    const width = canvas.clientWidth, height = canvas.clientHeight, scale = window.devicePixelRatio || 1;
    canvas.width = width * scale; canvas.height = height * scale;
    const ctx = canvas.getContext('2d'); ctx.setTransform(scale,0,0,scale,0,0); ctx.clearRect(0,0,width,height);
    ctx.font = '11px sans-serif';
    const points = series.flatMap(s=>s.points);
    if (!points.length) { ctx.fillStyle='#626d7a'; ctx.textAlign='center'; ctx.fillText(empty,width/2,height/2); return null; }
    const left = 58, right = 20, top = 20, bottom = 32;
    let lowTime = Math.min(...points.map(p=>time(p[0]))), highTime = Math.max(...points.map(p=>time(p[0])));
    if (lowTime === highTime) { lowTime -= 15*86400000; highTime += 15*86400000; }
    const values = points.map(p=>p[1]);
    const low = Math.min(...values), high = Math.max(...values), margin = Math.max((high-low)*.07,1);
    const min = low-margin, max = high+margin;
    const X = date => left+(time(date)-lowTime)/(highTime-lowTime)*(width-left-right);
    const Y = value => top+(max-value)/(max-min)*(height-top-bottom);
    ctx.textBaseline='middle'; ctx.textAlign='right';
    for (let i=0;i<=5;i++) {
      const value=min+(max-min)*i/5, y=Y(value);
      ctx.strokeStyle='#edf0f4'; ctx.lineWidth=1; ctx.beginPath(); ctx.moveTo(left,y); ctx.lineTo(width-right,y); ctx.stroke();
      ctx.fillStyle='#7a8593'; ctx.fillText(value.toFixed(max-min<10?1:0),left-9,y);
    }
    ctx.textAlign='center'; ctx.textBaseline='top';
    const tickCount = width<550?4:7;
    for (let i=0;i<tickCount;i++) {
      const timestamp = lowTime+(highTime-lowTime)*i/(tickCount-1);
      ctx.fillStyle='#7a8593';
      ctx.fillText(new Date(timestamp).toLocaleDateString('en-US',{month:'short',year:'2-digit',timeZone:'UTC'}),left+(width-left-right)*i/(tickCount-1),height-bottom+10);
    }
    markers.forEach(marker => {
      const x=X(marker.date); if(x<left||x>width-right)return;
      ctx.strokeStyle=marker.color; ctx.globalAlpha=.5; ctx.beginPath(); ctx.moveTo(x,top); ctx.lineTo(x,height-bottom); ctx.stroke(); ctx.globalAlpha=1;
      if(marker.label){ctx.fillStyle=marker.color;ctx.textAlign='left';ctx.fillText(marker.label,x+4,top+3);}
    });
    series.forEach(s => {
      ctx.strokeStyle=s.color; ctx.lineWidth=1.8; ctx.setLineDash(s.dashed?[5,4]:[]); ctx.beginPath();
      s.points.forEach((p,i)=>{const x=X(p[0]),y=Y(p[1]);i?ctx.lineTo(x,y):ctx.moveTo(x,y);}); ctx.stroke(); ctx.setLineDash([]);
      if(s.points.length===1){ctx.fillStyle=s.color;ctx.beginPath();ctx.arc(X(s.points[0][0]),Y(s.points[0][1]),3,0,Math.PI*2);ctx.fill();}
    });
    return {X,Y,series,markers:markers.filter(m=>X(m.date)>=left&&X(m.date)<=width-right)};
  }
  function tooltip(canvas, tip, event, content) {
    const rect=canvas.getBoundingClientRect();
    tip.innerHTML=content; tip.style.display='block';
    tip.style.left=Math.max(8,Math.min(event.clientX-rect.left+14,rect.width-tip.offsetWidth-8))+'px';
    tip.style.top=Math.max(8,Math.min(event.clientY-rect.top+12,rect.height-tip.offsetHeight-8))+'px';
  }
  function drawHistory() {
    const year=$('year').value;
    const points=DATA.spy.filter(p=>year==='all'||p.d.startsWith(year)).map(p=>[p.d,p.c]);
    const markers=[...byDate].filter(([d])=>year==='all'||d.startsWith(year)).map(([date,events])=>{
      const adds=events.filter(e=>e.added_t).length, removes=events.filter(e=>e.removed_t).length;
      return {date,events,color:adds>removes?'#1f5fa8':removes>adds?'#b3372f':'#929ba7'};
    });
    state.historyPlot=chart($('history-chart'),[{name:'SPY',color:COLORS[0],points}],markers);
  }
  const yearCounts=years.map(year=>({year,adds:DATA.events.filter(e=>e.date.startsWith(year)&&e.added_t).length,removes:DATA.events.filter(e=>e.date.startsWith(year)&&e.removed_t).length}));
  const maxCount=Math.max(...yearCounts.flatMap(y=>[y.adds,y.removes]));
  $('year-bars').innerHTML=yearCounts.map(y=>'<div class="year-bar"><span>'+y.year+'</span><span class="bars"><i style="background:#1f5fa8;width:'+y.adds/maxCount*100+'%"></i><i style="background:#b3372f;width:'+y.removes/maxCount*100+'%"></i></span><span>'+y.adds+' / '+y.removes+'</span></div>').join('');
  function nearestMarker(event) {
    if(!state.historyPlot)return null;
    const x=event.clientX-$('history-chart').getBoundingClientRect().left;
    return state.historyPlot.markers.reduce((best,m)=>Math.abs(state.historyPlot.X(m.date)-x)<(best?Math.abs(state.historyPlot.X(best.date)-x):9)?m:best,null);
  }
  $('history-chart').addEventListener('mousemove',event=>{
    const marker=nearestMarker(event);
    if(marker)tooltip($('history-chart'),$('history-tip'),event,'<b>'+fmtDate(marker.date)+'</b>'+marker.events.map(e=>'<div>'+(e.added_t?'+ '+esc(e.added_t)+' '+esc(e.added_n):'')+(e.removed_t?'<br>− '+esc(e.removed_t)+' '+esc(e.removed_n):'')+'</div>').join(''));
    else if(state.historyPlot){
      const x=event.clientX-$('history-chart').getBoundingClientRect().left;
      const nearest=state.historyPlot.series[0].points.reduce((a,b)=>Math.abs(state.historyPlot.X(a[0])-x)<Math.abs(state.historyPlot.X(b[0])-x)?a:b);
      tooltip($('history-chart'),$('history-tip'),event,'<b>'+fmtMonth(month(nearest[0]))+'</b><div>SPY $'+nearest[1].toFixed(2)+'</div>');
    }
  });
  $('history-chart').addEventListener('click',event=>{const marker=nearestMarker(event);if(marker){$('search').value=marker.date;renderOverview();$('table-title').scrollIntoView({behavior:'smooth'});}});
  $('history-chart').addEventListener('mouseleave',()=>$('history-tip').style.display='none');
  function openDetail(ticker, id, action) {
    const stock=stocks.get(ticker), event=DATA.events[id];
    if(!stock||!event)return;
    if(state.view!=='detail')state.returnView=state.view;
    state.view='detail'; state.detail={stock,event,action}; state.comparisons=[];
    $('baseline').value='event';$('horizon').value='all';$('include-spy').checked=true;
    $('overview').hidden=true;$('detail').hidden=false;
    $('detail-title').innerHTML=esc(ticker)+'<span>'+esc(event[action+'_n']||stock.name)+'</span>';
    $('detail-context').textContent=action==='removed'?'REMOVED FROM S&P 500':'ADDED TO S&P 500';
    const cache=DATA.prices[ticker];
    $('detail-meta').textContent='Effective '+fmtDate(event.date)+(cache?.fetched?' · Price cache dated '+cache.fetched:'');
    $('detail-reason').textContent=event.reason;
    $('detail-source').innerHTML='Event source: '+source(event);
    $('ticker-events').innerHTML=stock.events.slice().reverse().map(({event:e,action:a})=>'<tr><td><button class="event-link" data-ticker="'+esc(ticker)+'" data-event="'+e.id+'" data-action="'+a+'">'+fmtDate(e.date)+'</button></td><td>'+a+'</td><td>'+esc(e[a+'_n'])+'</td><td>'+esc(e.reason)+'</td><td class="source">'+source(e)+'</td></tr>').join('');
    bindTickers($('ticker-events'));
    renderComparison();window.scrollTo({top:0,behavior:'smooth'});
  }
  $('back').addEventListener('click',()=>showView(state.returnView));
  function renderComparison() {
    const {stock,event,action}=state.detail;
    const selected=[stock.ticker,...state.comparisons];
    $('compare').innerHTML='<option value="">Select ticker…</option>'+[...stocks.values()].filter(s=>s.prices.length&&!selected.includes(s.ticker)&&s.ticker!=='SPY').sort((a,b)=>a.ticker.localeCompare(b.ticker)).map(s=>'<option value="'+esc(s.ticker)+'">'+esc(s.ticker+' — '+s.name)+'</option>').join('');
    $('add-compare').disabled=state.comparisons.length>=3;
    $('compare-chips').innerHTML=state.comparisons.map(t=>'<span class="chip">'+esc(t)+'<button data-remove="'+esc(t)+'" aria-label="Remove '+esc(t)+'">×</button></span>').join('');
    $('compare-chips').querySelectorAll('[data-remove]').forEach(button=>button.addEventListener('click',()=>{state.comparisons=state.comparisons.filter(t=>t!==button.dataset.remove);renderComparison();}));
    const notes=[];
    if(!stock.prices.length)notes.push(stock.reused?'The available history for '+stock.ticker+' starts long after its earliest index event. It is excluded as possible ticker reuse.':'No usable monthly history is cached for '+stock.ticker+'. Its membership events and sources remain available below.');
    const instruments=selected.filter(t=>stocks.get(t).prices.length).map((t,i)=>({ticker:t,color:COLORS[i],raw:stocks.get(t).prices}));
    if($('include-spy').checked)instruments.push({ticker:'SPY',color:COLORS[4],raw:DATA.prices.SPY.px,dashed:true});
    instruments.forEach(s=>{s.months=new Map(s.raw.map(p=>[month(p[0]),p[1]]));});
    const start=$('baseline').value==='event'?month(event.date):null, horizon=$('horizon').value;
    let common=instruments.length?[...instruments[0].months.keys()].filter(m=>(!start||m>=start)&&instruments.every(s=>s.months.has(m))).sort():[];
    if(common.length&&horizon!=='all'){
      const end=monthIndex(common[0])+Number(horizon);
      common=common.filter(m=>monthIndex(m)<=end);
    }
    if(start&&common.length&&common[0]!==start)notes.push('The shared price history starts in '+fmtMonth(common[0])+', after the event month. Every displayed return uses this later start.');
    if(!stock.prices.length&&instruments.length)notes.push('The chart shows only the available comparison series; no return is inferred for '+stock.ticker+'.');
    if(common.length<2)notes.push('There are fewer than two common monthly observations. A performance estimate needs more price history.');
    $('detail-notes').innerHTML=notes.map(note=>'<div class="note">'+esc(note)+'</div>').join('');
    $('comparison-window').textContent=common.length?'Shared window: '+fmtMonth(common[0])+' – '+fmtMonth(common.at(-1))+' · '+common.length+' monthly observations · rebased to 100':'No shared monthly observations for this selection.';
    const months=common.length?monthIndex(common.at(-1))-monthIndex(common[0]):0;
    const benchmark=instruments.find(s=>s.ticker==='SPY');
    const benchmarkReturn=common.length>1&&benchmark?(benchmark.months.get(common.at(-1))/benchmark.months.get(common[0])-1)*100:null;
    const series=instruments.map(s=>({...s,points:common.map(m=>[m,s.months.get(m)/s.months.get(common[0])*100])}));
    const markers=$('baseline').value==='history'?[{date:event.date,color:action==='removed'?'#b3372f':'#1f5fa8',label:action}]:[];
    state.detailPlot=chart($('detail-chart'),series,markers,'No common price data for this selection');
    $('detail-legend').innerHTML=series.map(s=>'<span><i style="background:'+s.color+'"></i>'+esc(s.ticker)+'</span>').join('');
    $('performance').innerHTML=instruments.map(s=>{
      if(!common.length)return '<tr><td>'+esc(s.ticker)+'</td><td colspan="5">No common observations</td></tr>';
      const first=s.months.get(common[0]),last=s.months.get(common.at(-1)),total=common.length>1?(last/first-1)*100:null, annual=months>0?((last/first)**(12/months)-1)*100:null;
      return '<tr><td><b>'+esc(s.ticker)+'</b></td><td>'+pct(total)+'</td><td>'+pct(annual)+'</td><td>'+pct(total!=null&&benchmarkReturn!=null?total-benchmarkReturn:null,' pp')+'</td><td>$'+first.toFixed(2)+'</td><td>$'+last.toFixed(2)+'</td></tr>';
    }).join('')||'<tr><td colspan="6" class="empty">No usable price history in this selection.</td></tr>';
  }
  $('add-compare').addEventListener('click',()=>{const ticker=$('compare').value;if(ticker&&!state.comparisons.includes(ticker)&&state.comparisons.length<3){state.comparisons.push(ticker);renderComparison();}});
  ['baseline','horizon','include-spy'].forEach(id=>$(id).addEventListener('change',renderComparison));
  $('detail-chart').addEventListener('mousemove',event=>{
    const plot=state.detailPlot;if(!plot||!plot.series.length||!plot.series[0].points.length)return;
    const x=event.clientX-$('detail-chart').getBoundingClientRect().left;
    const points=plot.series[0].points, point=points.reduce((a,b)=>Math.abs(plot.X(a[0])-x)<Math.abs(plot.X(b[0])-x)?a:b), index=points.indexOf(point);
    tooltip($('detail-chart'),$('detail-tip'),event,'<b>'+fmtMonth(point[0])+'</b>'+plot.series.map(s=>'<div style="color:'+s.color+'">'+esc(s.ticker)+': '+s.points[index][1].toFixed(1)+'</div>').join(''));
  });
  $('detail-chart').addEventListener('mouseleave',()=>$('detail-tip').style.display='none');
  window.addEventListener('resize',()=>{if(state.view==='detail')renderComparison();else if(state.view==='changes')drawHistory();});
  showView('changes');
})();
