"""Merge Fortune + SEC + Wikidata + Census geocodes + 10-K scan into data/companies.json and data/edges.json."""
import json, re, glob, csv
from collections import defaultdict, Counter
items = sorted(json.load(open('data/fortune_list_2026.json')), key=lambda i: i['order'])
W = json.load(open('data/wikidata.json'))
STATES = {'Alabama':'AL','Alaska':'AK','Arizona':'AZ','Arkansas':'AR','California':'CA','Colorado':'CO','Connecticut':'CT','Delaware':'DE','District of Columbia':'DC','Florida':'FL','Georgia':'GA','Hawaii':'HI','Idaho':'ID','Illinois':'IL','Indiana':'IN','Iowa':'IA','Kansas':'KS','Kentucky':'KY','Louisiana':'LA','Maine':'ME','Maryland':'MD','Massachusetts':'MA','Michigan':'MI','Minnesota':'MN','Mississippi':'MS','Missouri':'MO','Montana':'MT','Nebraska':'NE','Nevada':'NV','New Hampshire':'NH','New Jersey':'NJ','New Mexico':'NM','New York':'NY','North Carolina':'NC','North Dakota':'ND','Ohio':'OH','Oklahoma':'OK','Oregon':'OR','Pennsylvania':'PA','Rhode Island':'RI','South Carolina':'SC','South Dakota':'SD','Tennessee':'TN','Texas':'TX','Utah':'UT','Vermont':'VT','Virginia':'VA','Washington':'WA','West Virginia':'WV','Wisconsin':'WI','Wyoming':'WY','Puerto Rico':'PR'}
SUFFIX = re.compile(r'\s+(city|town|village|CDP|borough|municipality|township|city and borough|consolidated government.*|metro government.*|urban county|unified government.*|metropolitan government.*|\(balance\))+$', re.I)
def norm(s): return re.sub(r'[^a-z]', '', s.lower().replace('saint', 'st').replace('st.', 'st').replace('ft.', 'fort').replace('mt.', 'mount'))
gaz = {}
for fn, kind in [('data/2024_Gaz_cousubs_national.txt', 'Census county subdivision'), ('data/2024_Gaz_place_national.txt', 'Census place')]:
    with open(fn, encoding='latin-1') as f:
        r = csv.reader(f, delimiter='\t'); hdr = [h.strip() for h in next(r)]
        for row in r:
            d = dict(zip(hdr, [x.strip() for x in row]))
            nm = SUFFIX.sub('', d['NAME']); nm = re.sub(r'\s+(city|town)$', '', nm)
            gaz[(d['USPS'], norm(nm))] = (float(d['INTPTLAT']), float(d['INTPTLONG']), kind)  # places override cousubs
def num(s):
    if s in (None, '', '-', 'n/a'): return None
    s = s.replace('$', '').replace(',', '').replace('%', '').strip()
    try: return float(s)
    except: return None
qmatch = {int(o): q for o, q in W['match'].items()}
q2o = {q: o for o, q in qmatch.items()}
companies = []
for it in items:
    o = it['order']; d = it['data']
    pg = json.load(open(f'data/fortune_pages/{o:03d}.json')); ci = pg['companyInfo'] or {}
    sec = json.load(open(f'data/sec/{o:03d}.json'))
    q = qmatch.get(o); wp = W['props'].get(q, {}) if q else {}
    tables = {t['title']: {v['title']: v['value'] for v in t['values']} for t in (pg.get('dataTables') or [])}
    kf = tables.get('Key Financials (last Fiscal Year)', {})
    founded = None; fsrc = None
    for t in tables.values():
        for k in ('Year founded', 'Founded'):
            if t.get(k) and re.fullmatch(r'\d{4}', t[k].strip()): founded = int(t[k]); fsrc = 'Fortune'
    if not founded and wp.get('inception'):
        ys = [int(x['id'][:4]) for x in wp['inception'] if x['id'] and re.match(r'^\d{4}', x['id'])]
        if ys: founded = min(ys); fsrc = 'Wikidata P571'
    st = STATES.get(d.get('State', ''), None) or {'District Of Columbia': 'DC'}.get(d.get('State', ''))
    city = d.get('Headquarters City', '')
    # aliases: Census names that differ, and neighborhoods geocoded to their parent city
    ALIAS = {('ID', 'boise'): 'boisecity', ('TN', 'nashville'): 'nashvilledavidson', ('TN', 'antioch'): 'nashvilledavidson',
             ('NY', 'longislandcity'): 'newyork', ('CA', 'woodlandhills'): 'losangeles', ('DC', 'washingtondc'): 'washington'}
    geo = gaz.get((st, ALIAS.get((st, norm(city)), norm(city)))) if st else None
    lat = lon = None; gsrc = None
    if geo: lat, lon, gsrc = geo[0], geo[1], geo[2] + ' (2024 Gazetteer)'
    else:
        for h in wp.get('hq', []):
            if h.get('coord'):
                m = re.match(r'Point\(([-\d.]+) ([-\d.]+)\)', h['coord'])
                if m: lon, lat = float(m.group(1)), float(m.group(2)); gsrc = 'Wikidata HQ (P159/P625)'; break
    rh = {}
    for r in pg.get('rankings', []):
        if r['slug'] == 'fortune500' and r.get('rank'): rh[r['year']] = r['rank']
    blurb = next((r.get('itemDescription') for r in pg.get('rankings', []) if r['slug'] == 'fortune500' and r['year'] == 2026 and r.get('itemDescription')), None)
    blurb = re.sub(r'<[^>]+>', '', blurb or '').strip() or None
    logo = (wp.get('logo') or [{}])[0].get('id')
    def hist(h): return {int(k): round(v / 1e6, 1) for k, v in (h or {}).items()}
    rev = num(d.get('Revenues ($M)')); prof = num(d.get('Profits ($M)'))
    companies.append({
        'id': o, 'rank': it['rank'], 'name': it['name'], 'fortuneUrl': 'https://fortune.com' + it['slug'],
        'ticker': ci.get('Ticker') or None, 'exchange': ci.get('StockQuote') or None, 'type': ci.get('Company type') or None,
        'sector': d.get('Sector'), 'industry': d.get('Industry'), 'city': city, 'state': d.get('State'), 'st': st,
        'lat': lat, 'lon': lon, 'geoSrc': gsrc,
        'revenue': rev, 'revChg': num(d.get('Revenue Percent Change')), 'profit': prof, 'profitChg': num(d.get('Profits Percent Change')),
        'assets': num(d.get('Assets ($M)')), 'equity': num(kf.get('Total Stockholder Equity ($M)')), 'mktcap': num(d.get('Market Value ($M)')),
        'employees': num(d.get('Employees')), 'margin': round(prof / rev * 100, 2) if rev and prof is not None else None,
        'rankChg': num(d.get('Change in Rank (500 only)')), 'newcomer': d.get('Newcomer to the Fortune 500') == 'yes',
        'femaleCeo': d.get('Female CEO') == 'yes', 'founderCeo': d.get('Founder is CEO') == 'yes', 'global500': d.get('Global 500') == 'yes',
        'mostAdmired': d.get("World's Most Admired Companies") == 'yes',
        'ceo': ci.get('CEO') or None, 'website': ci.get('Website') or None, 'founded': founded, 'foundedSrc': fsrc,
        'desc': pg.get('description') or None, 'blurb': blurb, 'fyNote': ci.get('Footnote'),
        'eps': num(tables.get('Earnings Per Share (last Fiscal Year)', {}).get('Earnings Per Share ($)')),
        'tr1': num(tables.get('Total Return', {}).get('Total Return to Investors (last year)')),
        'tr5': num(tables.get('Total Return', {}).get('Total Return to Investors (5 year, annualized)')),
        'tr10': num(tables.get('Total Return', {}).get('Total Return to Investors (10 year, annualized)')),
        'rankHist': dict(sorted(rh.items())),
        'cik': sec.get('cik'), 'sic': sec.get('sic'), 'sicDesc': sec.get('sicDescription'), 'stateInc': sec.get('stateOfIncorporation'),
        'fyEnd': sec.get('fiscalYearEnd'), 'formerNames': [f['name'] for f in (sec.get('formerNames') or [])][:6],
        'revHist': hist(sec.get('rev_hist')), 'niHist': hist(sec.get('ni_hist')), 'assetsHist': hist(sec.get('assets_hist')),
        'tenK': sec.get('latest10k'),
        'qid': q, 'wdDesc': (W['labels'].get(q) or [None, None])[1] if q else None,
        'wiki': (wp.get('enwiki') or [{}])[0].get('id'), 'logo': logo,
        'foundedBy': [x['label'] for x in wp.get('founded_by', []) if x.get('label')][:5],
        'wdIndustry': sorted({x['label'] for x in wp.get('industry', []) if x.get('label') and not re.match(r'^Q\d+$', x['label'])})[:6],
        'chair': [x['label'] for x in wp.get('chair', []) if x.get('label')][:2],
    })
byid = {c['id']: c for c in companies}
edges = []; seen = set()
def add(a, b, typ, label, src, ev=None, url=None, directed=True):
    if a == b: return
    key = (typ, a, b) if directed else (typ, min(a, b), max(a, b))
    if key in seen: return
    seen.add(key); edges.append({'s': a, 't': b, 'type': typ, 'label': label, 'src': src, 'ev': ev, 'url': url})
# 1) Industry peers: each company to its 3 nearest-by-revenue peers in the same Fortune industry
ind = defaultdict(list)
for c in companies: ind[c['industry']].append(c)
for k, l in ind.items():
    for c in l:
        near = sorted((x for x in l if x is not c), key=lambda x: abs((x['revenue'] or 0) - (c['revenue'] or 0)))[:3]
        for x in near: add(c['id'], x['id'], 'peer', f'Same Fortune industry: {k}', 'Fortune 500 2026 industry classification', directed=False)
# 2) Wikidata ownership / corporate structure
def wd(q): return f'https://www.wikidata.org/wiki/{q}'
for o, q in qmatch.items():
    p = W['props'].get(q, {})
    for e in p.get('parent', []):
        if e['id'] in q2o: add(q2o[e['id']], o, 'parent', 'Parent organization of', 'Wikidata P749', url=wd(q))
    for e in p.get('subsidiary', []):
        if e['id'] in q2o: add(o, q2o[e['id']], 'parent', 'Has subsidiary', 'Wikidata P355', url=wd(q))
    for e in p.get('owned_by', []):
        if e['id'] in q2o: add(q2o[e['id']], o, 'owner', 'Shareholder / owner of', 'Wikidata P127 (owned by)', url=wd(q))
    for e in p.get('owner_of', []):
        if e['id'] in q2o: add(o, q2o[e['id']], 'owner', 'Shareholder / owner of', 'Wikidata P1830 (owner of)', url=wd(q))
    for e in p.get('separated_from', []):
        if e['id'] in q2o: add(q2o[e['id']], o, 'spinoff', 'Spun off / separated', 'Wikidata P807 (separated from)', url=wd(q))
    for e in p.get('replaces', []):
        if e['id'] in q2o: add(q2o[e['id']], o, 'spinoff', 'Succeeded by / split', 'Wikidata P1365 (replaces)', url=wd(q))
    for e in p.get('replaced_by', []):
        if e['id'] in q2o: add(o, q2o[e['id']], 'spinoff', 'Succeeded by / merged into', 'Wikidata P1366 (replaced by)', url=wd(q))
# 3) Shared board members (Wikidata P3320, current statements without end date)
pb = defaultdict(set); pname = {}
for o, q in qmatch.items():
    for e in W['props'].get(q, {}).get('board', []):
        pb[e['id']].add(o); pname[e['id']] = e.get('label')
for pid, os_ in pb.items():
    os_ = sorted(os_)
    for i in range(len(os_)):
        for j in range(i + 1, len(os_)):
            a, b = os_[i], os_[j]
            key = ('board', a, b)
            ex = next((e for e in edges if e['type'] == 'board' and e['s'] == a and e['t'] == b), None) if key in seen else None
            if ex: ex['ev'] += f'; {pname[pid]}'; continue
            add(a, b, 'board', 'Shared board member', 'Wikidata P3320 (board member)', ev=pname[pid], url=wd(pid), directed=False)
# 4) Major customers named in 10-K (sentence-level extraction; filtered for proximity of name to a % figure)
PCT = re.compile(r'\d+(\.\d+)?\s?(%|percent)')
for f in sorted(glob.glob('data/10k/*.json')):
    o = int(f[-8:-5]); d = json.load(open(f))
    for h in d.get('hits', []):
        sn = h['snippet']; i = sn.find(h['alias'])
        if i < 0 or len(sn) >= 600: continue
        if not any(abs(m.start() - i) < 220 for m in PCT.finditer(sn)): continue
        if not re.search(r'(largest|significant|major|principal|top|10%|ten percent)\s.{0,40}customer|customers?\s.{0,80}accounted|accounted for.{0,80}(revenue|sales)|customer.{0,60}(represented|comprised)', sn, re.I): continue
        add(h['to'], o, 'customer', 'Major customer of (disclosed in 10-K)', f"SEC 10-K filed {d.get('date')}", ev=sn[:420], url=d.get('url'))
for e in edges:
    e['s'], e['t'] = int(e['s']), int(e['t'])
json.dump(companies, open('data/companies.json', 'w'), indent=0)
json.dump(edges, open('data/edges.json', 'w'), indent=0)
fields = ['ticker', 'sector', 'industry', 'city', 'lat', 'revenue', 'profit', 'assets', 'equity', 'mktcap', 'employees', 'ceo', 'founded', 'desc', 'website', 'qid', 'cik', 'revHist', 'wiki', 'rankHist']
cov = {k: sum(1 for c in companies if c.get(k) not in (None, '', {}, [])) for k in fields}
stats = {'companies': len(companies), 'coverage': cov, 'edges': dict(Counter(e['type'] for e in edges))}
json.dump(stats, open('data/stats.json', 'w'), indent=1); print(json.dumps(stats, indent=1))
print('no geo:', [(c['name'], c['city'], c['st']) for c in companies if c['lat'] is None])
for e in edges:
    if e['type'] == 'customer': print(byid[e['t']]['name'], '<-cust-', byid[e['s']]['name'], '|', e['ev'][:120])
