#!/usr/bin/env python
"""Build the static site in site/ from output/results.json, output/snapshots.csv and crush events."""
import os, json, shutil, html, math
import pandas as pd
from core import now_chi
from config import CFG
import crush as CR

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT, SITE = os.path.join(ROOT, "output"), os.path.join(ROOT, "site")
CHARTJS = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"
COLLECTING = "n/a – collecting"

CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:20px;color:#1d2330;background:#fafbfc}
h1{margin:0 0 4px}a{color:#1f5fbf;text-decoration:none}a:hover{text-decoration:underline}
.meta{color:#666;font-size:13px;margin-bottom:10px}.note{background:#fff8e1;border:1px solid #f0d58c;padding:10px 14px;border-radius:6px;font-size:13px;max-width:1200px}
.scroll{overflow-x:auto;max-height:80vh;overflow-y:auto;border:1px solid #e5e7eb}
table{border-collapse:collapse;font-size:12.5px;background:#fff}th,td{padding:4px 7px;border-bottom:1px solid #e5e7eb;text-align:right;white-space:nowrap}
th{position:sticky;top:0;background:#273449;color:#fff;cursor:pointer;user-select:none;z-index:1}th:hover{background:#3a4b66}
td.l,th.l{text-align:left}tr:hover td{background:#f1f5ff}
tr.rich td{background:#e3f6e8}tr.rich:hover td{background:#d0efd9}tr.cheap td{background:#fdecec}
.controls{margin:12px 0;display:flex;gap:14px;flex-wrap:wrap;align-items:center;font-size:13px}
.controls input[type=text]{padding:5px 8px;width:180px}.pill{display:inline-block;padding:1px 6px;border-radius:9px;font-size:11px}
.BMO{background:#dbeafe}.AMC{background:#ede9fe}.UNK{background:#eee;color:#777}
.Confirmed{background:#dcfce7;color:#166534}.Mismatch{background:#fee2e2;color:#991b1b}.Unconfirmed{background:#fef3c7;color:#92400e}
.gA{background:#16a34a;color:#fff}.gB{background:#65a30d;color:#fff}.gC{background:#ca8a04;color:#fff}.gF{background:#dc2626;color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:10px;max-width:1200px;margin:12px 0}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px}.card b{font-size:19px;display:block}.card span{color:#666;font-size:12px}
.chart{max-width:1100px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px;margin:12px 0}
.pos{color:#15803d}.neg{color:#b91c1c}.legend{font-size:12px;color:#555}.muted{color:#888}
"""


def f(v, d=2, suf=""):
    if v is None or v == "" or (isinstance(v, float) and math.isnan(v)):
        return ""
    return f"{v:.{d}f}{suf}" if isinstance(v, (int, float)) else str(v)


def num(v):
    try:
        v = float(v)
        return None if math.isnan(v) else v
    except Exception:
        return None


def row_for(r, crush_sum):
    st = r.get("stats") or {}
    post, liq, ps = r.get("post") or {}, r.get("liquidity") or {}, r.get("pnl_stats") or {}
    eo, avg = r.get("earnings_only_move_pct"), st.get("avg_abs_move_pct")
    cs = crush_sum.get(r["ticker"])
    return {"ticker": r["ticker"], "name": r.get("name", ""), "status": r.get("date_status") or "Unconfirmed",
            "next": r.get("next_earnings") or "", "timing": r.get("timing") or "", "dte": r.get("days_to_earnings"),
            "expiry": post.get("expiry", ""), "exp_lag": r.get("days_event_to_expiry"), "spot": r.get("spot"),
            "straddle": post.get("straddle"), "impl": r.get("implied_move_pct"), "eo": eo, "avg": avg,
            "med": st.get("median_abs_move_pct"), "ratio": st.get("implied_over_avg"),
            "eo_ratio": round(eo / avg, 3) if (eo and avg) else None, "exceed": st.get("pct_exceeded_implied"),
            "naive_hit": st.get("seller_hit_rate"), "n": st.get("n_quarters"), "iv": post.get("iv_straddle"),
            "sprd": post.get("spread_pct_of_straddle"), "src": post.get("price_src", ""),
            "tte": round(post["T_years"] * 252, 1) if post.get("T_years") is not None else None,
            "prem": ps.get("entry_premium_pct"), "cost": ps.get("cost_pct"), "gross": ps.get("gross_avg_pct"),
            "net": ps.get("net_avg_pct"), "net_prem": ps.get("net_avg_pct_of_premium"), "net_hit": ps.get("net_hit_rate"),
            "worst": ps.get("net_worst_pct"), "tail": ps.get("net_tail25_pct"),
            "liq": liq.get("grade", "F"), "oi": liq.get("atm_oi"), "vol": liq.get("atm_volume"),
            "proxy": "proxy" in ((r.get("model") or {}).get("sigma_ex_src") or ""),
            "crush": cs["avg_straddle_crush_pct"] if cs else None, "crush_iv": cs["avg_iv_crush_pct"] if cs else None,
            "crush_n": cs["n_events"] if cs else 0, "notes": len(r.get("notes") or [])}


def richness(x):
    """Rich score: earnings-only implied / avg realized; full-straddle ratio only if expiry <= 4 trading days away."""
    if x["eo_ratio"] is not None:
        return x["eo_ratio"]
    if x["ratio"] is not None and x.get("tte") is not None and x["tte"] <= 4:
        return x["ratio"]
    return None


def classify(x):
    """Return (css class, reason list). Rich needs score, quarters, liquidity, positive net expectancy & net hit rate."""
    sc = x["score"]
    fails = []
    if sc is None:
        return "", ["no fair score"]
    if (x.get("n") or 0) < CFG["rich_min_quarters"]: fails.append("few quarters")
    if x["liq"] not in CFG["rich_allowed_liquidity_grades"]: fails.append(f"liquidity {x['liq']}")
    if x["status"] == "Mismatch": fails.append("date mismatch")
    if x["net"] is None or x["net"] <= 0: fails.append("net expectancy <= 0")
    if (x["net_hit"] or 0) < CFG["rich_min_net_hit_rate"]: fails.append("net hit rate")
    if sc < CFG["rich_min_score"]: fails.append("score")
    if not fails:
        return "rich", []
    if sc < 0.9 or (x["net"] is not None and x["net"] < 0 and x["liq"] != "F"):
        return "cheap", fails
    return "", fails


COLS = [
    {"k": "ticker", "h": "Ticker", "l": 1}, {"k": "name", "h": "Company", "l": 1},
    {"k": "status", "h": "Date", "t": "Confirmed = Yahoo & Nasdaq agree; Mismatch = they differ; Unconfirmed = one source only"},
    {"k": "next", "h": "Next ER", "l": 1}, {"k": "timing", "h": "When", "t": "BMO/AMC/UNK (best-sourced)"},
    {"k": "dte", "h": "Days"}, {"k": "expiry", "h": "Post-ER exp", "l": 1},
    {"k": "exp_lag", "h": "Exp lag", "t": "Trading days from reaction day to expiry"},
    {"k": "spot", "h": "Spot", "fmt": "n"}, {"k": "straddle", "h": "Straddle", "fmt": "n"},
    {"k": "impl", "h": "Impl move", "fmt": "pct", "t": "Post-ER expiry ATM straddle / spot"},
    {"k": "eo", "h": "ER-only", "fmt": "pct", "t": "Earnings-day implied |move| from term structure"},
    {"k": "avg", "h": "Avg |mv|", "fmt": "pct"}, {"k": "med", "h": "Med |mv|", "fmt": "pct"},
    {"k": "ratio", "h": "Impl/Avg", "fmt": "x"},
    {"k": "exceed", "h": "% > impl", "fmt": "r", "t": "% of past quarters realized move > today's implied move"},
    {"k": "score", "h": "Rich score", "fmt": "x", "t": "ER-only implied / avg realized (falls back to Impl/Avg only if expiry <=4 tdays)"},
    {"k": "prem", "h": "Entry prem", "fmt": "pct", "t": "Model straddle value at the close before the event, % spot"},
    {"k": "cost", "h": "Costs", "fmt": "pct", "t": "Entry+exit slippage + commissions, % spot"},
    {"k": "gross", "h": "Gross exp", "fmt": "sgn", "t": "Avg gross P&L per quarter, % spot (residual time value included)"},
    {"k": "net", "h": "Net exp", "fmt": "sgn", "t": "Expectancy after costs, % spot"},
    {"k": "net_prem", "h": "Net % prem", "fmt": "r"}, {"k": "net_hit", "h": "Net hit", "fmt": "r"},
    {"k": "worst", "h": "Worst", "fmt": "sgn", "t": "Worst net quarter, % spot"},
    {"k": "tail", "h": "Worst 25%", "fmt": "sgn", "t": "Average of the worst quarter of outcomes (net, % spot)"},
    {"k": "liq", "h": "Liq", "t": "Liquidity grade (config.json thresholds on ATM OI, volume, spread % of mid)"},
    {"k": "oi", "h": "ATM OI"}, {"k": "vol", "h": "ATM vol"}, {"k": "sprd", "h": "Sprd %", "fmt": "n"},
    {"k": "crush", "h": "Avg crush", "fmt": "crush", "t": "Average straddle drop from last pre-event to first post-event snapshot (our snapshots)"},
    {"k": "n", "h": "N"},
]

INDEX_JS = r"""
const GR={A:4,B:3,C:2,F:1};let sortKey='next',asc=true;
function fmt(v,c,r){if(c.fmt==='crush')return v===null||v===undefined?'<span class="muted">n/a – collecting</span>':v.toFixed(1)+'% ('+r.crush_n+')';
 if(v===null||v===undefined||v==='')return'';if(c.fmt==='pct')return v.toFixed(2)+'%';if(c.fmt==='x')return v.toFixed(2)+'x';
 if(c.fmt==='sgn')return '<span class="'+(v>=0?'pos':'neg')+'">'+(v>0?'+':'')+v.toFixed(2)+'</span>';
 if(c.fmt==='r')return v.toFixed(0)+'%';if(c.fmt==='n')return typeof v==='number'?v.toFixed(2):v;return v}
function render(){const q=document.getElementById('q').value.toUpperCase().trim();const maxd=parseInt(document.getElementById('maxd').value||'9999');
 const onlyRich=document.getElementById('rich').checked;const hasOpt=document.getElementById('opt').checked;const minr=parseFloat(document.getElementById('minr').value||'0');
 const st=document.getElementById('st').value;const lg=parseInt(document.getElementById('lg').value);
 let rows=DATA.filter(r=>(!q||r.ticker.includes(q)||r.name.toUpperCase().includes(q))&&(r.dte===null||r.dte<=maxd)&&(!onlyRich||r.cls==='rich')
  &&(!hasOpt||r.impl!==null)&&((r.score||0)>=minr)&&(!st||r.status===st)&&(GR[r.liq]||1)>=lg);
 rows.sort((a,b)=>{let x=a[sortKey],y=b[sortKey];if(sortKey==='liq'){x=GR[x];y=GR[y]}if(x===null||x===''||x===undefined)return 1;if(y===null||y===''||y===undefined)return -1;
  return (x<y?-1:x>y?1:0)*(asc?1:-1)});
 document.querySelector('#t tbody').innerHTML=rows.map(r=>'<tr class="'+r.cls+'" title="'+(r.why||'')+'">'+COLS.map(c=>{let v=r[c.k];
  if(c.k==='ticker')return '<td class="l"><a href="t/'+v+'.html"><b>'+v+'</b></a></td>';
  if(c.k==='timing')return '<td><span class="pill '+v+'">'+v+'</span></td>';
  if(c.k==='status')return '<td><span class="pill '+v+'">'+v+'</span></td>';
  if(c.k==='liq')return '<td><span class="pill g'+v+'">'+v+'</span></td>';
  return '<td class="'+(c.l?'l':'')+'">'+fmt(v,c,r)+'</td>'}).join('')+'</tr>').join('');
 document.getElementById('cnt').textContent=rows.length+' of '+DATA.length+' shown';}
function hdr(){document.querySelector('#t thead').innerHTML='<tr>'+COLS.map(c=>'<th class="'+(c.l?'l':'')+'" title="'+(c.t||'')+'" data-k="'+c.k+'">'+c.h+(sortKey===c.k?(asc?' ▲':' ▼'):'')+'</th>').join('')+'</tr>';
 document.querySelectorAll('#t th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(sortKey===k)asc=!asc;else{sortKey=k;asc=!['score','ratio','gross','net','net_prem','net_hit','impl','eo','prem','oi','vol','liq','worst','tail'].includes(k)}hdr();render()})}
['q','maxd','rich','opt','minr','st','lg'].forEach(id=>document.getElementById(id).addEventListener('input',render));hdr();render();
"""


def page(title, body, extra_head=""):
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'><style>{CSS}</style>{extra_head}</head>"
            f"<body>{body}</body></html>")


LIMITS = ("yfinance is a free, unofficial Yahoo Finance scraper: option quotes are delayed (~15 min) and after hours "
          "bid/ask can be stale or zero (we fall back to last trade). Earnings dates are cross-checked against Nasdaq's "
          "earnings calendar, but both can be estimates until the company announces. There are <b>no historical option "
          "prices</b> in yfinance, so past implied moves cannot be reconstructed: the backtest applies <b>today's</b> term "
          "structure to every past quarter. IV-crush stats come only from our own snapshot.py runs.")

METHOD = (f"<b>Cost-aware P&amp;L model.</b> σ<sub>ex</sub> = ATM IV of the expiry before earnings (fallback: 63-day realized "
          f"vol excluding earnings days, flagged 'proxy'). Earnings-day variance E² = σ<sub>post</sub>²·T<sub>post</sub> − "
          f"σ<sub>ex</sub>²·(T<sub>post</sub> − 1 day). <b>Entry</b>: sell the ATM straddle at the close before the event, "
          f"valued with variance E² + σ<sub>ex</sub>²·T<sub>rem</sub> (T<sub>rem</sub> = trading days from reaction-day close to "
          f"expiry). <b>Exit</b>: buy back at the reaction-day close: Black-Scholes straddle with spot moved by the historical "
          f"close-to-close move, same strike, σ<sub>ex</sub>, T<sub>rem</sub> (= the residual time value; 0 if expiry is the "
          f"reaction day). <b>Gross</b> = entry − exit. <b>Net</b> = gross − entry slippage "
          f"({CFG['entry_slippage_frac_of_half_spread']}× half-spread) − exit slippage "
          f"({CFG['exit_slippage_frac_of_half_spread']}× half-spread × {CFG['exit_spread_multiplier']}) − commissions "
          f"(${CFG['commission_per_contract']}/contract × 2 legs × open+close). Spread = today's actual call+put bid/ask width "
          f"for the post-earnings expiry (default {CFG['default_spread_pct_of_mid_if_unknown']}% of mid if unknown). "
          f"Worst 25% = mean of the worst quarter of outcomes. Settings: config.json.")


def liq_text():
    g = CFG["liquidity_grades"]
    return "; ".join(f"{k}: OI≥{v['min_oi']}, vol≥{v['min_volume']}, spread≤{v['max_spread_pct']}%" for k, v in g.items()) + "; else F"


def detail(r, x, snaps, cev, generated):
    t = r["ticker"]; st = r.get("stats") or {}
    post, pre = r.get("post") or {}, r.get("pre") or {}
    liq, ps, md, cs = r.get("liquidity") or {}, r.get("pnl_stats") or {}, r.get("model") or {}, r.get("costs") or {}
    dc = r.get("date_check") or {}
    h = pd.DataFrame(r.get("history") or [])
    impl, eo = r.get("implied_move_pct"), r.get("earnings_only_move_pct")
    pq = {p["earnings_date"]: p for p in (r.get("pnl_per_quarter") or [])}
    status = r.get("date_status") or "Unconfirmed"
    sgn = lambda v: "" if v is None else f"<span class='{'pos' if v >= 0 else 'neg'}'>{v:+.2f}</span>"
    cards = [("Next earnings", f"{r.get('next_earnings','?')} <span class='pill {r.get('timing','')}'>{r.get('timing','')}</span>",
              f"{r.get('days_to_earnings','?')} days; reaction {r.get('reaction_day','?')}"),
             ("Date check", f"<span class='pill {status}'>{status}</span>",
              f"Yahoo {dc.get('yahoo_date')} {dc.get('yahoo_timing')}{' (est.)' if dc.get('yahoo_is_estimate') else ''} · Nasdaq {dc.get('nasdaq_date') or 'n/a'} {dc.get('nasdaq_timing') or ''}"),
             ("Spot", f(r.get("spot")), f"as of {r['as_of']} CT"),
             ("ATM straddle", f(post.get("straddle")), f"{post.get('expiry','')} K={f(post.get('strike'))} ({post.get('price_src','')})"),
             ("Implied move", f(impl, 2, "%"), f"IV {f(post.get('iv_straddle'),3)}"),
             ("ER-only implied", f(eo, 2, "%"), f"vs pre-ER expiry {pre.get('expiry','n/a')}"),
             ("Avg / median |move|", f"{f(st.get('avg_abs_move_pct'),2,'%')} / {f(st.get('median_abs_move_pct'),2,'%')}", f"n={st.get('n_quarters','')} max {f(st.get('max_abs_move_pct'),2,'%')}"),
             ("Rich score", f(x["score"], 2, "x"), ("RICH" if x["cls"] == "rich" else ("not rich: " + ", ".join(x["why_list"]) if x["why_list"] else ""))),
             ("Liquidity", f"<span class='pill g{liq.get('grade','F')}'>{liq.get('grade','F')}</span>",
              f"ATM OI {liq.get('atm_oi','')} · vol {liq.get('atm_volume','')} · spread {f(liq.get('spread_pct_of_mid'),1,'%')} of mid"),
             ("Entry premium (model)", f(ps.get("entry_premium_pct"), 2, "%"), f"σex {f(md.get('sigma_ex'),3)} ({'proxy' if x['proxy'] else 'pre-expiry IV'}), {md.get('t_rem_days','?')}d residual"),
             ("Costs / trade", f(ps.get("cost_pct"), 3, "%"), f"slip {f(cs.get('entry_slip_pct'),3)}+{f(cs.get('exit_slip_pct'),3)} · comm {f(cs.get('commission_pct'),3)} (% spot)"),
             ("Gross → Net expectancy", f"{sgn(ps.get('gross_avg_pct'))} → {sgn(ps.get('net_avg_pct'))}", f"% spot/quarter; net {f(ps.get('net_avg_pct_of_premium'),1,'%')} of premium"),
             ("Net hit rate", f(ps.get("net_hit_rate"), 0, "%"), f"gross {f(ps.get('gross_hit_rate'),0,'%')}"),
             ("Worst / worst-25% avg", f"{sgn(ps.get('net_worst_pct'))} / {sgn(ps.get('net_tail25_pct'))}", "net, % spot"),
             ("Avg IV crush (our data)", (f"{x['crush']:.1f}%" if x["crush"] is not None else COLLECTING),
              (f"IV {f(x['crush_iv'],1,'%')} over {x['crush_n']} event(s)" if x["crush"] is not None else "needs a pre- and post-event snapshot"))]
    cardh = "".join(f"<div class='card'><span>{a}</span><b>{b}</b><span>{c}</span></div>" for a, b, c in cards)
    rows = ""
    for _, q in h.iterrows():
        p1 = impl - q["abs_close_pct"] if impl else None
        m = pq.get(q["earnings_date"], {})
        cl = lambda v: "" if v is None else ("pos" if v >= 0 else "neg")
        rows += (f"<tr><td class='l'>{q['earnings_date']}</td><td>{q['timing']}{'*' if q['timing_inferred'] else ''}</td>"
                 f"<td class='l'>{q['reaction_date']}</td><td>{f(q['pre_close'])}</td>"
                 f"<td>{f(q['react_close'])}</td><td>{f(q['move_open_pct'],2,'%')}</td>"
                 f"<td>{f(q['move_close_pct'],2,'%')}</td><td>{f(q.get('eps_surprise_pct'),1,'%')}</td>"
                 f"<td class='{cl(p1)}'>{f(p1)}</td><td>{f(m.get('exit_value_pct'))}</td>"
                 f"<td class='{cl(m.get('gross_pct'))}'>{f(m.get('gross_pct'))}</td><td class='{cl(m.get('net_pct'))}'>{f(m.get('net_pct'))}</td></tr>")
    hist_tbl = ("<div class='scroll'><table><thead><tr><th class='l'>Earnings</th><th>When</th><th class='l'>Reaction day</th>"
                "<th>Pre close $</th><th>React close</th><th>Gap %</th><th>Close-close %</th><th>EPS surprise</th>"
                "<th title='today implied minus realized, no costs/residual'>Naive P&amp;L</th><th>Exit value (model)</th>"
                "<th>Gross (model)</th><th>Net (model)</th></tr></thead><tbody>" + rows + "</tbody></table></div>"
                "<p class='legend'>* timing unknown in data; reaction day inferred from the larger overnight gap. All P&amp;L in % of spot "
                "using today's option prices for every quarter.</p>")
    js_hist = json.dumps({"labels": h["earnings_date"].tolist() if not h.empty else [],
                          "close": h["abs_close_pct"].tolist() if not h.empty else [],
                          "open": h["abs_open_pct"].tolist() if not h.empty else [], "impl": impl, "eo": eo,
                          "net": [pq.get(d, {}).get("net_pct") for d in (h["earnings_date"].tolist() if not h.empty else [])]})
    # crush history
    ce = cev[cev["ticker"] == t] if cev is not None and len(cev) else pd.DataFrame()
    if len(ce):
        crush_html = ("<div class='scroll'><table><thead><tr><th class='l'>Event</th><th>When</th><th class='l'>Expiry</th><th class='l'>Before (CT)</th>"
                      "<th class='l'>After (CT)</th><th>Sess</th><th>Move</th><th>Straddle before→after</th><th>Straddle crush</th>"
                      "<th>IV before→after</th><th>IV crush</th><th>Held-strike P&amp;L % prem</th></tr></thead><tbody>" +
                      "".join(f"<tr><td class='l'>{e.event_date}</td><td>{e.timing}</td><td class='l'>{e.expiry}</td><td class='l'>{e.before_ts}</td>"
                              f"<td class='l'>{e.after_ts}</td><td>{e.after_session}</td><td>{f(e.move_pct,2,'%')}</td>"
                              f"<td>{f(e.straddle_before)} → {f(e.straddle_after)}</td><td>{f(e.straddle_crush_pct,1,'%')}</td>"
                              f"<td>{f(e.iv_before,3)} → {f(e.iv_after,3)}</td><td>{f(num(e.iv_crush_pct),1,'%')}</td>"
                              f"<td>{f(num(getattr(e,'held_pnl_pct_prem',None)),1,'%')}</td></tr>" for e in ce.itertuples())
                      + "</tbody></table></div>")
    else:
        crush_html = (f"<p class='muted'>{COLLECTING}: no event yet has both a pre-event snapshot and a post-event snapshot "
                      "on the same expiry. Crush appears automatically after the first earnings with snapshots on both sides "
                      "(the weekday ~9:00 AM CT morning snapshot captures the reaction-day open).</p>")
    sn = snaps[snaps["ticker"] == t].copy() if snaps is not None and len(snaps) else pd.DataFrame()
    snap_html = "<p class='muted'>No snapshot history yet.</p>"
    js_snap = "null"
    if len(sn):
        sn = sn.sort_values("snapshot_ts").groupby(["event_date", "snapshot_date", "session"], as_index=False).last().sort_values("snapshot_ts")
        events = []
        for ev, g in sn.groupby("event_date"):
            xs = [tdr + (0.3 if s == "am" else 0) for tdr, s in zip(g["tdays_to_reaction"], g["session"].fillna("pm"))]
            events.append({"event": ev, "x": xs, "impl": g["implied_move_pct"].tolist(), "straddle": g["straddle"].tolist()})
        js_snap = json.dumps(events, default=str)
        trs = "".join(f"<tr><td class='l'>{s.snapshot_ts}</td><td>{s.session}</td><td class='l'>{s.event_date}</td><td>{s.phase}</td><td>{s.tdays_to_reaction}</td>"
                      f"<td class='l'>{s.expiry}</td><td>{f(s.spot)}</td><td>{f(s.strike)}</td><td>{f(s.straddle)}</td>"
                      f"<td>{f(s.implied_move_pct,2,'%')}</td><td>{f(num(s.iv_straddle),3)}</td><td>{f(num(s.earnings_only_move_pct),2,'%')}</td>"
                      f"<td>{f(num(s.held_straddle))}</td></tr>" for s in sn.itertuples())
        snap_html = (f"<p class='legend'>{len(sn)} snapshot(s) (last per day+session). X = trading days to the reaction day "
                     "(negative = after; morning 'am' snapshots plotted +0.3 to the left of that day's close).</p>"
                     "<div class='chart'><canvas id='sc' height='100'></canvas></div><div class='scroll'>"
                     "<table><thead><tr><th class='l'>Snapshot (CT)</th><th>Sess</th><th class='l'>Event</th><th>Phase</th><th>T-days</th>"
                     "<th class='l'>Expiry</th><th>Spot</th><th>K</th><th>Straddle</th><th>Impl move</th><th>IV</th><th>ER-only</th><th>Held-K straddle</th></tr></thead><tbody>"
                     + trs + "</tbody></table></div>")
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in r.get("notes") or [])
    links = f"<p class='legend'>Static chart: <a href='../img/{t}_moves.png'>PNG</a> · data: <a href='../data/{t}_history.csv'>CSV</a> · <a href='../data/{t}_summary.json'>JSON</a></p>"
    body = f"""<p><a href='../index.html'>&larr; all Nasdaq-100</a></p><h1>{t} <small style='font-weight:normal;color:#666'>{html.escape(r.get('name',''))}</small>
<span class='pill {status}' style='font-size:13px'>{status}</span> <span class='pill g{liq.get('grade','F')}' style='font-size:13px'>Liquidity {liq.get('grade','F')}</span></h1>
<div class='meta'>Data as of {r['as_of']} (America/Chicago) · site built {generated} (America/Chicago) · seller's view (short ATM straddle) · date check: {html.escape(str(dc.get('detail','')))}</div>
<div class='grid'>{cardh}</div>{'<ul class=note>'+notes+'</ul>' if notes else ''}
<h2>Historical earnings moves vs today's implied move</h2><div class='chart'><canvas id='hc' height='100'></canvas></div>{links}
<h2>Per-quarter detail (gross vs net)</h2>{hist_tbl}
<h2>IV crush history (from our snapshots)</h2>{crush_html}
<h2>Straddle snapshot history (around earnings)</h2>{snap_html}
<p class='note'>{METHOD}</p><p class='note'>Liquidity grades: {liq_text()}. {LIMITS}</p>
<script>
const H={js_hist};const S={js_snap};
const lineAt=v=>H.labels.map(()=>v);
const ds=[{{type:'bar',label:'|close-to-close| move %',data:H.close,backgroundColor:H.net.map((n,i)=>n===null?(H.impl&&H.close[i]>H.impl?'#dc2626':'#2563eb'):(n<0?'#dc2626':'#2563eb'))}},
 {{type:'line',label:'|gap at open| %',data:H.open,showLine:false,pointStyle:'line',pointRadius:10,borderColor:'#111',borderWidth:2}}];
if(H.impl)ds.push({{type:'line',label:'Implied now '+H.impl.toFixed(2)+'%',data:lineAt(H.impl),borderColor:'#ea580c',borderDash:[6,4],pointRadius:0}});
if(H.eo)ds.push({{type:'line',label:'ER-only implied '+H.eo.toFixed(2)+'%',data:lineAt(H.eo),borderColor:'#7c3aed',borderDash:[2,3],pointRadius:0}});
new Chart(document.getElementById('hc'),{{data:{{labels:H.labels,datasets:ds}},options:{{plugins:{{title:{{display:true,text:'Red bars = quarters where the cost-aware model seller lost money'}}}},scales:{{y:{{title:{{display:true,text:'% move'}}}}}}}}}});
if(S){{const pal=['#2563eb','#16a34a','#ea580c','#7c3aed','#db2777'];const d=[];S.forEach((e,i)=>{{
 d.push({{label:'Straddle $ (ER '+e.event+')',data:e.x.map((x,j)=>({{x:x,y:e.straddle[j]}})),borderColor:pal[i%5],backgroundColor:pal[i%5],yAxisID:'y',showLine:true}});
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
    cev = CR.compute(snaps)
    cev.to_csv(CR.OUTCSV, index=False)
    csum = CR.summary(cev)
    for d in ("t", "img", "data"):
        os.makedirs(os.path.join(SITE, d), exist_ok=True)
    rows = []
    for r in res["results"]:
        x = row_for(r, csum); x["score"] = richness(x)
        x["cls"], x["why_list"] = classify(x)
        x["why"] = "not rich: " + ", ".join(x["why_list"]) if x["why_list"] else ("rich" if x["cls"] == "rich" else "")
        rows.append(x)
        t = r["ticker"]
        for suf, sub in (("_moves.png", "img"), ("_history.csv", "data"), ("_summary.json", "data")):
            src = os.path.join(OUT, t + suf)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(SITE, sub, t + suf))
        open(os.path.join(SITE, "t", f"{t}.html"), "w").write(detail(r, x, snaps, cev, generated))
    for fn in ("snapshots.csv", "crush_events.csv", "results.json"):
        if os.path.exists(os.path.join(OUT, fn)):
            shutil.copy(os.path.join(OUT, fn), os.path.join(SITE, "data", fn))
    shutil.copy(os.path.join(ROOT, "config.json"), os.path.join(SITE, "data", "config.json"))
    fails = "".join(f"<li><b>{x['ticker']}</b>: {html.escape(x['error'])}</li>" for x in res.get("failures", []))
    nsnap = 0 if snaps is None else len(snaps)
    last_snap = "" if snaps is None or not len(snaps) else snaps["snapshot_ts"].max()
    dcnt = res.get("date_status_counts") or {}
    lcnt = res.get("liquidity_counts") or {}
    body = f"""<h1>Nasdaq-100 earnings straddles — seller's view</h1>
<div class='meta'>Analysis data as of {res['generated']} (America/Chicago) · site built {generated} (America/Chicago) ·
{res['n_ok']} tickers analyzed, {res['n_fail']} failed · {nsnap} straddle snapshots (latest {last_snap} CT) · {len(cev)} IV-crush events ·
dates: {', '.join(f'{k} {v}' for k, v in sorted(dcnt.items()))} · liquidity: {', '.join(f'{k} {v}' for k, v in sorted(lcnt.items()))} ·
<a href='data/results.json'>results.json</a> · <a href='data/snapshots.csv'>snapshots.csv</a> · <a href='data/crush_events.csv'>crush_events.csv</a> · <a href='data/config.json'>config.json</a></div>
<p class='note'><b>How to read:</b> green = selling looks rich: rich score ≥ {CFG['rich_min_score']}x, liquidity in {'/'.join(CFG['rich_allowed_liquidity_grades'])},
positive net expectancy after costs, net hit rate ≥ {CFG['rich_min_net_hit_rate']:.0f}%, ≥{CFG['rich_min_quarters']} quarters, no date mismatch (hover a row for reasons).
Red = cheap to sell (score &lt; 0.9x or negative net expectancy on a tradable name). Default sort: soonest earnings. Click headers to sort.
<br>Liquidity grades: {liq_text()}.<br>{METHOD}<br>{LIMITS}</p>
<div class='controls'><input type='text' id='q' placeholder='Filter ticker / name'>
<label>Earnings within <input type='number' id='maxd' style='width:55px' placeholder='any'> days</label>
<label>Min rich score <input type='number' id='minr' step='0.1' style='width:55px' placeholder='0'></label>
<label>Date <select id='st'><option value=''>all</option><option>Confirmed</option><option>Mismatch</option><option>Unconfirmed</option></select></label>
<label>Liquidity <select id='lg'><option value='1'>all</option><option value='2'>C or better (hide F)</option><option value='3'>B or better</option><option value='4'>A only</option></select></label>
<label><input type='checkbox' id='opt' checked> has straddle</label><label><input type='checkbox' id='rich'> rich only</label>
<span id='cnt' class='legend'></span></div>
<div class='scroll'><table id='t'><thead></thead><tbody></tbody></table></div>
{'<h3>Failed tickers</h3><ul>'+fails+'</ul>' if fails else ''}
<script>const COLS={json.dumps(COLS)};const DATA={json.dumps([{k: v for k, v in x.items() if k != 'why_list'} for x in rows], default=str)};</script>
<script>{INDEX_JS}</script>"""
    open(os.path.join(SITE, "index.html"), "w").write(page("N100 earnings straddles", body))
    print(f"site built: {SITE}/index.html ({len(rows)} detail pages, {len(cev)} crush events)")
    return rows


if __name__ == "__main__":
    build()
