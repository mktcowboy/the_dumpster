#!/usr/bin/env python3
"""Build removed-tracker page: click-in charts for every removed S&P 500 stock."""
import json, datetime

REMOVED = json.load(open('removed_list.json'))
PRICES = json.load(open('removed_prices.json'))
SPY = json.load(open('spy_monthly.json'))  # [{'d': iso, 'c': close}]

spy_dates = [p['d'] for p in SPY]
spy_close = [p['c'] for p in SPY]

def spy_rebased(rem_date):
    """SPY closes rebased to 100 at first month >= rem_date; returns (dates, rebased)."""
    bi = next((i for i, d in enumerate(spy_dates) if d >= rem_date), None)
    if bi is None:
        return [], []
    base = spy_close[bi]
    return spy_dates[bi:], [round(c / base * 100, 2) for c in spy_close[bi:]]

records = []
no_data = []
for r in REMOVED:
    t = r['ticker']
    pts = PRICES.get(t)
    if not pts:
        no_data.append(t)
        records.append({'t': t, 'n': r['name'], 'rem': r['removed'], 'add': r['added'],
                        'reason': r['reason'], 'data': None})
        continue
    dates = [p[0] for p in pts]
    closes = [p[1] for p in pts]
    bi = next((i for i, d in enumerate(dates) if d >= r['removed']), None)
    if bi is None:
        # removal fell after the last monthly bar (mid-month removal): use last bar as base
        last_d = datetime.date.fromisoformat(dates[-1])
        rem_d = datetime.date.fromisoformat(r['removed'])
        if (rem_d - last_d).days <= 60:
            bi = len(dates) - 1
    if bi is None:
        no_data.append(t)
        records.append({'t': t, 'n': r['name'], 'rem': r['removed'], 'add': r['added'],
                        'reason': r['reason'], 'data': None})
        continue
    base = closes[bi]
    last = closes[-1]
    n = len(closes) - 1 - bi  # months elapsed
    tot = last / base - 1
    ann = (last / base) ** (12 / n) - 1 if n > 0 else 0.0
    sd, sr = spy_rebased(r['removed'])
    spy_tot = sr[-1] / 100 - 1 if sr else None
    # align lengths for chart (both monthly; trim to common tail length)
    status = 'trading' if dates[-1] >= '2026-09-01' else 'delisted ' + dates[-1]
    records.append({
        't': t, 'n': r['name'], 'rem': r['removed'], 'add': r['added'], 'reason': r['reason'],
        'px': [[d, c] for d, c in zip(dates, closes)],
        'bi': bi, 'base': base, 'last': last, 'lastd': dates[-1],
        'tot': round(tot * 100, 2), 'ann': round(ann * 100, 2),
        'spy_tot': round(spy_tot * 100, 2) if spy_tot is not None else None,
        'exc': round((tot - spy_tot) * 100, 2) if spy_tot is not None else None,
        'status': status,
    })

with_data = [r for r in records if r.get('px')]
print(f"tickers: {len(records)}, with data: {len(with_data)}, no data: {len(no_data)}")
med = sorted(r['tot'] for r in with_data)[len(with_data)//2]
beat = sum(1 for r in with_data if r['exc'] is not None and r['exc'] > 0)
print(f"median return since removal: {med:.1f}%, beating SPY: {beat}/{len(with_data)}")

# ---- chunk data files (each < ~100KB)
chunks, cur, cur_size = [], [], 0
for r in records:
    s = json.dumps(r, separators=(',', ':'))
    if cur and cur_size + len(s) > 95000:
        chunks.append(cur); cur, cur_size = [], 0
    cur.append(s); cur_size += len(s) + 1
if cur:
    chunks.append(cur)
print(f"chunks: {len(chunks)}")
for i, ch in enumerate(chunks, 1):
    open(f'drop/sp500-removed-tracker/data_{i}.js', 'w').write(
        'var RD = window.RD || [];\nRD.push(\n' + ',\n'.join(ch) + '\n);')

n_chunks = len(chunks)
scripts = '\n'.join(f'<script src="data_{i}.js"></script>' for i in range(1, n_chunks + 1))

page = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>S&amp;P 500 Removed Stocks Tracker</title>
<style>
  :root{ --ink:#1a1a1a; --navy:#14324f; --gray:#5b6470; --line:#e2e5e9;
         --add:#1f5fa8; --rem:#b3372f; --bg:#ffffff; --soft:#f6f7f9; --good:#1c6e3c; }
  *{box-sizing:border-box}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
       color:var(--ink); background:var(--bg); margin:0; line-height:1.5;
       font-variant-numeric:tabular-nums;}
  .wrap{max-width:1180px; margin:0 auto; padding:32px 24px 64px;}
  header{border-bottom:2px solid var(--navy); padding-bottom:18px; margin-bottom:8px;}
  h1{font-family:Georgia,"Times New Roman",serif; font-weight:600; font-size:30px;
     margin:0 0 6px; color:var(--navy); letter-spacing:-0.01em;}
  .sub{color:var(--gray); font-size:14px; margin:0;}
  .stats{display:flex; flex-wrap:wrap; margin:20px 0 6px; border:1px solid var(--line);}
  .stat{flex:1 1 150px; padding:14px 18px; border-right:1px solid var(--line);}
  .stat:last-child{border-right:none;}
  .stat .n{font-family:Georgia,serif; font-size:26px; color:var(--navy);}
  .stat .l{font-size:12px; color:var(--gray); text-transform:uppercase; letter-spacing:0.06em;}
  h2{font-family:Georgia,serif; font-size:20px; color:var(--navy); margin:34px 0 10px;
     border-bottom:1px solid var(--line); padding-bottom:8px;}
  .controls{display:flex; gap:12px; flex-wrap:wrap; align-items:center; margin:18px 0 12px;}
  .controls select,.controls input{font-size:14px; padding:8px 10px; border:1px solid var(--line);
     border-radius:2px; background:#fff; color:var(--ink);}
  .controls input{min-width:260px;}
  .count{font-size:13px; color:var(--gray); margin-left:auto;}
  table{width:100%; border-collapse:collapse; font-size:13.5px;}
  thead th{font-size:11px; text-transform:uppercase; letter-spacing:.07em; color:var(--gray);
     text-align:left; padding:10px; border-bottom:2px solid var(--navy); white-space:nowrap;
     user-select:none; cursor:pointer;}
  tbody td{padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top;}
  tbody tr.rowlink{cursor:pointer;}
  tbody tr.rowlink:hover{background:var(--soft);}
  td.date{white-space:nowrap; color:var(--navy); font-weight:600;}
  .tk{font-weight:700; color:var(--navy);}
  .nm{color:var(--gray); font-size:12.5px;}
  .pos{color:var(--good); font-weight:600;} .neg{color:var(--rem); font-weight:600;}
  .pill{font-size:11px; padding:2px 8px; border:1px solid var(--line); border-radius:20px; color:var(--gray); white-space:nowrap;}
  .pill.live{color:var(--good); border-color:var(--good);}
  #detail{display:none;}
  #back{font-size:14px; padding:8px 14px; border:1px solid var(--navy); background:#fff; color:var(--navy);
        cursor:pointer; border-radius:2px; margin-bottom:6px;}
  #back:hover{background:var(--navy); color:#fff;}
  .dhead h2{border:none; margin:6px 0 2px; padding:0; font-size:26px;}
  .dhead .meta{color:var(--gray); font-size:14px; margin:0 0 4px;}
  .dhead .reason{font-size:13.5px; color:#3a3f46; max-width:760px;}
  .cards{display:flex; flex-wrap:wrap; gap:0; margin:18px 0; border:1px solid var(--line);}
  .card{flex:1 1 140px; padding:12px 16px; border-right:1px solid var(--line);}
  .card:last-child{border-right:none;}
  .card .v{font-family:Georgia,serif; font-size:22px;}
  .card .k{font-size:11px; color:var(--gray); text-transform:uppercase; letter-spacing:.06em;}
  .chartbox{position:relative; border:1px solid var(--line);}
  canvas{display:block; width:100%; height:420px; cursor:crosshair;}
  #tip{position:absolute; pointer-events:none; background:#fff; border:1px solid var(--navy);
       box-shadow:0 4px 14px rgba(0,0,0,.14); padding:10px 12px; font-size:13px; max-width:300px;
       display:none; z-index:5;}
  #tip .td{font-weight:700; color:var(--navy); margin-bottom:4px; font-size:12px;
           text-transform:uppercase; letter-spacing:.05em;}
  .legend{display:flex; gap:22px; font-size:13px; color:var(--gray); padding:10px 4px 0; flex-wrap:wrap;}
  .sw{display:inline-block; width:22px; height:3px; vertical-align:middle; margin-right:7px;}
  .warn{background:#fdf6ec; border:1px solid #e8c87a; padding:10px 14px; font-size:13px; margin:14px 0; color:#6b4e12;}
  footer{margin-top:44px; border-top:1px solid var(--line); padding-top:14px; font-size:12.5px; color:var(--gray);}
  footer p{margin:6px 0;}
  @media (max-width:700px){ .stat{flex:1 1 45%;} canvas{height:300px;} }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>S&amp;P 500 Removed Stocks Tracker</h1>
  <p class="sub">Every stock removed from the S&amp;P 500 since 2007. Click any row for its chart &mdash; rebased to 100 on the removal date, with the add/remove dates marked and performance vs SPY since removal.</p>
</header>

<div id="list">
  <div class="stats">
    <div class="stat"><div class="n" id="s-tot"></div><div class="l">stocks removed</div></div>
    <div class="stat"><div class="n" id="s-cov"></div><div class="l">with price history</div></div>
    <div class="stat"><div class="n" id="s-med"></div><div class="l">median return since removal</div></div>
    <div class="stat"><div class="n" id="s-beat"></div><div class="l">beat SPY since removal</div></div>
  </div>
  <h2>All removed stocks</h2>
  <div class="controls">
    <input id="q" type="text" placeholder="Search ticker or company&hellip;">
    <select id="f"><option value="all">All</option><option value="data">With price data</option>
      <option value="live">Still trading</option><option value="dead">Delisted / no data</option></select>
    <select id="sort">
      <option value="rem-d">Removal date &darr;</option><option value="rem-a">Removal date &uarr;</option>
      <option value="ret-d">Return since removal &darr;</option><option value="ret-a">Return since removal &uarr;</option>
      <option value="exc-d">Excess vs SPY &darr;</option><option value="name">Name A&ndash;Z</option>
    </select>
    <span class="count" id="count"></span>
  </div>
  <table><thead><tr>
    <th>Ticker</th><th>Company</th><th>Removed</th><th>Return since removal</th><th>vs SPY</th><th>Status</th>
  </tr></thead><tbody id="rows"></tbody></table>
</div>

<div id="detail">
  <button id="back">&larr; All removed stocks</button>
  <div class="dhead">
    <h2 id="d-title"></h2>
    <p class="meta" id="d-meta"></p>
    <p class="reason" id="d-reason"></p>
  </div>
  <div id="d-warn"></div>
  <div class="cards" id="d-cards"></div>
  <div class="chartbox"><canvas id="ch"></canvas><div id="tip"></div></div>
  <div class="legend">
    <span><span class="sw" style="background:#14324f"></span><span id="lg-t">Stock</span>, rebased to 100 at removal</span>
    <span><span class="sw" style="background:#9ca3af"></span>SPY, rebased to 100 at removal</span>
    <span><span class="sw" style="background:#b3372f"></span>removed from S&amp;P 500</span>
    <span><span class="sw" style="background:#1f5fa8"></span>added to S&amp;P 500</span>
  </div>
</div>

<footer>
  <p><strong>Sources.</strong> Removal dates, names and reasons: Wikipedia, &ldquo;Historical components of the S&amp;P 500&rdquo; (retrieved 2026-10-14). Prices: monthly closes, Yahoo Finance.</p>
  <p><strong>Method.</strong> Returns are price returns (exclude dividends), rebased to 100 on the first month-end on/after the removal date. &ldquo;Since removal&rdquo; runs to the latest available price. Annualized = geometric mean over elapsed months.</p>
  <p><strong>Coverage.</strong> Tickers delisted after acquisition or bankruptcy (e.g., Lehman, Symbol Technologies) generally have no Yahoo price history and show as &ldquo;no data&rdquo;. A few still-listed tickers may fail to load for the same reason.</p>
</footer>
</div>
__SCRIPTS__
<script>
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const fmtD = iso => { const [y,m,d]=iso.split('-').map(Number);
  return new Date(y,m-1,d).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); };
const sgn = (v,suf='%',na='n/a') => v==null ? '<span class="nm">'+na+'</span>'
  : '<span class="'+(v>=0?'pos':'neg')+'">'+(v>=0?'+':'')+v.toFixed(1)+suf+'</span>';

// ---------- list view
const rowsEl = document.getElementById('rows');
function passFilter(r){
  const f = document.getElementById('f').value;
  if (f==='data') return !!r.px;
  if (f==='live') return r.status==='trading';
  if (f==='dead') return !r.px || r.status!=='trading';
  return true;
}
function renderList(){
  const q = document.getElementById('q').value.trim().toLowerCase();
  const s = document.getElementById('sort').value;
  let rows = RD.filter(r => passFilter(r) && (!q || (r.t+' '+r.n).toLowerCase().includes(q)));
  const key = {
    'rem-d':(a,b)=>a.rem<b.rem?1:-1, 'rem-a':(a,b)=>a.rem>b.rem?1:-1,
    'ret-d':(a,b)=>(b.tot??-1e9)-(a.tot??-1e9), 'ret-a':(a,b)=>(a.tot??1e9)-(b.tot??1e9),
    'exc-d':(a,b)=>(b.exc??-1e9)-(a.exc??-1e9), 'name':(a,b)=>a.n.localeCompare(b.n)
  }[s];
  rows.sort(key);
  rowsEl.innerHTML = rows.map(r => {
    const st = !r.px ? '<span class="pill">no data</span>'
      : r.status==='trading' ? '<span class="pill live">still trading</span>'
      : '<span class="pill">delisted '+esc(r.status.slice(9))+'</span>';
    return '<tr class="rowlink" data-t="'+esc(r.t)+'"><td><span class="tk">'+esc(r.t)+'</span></td>'+
      '<td><span class="nm">'+esc(r.n)+'</span></td>'+
      '<td class="date">'+fmtD(r.rem)+'</td>'+
      '<td>'+sgn(r.tot)+'</td><td>'+sgn(r.exc,' pp')+'</td><td>'+st+'</td></tr>';
  }).join('');
  document.getElementById('count').textContent = rows.length + ' of ' + RD.length + ' stocks';
  rowsEl.querySelectorAll('tr.rowlink').forEach(tr =>
    tr.addEventListener('click', () => openDetail(tr.dataset.t)));
}
['q','f','sort'].forEach(id => document.getElementById(id).addEventListener('input', renderList));
document.getElementById('f').addEventListener('change', renderList);
document.getElementById('sort').addEventListener('change', renderList);

// ---------- stats
(function(){
  const wd = RD.filter(r => r.px);
  document.getElementById('s-tot').textContent = RD.length;
  document.getElementById('s-cov').textContent = wd.length;
  const med = wd.map(r=>r.tot).sort((a,b)=>a-b)[Math.floor(wd.length/2)];
  document.getElementById('s-med').textContent = (med>=0?'+':'')+med.toFixed(0)+'%';
  const beat = wd.filter(r => r.exc!=null && r.exc>0).length;
  document.getElementById('s-beat').textContent = beat + ' of ' + wd.length;
})();

// ---------- detail view
const cv = document.getElementById('ch'), ctx = cv.getContext('2d'), tip = document.getElementById('tip');
let D = null; // current detail record
function openDetail(t){
  D = RD.find(r => r.t === t);
  document.getElementById('list').style.display='none';
  document.getElementById('detail').style.display='block';
  document.getElementById('d-title').innerHTML = esc(D.t)+' <span style="font-size:18px;color:#5b6470;font-family:sans-serif;">'+esc(D.n)+'</span>';
  document.getElementById('d-meta').textContent =
    'Removed '+fmtD(D.rem)+(D.add ? '  ·  Added '+fmtD(D.add) : '  ·  Added before 2007 (outside log window)');
  document.getElementById('d-reason').textContent = D.reason;
  document.getElementById('lg-t').textContent = D.t;
  const w = document.getElementById('d-warn');
  if (!D.px){
    w.innerHTML = '<div class="warn">No Yahoo price history for '+esc(D.t)+' &mdash; the ticker was almost certainly delisted (acquired or bankrupt). The removal record above is complete.</div>';
    document.getElementById('d-cards').innerHTML=''; drawEmpty(); window.scrollTo(0,0); return;
  }
  w.innerHTML = D.status!=='trading'
    ? '<div class="warn">Price history ends '+fmtD(D.lastd)+' &mdash; '+esc(D.t)+' no longer trades. Returns run from removal to the last available price.</div>' : '';
  const c = (k,v,cls='') => '<div class="card"><div class="v '+cls+'">'+v+'</div><div class="k">'+k+'</div></div>';
  document.getElementById('d-cards').innerHTML =
    c('Price at removal','$'+D.base.toFixed(2)) +
    c('Last price','$'+D.last.toFixed(2)) +
    c('Return since removal', sgn(D.tot), '') +
    c('Annualized', sgn(D.ann)) +
    c('SPY since removal', sgn(D.spy_tot)) +
    c('Excess vs SPY', sgn(D.exc,' pp'));
  draw(); window.scrollTo(0,0);
}
document.getElementById('back').addEventListener('click', () => {
  document.getElementById('detail').style.display='none';
  document.getElementById('list').style.display='block';
});
function drawEmpty(){
  const W=cv.clientWidth,H=cv.clientHeight,dpr=window.devicePixelRatio||1;
  cv.width=W*dpr; cv.height=H*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,W,H); ctx.fillStyle='#5b6470'; ctx.font='14px sans-serif';
  ctx.textAlign='center'; ctx.fillText('No price data available', W/2, H/2);
}
function draw(){
  const W=cv.clientWidth,H=cv.clientHeight,dpr=window.devicePixelRatio||1;
  cv.width=W*dpr; cv.height=H*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,W,H);
  const L=56,R=14,T=14,B=30,pw=W-L-R,ph=H-T-B;
  const dates=D.px.map(p=>p[0]);
  const x0=new Date(dates[0]), x1=new Date(dates[dates.length-1]);
  // rebased series from removal month
  const bi=D.bi, base=D.base;
  const sx=dates.slice(bi).map(d=>new Date(d)), sv=D.px.slice(bi).map(p=>p[1]/base*100);
  // spy rebased: align by month key
  const sm={}; SPY_M.forEach(p=>sm[p.d.slice(0,7)]=p.c);
  const sbase=sm[D.rem.slice(0,7)] || Object.values(sm)[0];
  const spyX=[], spyV=[];
  sx.forEach(d=>{ const k=d.toISOString().slice(0,7); if(sm[k]){spyX.push(d); spyV.push(sm[k]/sbase*100);} });
  const allV=sv.concat(spyV);
  const ymin=Math.min(...allV)*0.97, ymax=Math.max(...allV)*1.03;
  const X=d=>L+(d-x0)/(x1-x0)*pw, Y=v=>T+ph-(v-ymin)/(ymax-ymin)*ph;
  ctx.font='11px sans-serif';
  // gridlines
  const step=niceStep(ymin,ymax);
  ctx.strokeStyle='#eceff2'; ctx.fillStyle='#8a93a0'; ctx.textAlign='right'; ctx.textBaseline='middle';
  for(let v=Math.ceil(ymin/step)*step; v<=ymax; v+=step){
    const y=Y(v); ctx.beginPath(); ctx.moveTo(L,y); ctx.lineTo(W-R,y); ctx.stroke();
    ctx.fillText(Math.round(v)+'', L-8, y);
  }
  // year ticks
  ctx.textAlign='center'; ctx.textBaseline='top';
  for(let y=x0.getFullYear(); y<=x1.getFullYear(); y++){
    const d=new Date(y,0,1); if(d<x0||d>x1) continue;
    ctx.strokeStyle='#f0f2f4'; ctx.beginPath(); ctx.moveTo(X(d),T); ctx.lineTo(X(d),T+ph); ctx.stroke();
    ctx.fillStyle='#8a93a0'; ctx.fillText(y, X(d), T+ph+8);
  }
  // vertical event lines
  const remD=new Date(D.rem+'T12:00:00');
  ctx.strokeStyle='#b3372f'; ctx.lineWidth=1.5;
  ctx.beginPath(); ctx.moveTo(X(remD),T); ctx.lineTo(X(remD),T+ph); ctx.stroke();
  let addX=null;
  if(D.add){ const ad=new Date(D.add+'T12:00:00');
    if(ad>=x0&&ad<=x1){ addX=X(ad); ctx.strokeStyle='#1f5fa8'; ctx.lineWidth=1.5;
      ctx.beginPath(); ctx.moveTo(addX,T); ctx.lineTo(addX,T+ph); ctx.stroke(); } }
  // spy dashed
  ctx.strokeStyle='#9ca3af'; ctx.lineWidth=1.2; ctx.setLineDash([5,4]); ctx.beginPath();
  spyX.forEach((d,i)=>{ const x=X(d),y=Y(spyV[i]); i?ctx.lineTo(x,y):ctx.moveTo(x,y); });
  ctx.stroke(); ctx.setLineDash([]);
  // stock line
  ctx.strokeStyle='#14324f'; ctx.lineWidth=1.8; ctx.beginPath();
  sx.forEach((d,i)=>{ const x=X(d),y=Y(sv[i]); i?ctx.lineTo(x,y):ctx.moveTo(x,y); });
  ctx.stroke();
  D._plot={X,Y,sx,sv,spyX,spyV,x0,x1,L,pw,T,ph};
}
function niceStep(lo,hi){ const raw=(hi-lo)/6,mag=Math.pow(10,Math.floor(Math.log10(raw))),n=raw/mag;
  return (n<1.5?1:n<3.5?2:n<7.5?5:10)*mag; }
cv.addEventListener('mousemove', e=>{
  if(!D||!D.px||!D._plot){return;}
  const r=cv.getBoundingClientRect(), mx=e.clientX-r.left, my=e.clientY-r.top;
  const {X,Y,sx,sv,spyX,spyV}=D._plot;
  let bi2=0,bd=1e9;
  sx.forEach((d,i)=>{ const dd=Math.abs(X(d)-mx); if(dd<bd){bd=dd;bi2=i;} });
  if(bd<40){
    const d=sx[bi2];
    let htm='<div class="td">'+fmtD(d.toISOString().slice(0,10))+'</div>';
    htm+='<div><b>'+esc(D.t)+'</b> '+sv[bi2].toFixed(1)+' <span style="color:#5b6470">($'+(D.px[D.bi+bi2][1]).toFixed(2)+')</span></div>';
    const k=d.toISOString().slice(0,7);
    const si=spyX.findIndex(x=>x.toISOString().slice(0,7)===k);
    if(si>=0) htm+='<div><b>SPY</b> '+spyV[si].toFixed(1)+'</div>';
    tip.innerHTML=htm; tip.style.display='block';
    tip.style.left=Math.min(mx+16, r.width-310)+'px';
    tip.style.top=Math.max(my-10,8)+'px';
  } else tip.style.display='none';
});
cv.addEventListener('mouseleave', ()=>tip.style.display='none');
window.addEventListener('resize', ()=>{ if(D&&D.px) draw(); });
renderList();
</script>
</body>
</html>
"""
page = page.replace('__SCRIPTS__', scripts)
# SPY monthly embedded for the detail chart (small)
page = page.replace('</script>\n<script>\nconst esc',
                    '</script>\n<script>\nconst SPY_M = ' + json.dumps(SPY, separators=(',',':')) + ';\nconst esc')
open('drop/sp500-removed-tracker/index.html', 'w').write(page)
import os
print('index.html bytes:', os.path.getsize('drop/sp500-removed-tracker/index.html'))
for i in range(1, n_chunks+1):
    print(f'data_{i}.js bytes:', os.path.getsize(f'drop/sp500-removed-tracker/data_{i}.js'))
