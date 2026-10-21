#!/usr/bin/env python3
import json, os, re, base64, datetime, sys

ROOT=os.path.dirname(os.path.abspath(__file__))
def load(p, default=None):
    p=os.path.join(ROOT,p)
    if not os.path.exists(p): return default
    with open(p,encoding='utf-8') as f: return json.load(f)

registry=load('data/registry.json')
tanakh=load('data/tanakh_text.json')
agents={
 'tanakh_works':load('agents/tanakh_works.json',[]),
 'other_works':load('agents/other_works.json',[]),
 'people':load('agents/people.json',[]),
 'places':load('agents/places.json',[]),
 'themes':load('agents/themes.json',[]),
 'timeline':load('agents/timeline.json',[]),
 'essays':load('agents/essays.json',[]),
 'pathways':load('agents/pathways.json',[]),
}
warn=[]
# merge works
works=[]
seen=set()
for w in (agents['tanakh_works'] or [])+(agents['other_works'] or []):
    if not isinstance(w,dict) or not w.get('id'): continue
    if w['id'] in seen:
        warn.append(f"duplicate work {w['id']} ignored"); continue
    seen.add(w['id']); works.append(w)
# fall back to registry for missing works
for rw in registry['works']:
    if rw['id'] not in seen:
        warn.append(f"missing work {rw['id']} — using registry stub")
        works.append({**rw,'summary':'','why':'','date':'','language':'','themes':[],'people':[],'places':[],'connections':[],'key_passages':[],'structure':[],'sources':[]})
# fill defaults + normalize
corpus_order={c['id']:i for i,c in enumerate(registry['corpora'])}
for w in works:
    w.setdefault('title',w['id']); w.setdefault('he',w.get('he_title','')); w.setdefault('he_title',w.get('he',''))
    w.setdefault('also',[]); w.setdefault('corpus','tanakh'); w.setdefault('division','')
    w.setdefault('order',99); w.setdefault('date',''); w.setdefault('date_sort',0); w.setdefault('language','')
    w.setdefault('summary',''); w.setdefault('why',''); w.setdefault('structure',[]); w.setdefault('themes',[])
    w.setdefault('people',[]); w.setdefault('places',[]); w.setdefault('key_passages',[]); w.setdefault('connections',[]); w.setdefault('sources',[])
    w['order']=int(w.get('order') or 99)
    if isinstance(w.get('date_sort'),str):
        try:w['date_sort']=int(re.sub(r'[^0-9-]','',w['date_sort']))
        except:w['date_sort']=0
works.sort(key=lambda w:(corpus_order.get(w['corpus'],99),w['order']))
# people/places/themes normalize
def norm_list(key, fields):
    arr=agents[key] or []
    ids={x['id'] for x in arr if isinstance(x,dict) and x.get('id')}
    missing=[x for x in registry[key] if x not in ids]
    for m in missing: warn.append(f"missing {key[:-1] if key.endswith('s') else key}: {m}")
    if missing:
        for m in missing:
            base={'id':m,'name':m.replace('-',' ').title(),'he_name':'','bio':'','sources':[]}
            if key=='people': base.update({'dates':'','era':'','key_idea':'','works':[],'places':[],'themes':[],'connections':[]})
            if key=='places': base.update({'region':'','coordinates':[0,0],'ancient':True,'works':[],'people':[],'themes':[],'connections':[]})
            if key=='themes': base.update({'kind':'idea','short':'','essay':'','works':[],'people':[],'places':[],'connections':[]})
            arr.append(base)
    for x in arr:
        for f in fields: x.setdefault(f,[] if f in ('works','places','themes','people','connections','sources') else '')
    return arr
people=norm_list('people',['name','he_name','dates','era','bio','key_idea','works','places','themes','connections','sources'])
places=norm_list('places',['name','he_name','region','coordinates','ancient','bio','works','people','themes','connections','sources'])
themes=norm_list('themes',['name','he_name','kind','short','essay','works','people','places','connections','sources'])
for p in places:
    c=p.get('coordinates')
    if isinstance(c,str):
        try:c=[float(x) for x in re.findall(r'-?\d+\.?\d*',c)[:2]]
        except:c=[0,0]
    if not (isinstance(c,list) and len(c)==2): c=[0,0]
    p['coordinates']=c
timeline=agents['timeline'] or []
for e in timeline:
    e.setdefault('year',''); e.setdefault('sort',0); e.setdefault('label',''); e.setdefault('title',''); e.setdefault('text','')
    e.setdefault('works',[]); e.setdefault('people',[]); e.setdefault('places',[])
    if isinstance(e['sort'],str):
        try:e['sort']=int(re.sub(r'[^0-9-]','',e['sort']))
        except:e['sort']=0
timeline.sort(key=lambda e:e['sort'])
essays=agents['essays'] or []
for e in essays:
    e.setdefault('title',''); e.setdefault('dek',''); e.setdefault('body',[]); e.setdefault('works',[]); e.setdefault('people',[]); e.setdefault('themes',[]); e.setdefault('sources',[])
pathways=agents['pathways'] or []
for p in pathways:
    p.setdefault('title',''); p.setdefault('dek',''); p.setdefault('intro',''); p.setdefault('stops',[]); p.setdefault('themes',[])

# verify links
ids=set()
for arr in (works,people,places,themes): ids|={x['id'] for x in arr}
bad=[]
for w in works:
    for c in w.get('connections',[]):
        if isinstance(c,dict) and c.get('to') not in ids: bad.append((w['id'],c.get('to')))
for arr in (people,places,themes):
    for x in arr:
        for c in x.get('connections',[]):
            if isinstance(c,dict) and c.get('to') not in ids: bad.append((x['id'],c.get('to')))
if bad:
    warn.append(f"{len(bad)} connection targets missing; first: {bad[:5]}")

site={
 'works':works,'people':people,'places':places,'themes':themes,'timeline':timeline,'essays':essays,'pathways':pathways,
 'corpora':registry['corpora'],
 'map':load('assets/map.json',{'w':1000,'h':750,'paths':[]}),
 'generated':datetime.date.today().isoformat()
}

# css + fonts
css=open(os.path.join(ROOT,'src/style.css'),encoding='utf-8').read()
font_css=''
font_index=load('assets/fonts/index.json',{})
for family,files in font_index.items():
    for fn,style,weight,size in files:
        b64=base64.b64encode(open(os.path.join(ROOT,'assets/fonts',fn),'rb').read()).decode()
        font_css+=f"@font-face{{font-family:'{family}';src:url(data:font/woff2;base64,{b64}) format('woff2');font-style:{style};font-weight:{weight};font-display:swap}}\n"
css=font_css+css

js='\n'.join(open(os.path.join(ROOT,'src',f),encoding='utf-8').read() for f in ['core.js','views.js','graph.js','main.js'])
def jdump(o): return json.dumps(o,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
data_json=jdump(site)
tanakh_json=jdump(tanakh)

favicon="data:image/svg+xml,"+ "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%230a0c11'/%3E%3Cg fill='none' stroke='%23c9a45c' stroke-width='1.2'%3E%3Ccircle cx='16' cy='6' r='2.4'/%3E%3Ccircle cx='7' cy='20' r='2.4'/%3E%3Ccircle cx='25' cy='20' r='2.4'/%3E%3Ccircle cx='16' cy='27' r='2.4'/%3E%3Cpath d='M16 8.4v16M8.6 21.4l5.8-3.2M23.4 21.4l-5.8-3.2'/%3E%3C/g%3E%3C/svg%3E"

html=f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Chain of Tradition — An Atlas of the Jewish Library</title>
<meta name="description" content="A single-file, interactive atlas of the Tanakh, Mishnah, Talmud, Midrash, Rashi, Maimonides, the Shulchan Aruch, the Zohar, and the Siddur — with the full JPS 1917 Tanakh, themes, people, places, and essays.">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#0a0c11">
<link rel="icon" href="{favicon}">
<style>
{css}
</style>
</head>
<body>
<div id="app"><div style="min-height:100vh;display:grid;place-items:center;color:#8d8677;font-family:Georgia,serif;letter-spacing:.18em;text-transform:uppercase;font-size:.7rem">Unrolling the scroll…</div></div>
<script id="site-data" type="application/json">{data_json}</script>
<script id="tanakh-text" type="application/json">{tanakh_json}</script>
<script>
{js}
</script>
</body>
</html>
"""
out=os.path.join(ROOT,'index.html')
with open(out,'w',encoding='utf-8') as f: f.write(html)
print(f"Wrote {out}  {len(html)/1e6:.2f} MB")
print(f"works={len(works)} people={len(people)} places={len(places)} themes={len(themes)} timeline={len(timeline)} essays={len(essays)} pathways={len(pathways)}")
print(f"tanakh: {tanakh['stats']}")
if warn:
    print("WARNINGS:")
    for w in warn[:40]: print(" -",w)
