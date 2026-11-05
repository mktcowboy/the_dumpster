"""Wikipedia lead paragraph (plain text) for companies Fortune does not list as Public — used as ownership evidence."""
import json, requests, time
C = json.load(open('data/companies.json')); ev = json.load(open('data/ownership_evidence.json'))
for c in C:
    if c['type'] != 'Public' and c.get('wiki'):
        t = requests.utils.unquote(c['wiki'].rsplit('/', 1)[-1])
        r = requests.get('https://en.wikipedia.org/w/api.php', params={'action': 'query', 'prop': 'extracts', 'exintro': 1, 'explaintext': 1, 'titles': t, 'format': 'json', 'redirects': 1}, headers={'User-Agent': 'F500Explorer/1.0 (admin@example.com)'}).json()
        pg = next(iter(r['query']['pages'].values()))
        ev[str(c['id'])]['wiki_intro'] = pg.get('extract', '')[:1500]
        time.sleep(0.3)
json.dump(ev, open('data/ownership_evidence.json', 'w'), indent=0)
for c in C:
    if c['type'] != 'Public': print(c['rank'], c['name'], '::', (ev[str(c['id'])].get('wiki_intro') or '')[:260].replace('\n', ' '))
