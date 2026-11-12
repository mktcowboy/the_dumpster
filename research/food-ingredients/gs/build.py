import json, html
S = json.load(open('S.json'))
exec(open('data.py').read())
used = []
def ref(k):
    if k not in S: raise SystemExit("missing source "+k)
    if k not in used: used.append(k)
    return used.index(k)+1
e = html.escape
def cites(keys):
    out=[]
    for k in dict.fromkeys(keys):
        n=ref(k); out.append(f'<a class="c" href="{e(S[k][1])}" target="_blank" rel="noopener" title="{e(S[k][0])}">[{n}]</a>')
    return ''.join(out)

SOLVENTS = [
 ("Carbon dioxide (supercritical / subcritical / liquid)", "CO₂; critical point 31.1 °C / 73.8 bar",
  "Part I — GMP for all uses; no numeric residue limit", "GRAS, 21 CFR 184.1240: processing aid, cGMP, no limitation",
  "Listed (GMP) for caffeine extracts, cocoa powder, egg products, flavours, hop & pre-isomerized hop extract, natural extractives, spice extracts, green-coffee and tea-leaf decaffeination",
  "Not in S18—8; usable as a processing aid because CO₂ (INS 290) is a GMP additive (s.1.3.3—4)", "Table C.1 processing aid, all foods, residue not limited",
  "Designated food additive (No. 294)", ["EU","CFR_CO2","HC","FSANZ18","FSANZ134","GB2760","CIRS_GB","JP","KOFO"]),
 ("Propane", "C₃H₈; liquefied gas, bp −42 °C",
  "Part I — GMP for all uses", "GRAS, 21 CFR 184.1655, affirmed as propellant, aerating agent and gas (not named as an extraction solvent)",
  "Not on the List of Permitted Solvents", "S18—8: 1 mg/kg, all foods", "Table C.1 processing aid, all foods, residue not limited",
  "Not on the designated-additive list", ["EU","CFR_PRO","HC","FSANZ18","GB2760","CIRS_GB","JP"]),
 ("n-Butane", "C₄H₁₀; liquefied gas, bp −0.5 °C",
  "Part I — GMP for all uses", "GRAS, 21 CFR 184.1165, affirmed as propellant, aerating agent and gas",
  "Not listed", "S18—8: 1 mg/kg in flavouring substances; 0.1 mg/kg in other foods", "Table C.2: extraction solvent and propellant; extraction processes and bakery spray release oils",
  "Not on the designated-additive list", ["EU","CFR_BUT","HC","FSANZ18","GB2760","JP"]),
 ("Isobutane", "iso-C₄H₁₀; liquefied gas, bp −12 °C",
  "Not named separately (Annex I lists 'butane')", "GRAS, 21 CFR 184.1165 (with n-butane): propellant, aerating agent, gas",
  "Not listed", "S18—8: 1 mg/kg in flavouring substances; 0.1 mg/kg in other foods", "Not listed separately in the Appendix C entries reviewed",
  "Not on the designated-additive list", ["EU","CFR_BUT","HC","FSANZ18","GB2760","JP"]),
 ("Dimethyl ether (DME)", "CH₃OCH₃; liquefied gas, bp −24 °C",
  "Part II — only (a) defatted animal protein products incl. gelatine: max 0.009 mg/kg; (b) collagen & derivatives except gelatine: max 3 mg/kg",
  "GRN 741 'no questions' (2018): extraction solvent for marine/egg/microbial/algal/plant lipids, egg/plant/meat proteins, fruit sugars; 5–6 vol DME per vol starting material",
  "Not listed", "S18—8: 2 mg/kg, all foods", "Not found in the Appendix C entries reviewed", "Not on the designated-additive list",
  ["EU","EFSA_DME","GRN741","GRN741N","HC","FSANZ18","JP"]),
 ("1,1,1,2-Tetrafluoroethane (HFC-134a, R-134a)", "CF₃CH₂F; liquefied gas, bp −26 °C",
  "Part III — preparation of flavourings from natural flavouring materials; max 0.02 mg/kg in the foodstuff",
  "GRN 82 'no questions' (2002, INEOS Fluor): extraction solvent for food flavours",
  "Not listed", "Not in S18—8", "Not found in the Appendix C entries reviewed", "Not on the designated-additive list",
  ["EU","GRN82","HFC_PAT","HC","FSANZ18","JP"]),
 ("Nitrous oxide (as an extraction solvent)", "N₂O; critical point 36.4 °C / 72.4 bar",
  "Part I — GMP for all uses (named extraction solvent)", "GRAS, 21 CFR 184.1545, only as propellant/aerating agent/gas in dairy product analogs; no solvent use",
  "Not listed", "Not in S18—8", "Not found as a processing aid in the Appendix C entries reviewed", "Designated food additive (No. 4)",
  ["EU","CFR_N2O","HC","FSANZ18","JP","N2O_WARN"]),
]
CONFUSED = [
 ("Hexane", "A liquid petroleum solvent (bp 64–70 °C), not a gas. It is the standard solvent for soybean, canola and corn oil and many oleoresins.",
  "EU Part II: 1 mg/kg in fats, oils and cocoa butter; 10 mg/kg in foods containing defatted protein/flours; 30 mg/kg in defatted soy products as sold; 5 mg/kg in defatted cereal germs; 1 mg/kg from flavourings. US: 25 ppm in spice oleoresins; 2.2% in hops extract added to wort. Canada: 10 ppm in vegetable fats/oils and seed meals; 25 ppm in spice extracts. ANZ: 20 mg/kg.",
  ["EU","CFR_HEX","HC","FSANZ18"]),
 ("Ethyl acetate ('naturally decaffeinated')", "A liquid ester (bp 77 °C). It is the 'natural' or 'sugarcane' decaf process because it also occurs in fruit, but it is a liquid solvent.",
  "EU Part I: GMP. US 21 CFR 173.228: cGMP for decaffeinating coffee and tea. Canada: 10 ppm in decaf coffee, 50 ppm in decaf tea. ANZ: 10 mg/kg. The US colour additive tomato lycopene extract is defined as ethyl-acetate extracted.",
  ["EU","CFR_EA","HC","FSANZ18","CFR_LYCO"]),
 ("Methylene chloride (dichloromethane)", "A liquid chlorinated solvent (bp 40 °C) used in 'direct' or 'European' decaf and in some oleoresins. Volatile, but not a gas at room temperature.",
  "EU Part II: 2 mg/kg in roasted coffee, 5 mg/kg in tea; Part III 0.02 mg/kg from flavourings. US 173.255: 10 ppm in decaf roasted/instant coffee, 30 ppm in spice oleoresins, 2.2% in hops extract. Canada: 10 ppm in decaf coffee/tea. ANZ: 2 mg/kg in decaf coffee, decaf tea and flavourings.",
  ["EU","CFR_MC","HC","FSANZ18"]),
 ("Nitrous oxide as a whipped-cream propellant", "In aerosol cream N₂O dissolves in the fat and expands it into foam. That is an aerating or propellant use, not extraction, and it stays in the product.",
  "US 21 CFR 184.1545 (propellant/aerating agent/gas); 21 CFR Part 173 lists N₂O with other propellants for foamed and sprayed foods. EU's listing of N₂O as an extraction solvent is a separate permission.",
  ["CFR_N2O","CFR_173","EU"]),
 ("Nitrogen flushing / liquid-nitrogen freezing", "Nitrogen is used to displace oxygen in packaging (MAP), for sparging, and as a cryogen. It dissolves almost nothing, so it extracts nothing.",
  "US 21 CFR 184.1540 GRAS. China GB 2760 Table C.1 processing aid. Not an extraction solvent in the EU Annex.",
  ["CFR_N2","GB2760","EU"]),
 ("CO₂ for carbonation, MAP or dry ice", "The same gas, but used as an ingredient (carbonation), a packaging atmosphere or a coolant. Nothing is extracted.",
  "US 21 CFR 184.1240 (leavening agent; propellant, aerating agent and gas); only its processing-aid/solvent use counts here.", ["CFR_CO2"]),
 ("Acetone, ethanol, methanol, isopropanol", "Liquid solvents used for oleoresins, rosemary extract (acetone/ethanol grades), steviol glycosides (methanol) and so on.",
  "EU Part I (acetone, ethanol GMP; acetone banned for olive-pomace oil refining); Part II methanol 10 mg/kg, propan-2-ol 10 mg/kg. Canada: acetone 30 ppm and methanol 50 ppm in spice extracts; methanol 200 ppm in steviol glycosides.",
  ["EU","HC","CFR_173"]),
]

cats = sorted({r['cat'] for r in ROWS})
def solv_tags(s):
    t=[]; L=s.lower()
    if 'co2' in L: t.append('CO2')
    if 'dimethyl ether' in L or 'dme' in L: t.append('DME')
    if 'butane' in L: t.append('Butane/isobutane')
    if 'propane' in L: t.append('Propane')
    if 'hfc' in L or 'tetrafluoro' in L: t.append('HFC-134a')
    return t
rows_html=[]
for i,r in enumerate(ROWS,1):
    tags=solv_tags(r['solv'])
    st=r['status']; stc='res' if ('Research' in st or 'Studied' in st or 'Historical' in st or 'Pilot' in st) and 'Commercial' not in st else ('com' if 'Commercial' in st else 'reg')
    rows_html.append(f'''<tr data-cat="{e(r['cat'])}" data-solv="{e('|'.join(tags))}" data-status="{stc}">
<td class="num">{i}</td><td><b>{e(r['name'])}</b><div class="latin">{e(r['latin'])}</div></td><td>{e(r['cat'])}</td>
<td>{''.join(f'<span class="tag t-{e(x.split("/")[0].replace("-",""))}">{e(x)}</span>' for x in tags)}<div class="sm">{e(r['solv'])}</div></td>
<td>{e(r['what'])}</td><td>{e(r['uses'])}</td><td class="reg">{e(r['reg'])}</td><td><span class="st st-{stc}">{e(st)}</span></td><td class="src">{cites(r['src'])}</td></tr>''')

solv_html=[]
for s in SOLVENTS:
    name,chem,eu,us,ca,anz,cn,jp,src=s
    solv_html.append(f'''<div class="card"><h3>{e(name)}</h3><div class="chem">{e(chem)}</div>
<table class="mini"><tr><th>EU (Dir. 2009/32/EC)</th><td>{e(eu)}</td></tr><tr><th>United States</th><td>{e(us)}</td></tr>
<tr><th>Canada</th><td>{e(ca)}</td></tr><tr><th>Australia / NZ</th><td>{e(anz)}</td></tr><tr><th>China (GB 2760-2024)</th><td>{e(cn)}</td></tr>
<tr><th>Japan</th><td>{e(jp)}</td></tr></table><div class="src">Sources: {cites(src)}</div></div>''')

conf_html=[]
for c in CONFUSED:
    name,why,rules,src=c
    conf_html.append(f'<tr><td><b>{e(name)}</b></td><td>{e(why)}</td><td>{e(rules)}</td><td class="src">{cites(src)}</td></tr>')

src_html=''.join(f'<li id="s{n}"><a href="{e(S[k][1])}" target="_blank" rel="noopener">{e(S[k][0])}</a><div class="url">{e(S[k][1])}</div></li>' for n,k in enumerate(used,1))
n_ing=len(ROWS); n_solv=len(SOLVENTS)

LIT=json.load(open('lit.json')); exec(open('lit_meta.py').read())
groups=["CO2","Propane","Butane / isobutane","DME","HFC-134a","N2O","General / all gases"]
def stc(s): return 'pro' if s.startswith('Pro') else ('con' if s.startswith('Con') else 'neu')
lit_rows=[]
allp=[]
for r in LIT:
    g,st,tk=LITMETA[r['doi']]
    au=r['authors']; aus=(au[0].split()[-1]+(' et al.' if len(au)>2 else (' & '+au[1].split()[-1] if len(au)==2 else ''))) if au else ''
    allp.append(dict(g=g,st=st,tk=tk,title=r['title'],year=r['year'],au=aus,venue=r.get('venue') or '',oa=r['oa'],cr=r['cr'],s2=r.get('s2'),url='https://doi.org/'+r['doi'],doi=r['doi']))
for g_,st,title,yr,url,tk in REGDOCS:
    allp.append(dict(g=g_,st=st,tk=tk,title=title,year=yr,au='US FDA',venue='Regulatory document',oa=None,cr=None,s2=None,url=url,doi=''))
lit_html=[]
for g in groups:
    ps=sorted([p for p in allp if p['g']==g],key=lambda p:-(p['oa'] or -1))
    if not ps: continue
    trs=''.join(f"""<tr><td><a href="{e(p['url'])}" target="_blank" rel="noopener">{e(p['title'])}</a><div class="sm">{e(p['au'])}{' · '+e(p['venue']) if p['venue'] else ''}{' · doi:'+e(p['doi']) if p['doi'] else ''}</div></td><td>{p['year']}</td><td class="num">{p['oa'] if p['oa'] is not None else 'n/a'}</td><td class="num">{p['cr'] if p['cr'] is not None else 'n/a'}</td><td class="num">{p['s2'] if p['s2'] is not None else 'n/a'}</td><td><span class="sp sp-{stc(p['st'])}">{e(p['st'])}</span></td><td>{e(p['tk'])}</td></tr>""" for p in ps)
    lit_html.append(f'<h3 class="lg">{e(g)} <span class="sm">({len(ps)})</span></h3><div class="tablewrap"><table class="lit"><thead><tr><th>Paper</th><th>Year</th><th>OpenAlex cites</th><th>Crossref cites</th><th>S2 cites</th><th>Stance</th><th>Takeaway on residues / pros &amp; cons</th></tr></thead><tbody>{trs}</tbody></table></div>')
top=sorted([p for p in allp if p['oa']],key=lambda p:-p['oa'])[:5]
top_html=''.join(f"<li><a href='{e(p['url'])}' target='_blank' rel='noopener'>{e(p['title'])}</a> ({e(p['au'])}, {p['year']}): <b>{p['oa']}</b> OpenAlex citations [{e(p['g'])}]</li>" for p in top)
n_lit=len(allp)

exec(open('charts.py').read())
from collections import Counter
# ---- ingredient stats
solv_counts=Counter(); cat_counts=Counter(); st_counts=Counter()
for r in ROWS:
    for t in solv_tags(r['solv']): solv_counts[t]+=1
    cat_counts[r['cat']]+=1
    st=r['status']; c='res' if ('Research' in st or 'Studied' in st or 'Historical' in st or 'Pilot' in st) and 'Commercial' not in st else ('com' if 'Commercial' in st else 'reg')
    st_counts[c]+=1
solv_items=[(k,solv_counts.get(k,0)) for k in ['CO2','DME','Butane/isobutane','Propane','HFC-134a']]+[('N2O',0)]
ch_solv=hbar('Ingredients per gas solvent', sorted(solv_items,key=lambda x:-x[1]), color=PAL)
ch_cat=hbar('Ingredients by category', cat_counts.most_common(), color='#0072B2', labw=270)
ch_st=hbar('Ingredients by status', [('Commercial',st_counts['com']),('Regulatory-listed / cleared',st_counts['reg']),('Research / pilot / historical',st_counts['res'])], color=['#009E73','#0072B2','#CC79A7'], labw=230)
# ---- residue limits (all mg/kg, sourced)
G='#0072B2'; L='#999999'
lim=[("DME — gelatine / defatted animal protein (EU)",0.009,G,"EU"),
     ("HFC-134a — food, from flavourings (EU)",0.02,G,"EU"),
     ("Butane / isobutane — other foods (ANZ)",0.1,G,"FSANZ18"),
     ("Butane / isobutane — flavouring substances (ANZ)",1,G,"FSANZ18"),
     ("Propane — all foods (ANZ)",1,G,"FSANZ18"),
     ("DME — all foods (ANZ)",2,G,"FSANZ18"),
     ("DME — detection limit in GRN 741 tests (not a limit)",2,'#E69F00',"GRN741N"),
     ("DME — collagen, excl. gelatine (EU)",3,G,"EU"),
     ("Comparator: dichloromethane — flavourings (EU)",0.02,L,"EU"),
     ("Comparator: hexane — fats & oils (EU)",1,L,"EU"),
     ("Comparator: dichloromethane — roasted coffee (EU)",2,L,"EU"),
     ("Comparator: dichloromethane — decaf coffee (US, 10 ppm)",10,L,"CFR_MC"),
     ("Comparator: hexane — spice oleoresins (US, 25 ppm)",25,L,"CFR_HEX"),
     ("Comparator: hexane — defatted soy products (EU)",30,L,"EU")]
ch_lim=logbar('Maximum residue limits on one scale (mg/kg)', lim, w=760, labw=360)
lim_cites=cites([x[3] for x in lim])
# ---- literature
lit_summary=[]
for g in groups:
    ps=[p for p in allp if p['g']==g]
    if not ps: continue
    sc=Counter(stc(p['st']) for p in ps)
    lit_summary.append((g,len(ps),sc['pro'],sc['con'],sc['neu'],sum(p['oa'] or 0 for p in ps),max(ps,key=lambda p:p['oa'] or 0)))
ch_lit=hbar('Top 10 papers by OpenAlex citations', [((p['au']+' '+str(p['year'])),p['oa']) for p in sorted([p for p in allp if p['oa']],key=lambda p:-p['oa'])[:10]], color='#56B4E9', labw=200)
ch_stance=stacked('Literature stance per solvent group', [(g,{'Pro':pr,'Con':co,'Neutral':ne}) for g,n,pr,co,ne,t,_ in lit_summary], ['Pro','Con','Neutral'], ['#009E73','#D55E00','#999999'])
lit_sum_html=''.join(f"<tr><td><b>{e(g)}</b></td><td class='num'>{n}</td><td class='num'>{pr}</td><td class='num'>{co}</td><td class='num'>{ne}</td><td class='num'>{t:,}</td><td><a href='{e(top['url'])}' target='_blank' rel='noopener'>{e(top['au'])} {top['year']}</a> ({top['oa'] or 'n/a'})</td></tr>" for g,n,pr,co,ne,t,top in lit_summary)
# ---- permission matrix: (class, text)
P,LM,RS,NL,UK='ok','lim','rst','no','unk'
MX=[("CO₂",[(P,"Part I, GMP"),(P,"GRAS processing aid"),(P,"Listed, GMP (decaf, cocoa, egg, hops, spices, flavours)"),(P,"GMP additive used as processing aid"),(P,"Table C.1, no limit"),(P,"Designated additive")]),
    ("Propane",[(P,"Part I, GMP"),(RS,"GRAS only as propellant/aerating gas"),(NL,"Not listed"),(LM,"1 mg/kg"),(P,"Table C.1, no limit"),(NL,"Not designated")]),
    ("n-Butane",[(P,"Part I, GMP"),(RS,"GRAS only as propellant/aerating gas"),(NL,"Not listed"),(LM,"1 mg/kg flavourings / 0.1 other"),(LM,"Table C.2: extraction processes"),(NL,"Not designated")]),
    ("Isobutane",[(UK,"Not named separately"),(RS,"GRAS only as propellant/aerating gas"),(NL,"Not listed"),(LM,"1 mg/kg flavourings / 0.1 other"),(UK,"Not found separately"),(NL,"Not designated")]),
    ("Dimethyl ether",[(LM,"Part II: 0.009 mg/kg gelatine/defatted animal protein; 3 mg/kg collagen"),(P,"GRN 741, no questions"),(NL,"Not listed"),(LM,"2 mg/kg"),(UK,"Not found in entries reviewed"),(NL,"Not designated")]),
    ("HFC-134a",[(LM,"Part III: 0.02 mg/kg (flavourings)"),(P,"GRN 82, no questions (flavours)"),(NL,"Not listed"),(NL,"Not in S18—8"),(UK,"Not found in entries reviewed"),(NL,"Not designated")]),
    ("Nitrous oxide",[(P,"Part I, GMP"),(RS,"GRAS only as propellant/aerating gas"),(NL,"Not listed"),(NL,"Not in S18—8"),(UK,"Not found as processing aid"),(RS,"Designated additive (use as solvent not confirmed)")])]
mx_src=cites(["EU","CFR_CO2","CFR_PRO","CFR_BUT","CFR_N2O","GRN741","GRN82","HC","FSANZ18","FSANZ134","GB2760","JP"])
mx_html=''.join(f"<tr><th>{e(n)}</th>"+''.join(f"<td class='m-{c}'>{e(t)}</td>" for c,t in cells)+"</tr>" for n,cells in MX)
# ---- residue data table
RES=[("CO₂","No numeric limit (Part I, GMP)","GRAS cGMP (21 CFR 184.1240); Canada GMP","Unknown: no highly cited study quantifies residual CO₂; it leaves as a gas on depressurisation","Not estimated","Contaminants can carry over instead: CO₂ extracts pesticides efficiently",["EU","CFR_CO2","HC","L:10.1016/s0021-9673(97)00461-5"]),
     ("Propane","No numeric limit (Part I, GMP)","ANZ 1 mg/kg; US GRAS only as propellant","Unknown: papers compare yield and quality, not residue","Not estimated","Faster and higher-yield than CO₂ for seed oils; flammable",["EU","FSANZ18","CFR_PRO","L:10.1021/jf0732096"]),
     ("n-Butane / isobutane","Butane: no numeric limit (Part I); isobutane not named","ANZ 1 mg/kg flavourings, 0.1 mg/kg other foods","Unknown","Not estimated","Co-extracts natural constituents such as coumarin (cassia)",["EU","FSANZ18","L:10.1002/fsn3.1065"]),
     ("Dimethyl ether","0.009 mg/kg gelatine & defatted animal protein; 3 mg/kg collagen","EFSA 2015: no safety concern at these limits; adequate margin of exposure; in-vitro genotoxicity negative. ANZ 2 mg/kg. FDA GRN 741: no questions","GRN 741 Table 3.2-1: not detected (<2 ppm, GC-MS/GC-FID) in 5 extracted products","EFSA: 1.75 µg/kg bw/day (collagen at 3 mg/kg) and 0.014 µg/kg bw/day (gelatine). GRN 741: 0.033 mg/kg bw/day worst case at the 2 ppm detection limit","Fire hazard and solvent loss (2–5%) are the main drawbacks",["EU","EFSA_DME","GRN741N","GRN741","FSANZ18"]),
     ("HFC-134a","0.02 mg/kg in food (from flavourings, Part III)","FDA GRN 82: no questions (flavour extraction)","Unknown: GRN 82 dossier PDF not retrievable here","Not found","Strong greenhouse gas; occupational toxicity data reviewed",["EU","GRN82","L:10.1016/j.chemosphere.2005.03.084"]),
     ("Nitrous oxide","No numeric limit (Part I, GMP)","US GRAS only as propellant/aerating gas","Unknown; no documented food extraction use found","Not estimated","Oxidiser: SFE with organic samples is hazardous",["EU","CFR_N2O","L:10.1021/ac00069a028"])]
def rcites(keys):
    out=[]
    for k in keys:
        if k.startswith('L:'):
            d=k[2:]; out.append(f'<a class="c" href="https://doi.org/{e(d)}" target="_blank" rel="noopener" title="doi:{e(d)}">[doi]</a>')
        else: out.append(cites([k]))
    return ''.join(out)
res_html=''.join(f"<tr><td><b>{e(a)}</b></td><td>{e(b_)}</td><td>{e(c)}</td><td class='{'unk' if d.startswith('Unknown') else ''}'>{e(d)}</td><td class='{'unk' if f.startswith('Not') else ''}'>{e(f)}</td><td>{e(g)}</td><td class='src'>{rcites(s)}</td></tr>" for a,b_,c,d,f,g,s in RES)

cat_opts=''.join(f'<option>{e(c)}</option>' for c in cats)

page=f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Food ingredients made with gas solvents — exhaustive reference</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--ink:#1d2330;--mute:#5d6678;--line:#e3e6ec;--acc:#0f766e;--acc2:#e0f2f1}}
*{{box-sizing:border-box}}body{{margin:0;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--ink)}}
header{{background:linear-gradient(135deg,#0f766e,#155e75);color:#fff;padding:32px 24px 24px}}header h1{{margin:0 0 6px;font-size:26px}}header p{{margin:0;opacity:.9;max-width:900px}}
.stats{{display:flex;gap:12px;margin-top:16px;flex-wrap:wrap}}.stat{{background:rgba(255,255,255,.14);border-radius:10px;padding:8px 14px}}.stat b{{font-size:20px;display:block}}
nav{{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid var(--line);padding:8px 24px;display:flex;gap:18px;flex-wrap:wrap}}nav a{{color:var(--acc);text-decoration:none;font-weight:600}}
main{{padding:20px 24px;max-width:1600px;margin:0 auto}}section{{margin-bottom:40px}}h2{{font-size:20px;border-left:4px solid var(--acc);padding-left:10px}}
.controls{{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:10px 0 12px}}.controls input,.controls select{{padding:8px 10px;border:1px solid var(--line);border-radius:8px;font:inherit;background:#fff}}
.controls input{{flex:1;min-width:240px}}#count{{color:var(--mute)}}button{{padding:8px 12px;border-radius:8px;border:1px solid var(--line);background:#fff;cursor:pointer;font:inherit}}
.tablewrap{{overflow:auto;background:var(--card);border:1px solid var(--line);border-radius:12px}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}}
#main thead th{{position:sticky;top:0;background:#eef2f5;cursor:pointer;user-select:none;white-space:nowrap;font-size:13px}}#main thead th:after{{content:" ⇅";color:#9aa3b2}}
#main thead th.asc:after{{content:" ▲";color:var(--acc)}}#main thead th.desc:after{{content:" ▼";color:var(--acc)}}
tbody tr:hover{{background:#f9fbfb}}.latin{{color:var(--mute);font-style:italic;font-size:12px}}.sm{{font-size:12px;color:var(--mute);margin-top:3px}}.reg{{font-size:12.5px;min-width:280px}}
.num{{color:var(--mute)}}.tag{{display:inline-block;font-size:11px;font-weight:700;border-radius:999px;padding:1px 8px;margin:0 3px 2px 0;background:#e2e8f0}}
.t-CO2{{background:#dcfce7;color:#166534}}.t-DME{{background:#fef3c7;color:#92400e}}.t-Butane{{background:#fee2e2;color:#991b1b}}.t-Propane{{background:#ffedd5;color:#9a3412}}.t-HFC134a{{background:#e0e7ff;color:#3730a3}}
.st{{font-size:11.5px;border-radius:6px;padding:2px 6px;white-space:nowrap}}.st-com{{background:#dcfce7}}.st-reg{{background:#e0f2fe}}.st-res{{background:#f3e8ff}}
a.c{{color:var(--acc);text-decoration:none;font-size:12px;margin-right:2px}}a.c:hover{{text-decoration:underline}}.src{{white-space:normal;min-width:70px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
.card h3{{margin:0;font-size:16px}}.chem{{color:var(--mute);font-size:12px;margin-bottom:8px}}table.mini th{{width:150px;font-size:12px;color:var(--mute);font-weight:600}}table.mini td,table.mini th{{padding:6px 6px}}
.note{{background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:10px 14px;margin:10px 0;font-size:13px}}
ol.sources li{{margin-bottom:6px}}.url{{font-size:11px;color:var(--mute);word-break:break-all}}footer{{color:var(--mute);font-size:12px;padding:20px 24px}}
.toc{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px 16px;margin-bottom:18px}}.toc ol{{margin:6px 0 0;columns:3;padding-left:20px}}.toc a{{color:var(--acc)}}
.charts{{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:16px}}.charts figure{{margin:0;background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px}}.charts figure.wide{{grid-column:1/-1}}figcaption{{font-size:12.5px;color:var(--mute);margin-top:6px}}
table.matrix td,table.matrix th{{font-size:12.5px}}.m-ok{{background:#d1fae5}}.m-lim{{background:#dbeafe}}.m-rst{{background:#fef3c7}}.m-no{{background:#f1f1f1;color:#555}}.m-unk{{background:#fff;color:#777;font-style:italic}}
.legend{{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 10px;font-size:12px}}.legend span{{padding:3px 8px;border-radius:6px;border:1px solid var(--line)}}td.unk{{color:#6b7280;background:#f8f8f8;font-style:italic}}
h3.lg{{margin:18px 0 6px;font-size:16px}}table.lit td,table.lit th{{font-size:12.5px}}table.lit thead th{{background:#eef2f5}}.sp{{font-size:11.5px;border-radius:6px;padding:2px 6px;white-space:nowrap}}.sp-pro{{background:#dcfce7}}.sp-con{{background:#fee2e2}}.sp-neu{{background:#e5e7eb}}
@media print{{nav,.controls{{display:none}}}}
</style></head><body>
<header><h1>Food ingredients made with gas solvents</h1>
<p>Ingredients produced with supercritical or subcritical CO₂ and liquefied-gas solvents (propane, butane, isobutane, dimethyl ether, HFC-134a, nitrous oxide), with what each solvent pulls out, typical uses, and rules by jurisdiction. Every row links to its sources.</p>
<div class="stats"><div class="stat"><b>{n_ing}</b>ingredients</div><div class="stat"><b>{n_solv}</b>gas solvents profiled</div><div class="stat"><b>6</b>jurisdictions</div><div class="stat"><b>{len(used)}</b>sources</div></div></header>
<nav><a href="#table">1. Ingredient table</a><a href="#solvents">2. Solvent profiles</a><a href="#matrix">3. Permission matrix</a><a href="#residues">4. Residue data</a><a href="#charts">5. Charts</a><a href="#confused">6. Commonly confused</a><a href="#literature">7. Key literature</a><a href="#litsummary">7a. Literature summary</a><a href="#sources">8. Sources</a></nav>
<main>
<div class="toc" id="toc"><b>Contents</b><ol><li><a href="#table">Ingredient table</a></li><li><a href="#solvents">Solvent profiles</a></li><li><a href="#matrix">Permission matrix</a></li><li><a href="#residues">Residue data</a></li><li><a href="#charts">Charts</a></li><li><a href="#confused">Commonly confused</a></li><li><a href="#literature">Key literature</a></li><li><a href="#sources">Sources</a></li></ol></div>
<section id="table"><h2>1. Ingredients</h2>
<div class="note"><b>How to read this:</b> "Regulatory notes" sum up what applies to the solvent for that kind of food. For rules on the solvent itself, see section 2. The status column separates ingredients sold today (<span class="st st-com">Commercial</span>) from ones a regulation names explicitly (<span class="st st-reg">Regulatory-listed/cleared</span>) and ones only seen in studies, pilots or history (<span class="st st-res">Research/Historical</span>). The spice, herb and seed-oil CO₂ rows come from one manufacturer's current catalogue (FLAVEX). Other CO₂ extractors sell the same kinds of products. End-use examples are typical applications.</div>
<div class="controls"><input id="q" type="search" placeholder="Search ingredient, latin name, compound, use, rule…">
<select id="fcat"><option value="">All categories</option>{cat_opts}</select>
<select id="fsolv"><option value="">All solvents</option><option>CO2</option><option>DME</option><option>Butane/isobutane</option><option>Propane</option><option>HFC-134a</option></select>
<select id="fst"><option value="">Any status</option><option value="com">Commercial</option><option value="reg">Regulatory-listed/cleared</option><option value="res">Research / historical</option></select>
<button id="reset">Reset</button><span id="count"></span></div>
<div class="tablewrap"><table id="main"><thead><tr><th data-k="n">#</th><th>Ingredient</th><th>Category</th><th>Solvent(s)</th><th>What is extracted / removed</th><th>Typical end uses</th><th>Regulatory notes (EU · US · CA · ANZ · CN · JP)</th><th>Status</th><th>Sources</th></tr></thead>
<tbody>{''.join(rows_html)}</tbody></table></div></section>

<section id="solvents"><h2>2. Solvent profiles: rules and residue limits by jurisdiction</h2>
<div class="note">EU: Directive 2009/32/EC Annex I. Part I solvents are allowed for all uses under good manufacturing practice (GMP), meaning only technically unavoidable, harmless residues. Parts II and III set specific uses and maximum residues. Codex has no binding extraction-solvent standard, and its Inventory of Processing Aids is informational only. "Not listed" means the solvent is not on that jurisdiction's positive list. In Canada, Australia/NZ and the EU, that generally means it may not be used as an extraction solvent there.</div>
<div class="cards">{''.join(solv_html)}</div></section>

<section id="matrix"><h2>3. Permission matrix: solvent × jurisdiction (use as an extraction solvent)</h2>
<div class="legend"><span class="m-ok">Permitted (GMP / general)</span><span class="m-lim">Permitted with numeric limits or named uses</span><span class="m-rst">Approved only for a non-solvent use</span><span class="m-no">Not listed</span><span class="m-unk">Unclear / not found</span></div>
<div class="tablewrap"><table class="matrix"><thead><tr><th>Solvent</th><th>EU</th><th>US</th><th>Canada</th><th>AU / NZ</th><th>China</th><th>Japan</th></tr></thead><tbody>{mx_html}</tbody></table></div>
<p class="sm">Sources: {mx_src}. Details and caveats in section 2.</p></section>
<section id="residues"><h2>4. Residue data: solvents side by side</h2>
<div class="note">Limits are maximum residues in the food or ingredient. Grey "Unknown / Not estimated" cells mean no verified figure was found. They do not mean zero.</div>
<div class="tablewrap"><table class="lit"><thead><tr><th>Solvent</th><th>EU max residue (Dir. 2009/32/EC)</th><th>Other regulators: limits & findings</th><th>Measured residue values</th><th>Intake estimates</th><th>Pros / cons noted</th><th>Sources</th></tr></thead><tbody>{res_html}</tbody></table></div></section>
<section id="charts"><h2>5. Charts</h2><div class="charts">
<figure>{ch_solv}<figcaption>Ingredients in section 1 that use each solvent; an ingredient can count under more than one. CO₂ dominates. No food ingredient made with N₂O as a solvent was found.</figcaption></figure>
<figure>{ch_st}<figcaption>Status of the {n_ing} ingredients. "Commercial" includes mixed statuses such as "Commercial / studied".</figcaption></figure>
<figure class="wide">{ch_cat}<figcaption>Ingredients by category. Spice, herb and flavour extracts are mostly CO₂ products.</figcaption></figure>
<figure class="wide">{ch_lim}<figcaption>Numeric residue limits for gas solvents (blue) next to liquid-solvent comparators (grey), on a log scale. The orange bar is the GRN 741 detection limit, not a limit. CO₂, propane, butane and N₂O have no EU numeric limit (GMP). Sources: {lim_cites}</figcaption></figure>
<figure>{ch_lit}<figcaption>Most-cited papers in section 7 (OpenAlex, 9 Nov 2026). General supercritical-fluid reviews dominate; none of them quantifies residues.</figcaption></figure>
<figure>{ch_stance}<figcaption>Pro / con / neutral stance of the listed papers and regulatory documents, by solvent group.</figcaption></figure>
</div></section>
<section id="confused"><h2>6. Commonly confused: why these don't count</h2>
<div class="tablewrap"><table><thead><tr><th>Item</th><th>Why it's not a gas-solvent process</th><th>Relevant rules / limits</th><th>Sources</th></tr></thead><tbody>{''.join(conf_html)}</tbody></table></div></section>

<section id="literature"><h2>7. Key literature on residues</h2>
<div class="note"><b>How this was compiled:</b> candidates came from OpenAlex keyword searches for each solvent, ranked by citation count. Counts were pulled on 9 Nov 2026 from the OpenAlex API (primary ranking), Crossref <code>is-referenced-by-count</code> and Semantic Scholar (S2; "n/a" where rate-limited). Every DOI was checked against Crossref. Stance: <span class="sp sp-pro">Pro</span> argues for or shows benefits of the gas solvent, <span class="sp sp-con">Con</span> raises residue, contaminant, safety or environmental concerns, <span class="sp sp-neu">Neutral</span> is a comparison or regulatory assessment. Where an abstract wasn't available the takeaway describes the paper's scope ("Scope:") rather than its findings. <b>Main finding:</b> very few highly cited papers measure residual gas solvent in finished food. The quantitative residue data sit mainly in regulatory dossiers (EFSA DME opinions, FDA GRAS notices). The research literature mostly assumes CO₂ and liquefied gases leave negligible residue once depressurised.</div>
<p><b>Most-cited overall ({n_lit} items listed):</b></p><ol>{top_html}</ol>
<h3 class='lg' id='litsummary'>7a. Literature summary by solvent</h3><div class='tablewrap'><table class='lit'><thead><tr><th>Solvent group</th><th>Items</th><th>Pro</th><th>Con</th><th>Neutral</th><th>Total OpenAlex citations</th><th>Most-cited item</th></tr></thead><tbody>{lit_sum_html}</tbody></table></div>
{''.join(lit_html)}
</section>
<section id="sources"><h2>8. Sources</h2><ol class="sources">{src_html}</ol>
<p class="note">Links were checked on 9 Nov 2026. Some publisher pages (Wiley, ACS, ScienceDirect, MDPI) and the Chinese CFSA lookup block automated checkers or load slowly outside China, but they open normally in a browser. DOIs are used where possible so links stay stable.</p></section>
</main>
<footer>Compiled 9 Nov 2026. This is a reference summary, not legal advice. Check the current consolidated regulation before relying on any limit.</footer>
<script>
(function(){{
var tb=document.querySelector('#main tbody'),rows=[].slice.call(tb.rows),q=document.getElementById('q'),fc=document.getElementById('fcat'),fs=document.getElementById('fsolv'),fst=document.getElementById('fst'),cnt=document.getElementById('count');
function apply(){{var t=q.value.toLowerCase().trim(),c=fc.value,s=fs.value,st=fst.value,n=0;
rows.forEach(function(r){{var ok=(!t||r.textContent.toLowerCase().indexOf(t)>-1)&&(!c||r.dataset.cat===c)&&(!s||r.dataset.solv.split('|').indexOf(s)>-1)&&(!st||r.dataset.status===st);r.style.display=ok?'':'none';if(ok)n++;}});
cnt.textContent=n+' of '+rows.length+' shown';}}
[q,fc,fs,fst].forEach(function(el){{el.addEventListener('input',apply);el.addEventListener('change',apply);}});
document.getElementById('reset').onclick=function(){{q.value='';fc.value='';fs.value='';fst.value='';apply();}};
var ths=document.querySelectorAll('#main thead th');
ths.forEach(function(th,i){{th.addEventListener('click',function(){{var asc=!th.classList.contains('asc');ths.forEach(function(h){{h.classList.remove('asc','desc')}});th.classList.add(asc?'asc':'desc');
rows.sort(function(a,b){{var x=a.cells[i].textContent.trim(),y=b.cells[i].textContent.trim();var nx=parseFloat(x),ny=parseFloat(y);var r=(i===0&&!isNaN(nx)&&!isNaN(ny))?nx-ny:x.localeCompare(y,undefined,{{numeric:true,sensitivity:'base'}});return asc?r:-r;}});
rows.forEach(function(r){{tb.appendChild(r)}});}});}});
apply();}})();
</script></body></html>'''
open('/workspace/gas-solvent-food-ingredients.html','w').write(page)
print('lit',n_lit, dict(solv_counts), dict(st_counts)); print(n_ing, n_solv, len(used), [k for k in S if k not in used])
