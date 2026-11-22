#!/usr/bin/env python3
"""Extract ranked/picked items from every list URL in lists.csv.

Usage: python3 extract_lists.py [lists.csv] [cache_dir]
Writes items.json. Pages are fetched with curl (browser UA) into cache_dir and
reused. Site-specific parsers are in custom.py; a generic heading/numbered-line
fallback covers the rest. Pages that block automated fetches can be filled from
manual.json ({list name: {"items": [[title, creator], ...], "how": "..."}} or
{"note": "..."}), which holds items read through a separate page reader.
No item is ever synthesized: an empty result is reported as not retrievable."""
import csv,json,os,re,sys,subprocess,hashlib
from bs4 import BeautifulSoup
import trafilatura
import custom
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'
SRC=sys.argv[1] if len(sys.argv)>1 else 'lists.csv'
CACHE=sys.argv[2] if len(sys.argv)>2 else 'cache'
def fetch(url):
    p=os.path.join(CACHE,hashlib.md5(url.encode()).hexdigest()[:12]+'.html')
    if not (os.path.exists(p) and os.path.getsize(p)>3000):
        subprocess.run(['curl','-s','-L','--compressed','--max-time','30','-A',UA,'-H','Accept-Language: en-US,en','-o',p,url])
    return open(p,encoding='utf8',errors='ignore').read() if os.path.exists(p) else ''
BLOCK=re.compile(r'(Just a moment|Security Verification|captcha|Access Denied|Request Rejected)',re.I)
def expand(url, html):
    """Kirkus best-of book lists continue on ?page=2, ?page=3, and so on. Pull every page that adds books."""
    if not html or 'kirkusreviews.com/best-of/' not in url or '/books' not in url or 'page=' in url:
        return html
    base=url.split('?')[0]
    parts=[html]
    seen=set(re.findall(r'href="(/book-reviews/[^"]+)" class="card-text"', html))
    for n in range(2, 16):
        if f'page={n}' not in parts[-1]:
            break
        nxt=fetch(base+f'?page={n}')
        found=set(re.findall(r'href="(/book-reviews/[^"]+)" class="card-text"', nxt or ''))
        if not found-seen:
            break
        seen |= found
        parts.append(nxt)
    return '\n'.join(parts)
def main():
    os.makedirs(CACHE,exist_ok=True)
    rows=list(csv.DictReader(open(SRC)))
    manual=json.load(open('manual.json')) if os.path.exists('manual.json') else {}
    res=[]
    for x in rows:
        name=x['list']; m=manual.get(name,{})
        items=[];how='';note=m.get('note','')
        if m.get('items'):
            items=[tuple(i) for i in m['items']];how=m.get('how','page reader')
        elif not note:
            h=expand(x['url'], fetch(x['url']))
            if len(h)<3000 or (BLOCK.search(h[:20000]) and len(h)<150000):
                note='items not retrievable: site blocks automated fetches'
            else:
                s=BeautifulSoup(h,'lxml')
                md=trafilatura.extract(h,output_format='markdown',include_formatting=True,include_links=False,favor_recall=True) or ''
                md='\n'.join(l.strip() for l in md.replace('\xa0',' ').splitlines() if l.strip())
                r=custom.P(s,h,md,name)
                if r is None: r,how=custom.generic(s,md)
                else: how='site parser'
                items=custom.uniq(custom.post(name,[(custom.C(a),custom.C(b)) for a,b in r]))
                if not items: note='items not retrievable: list is rendered by JavaScript or not present in the page HTML'
        if m.get('partial'): note=m['partial']
        res.append({'list':name,'topic':x['topic'],'outlet':x['outlet'],'url':x['url'],'items':items,'how':how,'note':note})
    json.dump(res,open('items.json','w'),indent=1,ensure_ascii=False)
    for i,r in enumerate(res):
        print(i,r['how'],len(r['items']),'|',r['list'][:45],'|',' ;; '.join(f'{a}/{b}' if b else a for a,b in r['items'][:4])[:200],'|',r['note'][:50])
if __name__=='__main__': main()
