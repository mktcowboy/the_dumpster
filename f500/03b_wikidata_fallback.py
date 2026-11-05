"""Wikidata fallback: match remaining companies by name search (must be a business in the US), then fetch same props; refresh labels."""
import json, time, requests, re
exec(open('03_fetch_wikidata.py').read().split('order2 = {}')[0])  # reuse q(), v(), qid(), items
W = json.load(open('data/wikidata.json'))
items = json.load(open('data/fortune_list_2026.json'))
API = 'https://www.wikidata.org/w/api.php'
# Manual review of name-search matches (wrong items removed, correct QIDs verified by label/description)
WRONG = {'Q5513286', 'Q259195', 'Q466587', 'Q16986267'}
OVERRIDES = {'GE Vernova': 'Q118957699', 'APA': 'Q119991', 'Kenvue': 'Q118905792', 'Lululemon athletica': 'Q6702957',
             'Reliance': 'Q7311031', 'Galaxy Digital': 'Q138026190', 'FM': 'Q1391731', 'APi Group': 'Q30298154',
             'GuideWell Mutual Holding': 'Q65050916', 'Gold.com': 'Q30647067'}
W['match'] = {o: x for o, x in W['match'].items() if x not in WRONG}
for it in items:
    if it['name'] in OVERRIDES: W['match'][str(it['order'])] = OVERRIDES[it['name']]
for it in items:
    o = str(it['order'])
    if o in W['match'] or it['name'] in ('Constellation Energy', 'Ingersoll Rand'): continue
    nm = re.sub(r'\s+(Holdings|Group|Hldgs\.)$', '', it['name'])
    r = requests.get(API, params={'action': 'wbsearchentities', 'search': nm, 'language': 'en', 'format': 'json', 'limit': 7}, headers=H).json()
    cands = [x['id'] for x in r.get('search', [])]
    if not cands: print('none', nm); continue
    vals = ' '.join('wd:' + c for c in cands)
    ok = {qid(v(b, 'item')) for b in q(f'SELECT DISTINCT ?item WHERE {{ VALUES ?item {{ {vals} }} ?item wdt:P31/wdt:P279* wd:Q4830453. {{?item wdt:P17 wd:Q30}} UNION {{?item wdt:P159/wdt:P17 wd:Q30}} }}')}
    pick = next((c for c in cands if c in ok), None)
    print(it['name'], '->', pick)
    if pick and pick not in W['match'].values(): W['match'][o] = pick
    time.sleep(0.5)
Q = [x for x in W['match'].values() if x not in W['props']]
props = {'inception': 'P571', 'hq': 'P159', 'ceo': 'P169', 'chair': 'P488', 'parent': 'P749', 'subsidiary': 'P355',
         'owned_by': 'P127', 'owner_of': 'P1830', 'board': 'P3320', 'replaces': 'P1365', 'replaced_by': 'P1366',
         'separated_from': 'P807', 'founded_by': 'P112', 'logo': 'P154', 'industry': 'P452'}
for x in Q: W['props'][x] = {}
vals = ' '.join('wd:' + x for x in Q)
for name, p in props.items():
    s = f'''SELECT ?item ?val ?valLabel ?coord WHERE {{ VALUES ?item {{ {vals} }} ?item p:{p} ?st. ?st ps:{p} ?val.
      FILTER NOT EXISTS {{ ?st pq:P582 ?end }} {"OPTIONAL { ?val wdt:P625 ?coord }" if name == 'hq' else ''}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}'''
    for b in q(s):
        W['props'][qid(v(b, 'item'))].setdefault(name, []).append({'id': qid(v(b, 'val')) if name not in ('inception', 'logo') else v(b, 'val'), 'label': v(b, 'valLabel'), 'coord': v(b, 'coord')})
for b in q(f'SELECT ?item ?val WHERE {{ VALUES ?item {{ {vals} }} ?val schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>. }}'):
    W['props'][qid(v(b, 'item'))].setdefault('enwiki', []).append({'id': v(b, 'val')})
allq = list(W['match'].values())
for i in range(0, len(allq), 100):
    vs = ' '.join('wd:' + x for x in allq[i:i+100])
    for b in q(f'SELECT ?item ?l ?d WHERE {{ VALUES ?item {{ {vs} }} OPTIONAL {{ ?item rdfs:label ?l FILTER(lang(?l)="en") }} OPTIONAL {{ ?item schema:description ?d FILTER(lang(?d)="en") }} }}'):
        W['labels'][qid(v(b, 'item'))] = (v(b, 'l'), v(b, 'd'))
    time.sleep(1)
print('matched', len(W['match']), 'labels', len(W['labels']))
json.dump(W, open('data/wikidata.json', 'w'), indent=0)
