"""Wikidata instance-of (P31), legal form (P1454), parent (P749) with country, owned-by for ownership classification."""
import json, time, requests
EP = 'https://query.wikidata.org/sparql'
H = {'User-Agent': 'F500Explorer/1.0 (research; admin@example.com)', 'Accept': 'application/sparql-results+json'}
W = json.load(open('data/wikidata.json'))
Q = sorted(set(W['match'].values()))
out = {q: {} for q in Q}
def run(s):
    for a in range(5):
        r = requests.post(EP, data={'query': s}, headers=H, timeout=120)
        if r.status_code == 200: return r.json()['results']['bindings']
        time.sleep(5 + 5 * a)
    return []
for name, p in [('p31', 'P31'), ('legal', 'P1454'), ('parent', 'P749')]:
    for i in range(0, len(Q), 120):
        vals = ' '.join('wd:' + x for x in Q[i:i+120])
        s = f'''SELECT ?item ?val ?valLabel ?ctryLabel WHERE {{ VALUES ?item {{ {vals} }} ?item p:{p} ?st. ?st ps:{p} ?val. FILTER NOT EXISTS {{ ?st pq:P582 ?e }}
          OPTIONAL {{ ?val wdt:P17 ?ctry }} SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}'''
        for b in run(s):
            q = b['item']['value'].rsplit('/', 1)[-1]
            out[q].setdefault(name, []).append({'id': b['val']['value'].rsplit('/', 1)[-1], 'label': b.get('valLabel', {}).get('value'), 'country': b.get('ctryLabel', {}).get('value')})
        time.sleep(1)
json.dump(out, open('data/wikidata_ownership.json', 'w'), indent=0)
from collections import Counter
print(Counter(x['label'] for v in out.values() for x in v.get('p31', [])).most_common(40))
print(Counter(x['label'] for v in out.values() for x in v.get('legal', [])).most_common(20))
