"""SEC EDGAR: map tickers->CIK, fetch submissions + companyfacts, extract annual financial history."""
import json, os, time, requests, threading
from concurrent.futures import ThreadPoolExecutor
UA = {'User-Agent': 'F500Explorer research admin@example.com', 'Accept-Encoding': 'gzip'}
os.makedirs('data/sec', exist_ok=True)
items = json.load(open('data/fortune_list_2026.json'))
tick = {v['ticker'].upper(): v for v in json.load(open('data/sec_tickers.json')).values()}
lock = threading.Lock(); last = [0]
def throttle():
    with lock:
        w = last[0] + 0.13 - time.time()
        if w > 0: time.sleep(w)
        last[0] = time.time()
def get(url):
    for a in range(4):
        throttle()
        r = requests.get(url, headers=UA, timeout=60)
        if r.status_code == 200: return r.json()
        if r.status_code == 404: return None
        time.sleep(3)
REV = ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet',
       'RevenueFromContractWithCustomerIncludingAssessedTax', 'RevenuesNetOfInterestExpense', 'SalesRevenueGoodsNet']
NI = ['NetIncomeLoss', 'ProfitLoss', 'NetIncomeLossAvailableToCommonStockholdersBasic']
def annual(facts, names):
    best = {}
    for n in names:
        u = facts.get('us-gaap', {}).get(n, {}).get('units', {}).get('USD', [])
        for x in u:
            if x.get('form') in ('10-K', '10-K/A') and x.get('fp') == 'FY' and 'start' in x:
                d = (time.mktime(time.strptime(x['end'], '%Y-%m-%d')) - time.mktime(time.strptime(x['start'], '%Y-%m-%d'))) / 86400
                if 340 < d < 380:
                    y = int(x['end'][:4]) if x['end'][5:7] > '06' else int(x['end'][:4]) - 1  # fiscal-year label
                    y = int(x['end'][:4])
                    if y not in best or x['val'] > best[y][0] and n == best[y][1]: best.setdefault(y, (x['val'], n))
                    if best[y][1] == n and x['val'] > best[y][0]: best[y] = (x['val'], n)
        # prefer first concept list order but fill missing years from later ones
    return {y: v[0] for y, v in sorted(best.items())[-8:]}
def one(it):
    fn = f"data/sec/{it['order']:03d}.json"
    if os.path.exists(fn): return
    pg = json.load(open(f"data/fortune_pages/{it['order']:03d}.json"))
    t = (pg['companyInfo'].get('Ticker') or '').upper().replace('.', '-').strip()
    out = {'ticker': t}
    m = tick.get(t) or tick.get(t.replace('-', ''))
    if not m: json.dump(out, open(fn, 'w')); return
    cik = m['cik_str']; out['cik'] = cik; out['sec_title'] = m['title']
    s = get(f'https://data.sec.gov/submissions/CIK{cik:010d}.json') or {}
    out.update({k: s.get(k) for k in ['sic', 'sicDescription', 'stateOfIncorporation', 'fiscalYearEnd', 'formerNames', 'website', 'exchanges']})
    out['business_address'] = (s.get('addresses') or {}).get('business')
    r = s.get('filings', {}).get('recent', {})
    for i, f in enumerate(r.get('form', [])):
        if f == '10-K':
            out['latest10k'] = {'accession': r['accessionNumber'][i], 'doc': r['primaryDocument'][i], 'date': r['filingDate'][i]}; break
    f = get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json')
    if f:
        fa = f.get('facts', {})
        out['rev_hist'] = annual(fa, REV); out['ni_hist'] = annual(fa, NI)
        a = fa.get('us-gaap', {}).get('Assets', {}).get('units', {}).get('USD', [])
        out['assets_hist'] = {int(x['end'][:4]): x['val'] for x in a if x.get('form') == '10-K' and x.get('fp') == 'FY'}
        out['assets_hist'] = dict(sorted(out['assets_hist'].items())[-8:])
        e = fa.get('dei', {}).get('EntityCommonStockSharesOutstanding', {}).get('units', {}).get('shares', [])
        if e: out['shares_out'] = sorted(e, key=lambda x: x['end'])[-1]['val']
    json.dump(out, open(fn, 'w'))
with ThreadPoolExecutor(4) as ex:
    for _ in ex.map(one, items): pass
print('done', len(os.listdir('data/sec')))
