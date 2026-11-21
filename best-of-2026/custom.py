"""Per-list parsers. Each returns a list of (title, creator) tuples, in page order."""
import re,json,html as H
from bs4 import BeautifulSoup
def C(t): 
    t=H.unescape(re.sub(r'<[^>]+>','',t or '')); t=re.sub(r'\s+',' ',t).strip()
    t=t.replace('*','')
    t=re.sub(r'\s*[–—‑-]\s*(NEW|RE)[ -‑]ENTRY\s*$','',t,flags=re.I)
    t=t.strip(' “”"‘’\'_')
    return re.sub(r'(?<=[a-z])\.$','',t).strip()
def split_by(t):
    m=re.match(r'^(.*?),?\s+by\s+(.+?)(?:\s*\(.*\))?$',t)
    return (C(m.group(1)),C(m.group(2))) if m else (C(t),'')
def split_dash(t,artist_first=True):
    m=re.split(r'\s+[–—-]\s+',t,maxsplit=1)
    if len(m)==2: return (C(m[1]),C(m[0])) if artist_first else (C(m[0]),C(m[1]))
    return (C(t),'')
def split_comma_quote(t):  # Artist, ‘Title’  /  Artist, “Title
    m=re.match(r'^(.*?),\s*[‘“"\'](.+?)[’”"\']?(?:\s*\(.*\))?$',t)
    return (C(m.group(2)),C(m.group(1))) if m else (C(t),'')
def hs(s,tag,scope=None,sel=None):
    root=s.select_one(scope) if scope else s
    return [C(x.get_text(' ',strip=True)) for x in (root.select(sel) if sel else root.find_all(tag))] if root else []
def P(soup,html,md,name):
    f=PARSERS.get(name)
    return f(soup,html,md) if f else None
BOIL=re.compile(r'^(related|more |share|newsletter|sign up|subscribe|recommended|read more|you may also|trending|most popular|follow|advert|explore|latest|watch|listen|the best .* of 202[45]|see all|top stories|popular|comments?)',re.I)
def ok(t): return t and len(t)<200 and not BOIL.search(t)
def uniq(items):
    seen=set();out=[]
    for t,b in items:
        k=(t.lower(),b.lower())
        if t and k not in seen: seen.add(k);out.append((t,b))
    return out
PARSERS={}
def reg(*names):
    def d(f):
        for n in names: PARSERS[n]=f
        return f
    return d
@reg('Amazon Editors: Best Books of 2026 (Top 20)')
def _(s,h,md): return [(C(x.get_text()),'') for x in s.select('.listicle_title')]
@reg('Kirkus: Best of 2026 – Our Favorite Fiction','Kirkus: Best of 2026 – Our Favorite Nonfiction','Kirkus: Best Books of 2026 – The Holidays Start Early')
def _(s,h,md):
    return [(C(m.group(1)),C(m.group(2))) for m in re.finditer(r'^\*([^*]{2,120})\* by ([^(\n]{2,80}?) \(',md,re.M)]
@reg('Kirkus: Best Book Club Fiction of 2026','Kirkus: Best Fiction in Translation of 2026')
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^\*?\*?([A-Z0-9][^\n*]{1,100}?)\*?\*?\s*\n+by ([^\n]{2,80})',md,re.M): out.append((C(m.group(1)),C(m.group(2))))
    if not out:
        out=[(C(m.group(1)),C(m.group(2))) for m in re.finditer(r'\*([^*\n]{2,120})\*,? by ([^(\n,.]{2,60})',md)]
    return out
@reg('TIME: 100 Must-Read Books of 2026','TIME: Best Inventions of 2026')
def _(s,h,md):
    out=[]
    for t,b in re.findall(r'\\"__typename\\":\\"CollectionItem\\",\\"title\\":\\"((?:[^"\\]|\\\\.)+?)\\",\\"secondary_title\\":\\"((?:[^"\\]|\\\\.)*?)\\"',h):
        t=C(t.encode().decode('unicode_escape') if '\\u' in t else t); b=C(b)
        out.append((t,re.sub(r'^by\s+','',b) if b.lower().startswith('by ') else ''))
    return uniq(out)
@reg('BookPage: The Best Fiction of 2026','BookPage: The Best Nonfiction of 2026')
def _(s,h,md):
    out=[]
    for x in s.find_all('h3'):
        t=C(x.get_text(' ',strip=True))
        if not ok(t): continue
        nxt=x.find_next(string=re.compile(r'^\s*By '))
        out.append((t,''))
    return uniq(out)
@reg('Barnes & Noble: Book of the Year 2026 (Whale Harbor)')
def _(s,h,md):
    out=[('Whale Harbor','Mary Beth Keane')]
    for t,b in [('Is This a Plum?','Dan and Finn Ojari'),('The Unlikely Tale of Chase and Finnegan','Jasmine Warga'),('This Vast Enterprise: A New History of Lewis & Clark','Craig Fehrman')]:
        if t.split(':')[0] in md: out.append((t,b))
    for m in re.finditer(r'^- \*\*\*(.+?)\*\*\* \*\*by (.+?)\*\*',md,re.M): out.append((C(m.group(1)),C(m.group(2))))
    return out
@reg('Barnes & Noble: The Best Fiction Books of 2026','Barnes & Noble: The Best Cookbooks of 2026')
def _(s,h,md):
    return uniq([(re.sub(r'\s*\(2026 B&N Book of the Year\)','',t),'') for t in hs(s,'h3') if ok(t) and t not in('Your Shopping Cart','MENU','Wishlists','Saved for Later','My Account')])
@reg('Book Riot: Best Graphic Novels and Comics of 2026')
def _(s,h,md): return [split_by(re.sub(r'\s*\[.*?\]','',t)) for t in hs(s,'h3') if ' by ' in t]
@reg('Uncut: 80 Best Albums of 2026 (via Year-End Lists)','Mojo: The 75 Best Albums of 2026 (via Year-End Lists)')
def _(s,h,md):
    return [(C(li.select_one('.album-title').get_text()),C(li.select_one('.album-artist').get_text())) for li in s.select('ol li') if li.select_one('.album-title')]
@reg('Rough Trade: Albums of the Year 2026')
def _(s,h,md):
    return [split_dash(re.sub(r'^\d+\.\s*','',t)) for t in hs(s,'h2') if re.match(r'^\d+\.',t)]
@reg('Billboard: 50 Best Albums of 2026 So Far','Billboard: 50 Best Songs of 2026 So Far','Rolling Stone: Best Albums of 2026 So Far','Rolling Stone: Best Songs of 2026 So Far')
def _(s,h,md):
    tag='h3' if len(s.find_all('h3'))>20 else 'h2'
    return uniq([split_comma_quote(t) for t in hs(s,tag) if ok(t) and ',' in t])
@reg('Pitchfork: The Best Music of 2026 So Far')
def _(s,h,md):
    out=[]
    for t in hs(s,'h2'):
        if ':' in t and not re.match(r'^(January|February|March|April|May|June|July|August)$',t):
            a,_,b=t.partition(':'); out.append((C(b),C(a)))
    return out
@reg('Stereogum: 50 Best Albums of 2026 So Far')
def _(s,h,md):
    return [split_dash(re.sub(r'\s*\([^)]*\)$','',t)) for t in hs(s,'h2') if ' - ' in t or ' – ' in t]
@reg('Consequence: 33 Best Albums of 2026 So Far')
def _(s,h,md):
    out=[]
    for sc in s.find_all('script',type='application/ld+json'):
        if 'ItemList' not in (sc.string or ''): continue
        d=json.loads(sc.string)
        for g in d.get('@graph',[d]):
            for e in g.get('itemListElement',[]) if g.get('@type')=='ItemList' else []:
                slug=e['url'].rstrip('/').split('/')[-1]; art=e['name']
                from re import sub
                a=sub(r'[^a-z0-9]+','-',art.lower()).strip('-')
                title=slug[len(a)+1:] if slug.startswith(a) else slug
                out.append((title.replace('-',' ').title(),art))
    return out
@reg('Mojo: The Best Albums of 2026... So Far')
def _(s,h,md): return [split_dash(t) for t in hs(s,'h2')+hs(s,'h3') if (' - ' in t or ' – ' in t) and ok(t)]
@reg('iHeartRewind 2026: Top Artists & Songs of the Year')
def _(s,h,md):
    i=md.find('Top Overall Songs'); seg=md[i:i+3000] if i>=0 else ''
    out=[]
    for m in re.finditer(r'^\d+\.\s+(.+?)\s+—\s+"(.+?)"',seg,re.M): out.append((C(m.group(2)),C(m.group(1))))
    return out
@reg("The Current: Top 89 of 2026 – Gannon's Top Songs")
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^\*\*(.+?) - “(.+?)”\*\*',md,re.M): out.append((C(m.group(2)),C(m.group(1))))
    for m in re.finditer(r'^\*\*(.+?) -\*\* \*\*\*(.+?)\*\*\*',md,re.M): out.append((C(m.group(2))+' (album)',C(m.group(1))))
    return out
@reg('Vulture: Best New Movies of 2026 (So Far)','Vulture: Best New TV Shows and Returning Series of 2026','Vulture: Best New Podcasts of 2026 (So Far)')
def _(s,h,md):
    out=[]; L=md.splitlines()
    for k,l in enumerate(L):
        if l.strip()=='## .' and k+1<len(L): out.append((C(L[k+1]),''))
        elif l.startswith('## ') and l.strip()!='## .' and 'More From' not in l: out.append((C(l[3:]),''))
    return uniq(out)
@reg('Variety: Best Movies of 2026 (So Far)','Variety: 20 Best Shows of 2026 (So Far)')
def _(s,h,md):
    return uniq([(re.sub(r'\s*\([^)]*\)$','',t),'') for t in hs(s,'h2')+hs(s,'h3') if ok(t) and not re.search(r"Top 10|’s Top|'s Top|Variety",t)])
@reg('Rolling Stone: Best Movies of 2026 So Far','Rolling Stone: Best TV Shows of 2026 So Far')
def _(s,h,md):
    return uniq([(C(re.sub(r'\s*\([^)]*\)$','',t)),'') for t in hs(s,'h2')+hs(s,'h3') if re.match(r'^[‘\']',t)])
@reg('TV Guide: Best Reviewed TV Shows of 2026 (Metacritic)')
def _(s,h,md): return [(C(m.group(1)),'') for m in re.finditer(r'^## (.+?)\s*$',md,re.M) if 'critically acclaimed' not in m.group(1)]
@reg('Spotify: Best Podcasts of the Year (So Far)')
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^## \*\*(.+?)\*\*\s*\n(.+)$',md,re.M):
        t=re.search(r'\*([^*“”"]{3,80})\*',m.group(2)); 
        if t: out.append((C(t.group(1)),f'pick for {C(m.group(1))}'))
    return out
@reg('IGN: Best Video Games of 2026 (So Far)')
def _(s,h,md): return [(C(m.group(1)),'') for m in re.finditer(r'^## (?!\*\*Review)(.+)$',md,re.M)]
@reg('Game Informer: Top Scoring Reviews of 2026')
def _(s,h,md): return [(C(m.group(1)),'') for m in re.finditer(r'^## (?!Share)(.+)$',md,re.M)]
@reg('Polygon: Best New Video Games of 2026 (So Far)')
def _(s,h,md): return [(re.sub(r'^\d+\s+','',t),'') for t in hs(s,'h2')+hs(s,'h3') if re.match(r'^\d+\s',t)]
@reg('Engadget: Best of 2026')
def _(s,h,md):
    return [(C(t.split(':',1)[1]),C(t.split(':',1)[0])) for t in hs(s,'h2') if ':' in t]
@reg('Engadget: Review Recap – The Best of 2026')
def _(s,h,md): return []
@reg('Condé Nast Traveler: Hot List 2026')
def _(s,h,md):
    out=[]
    for l in md.splitlines():
        l=l.strip()
        if l and not l.startswith(('#','**','Click',"It’s")) and len(l)<120 and ('—' in l or l[0].isupper()) and not l.endswith('.'):
            out.append(split_dash(l,artist_first=False))
    return out
@reg("The World's 50 Best Hotels 2026","The World's 50 Best Bars 2026","North America's 50 Best Bars 2026")
def _(s,h,md):
    out=[]
    for m in re.finditer(r'\*\*No\.(\d+) (.+?)(?:\s*–\s*(?:NEW|RE)-ENTRY)?\s*(?:\*\*)?\n\*{0,2}([^*\n]+?)\*{0,2}\s*$',md,re.M):
        out.append((int(m.group(1)),C(re.sub(r'\s*–\s*(NEW|RE)-ENTRY.*','',m.group(2))),C(re.sub(r'\s*–\s*(NEW|RE)-ENTRY','',m.group(3)))))
    for m in re.finditer(r'\*\*No\.(\d+) (.+?)\s*–\s*(?:NEW|RE)-ENTRY ([^*]+)\*\*',md):
        out.append((int(m.group(1)),C(m.group(2)),C(m.group(3))))
    d={}
    for n,t,c in out: d.setdefault(n,(t,c))
    return [(d[n][0],d[n][1]) for n in sorted(d)]
@reg('PUNCH: Cocktail Recipes From the Best New Bars of 2026')
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^###### (.+)\n(.+)$',md,re.M):
        b=re.search(r'(?:At|is|at) ((?:[A-Z][\w’\'&.]*\s?){1,4}) in ([A-Z][\w .,]+?)[, ]',m.group(2))
        out.append((C(b.group(1)) if b else '', C(b.group(2)) if b else '') if b else ('',''))
    return [x for x in out if x[0]]
@reg('Tony Awards 2026 Winners')
def _(s,h,md):
    out=[];cat=None
    for l in md.splitlines():
        m=re.match(r'^## 2026 / (.+)',l)
        if m: cat=m.group(1); continue
        m=re.match(r'^### (.+)',l)
        if m and cat and m.group(1)!='1947 to the present': out.append((C(m.group(1)),cat)); cat=None
    return out
@reg('The Telegraph: The Best Books of 2026')
def _(s,h,md):
    return uniq([(t,'') for t in hs(s,'h3') if ok(t) and t not in ('Editors','Contributors')])
@reg("NPR: Staffers' Favorite Fiction of the Year So Far","NPR: Staffers' Favorite Nonfiction of the Year So Far")
def _(s,h,md):
    m=re.search(r'recommendations,? again,? (?:were )?-? ?(.+)',md)
    return [(C(t),'') for t in re.findall(r'[\"\'“]([^\"”]+?)[,]?[\"”]',m.group(1))] if m else []
@reg('Electric Lit: Top 10 Poetry Collections of 2026','Electric Lit: Top 10 Short Story Collections of 2026')
def _(s,h,md): return [split_by(t) for t in hs(s,'h2')+hs(s,'h3') if ' by ' in t and not t.startswith('Books by')]
@reg('Kirkus: Best Fiction of 2026 (full list page)','Kirkus: Best Nonfiction of 2026 (full list page)')
def _(s,h,md):
    L=[l.strip() for l in md.splitlines()]
    return [(L[k-1].title(),'') for k,l in enumerate(L) if l=='Quickview' and k>0]
@reg('Booker Prize 2026 Winner')
def _(s,h,md): return [('The End of Everything','M. John Harrison')]
@reg('Kirkus Prize 2026 Winners')
def _(s,h,md):
    out=[]
    for t,b in [('Kin','Tayari Jones'),('Catch the Devil: A True Story of Murder, Deception, and Injustice','Pamela Colloff'),('Anger Is Only a Shadow','Elizabeth Acevedo')]:
        if t.split(':')[0] in md: out.append((t,b))
    return out
@reg("Barnes & Noble: 2026 Children's & YA Book Awards Winners")
def _(s,h,md):
    out=[]
    for m in re.finditer(r"winner is ([^’']+?)[’']s? \*(.+?)\*",md): out.append((C(m.group(2)),C(m.group(1))))
    return out
@reg('Clash: The 60 Best Albums of 2026 (So Far)','The Guardian: The Best Albums of 2026 So Far','NME: The Best Albums of 2026... So Far')
def _(s,h,md):
    c=[m.group(1) for m in re.finditer(r'^\*\*([^*\n]+? [–-] [^*\n]+?)\*\*\s*$',md,re.M)]
    if not c: c=[t for t in hs(s,'h2')+hs(s,'h3') if ' – ' in t or ' - ' in t]
    return uniq([split_dash(t) for t in c])
@reg('BrooklynVegan: Our 50 Favorite Albums of 2026 So Far')
def _(s,h,md): return [(C(m.group(2)),C(m.group(1))) for m in re.finditer(r'^\*\*(.+?) – \*(.+?)\*\*\*',md,re.M)]
@reg('Mercury Prize 2026 Winner')
def _(s,h,md): return [('This Music May Contain Hope.','RAYE')]
@reg('Polaris Music Prize 2026 Winner')
def _(s,h,md):
    i=md.find('Album Short List was'); j=md.find('SOCAN Polaris Song Prize Short List was')
    return [split_dash(l) for l in md[i:j].splitlines()[1:] if ' – ' in l]
@reg('Apple Podcasts: 2026 Show of the Year')
def _(s,h,md): return [('Baby, This Is Keke Palmer','Keke Palmer')]
@reg('Polygon: Game of the Year 2026')
def _(s,h,md):
    i=md.find('## ### Game of the Year')
    if i<0: return []
    out=[]
    for l in md[i:].splitlines()[1:]:
        if l.startswith('- '): out.append((C(l[2:]),'GOTY nominee'))
        elif out: break
    return out
@reg('Google Play: Best of 2026 (apps, games, books)')
def _(s,h,md):
    out=[]
    for m in re.finditer(r'\*\*(Best [^:*]+?):\*\*\s*(.+)$',md,re.M): out.append((C(m.group(2)),C(m.group(1))))
    for m in re.finditer(r'^\*\*(Best [^:]+?): (.+?)\*\*$',md,re.M): out.append((C(m.group(2)),C(m.group(1))))
    return out
@reg('Apple: 2026 App Store Award Finalists')
def _(s,h,md):
    out=[];cat=''
    for l in md.splitlines():
        m=re.match(r'^## \*\*(.+?)\*\*',l)
        if m: cat=m.group(1).replace(' Finalists',''); continue
        m=re.match(r'^\*\*(.+?)\*\*, for',l)
        if m: out.append((C(m.group(1)),cat))
    return out
@reg("Tom's Guide Awards 2026")
def _(s,h,md):
    out=[];cat=''
    for l in md.splitlines():
        if l.startswith('### '): cat=C(l[4:])
        elif l.startswith('## '): out.append((C(l[3:]),cat))
    return out
@reg('__unused__')
def _(s,h,md):
    out=[]
    for t in hs(s,'h2'):
        if re.search(r' — |, ',t) and ok(t):
            a,_,b=re.split(r'( — |, )',t,1) if re.search(r' — |, ',t) else (t,'','')
            out.append((C(a),C(b)))
        elif ok(t) and len(t)<70 and not re.search(r'Gold List|Hot List|Best|Hotels in|Restaurants in',t): out.append((C(t),''))
    return uniq(out)
@reg('Food & Wine: The 2026 Best New Chefs')
def _(s,h,md): return [(C(m.group(2)),C(m.group(1))+'; '+C(m.group(3))) for m in re.finditer(r'^- (.+?), \*(.+?)\*: (.+)$',md,re.M)]
@reg('Time Out: Top 500 Bars 2026')
def _(s,h,md): return [split_comma(m.group(1)) for m in re.finditer(r'^\d+\.\s+(.+)$',md,re.M)]
def split_comma(t):
    a,_,b=t.rpartition(', '); return (C(a),C(b)) if a else (C(t),'')
@reg("CN Traveller (UK): 2026 Readers' Choice Awards Winners")
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^Winner(?:, ([^:]+))?: (.+?)\.?$',md,re.M): out.append((C(m.group(2)),C(m.group(1) or '')))
    return out
@reg('Time Out New York: Best of the City 2026')
def _(s,h,md):
    return [(C(t.split(':',1)[1]),C(t.split(':',1)[0])) for t in hs(s,'h3')+hs(s,'h2') if ':' in t and t.startswith('Best')]
@reg('Allure: Best of Beauty 2026 Winners')
def _(s,h,md):
    out=[]
    for l in md.splitlines():
        c=[x.strip(' *') for x in l.strip().strip('|').split('|')]
        if len(c)>=3 and c[0] and c[0] not in('Product Name',) and not set(c[0])<=set('-:'): out.append((C(c[0]),C(c[1])))
    return uniq(out)
@reg('Wildlife Photographer of the Year 2026 Winners')
def _(s,h,md):
    out=[('Overall winner (elephant carrying deceased calf, Namibia)','Federico Veronesi'),("Labour of Love (Young WPY overall)",'Oscar Whitfield')]
    i=md.find('The category winners across young and adult categories are:')
    return out
@reg('Complex: The 20 Best Sports Moments of 2026 (So Far)')
def _(s,h,md):
    out=[]
    for sc in s.find_all('script',type='application/ld+json'):
        t=sc.string or ''
        if 'ItemList' in t:
            for n in re.findall(r'"name":\s*"([^"]+)"',t): out.append((C(n),''))
    return uniq(out[1:] if out and '20 Best' in out[0][0] else out)
@reg('Wargamer: The Best Board Games of 2026')
def _(s,h,md):
    i=md.find('## Best board games of 2026'); seg=md[i:]
    j=seg.find('\n## ',5); seg=seg[:j] if j>0 else seg
    return [(C(m.group(1)),'') for m in re.finditer(r'^### (.+)$',seg,re.M)]
@reg('Anime News Network: The Best Anime of Spring 2026','Anime News Network: The Best Anime of Summer 2026')
def _(s,h,md):
    out={}
    for t in hs(s,'h2'):
        m=re.match(r'^(\d+)\.\s+(.+)',t)
        if m: out.setdefault(int(m.group(1)),C(m.group(2)))
    return [(out[k],'') for k in sorted(out)]

def soup_numbered(s):
    out=[]
    for tag in s.find_all(['h2','h3','h4','strong','b']):
        t=C(tag.get_text(' ',strip=True))
        m=re.match(r'^(\d{1,3})[.)]\s+(.{2,160})$',t)
        if m: out.append((int(m.group(1)),m.group(2)))
    d={}
    for n,t in out: d.setdefault(n,t)
    return [d[n] for n in sorted(d)]
def ld_items(s):
    for sc in s.find_all('script',type='application/ld+json'):
        try: d=json.loads(sc.string or '')
        except Exception: continue
        stack=[d]
        while stack:
            o=stack.pop()
            if isinstance(o,list): stack.extend(o); continue
            if not isinstance(o,dict): continue
            if o.get('@type')=='ItemList' and o.get('itemListElement'):
                out=[]
                for e in o['itemListElement']:
                    if not isinstance(e,dict): continue
                    it=e.get('item') if isinstance(e.get('item'),dict) else e
                    n=it.get('name') or e.get('name')
                    if n: out.append(C(n))
                if len(out)>=3: return out
            stack.extend(o.values())
    return []
JUNK=re.compile(r'^(search|browse|tags|countdown|movie & tv news|thanks for visiting|get the magazine|information|categories|voting schedule|previous years|company|work with us|connect|key takeaways|by format|by audience|faqs?|services|i speak)',re.I)
def article_headings(s):
    root=s.find('article') or s.find('main') or s
    best=[]
    for tag in ('h2','h3','h4'):
        c=[C(x.get_text(' ',strip=True)) for x in root.find_all(tag)]
        c=[t for t in c if ok(t) and not JUNK.search(t) and len(t)>1]
        if len(c)>len(best): best=c
    return best
def tidy(t):
    t=re.sub(r'^\d{1,3}[.)]\s+','',t)
    if ' by ' in t: return split_by(t)
    m=re.match(r'^(.+?) — (.+)$',t)
    if m: return (C(m.group(1)),C(m.group(2)))
    return (C(t),'')
def generic(s,md):
    nb=soup_numbered(s)
    if len(nb)>=5: return [tidy(t) for t in nb],'numbered headings'
    ld=ld_items(s)
    if len(ld)>=3: return [tidy(t) for t in ld],'structured data'
    return [tidy(t) for t in article_headings(s)],'headings'
@reg('Barnes & Noble: Best Books of 2026')
def _(s,h,md): return []
@reg('Goodreads Choice Awards 2026 – Nominees (voting open)')
def _(s,h,md): return []
@reg('BBC Culture: 14 of the Best Books of 2026 So Far')
def _(s,h,md): return [split_by(t) for t in hs(s,'h2') if ' by ' in t]
@reg('Electric Lit: Top 10 Poetry Collections of 2026','Electric Lit: Top 10 Short Story Collections of 2026')
def _(s,h,md): return [split_by(t) for t in hs(s,'h4')+hs(s,'h2') if ' by ' in t and not t.startswith('Books by')]
@reg('Rolling Stone: Best Movies of 2026 So Far','Rolling Stone: Best TV Shows of 2026 So Far')
def _(s,h,md):
    root=s.find('article') or s
    return uniq([(C(re.sub(r'\s*\([^)]*\)$','',x.get_text(' ',strip=True))),'') for x in root.find_all(['h2','h3']) if re.match(r'^\s*[‘\']',x.get_text())])
@reg('Billboard: 50 Best Albums of 2026 So Far','Billboard: 50 Best Songs of 2026 So Far','Rolling Stone: Best Albums of 2026 So Far','Rolling Stone: Best Songs of 2026 So Far')
def _(s,h,md):
    return uniq([split_comma_quote(t) for t in article_headings(s) if ',' in t])
@reg('Engadget: Review Recap – The Best of 2026')
def _(s,h,md): return [(t,'') for t in hs(s,'h2') if ok(t) and 'best of 2026' not in t.lower()]
@reg('PUNCH: Cocktail Recipes From the Best New Bars of 2026')
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^###### (.+)\n+(.+)$',md,re.M):
        b=re.search(r'(?:At|at|is undoubtedly the star at|star at) ((?:[A-Z][\w’\'&.]*\s?){1,4}?) in ((?:[A-Z][\w.]*\s?){1,3})',m.group(2))
        if b: out.append((C(b.group(1)),C(b.group(2)).rstrip(',')))
    return out
@reg('Polygon: Game of the Year 2026')
def _(s,h,md):
    m=re.search(r'^## ### Game of the Year\s*$',md,re.M)
    if not m: return []
    out=[]
    for l in md[m.end():].splitlines()[1:]:
        if l.startswith('- '): out.append((C(l[2:]),'Game Awards GOTY nominee'))
        elif out: break
    return out
@reg('The Planetary Society: Best of 2026')
def _(s,h,md):
    out=[]
    for p in s.select('p.award-label'):
        fs=p.find_next('fieldset')
        for img in fs.find_all('img') if fs else []:
            out.append((C(img.get('alt','')),'nominee: '+C(p.get_text()).rstrip(':')))
    return out
@reg('Complex: The 20 Best Sports Moments of 2026 (So Far)','Rotten Tomatoes: Best New Movies of 2026','Rotten Tomatoes: Best TV Shows of 2026','Rotten Tomatoes: Best New Documentaries of 2026','Apple Podcasts: Best of 2026','Chicago Public Library: Top 10 Favorite Books of 2026')
def _(s,h,md): return [tidy(t) for t in ld_items(s)]
@reg('Travel + Leisure: 50 Best Places to Travel in 2026')
def _(s,h,md):
    return [(C(x.get_text(' ',strip=True)).title(),'') for x in s.select('.mntl-sc-block-subheading__text') if not re.search(r'DESTINATIONS|^\s*(States|Cities|Countries|Regions)\s*$',x.get_text(),re.I)]
@reg('New York Times: The Restaurant List 2026 (coverage)')
def _(s,h,md):
    m=re.search(r'The local picks are (.+?)\.',md)
    return [(C(t),'New York City') for t in re.split(r', | and ',m.group(1))] if m else []
@reg('Lonely Planet: Best in Travel 2026 (CNN coverage)')
def _(s,h,md):
    out=[]
    for l in md.splitlines():
        m=re.match(r"^\*\*Also on Lonely Planet.{0,40}?:\*\*\s*(.+)$",l)
        if m:
            for t in re.split(r';\s*',m.group(1)): out.append((C(t.rstrip('.')),'destination'))
    i=md.find('## Best places'); j=md.find('## Fun times')
    for b in re.findall(r'\*\*([^*]+)\*\*',md[i:j]):
        if not b.startswith('Also'): out.append((C(b),'destination'))
    return uniq(out)
@reg('Publishers Weekly: Best Books 2026 (all 150)','Publishers Weekly: Best Books 2026 Top 10','Publishers Weekly: Best Nonfiction 2026','Publishers Weekly: Best Poetry 2026','Publishers Weekly: Best Comics 2026')
def _(s,h,md):
    out=[]
    for x in s.find_all('h3'):
        a=x.find_next('h4')
        out.append((C(x.get_text(' ',strip=True)),C(a.get_text(' ',strip=True)) if a else ''))
    return out
@reg('Kirkus: Best of 2026 – Our Favorite Fiction','Kirkus: Best of 2026 – Our Favorite Nonfiction','Kirkus: Best Books of 2026 – The Holidays Start Early')
def _(s,h,md):
    return [(C(m.group(1)),C(m.group(2))) for m in re.finditer(r'\*([^*\n]{2,120})\* by ([^(\n*]{2,80}?) \(',md)]
@reg('Billboard: 50 Best Albums of 2026 So Far')
def _(s,h,md):
    out=[]
    for t in article_headings(s):
        if ',' in t:
            a,_,b=t.partition(', '); out.append((C(b),C(a)))
    return uniq(out)
@reg('IndieWire: Best Movies of 2026 (So Far)','IndieWire: Best TV Series of 2026 (So Far)')
def _(s,h,md):
    out=[]
    for t in hs(s,'h2'):
        m=re.match(r'^[“"]?(.+?)[”"]\s*(.*)$',t)
        if m: out.append((C(m.group(1)+(' '+m.group(2) if m.group(2) and not m.group(2).startswith('(') else '')),C(re.sub(r'^\(dir\.\s*|\)$','',m.group(2))) if m.group(2).startswith('(') else ''))
        elif ok(t) and len(t)<60 and not JUNK.search(t) and not re.search(r'IndieWire|Newsletter|Most|Popular',t): out.append((C(t),''))
    return uniq(out)
@reg('Spotify: Best Podcasts of the Year (So Far)')
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^## \*\*(.+?)\*\*\s*\n(.+)$',md,re.M):
        t=re.search(r'\*[“"]?([^*”"]{3,80}?)[”"]?\*',m.group(2))
        if t: out.append((C(t.group(1)),f'pick for {C(m.group(1))}'))
    return out
@reg("The World's 50 Best Restaurants 2026 – Full List")
def _(s,h,md):
    d={}
    for tag in s.find_all(['p','h2','h3','strong']):
        t=C(tag.get_text(' ',strip=True)); m=re.match(r'^(\d{1,2})\.\s+(.{2,150})$',t)
        if m: d.setdefault(int(m.group(1)),m.group(2))
    out=[]
    for n in sorted(d):
        t=re.sub(r'\s*\((?:Best|Highest|Art of|The ).*?\)\s*$','',d[n]); a,_,b=t.partition(', ')
        out.append((C(a),C(b)))
    return out
@reg('Robb Report: The 10 Best New Restaurants in America for 2026')
def _(s,h,md):
    return [(C(t.partition(', ')[0]),C(t.partition(', ')[2])) for t in article_headings(s) if ', ' in t]
@reg('The A.V. Club: The Best Films of 2026 So Far','The A.V. Club: The Best TV of 2026 So Far')
def _(s,h,md): return [(t,'') for t in article_headings(s) if len(t)<80 and not JUNK.search(t)]
@reg('Kirkus: Best of 2026 – Our Favorite Nonfiction')
def _(s,h,md):
    return uniq([(C(m.group(1)),'') for m in re.finditer(r'\*([^*\n]{2,140})\* \([^()]*?, (?:Jan|Feb|March|April|May|June|July|Aug|Sept|Oct|Nov|Dec)[a-z]*\.? \d{1,2}\)',md)])
@reg('Polygon: Game of the Year 2026')
def _(s,h,md):
    cats={};order=[];cat=None
    for l in md.splitlines():
        m=re.match(r'^## ### (.+)$',l)
        if m: cat=C(m.group(1)); continue
        if l.startswith('## '): cat=None; continue
        if cat and l.startswith('- '):
            t=C(l[2:])
            if t not in cats: cats[t]=[];order.append(t)
            cats[t].append(cat)
    return [(t,'Game Awards nominee: '+', '.join(cats[t])) for t in order]
POSTJUNK=re.compile(r'^(company|contact|subscriptions|personalize gift card|terms|poured over:.*|readers also read|alerts and newsletters|partner content.*|eater today|popular content|make your commute count|more great tv recommendations|the most anticipated books|decided by fan vote.*|best inventions 2026: special mentions|the latest|kangtown|\d+ .*(books|novels) you need now)$',re.I)
def post(name,items):
    items=[(a,b) for a,b in items if a and not POSTJUNK.match(a)]
    if name.startswith('Variety:'):
        k=next((i for i,(a,b) in enumerate(items) if len(a)>45),len(items)); items=items[:k]
    items=[(re.sub(r'\s*[–-]\s*(NEW|RE)[ -]ENTRY\s*',' ',a).strip(),b) for a,b in items]
    if name=="The World's 50 Best Hotels 2026":
        items=[('San Domenico Palace','Taormina') if a.startswith('San Domenico Palace') else (a,b) for a,b in items]
    return items
@reg('Barnes & Noble: Book of the Year 2026 (Whale Harbor)')
def _(s,h,md):
    out=[('Whale Harbor','Mary Beth Keane'),('Is This a Plum?','Dan and Finn Ojari'),('The Unlikely Tale of Chase and Finnegan','Jasmine Warga'),('This Vast Enterprise: A New History of Lewis & Clark','Craig Fehrman')]
    out=[(t,b) for t,b in out if t.split(':')[0] in md]
    i=md.find('Finalists were')
    seg=md[i:] if i>=0 else ''
    for l in seg.splitlines()[1:]:
        m=re.match(r'^- \*\*\*(.+?)\*\*\* \*\*by (.+?)\*\*',l)
        if m: out.append((C(m.group(1)),C(m.group(2))))
        elif out and not l.startswith('- '): break
    return out
