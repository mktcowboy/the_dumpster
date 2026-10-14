#!/usr/bin/env python3
"""Build self-contained index.html: 20 years of S&P 500 constituent changes over SPY."""
import json, datetime, html as htmllib

EV = json.load(open('changes_20yr.json'))
SPY = json.load(open('spy_monthly.json'))

# group events by date
days = {}
for e in EV:
    days.setdefault(e['date'], []).append(e)
day_list = sorted(days.items())  # (date, [events])

adds = sum(1 for e in EV if e['added_t'])
rems = sum(1 for e in EV if e['removed_t'])
from collections import Counter
yc = Counter(e['date'][:4] for e in EV)
busiest_year = yc.most_common(1)[0]
dc = Counter(e['date'] for e in EV)
busiest_day = dc.most_common(1)[0]
distinct_added = len(set(e['added_t'] for e in EV if e['added_t']))
distinct_removed = len(set(e['removed_t'] for e in EV if e['removed_t']))
first_date, last_date = EV[0]['date'], EV[-1]['date']

spy_json = json.dumps(SPY, separators=(',', ':')).replace('</', '<\\/')
ev_json = json.dumps(EV, separators=(',', ':')).replace('</', '<\\/')

years = sorted(yc)
year_opts = ''.join(f'<option value="{y}">{y}</option>' for y in years)

page = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>S&amp;P 500 Constituent Changes &mdash; 20 Years</title>
<style>
  :root{
    --ink:#1a1a1a; --navy:#14324f; --gray:#5b6470; --line:#e2e5e9;
    --add:#1f5fa8; --rem:#b3372f; --bg:#ffffff; --soft:#f6f7f9;
  }
  *{box-sizing:border-box}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
       color:var(--ink); background:var(--bg); margin:0; line-height:1.5;
       font-variant-numeric:tabular-nums;}
  .wrap{max-width:1180px; margin:0 auto; padding:32px 24px 64px;}
  header{border-bottom:2px solid var(--navy); padding-bottom:18px; margin-bottom:8px;}
  h1{font-family:Georgia,"Times New Roman",serif; font-weight:600; font-size:30px;
     margin:0 0 6px; color:var(--navy); letter-spacing:-0.01em;}
  .sub{color:var(--gray); font-size:14px; margin:0;}
  .stats{display:flex; flex-wrap:wrap; gap:0; margin:20px 0 6px; border:1px solid var(--line);}
  .stat{flex:1 1 150px; padding:14px 18px; border-right:1px solid var(--line);}
  .stat:last-child{border-right:none;}
  .stat .n{font-family:Georgia,serif; font-size:26px; color:var(--navy);}
  .stat .l{font-size:12px; color:var(--gray); text-transform:uppercase; letter-spacing:0.06em;}
  h2{font-family:Georgia,serif; font-size:20px; color:var(--navy); margin:34px 0 10px;
     border-bottom:1px solid var(--line); padding-bottom:8px;}
  .chartbox{position:relative; border:1px solid var(--line); background:#fff;}
  canvas{display:block; width:100%; height:440px; cursor:crosshair;}
  .legend{display:flex; gap:22px; font-size:13px; color:var(--gray); padding:10px 4px 0; flex-wrap:wrap;}
  .sw{display:inline-block; width:22px; height:3px; vertical-align:middle; margin-right:7px;}
  #tip{position:absolute; pointer-events:none; background:#fff; border:1px solid var(--navy);
       box-shadow:0 4px 14px rgba(0,0,0,.14); padding:10px 12px; font-size:13px; max-width:340px;
       display:none; z-index:5;}
  #tip .td{font-weight:700; color:var(--navy); margin-bottom:6px; font-size:12px;
           text-transform:uppercase; letter-spacing:.05em;}
  #tip .ev{margin:5px 0; border-top:1px solid var(--line); padding-top:5px;}
  #tip .ev:first-of-type{border-top:none; padding-top:0;}
  .tk{font-weight:700;}
  .a{color:var(--add);} .r{color:var(--rem);}
  .hint{font-size:12px; color:var(--gray); margin-top:8px;}
  .ybars{display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:8px 18px; margin-top:6px;}
  .ybar-row{font-size:12px;}
  .ybar-row .yl{color:var(--navy); font-weight:700; display:inline-block; width:38px;}
  .bar{height:8px; display:inline-block; vertical-align:middle;}
  .ybar-row .ct{color:var(--gray); margin-left:6px;}
  .controls{display:flex; gap:12px; flex-wrap:wrap; align-items:center; margin:18px 0 12px;}
  .controls select, .controls input{font-size:14px; padding:8px 10px; border:1px solid var(--line);
     border-radius:2px; background:#fff; color:var(--ink);}
  .controls input{min-width:260px;}
  .count{font-size:13px; color:var(--gray); margin-left:auto;}
  table{width:100%; border-collapse:collapse; font-size:13.5px; margin-top:4px;}
  thead th{font-size:11px; text-transform:uppercase; letter-spacing:.07em; color:var(--gray);
     text-align:left; padding:10px 10px; border-bottom:2px solid var(--navy); cursor:pointer;
     white-space:nowrap; user-select:none;}
  tbody td{padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top;}
  tbody tr:hover{background:var(--soft);}
  td.date{white-space:nowrap; color:var(--navy); font-weight:600;}
  .nm{color:var(--gray); font-size:12.5px;}
  .rsn{color:#3a3f46; font-size:13px;}
  .more{color:var(--navy); cursor:pointer; font-size:12.5px; white-space:nowrap;}
  footer{margin-top:44px; border-top:1px solid var(--line); padding-top:14px; font-size:12.5px; color:var(--gray);}
  footer p{margin:6px 0;}
  @media (max-width:700px){ .stat{flex:1 1 45%;} canvas{height:320px;} }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>S&amp;P 500 Constituent Changes &mdash; 20 Years</h1>
  <p class="sub">Every recorded addition and removal, """ + first_date + """ through """ + last_date + """, plotted against SPY. Change data: Wikipedia &ldquo;Historical components of the S&amp;P 500&rdquo; (retrieved """ + datetime.date.today().isoformat() + """); prices: SPY monthly closes, Yahoo Finance.</p>
</header>

<div class="stats">
  <div class="stat"><div class="n">""" + str(len(EV)) + """</div><div class="l">change events</div></div>
  <div class="stat"><div class="n">""" + str(adds) + """</div><div class="l">additions</div></div>
  <div class="stat"><div class="n">""" + str(rems) + """</div><div class="l">removals</div></div>
  <div class="stat"><div class="n">""" + str(distinct_added) + """</div><div class="l">distinct tickers added</div></div>
  <div class="stat"><div class="n">""" + str(distinct_removed) + """</div><div class="l">distinct tickers removed</div></div>
  <div class="stat"><div class="n">""" + busiest_year[0] + """</div><div class="l">busiest year (""" + str(busiest_year[1]) + """ changes)</div></div>
</div>

<h2>SPY with constituent-change markers</h2>
<div class="chartbox">
  <canvas id="ch"></canvas>
  <div id="tip"></div>
</div>
<div class="legend">
  <span><span class="sw" style="background:#14324f"></span>SPY monthly close</span>
  <span><span class="sw" style="background:#1f5fa8"></span>net additions that day</span>
  <span><span class="sw" style="background:#b3372f"></span>net removals that day</span>
  <span><span class="sw" style="background:#9ca3af"></span>balanced</span>
</div>
<p class="hint">Hover the chart for prices and that day&rsquo;s changes. Click a marker to jump to it in the table below. Select a year to zoom the chart.</p>

<h2>Additions vs removals by year</h2>
<div class="ybars" id="ybars"></div>

<h2>Full change log</h2>
<div class="controls">
  <select id="yr"><option value="all">All years</option>""" + year_opts + """</select>
  <input id="q" type="text" placeholder="Search ticker, company, or reason&hellip;">
  <button id="sort" style="font-size:14px;padding:8px 12px;border:1px solid var(--line);background:#fff;cursor:pointer;">Newest first</button>
  <span class="count" id="count"></span>
</div>
<table>
  <thead><tr>
    <th id="th-date">Effective date &#8597;</th><th>Added</th><th>Removed</th><th>Reason</th>
  </tr></thead>
  <tbody id="rows"></tbody>
</table>

<footer>
  <p><strong>Sources.</strong> Change log compiled from the Wikipedia article &ldquo;Historical components of the S&amp;P 500&rdquo; (effective dates as published; announcement vs. effective dates can differ by a day). SPY monthly closes from Yahoo Finance.</p>
  <p><strong>Coverage.</strong> Wikipedia&rsquo;s table is community-maintained and essentially complete for recent years; a handful of early-2000s entries may be missing. S&amp;P occasionally swaps more than one pair on a single date (e.g., quarterly rebalances).</p>
  <p><strong>Note.</strong> A row with an empty &ldquo;Added&rdquo; or &ldquo;Removed&rdquo; cell reflects a spin-off or other corporate action recorded as a one-sided index change.</p>
</footer>
</div>

<script>
const SPY = __SPY__;
const EVENTS = __EVENTS__;
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

// ---- group events by date
const byDate = {};
EVENTS.forEach(e => { (byDate[e.date] = byDate[e.date] || []).push(e); });
const dayKeys = Object.keys(byDate).sort();

// ---- year bars
(function(){
  const yrs = {};
  EVENTS.forEach(e => {
    const y = e.date.slice(0,4);
    yrs[y] = yrs[y] || {a:0, r:0};
    if (e.added_t) yrs[y].a++;
    if (e.removed_t) yrs[y].r++;
  });
  const mx = Math.max(...Object.values(yrs).map(v => Math.max(v.a, v.r)));
  const el = document.getElementById('ybars');
  Object.keys(yrs).sort().forEach(y => {
    const v = yrs[y];
    el.innerHTML += '<div class="ybar-row"><span class="yl">'+y+'</span>'+
      '<span class="bar" style="width:'+(v.a/mx*100).toFixed(1)+'px;background:#1f5fa8" title="added"></span>'+
      '<span class="bar" style="width:'+(v.r/mx*100).toFixed(1)+'px;background:#b3372f" title="removed"></span>'+
      '<span class="ct">'+v.a+' / '+v.r+'</span></div>';
  });
})();

// ---- chart
const cv = document.getElementById('ch'), ctx = cv.getContext('2d'), tip = document.getElementById('tip');
let zoomYear = 'all';
const NAVY='#14324f', ADD='#1f5fa8', REM='#b3372f', BAL='#9ca3af';
let markers = []; // {x, date}

function xDomain(){
  if (zoomYear === 'all') return [new Date(SPY[0].d), new Date(SPY[SPY.length-1].d)];
  return [new Date(zoomYear+'-01-01'), new Date(zoomYear+'-12-31')];
}
function draw(){
  const W = cv.clientWidth, H = cv.clientHeight, dpr = window.devicePixelRatio || 1;
  cv.width = W*dpr; cv.height = H*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,W,H);
  const L=58, R=14, T=14, B=30, pw=W-L-R, ph=H-T-B;
  const [x0,x1] = xDomain();
  const pts = SPY.filter(p => { const d=new Date(p.d); return d>=x0 && d<=x1; });
  if (pts.length < 2) return;
  const vals = pts.map(p=>p.c);
  const ymin = Math.min(...vals)*0.94, ymax = Math.max(...vals)*1.04;
  const X = d => L + (d - x0)/(x1 - x0)*pw;
  const Y = v => T + ph - (v - ymin)/(ymax - ymin)*ph;

  // gridlines + y labels
  ctx.strokeStyle='#eceff2'; ctx.fillStyle='#8a93a0'; ctx.font='11px sans-serif';
  ctx.lineWidth=1; ctx.textAlign='right'; ctx.textBaseline='middle';
  const step = niceStep(ymin, ymax);
  for (let v = Math.ceil(ymin/step)*step; v <= ymax; v += step){
    const y = Y(v);
    ctx.beginPath(); ctx.moveTo(L,y); ctx.lineTo(W-R,y); ctx.stroke();
    ctx.fillText('$'+Math.round(v), L-8, y);
  }
  // year ticks
  ctx.textAlign='center'; ctx.textBaseline='top';
  const y0 = x0.getFullYear(), y1 = x1.getFullYear();
  for (let y=y0; y<=y1; y++){
    const d = new Date(y,0,1);
    if (d < x0 || d > x1) continue;
    const x = X(d);
    ctx.strokeStyle='#f0f2f4';
    ctx.beginPath(); ctx.moveTo(x,T); ctx.lineTo(x,T+ph); ctx.stroke();
    ctx.fillStyle='#8a93a0'; ctx.fillText(String(y), x, T+ph+8);
  }
  // SPY line
  ctx.strokeStyle=NAVY; ctx.lineWidth=1.6; ctx.beginPath();
  pts.forEach((p,i)=>{ const x=X(new Date(p.d)), y=Y(p.c); i?ctx.lineTo(x,y):ctx.moveTo(x,y); });
  ctx.stroke();

  // event markers
  markers = [];
  dayKeys.forEach(dk => {
    const d = new Date(dk+'T12:00:00');
    if (d < x0 || d > x1) return;
    const evs = byDate[dk];
    const na = evs.filter(e=>e.added_t).length, nr = evs.filter(e=>e.removed_t).length;
    const col = na>nr ? ADD : nr>na ? REM : BAL;
    const x = X(d);
    markers.push({x, date:dk});
    ctx.strokeStyle=col; ctx.globalAlpha=0.55; ctx.lineWidth=1;
    ctx.beginPath(); ctx.moveTo(x,T); ctx.lineTo(x,T+ph); ctx.stroke();
    ctx.globalAlpha=1;
    if (evs.length > 1){
      ctx.fillStyle=col;
      ctx.beginPath(); ctx.arc(x, T+4, 5, 0, 7); ctx.fill();
      ctx.fillStyle='#fff'; ctx.font='bold 8px sans-serif'; ctx.textAlign='center'; ctx.textBaseline='middle';
      ctx.fillText(evs.length, x, T+4);
    }
  });
}
function niceStep(lo, hi){
  const raw=(hi-lo)/6, mag=Math.pow(10,Math.floor(Math.log10(raw))), n=raw/mag;
  return (n<1.5?1:n<3.5?2:n<7.5?5:10)*mag;
}
function fmtDate(iso){ const [y,m,dd]=iso.split('-').map(Number);
  return new Date(y,m-1,dd).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); }

cv.addEventListener('mousemove', e => {
  const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  let best=null, bd=1e9;
  markers.forEach(m => { const d=Math.abs(m.x-mx); if (d<bd){bd=d;best=m;} });
  if (best && bd < 9){
    const evs = byDate[best.date];
    let htm = '<div class="td">'+fmtDate(best.date)+' &mdash; '+evs.length+' change'+(evs.length>1?'s':'')+'</div>';
    evs.forEach(ev => {
      htm += '<div class="ev">';
      if (ev.added_t) htm += '<span class="tk a">+ '+esc(ev.added_t)+'</span> <span class="nm">'+esc(ev.added_n)+'</span><br>';
      if (ev.removed_t) htm += '<span class="tk r">&minus; '+esc(ev.removed_t)+'</span> <span class="nm">'+esc(ev.removed_n)+'</span>';
      htm += '</div>';
    });
    tip.innerHTML = htm; tip.style.display='block';
    const tw = tip.offsetWidth;
    tip.style.left = Math.min(mx+16, r.width-tw-8)+'px';
    tip.style.top = Math.max(my-10, 8)+'px';
    cv.style.cursor='pointer';
  } else {
    tip.style.display='none'; cv.style.cursor='crosshair';
  }
});
cv.addEventListener('mouseleave', ()=> tip.style.display='none');
cv.addEventListener('click', e => {
  const r = cv.getBoundingClientRect(), mx = e.clientX - r.left;
  let best=null, bd=1e9;
  markers.forEach(m => { const d=Math.abs(m.x-mx); if (d<bd){bd=d;best=m;} });
  if (best && bd < 9){
    document.getElementById('yr').value = best.date.slice(0,4);
    document.getElementById('q').value = best.date;
    zoomYear = best.date.slice(0,4);
    render(); draw();
    document.getElementById('rows').scrollIntoView({behavior:'smooth', block:'start'});
  }
});
window.addEventListener('resize', draw);

// ---- table
let desc = true;
function filtered(){
  const y = document.getElementById('yr').value;
  const q = document.getElementById('q').value.trim().toLowerCase();
  let rows = EVENTS.filter(e =>
    (y==='all' || e.date.slice(0,4)===y) &&
    (!q || (e.added_t+' '+e.added_n+' '+e.removed_t+' '+e.removed_n+' '+e.reason+' '+e.date).toLowerCase().includes(q)));
  rows.sort((a,b)=> desc ? (a.date<b.date?1:-1) : (a.date>b.date?1:-1));
  return rows;
}
function render(){
  const rows = filtered();
  const tb = document.getElementById('rows');
  tb.innerHTML = rows.map((e,i) => {
    const rsn = e.reason.length > 130
      ? '<span class="rsn-short">'+esc(e.reason.slice(0,130))+'&hellip; </span><span class="rsn-full" style="display:none">'+esc(e.reason)+' </span><span class="more" data-i="'+i+'">more</span>'
      : esc(e.reason);
    return '<tr><td class="date">'+fmtDate(e.date)+'</td>'+
      '<td>'+(e.added_t?'<span class="tk a">'+esc(e.added_t)+'</span> <span class="nm">'+esc(e.added_n)+'</span>':'<span class="nm">&mdash;</span>')+'</td>'+
      '<td>'+(e.removed_t?'<span class="tk r">'+esc(e.removed_t)+'</span> <span class="nm">'+esc(e.removed_n)+'</span>':'<span class="nm">&mdash;</span>')+'</td>'+
      '<td class="rsn">'+rsn+'</td></tr>';
  }).join('');
  document.getElementById('count').textContent = rows.length + ' of ' + EVENTS.length + ' events';
  tb.querySelectorAll('.more').forEach(m => m.addEventListener('click', () => {
    const td = m.closest('td');
    const short = td.querySelector('.rsn-short'), full = td.querySelector('.rsn-full');
    const open = full.style.display !== 'none';
    full.style.display = open ? 'none' : 'inline';
    short.style.display = open ? 'inline' : 'none';
    m.textContent = open ? 'more' : 'less';
  }));
}
document.getElementById('yr').addEventListener('change', e => { zoomYear = e.target.value; render(); draw(); });
document.getElementById('q').addEventListener('input', render);
document.getElementById('sort').addEventListener('click', e => {
  desc = !desc; e.target.textContent = desc ? 'Newest first' : 'Oldest first'; render();
});
document.getElementById('th-date').addEventListener('click', () => {
  desc = !desc;
  document.getElementById('sort').textContent = desc ? 'Newest first' : 'Oldest first';
  render();
});
render(); draw();
</script>
</body>
</html>
"""

page = page.replace('__SPY__', spy_json).replace('__EVENTS__', ev_json)
open('index.html','w').write(page)
import os
print("index.html bytes:", os.path.getsize('index.html'))
print("events:", len(EV), "| spy pts:", len(SPY))
