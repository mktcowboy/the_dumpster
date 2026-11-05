"""Wikidata: match companies (by SEC CIK P5531, else official website P856), pull founding, HQ, CEO, ownership, subsidiaries, board members, spin-off/merger links."""
import json, os, re, time, requests, glob
EP = 'https://query.wikidata.org/sparql'
H = {'User-Agent': 'F500Explorer/1.0 (research; admin@example.com)', 'Accept': 'application/sparql-results+json'}
items = json.load(open('data/fortune_list_2026.json'))
def q(s):
    for a in range(5):
        r = requests.post(EP, data={'query': s}, headers=H, timeout=120)
        if r.status_code == 200: return r.json()['results']['bindings']
        print('sparql', r.status_code, r.text[:200]); time.sleep(5 + 5 * a)
    return []
def v(b, k): return b[k]['value'] if k in b else None
def qid(u): return u.rsplit('/', 1)[-1] if u else None
order2 = {}
ciks = {}
for it in items:
    o = it['order']; s = json.load(open(f'data/sec/{o:03d}.json'))
    if s.get('cik'): ciks[f"{s['cik']:010d}"] = o
match = {}
keys = list(ciks)
for i in range(0, len(keys), 150):
    vals = ' '.join(f'"{k}"' for k in keys[i:i+150])
    for b in q(f'SELECT ?item ?cik WHERE {{ VALUES ?cik {{ {vals} }} ?item wdt:P5531 ?cik. }}'):
        o = ciks[v(b, 'cik')]
        match.setdefault(o, []).append(qid(v(b, 'item')))
# website fallback
def dom(u): return re.sub(r'^(https?://)?(www\d?\.)?', '', (u or '').lower()).split('/')[0]
missing = [it for it in items if it['order'] not in match]
doms = {}
for it in missing:
    pg = json.load(open(f"data/fortune_pages/{it['order']:03d}.json"))
    d = dom(pg['companyInfo'].get('Website'))
    if d: doms.setdefault(d, []).append(it['order'])
dl = list(doms)
for i in range(0, len(dl), 60):
    vals = ' '.join(f'<https://www.{d}/> <https://{d}/> <http://www.{d}/> <https://www.{d}> <https://{d}> <http://www.{d}> <http://{d}/>' for d in dl[i:i+60])
    for b in q(f'SELECT ?item ?w WHERE {{ VALUES ?w {{ {vals} }} ?item wdt:P856 ?w. ?item wdt:P31/wdt:P279* wd:Q4830453. }}'):
        for o in doms.get(dom(v(b, 'w')), []):
            match.setdefault(o, []).append(qid(v(b, 'item')))
# resolve multiple matches: prefer item with most sitelinks
allq = sorted({x for l in match.values() for x in l})
sl = {}
for i in range(0, len(allq), 200):
    vals = ' '.join('wd:' + x for x in allq[i:i+200])
    for b in q(f'SELECT ?item ?n WHERE {{ VALUES ?item {{ {vals} }} ?item wikibase:sitelinks ?n. }}'):
        sl[qid(v(b, 'item'))] = int(v(b, 'n'))
best = {o: max(set(l), key=lambda x: sl.get(x, 0)) for o, l in match.items()}
print('matched', len(best), 'of', len(items))
Q = list(best.values())
props = {'inception': 'P571', 'hq': 'P159', 'ceo': 'P169', 'chair': 'P488', 'parent': 'P749', 'subsidiary': 'P355',
         'owned_by': 'P127', 'owner_of': 'P1830', 'board': 'P3320', 'replaces': 'P1365', 'replaced_by': 'P1366',
         'separated_from': 'P807', 'founded_by': 'P112', 'enwiki': None, 'logo': 'P154', 'industry': 'P452'}
out = {x: {} for x in Q}
for name, p in props.items():
    for i in range(0, len(Q), 100):
        vals = ' '.join('wd:' + x for x in Q[i:i+100])
        if name == 'enwiki':
            s = f'SELECT ?item ?val WHERE {{ VALUES ?item {{ {vals} }} ?val schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>. }}'
        else:
            s = f'''SELECT ?item ?val ?valLabel ?coord WHERE {{ VALUES ?item {{ {vals} }} ?item p:{p} ?st. ?st ps:{p} ?val.
              FILTER NOT EXISTS {{ ?st pq:P582 ?end }} {"OPTIONAL { ?val wdt:P625 ?coord }" if name == 'hq' else ''}
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}'''
        for b in q(s):
            it = qid(v(b, 'item'))
            out[it].setdefault(name, []).append({'id': qid(v(b, 'val')) if name not in ('inception', 'enwiki', 'logo') else v(b, 'val'),
                                                 'label': v(b, 'valLabel'), 'coord': v(b, 'coord')})
        time.sleep(1)
    print(name, sum(1 for x in out.values() if name in x))
# labels of matched items
lab = {}
for i in range(0, len(Q), 200):
    vals = ' '.join('wd:' + x for x in Q[i:i+200])
    for b in q(f'SELECT ?item ?l ?d WHERE {{ VALUES ?item {{ {vals} }} ?item rdfs:label ?l FILTER(lang(?l)="en") OPTIONAL {{ ?item schema:description ?d FILTER(lang(?d)="en") }} }}'):
        lab[qid(v(b, 'item'))] = (v(b, 'l'), v(b, 'd'))
json.dump({'match': {str(o): q_ for o, q_ in best.items()}, 'labels': lab, 'props': out}, open('data/wikidata.json', 'w'), indent=0)
