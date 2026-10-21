#!/usr/bin/env python
"""Build the static site in site/ from output/results.json and output/snapshots.csv."""
import os, json, shutil, html, math
import pandas as pd
from core import now_chi

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT, SITE = os.path.join(ROOT, "output"), os.path.join(ROOT, "site")
CHARTJS = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"

CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:20px;color:#1d2330;background:#fafbfc}
h1{margin:0 0 4px}a{color:#1f5fbf;text-decoration:none}a:hover{text-decoration:underline}
.meta{color:#666;font-size:13px;margin-bottom:10px}.note{background:#fff8e1;border:1px solid #f0d58c;padding:10px 14px;border-radius:6px;font-size:13px;max-width:1100px}
table{border-collapse:collapse;font-size:13px;background:#fff}th,td{padding:5px 8px;border-bottom:1px solid #e5e7eb;text-align:right;white-space:nowrap}
th{position:sticky;top:0;background:#273449;color:#fff;cursor:pointer;user-select:none}th:hover{background:#3a4b66}
td.l,th.l{text-align:left}tr:hover td{background:#f1f5ff}
tr.rich td{background:#e3f6e8}tr.rich:hover td{background:#d0efd9}tr.cheap td{background:#fdecec}
.controls{margin:12px 0;display:flex;gap:14px;flex-wrap:wrap;align-items:center;font-size:13px}
.controls input[type=text]{padding:5px 8px;width:200px}.pill{display:inline-block;padding:1px 6px;border-radius:9px;font-size:11px}
.BMO{background:#dbeafe}.AMC{background:#ede9fe}.UNK{background:#eee;color:#777}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;max-width:1100px;margin:12px 0}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px}.card b{font-size:20px;display:block}.card span{color:#666;font-size:12px}
.chart{max-width:1100px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px;margin:12px 0}
.pos{color:#15803d}.neg{color:#b91c1c}.legend{font-size:12px;color:#555}
"""


def f(v, d=2, suf=""):
    if v is None or (isinstance(v, float) and math.isnan(v)) or v == "":
        return ""
    return f"{v:.{d}f}{suf}" if isinstance(v, (int, float)) else str(v)


def row_for(r):
    st, se = r.get("stats") or {}, r.get("stats_earnings_only") or {}
    post = r.get("post") or {}
    eo = r.get("earnings_only_move_pct")
    avg = st.get("avg_abs_move_pct")
    return {"ticker": r["ticker"], "name": r.get("name", ""), "next": r.get("next_earnings") or "",
            "timing": r.get("timing") or "", "dte": r.get("days_to_earnings"), "expiry": post.get("expiry", ""),
            "exp_lag": r.get("days_event_to_expiry"), "spot": r.get("spot"), "straddle": post.get("straddle"),
            "impl": r.get("implied_move_pct"), "eo": eo, "avg": avg, "med": st.get("median_abs_move_pct"),
            "ratio": st.get("implied_over_avg"), "eo_ratio": round(eo / avg, 3) if (eo and avg) else None,
            "exceed": st.get("pct_exceeded_implied"), "hit": st.get("seller_hit_rate"),
            "eo_hit": se.get("seller_hit_rate"), "pnl": st.get("avg_pnl_pct_spot"), "eo_pnl": se.get("avg_pnl_pct_spot"),
            "n": st.get("n_quarters"), "iv": post.get("iv_straddle"), "sprd": post.get("spread_pct_of_straddle"),
            "src": post.get("price_src", ""), "tte": round(post["T_years"] * 252, 1) if post.get("T_years") is not None else None, "notes": len(r.get("notes") or [])}


def richness(x):
    """Seller-richness score used for highlighting: earnings-only implied / avg realized when available."""
    if x["eo_ratio"] is not None:
        return x["eo_ratio"]
    # Full straddle ratio is only a fair proxy when almost all remaining time value is the event itself
    if x["ratio"] is not None and x.get("tte") is not None and x["tte"] <= 4:
        return x["ratio"]
    return None


def cls(x):
    sc = richness(x)
    if sc is None or not x.get("n") or x["n"] < 6:
        return ""
    if x.get("src") != "mid" or x.get("sprd") is None or x["sprd"] > 40:   # quotes too wide/stale to trust
        return ""
    hit = x["eo_hit"] if x["eo_ratio"] is not None else x["hit"]
    if sc >= 1.25 and (hit or 0) >= 75:
        return "rich"
    if sc < 0.9:
        return "cheap"
    return ""


INDEX_JS = r"""
const cols=COLS;let data=DATA;let sortKey='next',asc=true;
function fmt(v,c){if(v===null||v===undefined||v==='')return'';if(c.fmt==='pct')return v.toFixed(2)+'%';if(c.fmt==='x')return v.toFixed(2)+'x';
 if(c.fmt==='r')return v.toFixed(0)+'%';if(c.fmt==='n')return typeof v==='number'?v.toFixed(2):v;return v}
function render(){const q=document.getElementById('q').value.toUpperCase().trim();const maxd=parseInt(document.getElementById('maxd').value||'9999');
 const onlyRich=document.getElementById('rich').checked;const hasOpt=document.getElementById('opt').checked;const minr=parseFloat(document.getElementById('minr').value||'0');
 let rows=data.filter(r=>(!q||r.ticker.includes(q)||r.name.toUpperCase().includes(q))&&(r.dte===null||r.dte<=maxd)&&(!onlyRich||r.cls==='rich')&&(!hasOpt||r.impl!==null)&&((r.score||0)>=minr));
 rows.sort((a,b)=>{let x=a[sortKey],y=b[sortKey];if(x===null||x===''||x===undefined)return 1;if(y===null||y===''||y===undefined)return -1;
  return (x<y?-1:x>y?1:0)*(asc?1:-1)});
 const tb=document.querySelector('#t tbody');tb.innerHTML=rows.map(r=>'<tr class="'+r.cls+'">'+cols.map(c=>{let v=r[c.k];
  if(c.k==='ticker')return '<td class="l"><a href="t/'+v+'.html"><b>'+v+'</b></a></td>';
  if(c.k==='timing')return '<td><span class="pill '+v+'">'+v+'</span></td>';
  return '<td class="'+(c.l?'l':'')+'">'+fmt(v,c)+'</td>'}).join('')+'</tr>').join('');
 document.getElementById('cnt').textContent=rows.length+' of '+data.length+' shown';}
function hdr(){document.querySelector('#t thead').innerHTML='<tr>'+cols.map(c=>'<th class="'+(c.l?'l':'')+'" title="'+(c.t||'')+'" data-k="'+c.k+'">'+c.h+(sortKey===c.k?(asc?' ▲':' ▼'):'')+'</th>').join('')+'</tr>';
 document.querySelectorAll('#t th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(sortKey===k)asc=!asc;else{sortKey=k;asc=!['score','ratio','eo_ratio','hit','eo_hit','pnl','impl','eo'].includes(k)}hdr();render()})}
['q','maxd','rich','opt','minr'].forEach(id=>document.getElementById(id).addEventListener('input',render));hdr();render();
"""

COLS = [
    {"k": "ticker", "h": "Ticker", "l": 1}, {"k": "name", "h": "Company", "l": 1},
    {"k": "next", "h": "Next ER", "l": 1}, {"k": "timing", "h": "When", "t": "BMO=before open, AMC=after close, UNK=unknown/unconfirmed (assumed AMC)"},
    {"k": "dte", "h": "Days", "t": "Calendar days to earnings"},
    {"k": "expiry", "h": "Post-ER expiry", "l": 1}, {"k": "exp_lag", "h": "Exp lag", "t": "Trading days from reaction day to expiry (time value beyond the event)"},
    {"k": "spot", "h": "Spot", "fmt": "n"}, {"k": "straddle", "h": "ATM straddle", "fmt": "n"},
    {"k": "impl", "h": "Impl move", "fmt": "pct", "t": "Post-earnings expiry ATM straddle / spot (includes non-earnings time value)"},
    {"k": "eo", "h": "ER-only impl", "fmt": "pct", "t": "Earnings-day implied |move| from term-structure variance difference vs the expiry before earnings"},
    {"k": "avg", "h": "Avg |move|", "fmt": "pct", "t": "Mean abs close-to-close earnings reaction, last up to 12 quarters"},
    {"k": "med", "h": "Med |move|", "fmt": "pct"},
    {"k": "ratio", "h": "Impl/Avg", "fmt": "x"}, {"k": "eo_ratio", "h": "ERonly/Avg", "fmt": "x"},
    {"k": "exceed", "h": "% > impl", "fmt": "r", "t": "% of past quarters where realized move exceeded today's implied move"},
    {"k": "hit", "h": "Seller hit", "fmt": "r", "t": "% of past quarters a straddle sold at today's implied move would have won (ignores residual time value)"},
    {"k": "eo_hit", "h": "Hit (ER-only)", "fmt": "r"},
    {"k": "pnl", "h": "Avg P&L %spot", "fmt": "n", "t": "Mean(implied - realized) using today's full implied move"},
    {"k": "eo_pnl", "h": "Avg P&L ER-only", "fmt": "n"},
    {"k": "score", "h": "Rich score", "fmt": "x", "t": "ER-only implied / avg realized; falls back to Impl/Avg only if expiry is <=4 trading days away"},
    {"k": "tte", "h": "TDays to exp", "fmt": "n"},
    {"k": "n", "h": "N"}, {"k": "sprd", "h": "Sprd %", "fmt": "n", "t": "Bid-ask width as % of straddle"},
]


def page(title, body, extra_head=""):
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'><style>{CSS}</style>{extra_head}</head>"
            f"<body>{body}</body></html>")


LIMITS = ("yfinance is a free, unofficial Yahoo Finance scraper: option quotes are delayed (~15 min) and after hours "
          "bid/ask can be stale or zero (we fall back to last trade). Earnings dates/times for future events are "
          "often estimates; 'UNK' timing is assumed AMC. There are <b>no historical option prices</b> in yfinance, so "
          "past implied moves cannot be reconstructed: the backtest applies <b>today's</b> implied move to every past "
          "quarter, and the P&amp;L ignores residual time value, bid-ask, commissions and assignment. The full straddle "
          "includes non-earnings time value up to expiry, so the 'ER-only' columns (term-structure variance difference) "
          "are the fairer comparison. Straddle-price history comes only from our own snapshot.py runs.")


def detail(r, snaps, generated):
    t = r["ticker"]; st = r.get("stats") or {}; se = r.get("stats_earnings_only") or {}
    post, pre = r.get("post") or {}, r.get("pre") or {}
    h = pd.DataFrame(r.get("history") or [])
    impl, eo = r.get("implied_move_pct"), r.get("earnings_only_move_pct")
    cards = [("Next earnings", f"{r.get('next_earnings','?')} <span class='pill {r.get('timing','')}'>{r.get('timing','')}</span>",
              f"{r.get('days_to_earnings','?')} days; reaction {r.get('reaction_day','?')}"),
             ("Spot", f(r.get("spot")), f"as of {r['as_of']} CT"),
             ("ATM straddle", f(post.get("straddle")), f"{post.get('expiry','')} K={f(post.get('strike'))} ({post.get('price_src','')})"),
             ("Implied move", f(impl, 2, "%"), f"IV {f(post.get('iv_straddle'),3)}"),
             ("ER-only implied", f(eo, 2, "%"), f"vs pre-ER expiry {pre.get('expiry','n/a')}"),
             ("Avg / median |move|", f"{f(st.get('avg_abs_move_pct'),2,'%')} / {f(st.get('median_abs_move_pct'),2,'%')}", f"n={st.get('n_quarters','')} max {f(st.get('max_abs_move_pct'),2,'%')}"),
             ("Impl / avg", f(st.get("implied_over_avg"), 2, "x"), f"ER-only: {f(eo/st['avg_abs_move_pct'],2,'x') if eo and st.get('avg_abs_move_pct') else 'n/a'}"),
             ("Seller hit rate", f(st.get("seller_hit_rate"), 0, "%"), f"ER-only: {f(se.get('seller_hit_rate'),0,'%')}; exceeded {f(st.get('pct_exceeded_implied'),0,'%')}"),
             ("Avg P&L (% spot)", f(st.get("avg_pnl_pct_spot"), 2), f"worst {f(st.get('worst_pnl_pct_spot'),2)}; ER-only avg {f(se.get('avg_pnl_pct_spot'),2)}")]
    cardh = "".join(f"<div class='card'><span>{a}</span><b>{b}</b><span>{c}</span></div>" for a, b, c in cards)
    rows = ""
    for _, x in h.iterrows():
        p1 = impl - x["abs_close_pct"] if impl else None
        p2 = eo - x["abs_close_pct"] if eo else None
        cl = lambda v: "" if v is None else ("pos" if v >= 0 else "neg")
        rows += (f"<tr><td class='l'>{x['earnings_date']}</td><td>{x['timing']}{'*' if x['timing_inferred'] else ''}</td>"
                 f"<td class='l'>{x['pre_close_date']}</td><td class='l'>{x['reaction_date']}</td><td>{f(x['pre_close'])}</td>"
                 f"<td>{f(x['react_open'])}</td><td>{f(x['react_close'])}</td><td>{f(x['move_open_pct'],2,'%')}</td>"
                 f"<td>{f(x['move_close_pct'],2,'%')}</td><td>{f(x.get('eps_surprise_pct'),1,'%')}</td>"
                 f"<td class='{cl(p1)}'>{f(p1)}</td><td class='{cl(p2)}'>{f(p2)}</td></tr>")
    hist_tbl = ("<table><thead><tr><th class='l'>Earnings</th><th>When</th><th class='l'>Pre close</th><th class='l'>Reaction day</th>"
                "<th>Pre close $</th><th>React open</th><th>React close</th><th>Gap %</th><th>Close-close %</th><th>EPS surprise</th>"
                "<th>Seller P&amp;L @impl</th><th>Seller P&amp;L @ER-only</th></tr></thead><tbody>" + rows + "</tbody></table>"
                "<p class='legend'>* timing unknown in data; reaction day inferred from the larger overnight gap. P&amp;L = implied move minus "
                "realized |close-to-close| move, % of spot, using today's implied move for every quarter.</p>")
    js_hist = json.dumps({"labels": h["earnings_date"].tolist() if not h.empty else [],
                          "close": h["abs_close_pct"].tolist() if not h.empty else [],
                          "open": h["abs_open_pct"].tolist() if not h.empty else [], "impl": impl, "eo": eo})
    sn = snaps[snaps["ticker"] == t].copy() if snaps is not None and len(snaps) else pd.DataFrame()
    snap_html = "<p>No snapshot history yet. Run <code>python snapshot.py</code> daily (e.g. via cron) to build the series.</p>"
    js_snap = "null"
    if len(sn):
        sn = sn.sort_values("snapshot_ts").groupby(["event_date", "snapshot_date"], as_index=False).last()
        events = []
        for ev, g in sn.groupby("event_date"):
            events.append({"event": ev, "x": g["tdays_to_reaction"].tolist(), "impl": g["implied_move_pct"].tolist(),
                           "straddle": g["straddle"].tolist(), "iv": g["iv_straddle"].tolist(),
                           "exp": g["expiry"].tolist(), "dates": g["snapshot_date"].tolist()})
        js_snap = json.dumps(events, default=str)
        trs = "".join(f"<tr><td class='l'>{x.snapshot_ts}</td><td class='l'>{x.event_date}</td><td>{x.phase}</td><td>{x.tdays_to_reaction}</td>"
                      f"<td class='l'>{x.expiry}</td><td>{f(x.spot)}</td><td>{f(x.strike)}</td><td>{f(x.straddle)}</td>"
                      f"<td>{f(x.implied_move_pct,2,'%')}</td><td>{f(x.iv_straddle,3)}</td><td>{f(x.earnings_only_move_pct,2,'%') if x.earnings_only_move_pct==x.earnings_only_move_pct else ''}</td></tr>"
                      for x in sn.itertuples())
        snap_html = (f"<p class='legend'>{len(sn)} daily snapshot(s). X axis = trading days to the reaction day (negative = after the event).</p>"
                     "<div class='chart'><canvas id='sc' height='110'></canvas></div>"
                     "<table><thead><tr><th class='l'>Snapshot (CT)</th><th class='l'>Event</th><th>Phase</th><th>T-days to reaction</th>"
                     "<th class='l'>Expiry</th><th>Spot</th><th>K</th><th>Straddle</th><th>Impl move</th><th>IV</th><th>ER-only</th></tr></thead><tbody>"
                     + trs + "</tbody></table>")
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in r.get("notes") or [])
    png = f"<p class='legend'>Static chart: <a href='../img/{t}_moves.png'>PNG</a> · data: <a href='../data/{t}_history.csv'>CSV</a> · <a href='../data/{t}_summary.json'>JSON</a></p>"
    body = f"""<p><a href='../index.html'>&larr; all Nasdaq-100</a></p><h1>{t} <small style='font-weight:normal;color:#666'>{html.escape(r.get('name',''))}</small></h1>
<div class='meta'>Data as of {r['as_of']} (America/Chicago) · site built {generated} (America/Chicago) · seller's view (short ATM straddle)</div>
<div class='grid'>{cardh}</div>{'<ul class=note>'+notes+'</ul>' if notes else ''}
<h2>Historical earnings moves vs today's implied move</h2><div class='chart'><canvas id='hc' height='110'></canvas></div>{png}
<h2>Per-quarter detail</h2>{hist_tbl}
<h2>Straddle snapshot history (around earnings)</h2>{snap_html}
<p class='note'>{LIMITS}</p>
<script>
const H={js_hist};const S={js_snap};
const lineAt=(v,n)=>H.labels.map(()=>v);
const ds=[{{type:'bar',label:'|close-to-close| move %',data:H.close,backgroundColor:H.close.map(v=>H.impl&&v>H.impl?'#dc2626':'#2563eb')}},
 {{type:'line',label:'|gap at open| %',data:H.open,showLine:false,pointStyle:'line',pointRadius:10,borderColor:'#111',borderWidth:2}}];
if(H.impl)ds.push({{type:'line',label:'Implied now '+H.impl.toFixed(2)+'%',data:lineAt(H.impl),borderColor:'#ea580c',borderDash:[6,4],pointRadius:0}});
if(H.eo)ds.push({{type:'line',label:'ER-only implied '+H.eo.toFixed(2)+'%',data:lineAt(H.eo),borderColor:'#7c3aed',borderDash:[2,3],pointRadius:0}});
new Chart(document.getElementById('hc'),{{data:{{labels:H.labels,datasets:ds}},options:{{plugins:{{title:{{display:true,text:'Red bars = quarters a seller at today\\'s implied move would have lost'}}}},scales:{{y:{{title:{{display:true,text:'% move'}}}}}}}}}});
if(S){{const pal=['#2563eb','#16a34a','#ea580c','#7c3aed','#db2777'];const d=[];S.forEach((e,i)=>{{
 d.push({{label:'Straddle $ (ER '+e.event+')',data:e.x.map((x,j)=>({{x:x,y:e.straddle[j]}})),borderColor:pal[i%5],yAxisID:'y',showLine:true}});
 d.push({{label:'Implied move % (ER '+e.event+')',data:e.x.map((x,j)=>({{x:x,y:e.impl[j]}})),borderColor:pal[i%5],borderDash:[5,4],yAxisID:'y1',showLine:true}});}});
 new Chart(document.getElementById('sc'),{{type:'scatter',data:{{datasets:d}},options:{{scales:{{x:{{reverse:true,title:{{display:true,text:'Trading days to reaction day (0 = reaction, negative = after)'}}}},
 y:{{title:{{display:true,text:'Straddle $'}}}},y1:{{position:'right',title:{{display:true,text:'Implied move %'}},grid:{{drawOnChartArea:false}}}}}}}}}});}}
</script>"""
    return page(f"{t} earnings straddle", body, f"<script src='{CHARTJS}'></script>")


def build():
    res = json.load(open(os.path.join(OUT, "results.json")))
    generated = now_chi().isoformat(timespec="seconds")
    snaps = None
    sp = os.path.join(OUT, "snapshots.csv")
    if os.path.exists(sp):
        snaps = pd.read_csv(sp)
    for d in ("t", "img", "data"):
        os.makedirs(os.path.join(SITE, d), exist_ok=True)
    rows = []
    for r in res["results"]:
        x = row_for(r); x["score"] = richness(x); x["cls"] = cls(x); rows.append(x)
        t = r["ticker"]
        for suf, sub in (("_moves.png", "img"), ("_history.csv", "data"), ("_summary.json", "data")):
            src = os.path.join(OUT, t + suf)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(SITE, sub, t + suf))
        open(os.path.join(SITE, "t", f"{t}.html"), "w").write(detail(r, snaps, generated))
    if os.path.exists(sp):
        shutil.copy(sp, os.path.join(SITE, "data", "snapshots.csv"))
    shutil.copy(os.path.join(OUT, "results.json"), os.path.join(SITE, "data", "results.json"))
    fails = "".join(f"<li><b>{x['ticker']}</b>: {html.escape(x['error'])}</li>" for x in res.get("failures", []))
    nsnap = 0 if snaps is None else len(snaps)
    last_snap = "" if snaps is None or not len(snaps) else snaps["snapshot_ts"].max()
    body = f"""<h1>Nasdaq-100 earnings straddles — seller's view</h1>
<div class='meta'>Analysis data as of {res['generated']} (America/Chicago) · site built {generated} (America/Chicago) ·
{res['n_ok']} tickers analyzed, {res['n_fail']} failed · {nsnap} straddle snapshots (latest {last_snap} CT) ·
<a href='data/results.json'>results.json</a> · <a href='data/snapshots.csv'>snapshots.csv</a></div>
<p class='note'><b>How to read:</b> green rows = selling looks rich (rich score ≥ 1.25× avg historical move, ≥75% hypothetical
seller hit rate, ≥6 quarters, bid/ask mid with spread ≤40% of straddle); red = implied below 0.9× history (cheap to sell). Default sort: soonest earnings. Click headers to sort.<br>{LIMITS}</p>
<div class='controls'><input type='text' id='q' placeholder='Filter ticker / name'>
<label>Earnings within <input type='number' id='maxd' style='width:60px' value='' placeholder='any'> days</label>
<label>Min rich score <input type='number' id='minr' step='0.1' style='width:60px' placeholder='0'></label>
<label><input type='checkbox' id='opt' checked> has straddle</label><label><input type='checkbox' id='rich'> rich only</label>
<span id='cnt' class='legend'></span></div>
<table id='t'><thead></thead><tbody></tbody></table>
{'<h3>Failed tickers</h3><ul>'+fails+'</ul>' if fails else ''}
<script>const COLS={json.dumps(COLS)};const DATA={json.dumps(rows, default=str)};</script>
<script>{INDEX_JS.replace('COLS', 'COLS').replace('DATA', 'DATA')}</script>"""
    open(os.path.join(SITE, "index.html"), "w").write(page("N100 earnings straddles", body))
    print(f"site built: {SITE}/index.html ({len(rows)} detail pages)")
    return rows


if __name__ == "__main__":
    build()
