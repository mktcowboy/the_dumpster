"""Fetch Fortune 500 2026 list + each company profile page from fortune.com (public __NEXT_DATA__)."""
import re, json, os, time, requests
from concurrent.futures import ThreadPoolExecutor
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
os.makedirs('data/fortune_pages', exist_ok=True)
def nd(html):
    return json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S).group(1))
if not os.path.exists('data/next2026.json'):
    h = requests.get('https://fortune.com/ranking/fortune500/2026/', headers={'User-Agent': UA}).text
    json.dump(nd(h), open('data/next2026.json', 'w'))
items = json.load(open('data/next2026.json'))['props']['pageProps']['franchiseSearch']['items']
items = sorted([i for i in items if i['rank'] <= 500], key=lambda i: i['rank'])
json.dump(items, open('data/fortune_list_2026.json', 'w'), indent=1)
def get(it):
    fn = f"data/fortune_pages/{it['order']:03d}.json"
    if os.path.exists(fn): return
    url = 'https://fortune.com' + it['slug']
    for a in range(3):
        try:
            r = requests.get(url, headers={'User-Agent': UA}, timeout=30)
            c = nd(r.text)['props']['pageProps']['company']
            keep = {k: c.get(k) for k in ['companyInfo', 'description', 'dataTables', 'permalink', 'title']}
            keep['rankings'] = [{k: l.get(k) for k in ['slug', 'title', 'year', 'rank', 'itemDescription']}
                                for l in (c.get('yearFilteredRankings') or []) + (c.get('companyRankingLists') or [])]
            json.dump(keep, open(fn, 'w')); return
        except Exception as e:
            print('retry', it['name'], e); time.sleep(2)
with ThreadPoolExecutor(6) as ex: list(ex.map(get, items))
print('done', len(os.listdir('data/fortune_pages')))
