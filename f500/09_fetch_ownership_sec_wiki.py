"""Ownership evidence: SEC submissions (exchanges, delisting/deregistration forms) for every CIK, SEC name search for
companies Fortune lists as private, and the 'type' field of each private company's Wikipedia infobox."""
import json, re, time, requests
UA = {'User-Agent': 'F500Explorer research admin@example.com'}
C = json.load(open('data/companies.json'))
out = {}
EXTRA_NAMES = {}  # filled from SEC autocomplete for Fortune-private companies without CIK
def sub(cik):
    time.sleep(0.12); r = requests.get(f'https://data.sec.gov/submissions/CIK{int(cik):010d}.json', headers=UA, timeout=60)
    return r.json() if r.status_code == 200 else None
for c in C:
    o = {'cik': c['cik']}
    if not c['cik'] and c['type'] != 'Public':
        try:
            r = requests.get('https://efts.sec.gov/LATEST/search-index', params={'keysTyped': c['name']}, headers=UA, timeout=30).json()
            hits = r.get('hits', {}).get('hits', [])
            norm = lambda s: re.sub(r'[^a-z]', '', s.lower().replace('inc', '').replace('corp', ''))
            for h in hits:
                nm = (h['_source'].get('entity_words') or h['_source'].get('entity') or '')
                if norm(nm).startswith(norm(c['name'])[:10]): o['cik'] = int(h['_id']); o['sec_name_match'] = nm; break
        except Exception as e: print('search fail', c['name'], e)
        time.sleep(0.2)
    if o['cik']:
        s = sub(o['cik'])
        if s:
            f = s['filings']['recent']
            o['sec_name'] = s.get('name'); o['exchanges'] = s.get('exchanges'); o['tickers'] = s.get('tickers')
            o['dereg'] = [{'form': f['form'][i], 'date': f['filingDate'][i]} for i in range(len(f['form'])) if f['form'][i] in ('25-NSE', '25', '15-12B', '15-12G', '15-15D') and f['filingDate'][i] >= '2025-06-01'][:4]
            o['last10k'] = next((f['filingDate'][i] for i in range(len(f['form'])) if f['form'][i] == '10-K'), None)
    out[c['id']] = o
# Wikipedia infobox type for every company Fortune does not list as Public, plus OTC-traded ones
def infobox_type(url):
    title = url.rsplit('/', 1)[-1]
    r = requests.get('https://en.wikipedia.org/w/api.php', params={'action': 'parse', 'page': requests.utils.unquote(title), 'prop': 'wikitext', 'section': 0, 'format': 'json', 'redirects': 1}, headers={'User-Agent': 'F500Explorer/1.0 (admin@example.com)'}, timeout=30).json()
    wt = r.get('parse', {}).get('wikitext', {}).get('*', '')
    m = re.search(r'\|\s*type\s*=\s*(.+)', wt)
    if not m: return None
    t = m.group(1)
    t = re.sub(r'\{\{(?:nowrap|plainlist|ubl|unbulleted list)\|', '', t, flags=re.I)
    t = re.sub(r'<ref[^>]*/>|<ref.*?</ref>|<ref.*', '', t); t = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', t)
    t = re.sub(r'\{\{[^}]*\}\}', '', t); t = re.sub(r'<br\s*/?>', '; ', t); t = re.sub(r"'''?|\}\}|\{\{", '', t)
    return re.sub(r'\s+', ' ', t).strip(' ;|') or None
for c in C:
    if (c['type'] != 'Public' or c['exchange'] in ('OTC', None)) and c.get('wiki'):
        try: out[c['id']]['wiki_type'] = infobox_type(c['wiki'])
        except Exception as e: print('wiki fail', c['name'], e)
        time.sleep(0.3)
json.dump(out, open('data/ownership_evidence.json', 'w'), indent=0)
for c in C:
    o = out[c['id']]
    if c['type'] != 'Public' or o.get('dereg') or c['exchange'] in ('OTC', None):
        print(c['rank'], c['name'], '|', o.get('wiki_type'), '|', o.get('dereg'), '|', o.get('exchanges'), o.get('sec_name_match',''))
