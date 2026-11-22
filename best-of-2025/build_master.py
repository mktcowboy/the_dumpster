#!/usr/bin/env python3
"""Build the master list from items.json (written by extract_lists.py).

Writes the markdown (default best_of_2025_master.md; this repo uses MASTER.md)
and master_rank.json. The markdown groups every list by topic and appends titles
that appear on two or more lists. master_rank.json is every extracted title,
merged within its topic, sorted so a title on more lists ranks higher. Titles
that appear on only one list are included. No dates are written.

Usage: python3 build_master.py [MASTER.md]
"""
import json,re,unicodedata,collections,sys,hashlib
OUT=sys.argv[1] if len(sys.argv)>1 else 'best_of_2025_master.md'
RANK='master_rank.json'
# Same fingerprints as scripts/check_privacy.py. Drop a whole token only.
BLOCKED={'8802b69f05738c4ed94b86a0fa4cee921db823e62d47a70d9034a1abcaa3bb9b','9fbb8412cdc93b8c5919da05fe115ab04af1b15acc0e14c91d025b249a88f268','614e8e1f4c3876db53f8d40288168711fa77930b5ccbf0b9626c9b01aa42d5f2','e016ef65bf37def457ab09faa9d48effdf0186a7dab671318b6d39de1a4f551c'}
def scrub(s):
    def repl(m):
        return '\0' if hashlib.sha256(m.group(0).lower().encode()).hexdigest() in BLOCKED else m.group(0)
    s=re.sub(r'[A-Za-z0-9]+',repl,s)
    # Drop a removed token and the space on one side. Keep one space only when it sat between words.
    s=re.sub(r'[ \t]*\0[ \t]*',lambda m:' ' if len(m.group(0).strip('\0'))>=2 else '',s)
    return s
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
def topic_counts(lists):
    """Map a normalized title to {list name: (display title, creator)}.

    The same rules as the overlap section: ignore case, punctuation, a leading
    The/A, parenthetical notes, and season or part labels. A bare title absorbs
    the subtitled form when both were extracted."""
    counts=collections.defaultdict(dict)
    for x in lists:
        for a,b in x['items']:
            k=norm(a)
            if len(k)<2: continue
            counts[k].setdefault(x['list'],(a,b))
    for x in lists:
        for a,b in x['items']:
            bk=base(a); k=norm(a)
            if bk and bk!=k and bk in counts and k in counts:
                for ln,v in counts.pop(k).items(): counts[bk].setdefault(ln,v)
    return counts
def pick_title(v):
    return collections.Counter(a for a,b in v.values()).most_common(1)[0][0]
def pick_creator(v):
    creators=sorted({b for a,b in v.values() if b and len(b)<60 and not b.startswith(('Game Awards','pick for','nominee','destination'))})
    return creators[0] if len(creators)==1 else ''
# Section labels that some lists store in the creator field. Not a person, artist, or place.
LABELS={'fiction','nonfiction','poetry','science','ideas','music','politics','history','biography & memoir','memoir','novel',"sport & children's"}
def tidy_creator(b):
    """Drop a trailing publisher and a leading 'dirs.' note. Keep the name."""
    s=b.strip()
    if len(s)>2 and s.startswith('(') and s.endswith(')') and s.count('(')==1:
        s=s[1:-1].strip()
    else:
        cut=re.sub(r'\s*\([^)]*\)\s*$','',s).strip()
        if cut: s=cut
    s=s.lstrip('(').rstrip(')').strip()
    s=re.sub(r'^(?:dirs?|dir)\.\s*','',s,flags=re.I).strip()
    return s
def display_creator(v):
    """Creator for the ranked table: the name when the lists agree, blank when they don't.
    A trailing publisher in parentheses is dropped. Genre labels are ignored."""
    names=[]
    for a,b in v.values():
        if not b: continue
        b=b.strip()
        if not b or len(b)>=60 or b.startswith(('Game Awards','pick for','nominee','destination')): continue
        if 'section labels' in b.lower(): continue
        stem=tidy_creator(b)
        if not stem or stem.lower() in LABELS: continue
        names.append(stem)
    if not names: return ''
    top=collections.Counter(names).most_common(2)
    if len(top)>1 and top[0][1]==top[1][1]: return ''
    return top[0][0]
def ranked_rows(counts):
    rows=[]
    for v in counts.values():
        if not v: continue
        rows.append((len(v), list(v.values())[0][0].lower(), pick_title(v), pick_creator(v), display_creator(v), list(v)))
    rows.sort(key=lambda r:(-r[0], r[1]))
    return rows
topics=collections.OrderedDict()
for x in d: topics.setdefault(x['topic'],[]).append(x)
L=['# Best of 2025: Master List of Items','',
'Every list in the Best of 2025 directory, grouped by topic, with the items each list names. Ranked lists keep their order (numbered); unranked lists are bulleted. Where a list could not be read, its heading stays with the reason. An overlap section at the end shows items that appear on two or more lists within the same topic.','']
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
ranked=[]
meta={x['list']:(x.get('outlet') or '', x.get('url') or '') for x in d}
catalog=[]
index={}
def ref(name):
    if name not in index:
        outlet,url=meta.get(name,('',''))
        index[name]=len(catalog)
        catalog.append({'name':name,'outlet':outlet,'url':url})
    return index[name]
for t,lists in topics.items():
    counts=topic_counts(lists)
    rows=ranked_rows(counts)
    if rows:
        ranked.append({'topic':t,'lists':len(lists),'items':[
            {'title':title,'creator':shown,'count':n,'sources':[ref(name) for name in sources]}
            for n,_sort,title,_md_creator,shown,sources in rows]})
    ov=[(title,creator,n,sources) for n,_sort,title,creator,_shown,sources in rows if n>=2]
    if not ov: continue
    L+=[f'### {t}','']
    for title,creator,n,sources in ov:
        cr=f' ({md_esc(creator)})' if creator else ''
        L.append(f'- **{md_esc(title)}**{cr} — {n} lists: '+'; '.join(md_esc(name) for name in sources))
        summary.append((n,t,title,cr))
    L.append('')
open(OUT,'w').write(scrub('\n'.join(L)+'\n'))
open('overlap_top.json','w').write(scrub(json.dumps(sorted(summary,reverse=True)[:40],ensure_ascii=False,indent=0)))
open(RANK,'w').write(scrub(json.dumps({'lists':catalog,'topics':ranked},ensure_ascii=False,indent=1))+'\n')
n_titles=sum(len(t['items']) for t in ranked)
print(OUT,len(L),'lines;',n_ok,'extracted',n_bad,'not retrievable;',RANK,n_titles,'titles')
