"""Scan each public company's latest 10-K for sentences naming another Fortune 500 company as a major customer
(sentence must mention 'customer'/'client' and a percentage of revenue/sales). Evidence snippet saved per edge."""
import json, os, re, time, html as H, requests, threading
from concurrent.futures import ThreadPoolExecutor
UA = {'User-Agent': 'F500Explorer research admin@example.com', 'Accept-Encoding': 'gzip'}
os.makedirs('data/10k', exist_ok=True)
items = json.load(open('data/fortune_list_2026.json'))
SUF = r'(,?\s+(Inc\.?|Corp\.?|Corporation|Co\.?|Company|Companies|Group|Holdings?|Hldgs\.?|Incorporated|International|plc|Ltd\.?))+$'
def aliases(name):
    n = re.sub(SUF, '', name).strip()
    a = {n}
    extra = {'Walmart': ['Wal-Mart'], 'Alphabet': ['Google'], 'Meta Platforms': ['Meta', 'Facebook'], 'International Business Machines': ['IBM'],
             'Hewlett Packard Enterprise': ['HPE'], 'HP': ['HP Inc'], 'Home Depot': ['The Home Depot'], 'CVS Health': ['CVS'],
             'Cencora': ['AmerisourceBergen'], 'Lowe\'s': ["Lowe's Companies", "Lowe’s"], 'Costco Wholesale': ['Costco'],
             'ExxonMobil Holdings': ['ExxonMobil', 'Exxon Mobil'], 'Dell Technologies': ['Dell'], 'General Motors': ['GM'],
             'United Parcel Service': ['UPS'], 'Walt Disney': ['Disney'], 'Cigna Group': ['Cigna'], 'Apple': ['Apple'], 'Amazon': ['Amazon', 'Amazon.com'],
             'Lockheed Martin': ['Lockheed'], 'Boeing': ['Boeing'], 'RTX': ['Raytheon', 'RTX'], 'General Dynamics': ['General Dynamics'],
             'Northrop Grumman': ['Northrop'], 'Kroger': ['Kroger'], 'Target': ['Target Corporation'], 'Best Buy': ['Best Buy'],
             'Dollar General': ['Dollar General'], 'Tractor Supply': ['Tractor Supply'], 'TJX': ['TJX'], 'McKesson': ['McKesson'], 'Cardinal Health': ['Cardinal Health'],
             'Microsoft': ['Microsoft'], 'Ford Motor': ['Ford'], 'Stellantis': ['Stellantis'], 'Tesla': ['Tesla'], 'Verizon Communications': ['Verizon'], 'AT&T': ['AT&T']}
    for k, l in extra.items():
        if re.sub(SUF, '', name).strip() == k or name == k: a |= set(l)
    bad = {'Target', 'Progressive', 'Visa', 'Ball', 'Crown', 'Discover', 'Global', 'Universal', 'Graybar', 'Sonic', 'Alliance', 'Performance', 'Principal', 'Dominion', 'Southern', 'Entergy', 'Republic', 'Ally', 'Fox', 'Chewy', 'Gap', 'Altria', 'Hess', 'Unum', 'Loews', 'Avantor'}
    return [x for x in a if x not in bad and len(x) >= 3]
names = {it['order']: aliases(it['name']) for it in items}
pat = {o: re.compile(r'(?<![A-Za-z])(' + '|'.join(re.escape(x) for x in sorted(l, key=len, reverse=True)) + r')(?![A-Za-z])') for o, l in names.items() if l}
lock = threading.Lock(); last = [0]
def get(url):
    for a in range(4):
        with lock:
            w = last[0] + 0.13 - time.time()
            if w > 0: time.sleep(w)
            last[0] = time.time()
        r = requests.get(url, headers=UA, timeout=120)
        if r.status_code == 200: return r.text
        time.sleep(3)
def text(h):
    h = re.sub(r'(?is)<(script|style).*?</\1>', ' ', h)
    h = re.sub(r'(?s)<ix:header>.*?</ix:header>', ' ', h)
    h = re.sub(r'<[^>]+>', ' ', h); h = H.unescape(h)
    return re.sub(r'\s+', ' ', h)
CUST = re.compile(r'\b(customers?|clients?)\b', re.I)
PCT = re.compile(r'\d+(\.\d+)?\s?(%|percent)')
REVW = re.compile(r'\b(revenues?|sales|net sales)\b', re.I)
def one(it):
    o = it['order']; fn = f'data/10k/{o:03d}.json'
    if os.path.exists(fn): return
    s = json.load(open(f'data/sec/{o:03d}.json'))
    k = s.get('latest10k')
    if not k: json.dump({'scanned': False}, open(fn, 'w')); return
    url = f"https://www.sec.gov/Archives/edgar/data/{s['cik']}/{k['accession'].replace('-', '')}/{k['doc']}"
    h = get(url)
    if not h: json.dump({'scanned': False, 'url': url}, open(fn, 'w')); return
    t = text(h)
    sents = re.split(r'(?<=[.;])\s+(?=[A-Z])', t)
    hits = []
    for sn in sents:
        if len(sn) > 900 or not CUST.search(sn) or not PCT.search(sn) or not REVW.search(sn): continue
        for o2, p in pat.items():
            if o2 == o: continue
            m = p.search(sn)
            if m: hits.append({'to': o2, 'alias': m.group(1), 'snippet': sn[:600]})
    json.dump({'scanned': True, 'url': url, 'date': k['date'], 'hits': hits}, open(fn, 'w'))
with ThreadPoolExecutor(4) as ex:
    for _ in ex.map(one, items): pass
print('done')
