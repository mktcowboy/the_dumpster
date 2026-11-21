#!/usr/bin/env python3
"""Build best_of_2026_master.md from items.json (written by extract_lists.py).
Groups lists by topic, lists every extracted item, and appends a cross-list
overlap section per topic. No dates are written."""
import json,re,unicodedata,collections,sys
OUT=sys.argv[1] if len(sys.argv)>1 else 'best_of_2026_master.md'
d=json.load(open('items.json'))
ROMAN={'ii':'2','iii':'3','iv':'4','v':'5','vi':'6','vii':'7','viii':'8','ix':'9','x':'10'}
WORDN={'one':'1','two':'2','three':'3','four':'4','five':'5','six':'6'}
def norm(t):
    t=unicodedata.normalize('NFKD',t).encode('ascii','ignore').decode().lower()
    t=re.sub(r'\([^)]*\)|\[[^\]]*\]','',t)
    t=re.sub(r'[:,]?\s*(a novel|a memoir|a cookbook|stories)$','',t.strip())
    t=re.sub(r"[:\s,\-–]*(season|series|part)\s+(\w+)\b",lambda m:' s'+WORDN.get(m.group(2),m.group(2)),t)
    t=re.sub(r'[:\s]*limited series$','',t)
    w=re.sub(r"['’]",'',t); w=re.sub(r'&',' and ',w); w=re.split(r'\W+',w)
    w=[ROMAN.get(x,x) if i==len(w)-1 or (i>0 and w[i-1] in('vol','volume')) else x for i,x in enumerate(w) if x]
    if w and w[0] in('the','a','an') and len(w)>1: w=w[1:]
    return ''.join(w)
def base(t): return norm(t.split(':')[0]) if ':' in t else None
def md_esc(t): return re.sub(r'([\\`*_\[\]<>|#])',r'\\\1',t)
topics=collections.OrderedDict()
for x in d: topics.setdefault(x['topic'],[]).append(x)
L=['# Best of 2026: Master List of Items','',
'Every list in the Best of 2026 directory, grouped by topic, with the items each list names. Ranked lists keep their order (numbered); unranked lists are bulleted. Where a list could not be read, its heading stays with the reason. An overlap section at the end shows items that appear on two or more lists within the same topic.','']
n_ok=sum(1 for x in d if x['items']); n_bad=len(d)-n_ok
L+=[f'Lists: {len(d)} total, {n_ok} with items extracted, {n_bad} not retrievable.','','## Contents','']
for t in topics: L.append(f'- [{t}](#{re.sub(r"[^a-z0-9 -]","",t.lower()).replace(" ","-")}) ({len(topics[t])} list{"s" if len(topics[t])!=1 else ""})')
L.append('- [Overlap across lists](#overlap-across-lists)'); L.append('')
RANKED=re.compile(r'(top \d+|\d+ best|best .*\(top|ranked|aggregate|rough trade|uncut|mojo: the 75|world.s 50|north america.s 50|50 best cities|top 500|paste|metacritic|time out: best movies|time out: 39|empire|anime news|amazon editors|rolling stone: best albums|iheart)',re.I)
for t,lists in topics.items():
    L+=[f'## {t}','']
    for x in lists:
        L+=[f'### {md_esc(x["list"])}',f'{md_esc(x["outlet"])} · [link]({x["url"]})','']
        if not x['items']:
            L+=[f'*{x["note"] or "items not retrievable"}*','']; continue
        if x['note']: L+=[f'*Note: {x["note"]}*','']
        ranked=bool(RANKED.search(x['list'])) and not x['list'].startswith(('Kirkus','Goodreads'))
        for i,(a,b) in enumerate(x['items'],1):
            s=md_esc(a)+(f' — {md_esc(b)}' if b else '')
            L.append(f'{i}. {s}' if ranked else f'- {s}')
        L.append('')
L+=['## Overlap across lists','','Items on two or more lists within the same topic, most lists first. Titles are matched ignoring case, punctuation, leading "The/A", parenthetical notes and season/part labels; a title without a subtitle is merged with the subtitled version of the same title. Matching is by title only, so check the creator when a common title appears.','']
summary=[]
for t,lists in topics.items():
    full={};counts=collections.defaultdict(dict)
    for x in lists:
        for a,b in x['items']:
            k=norm(a)
            if len(k)<2: continue
            counts[k].setdefault(x['list'],(a,b))
    keys=set(counts)
    for k in list(counts):
        for x in lists: pass
    # merge subtitled titles into their base when the base exists as its own title
    for x in lists:
        for a,b in x['items']:
            bk=base(a); k=norm(a)
            if bk and bk!=k and bk in counts and k in counts:
                for ln,v in counts.pop(k).items(): counts[bk].setdefault(ln,v)
    ov=[(k,v) for k,v in counts.items() if len(v)>=2]
    ov.sort(key=lambda kv:(-len(kv[1]),list(kv[1].values())[0][0].lower()))
    if not ov: continue
    L+=[f'### {t}','']
    for k,v in ov:
        names=collections.Counter(a for a,b in v.values()).most_common(1)[0][0]
        creators=sorted({b for a,b in v.values() if b and len(b)<60 and not b.startswith(('Game Awards','pick for','nominee','destination'))})
        cr=f' ({md_esc(creators[0])})' if len(creators)==1 else ''
        L.append(f'- **{md_esc(names)}**{cr} — {len(v)} lists: '+'; '.join(md_esc(n) for n in v))
        summary.append((len(v),t,names,cr))
    L.append('')
open(OUT,'w').write('\n'.join(L)+'\n')
json.dump(sorted(summary,reverse=True)[:40],open('overlap_top.json','w'),ensure_ascii=False,indent=0)
print(OUT,len(L),'lines;',n_ok,'extracted',n_bad,'not retrievable')
