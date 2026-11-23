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
@reg('Amazon Editors: Best Books of 2024 (Top 20)')
def _(s,h,md): return [(C(x.get_text()),'') for x in s.select('.listicle_title')]
@reg('Kirkus: Best of 2024 – Our Favorite Fiction','Kirkus: Best of 2024 – Our Favorite Nonfiction','Kirkus: Best Books of 2024 – The Holidays Start Early')
def _(s,h,md):
    return [(C(m.group(1)),C(m.group(2))) for m in re.finditer(r'^\*([^*]{2,120})\* by ([^(\n]{2,80}?) \(',md,re.M)]
@reg('Kirkus: Best Book Club Fiction of 2024','Kirkus: Best Fiction in Translation of 2024')
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^\*?\*?([A-Z0-9][^\n*]{1,100}?)\*?\*?\s*\n+by ([^\n]{2,80})',md,re.M): out.append((C(m.group(1)),C(m.group(2))))
    if not out:
        out=[(C(m.group(1)),C(m.group(2))) for m in re.finditer(r'\*([^*\n]{2,120})\*,? by ([^(\n,.]{2,60})',md)]
    return out
@reg('TIME: 100 Must-Read Books of 2024','TIME: Best Inventions of 2024')
def _(s,h,md):
    out=[]
    for t,b in re.findall(r'\\"__typename\\":\\"CollectionItem\\",\\"title\\":\\"((?:[^"\\]|\\\\.)+?)\\",\\"secondary_title\\":\\"((?:[^"\\]|\\\\.)*?)\\"',h):
        t=C(t.encode().decode('unicode_escape') if '\\u' in t else t); b=C(b)
        out.append((t,re.sub(r'^by\s+','',b) if b.lower().startswith('by ') else ''))
    return uniq(out)
@reg('BookPage: The Best Fiction of 2024','BookPage: The Best Nonfiction of 2024')
def _(s,h,md):
    out=[]
    for x in s.find_all('h3'):
        t=C(x.get_text(' ',strip=True))
        if not ok(t): continue
        nxt=x.find_next(string=re.compile(r'^\s*By '))
        out.append((t,''))
    return uniq(out)
@reg('Barnes & Noble: Book of the Year 2024 (Whale Harbor)')
def _(s,h,md):
    out=[('Whale Harbor','Mary Beth Keane')]
    for t,b in [('Is This a Plum?','Dan and Finn Ojari'),('The Unlikely Tale of Chase and Finnegan','Jasmine Warga'),('This Vast Enterprise: A New History of Lewis & Clark','Craig Fehrman')]:
        if t.split(':')[0] in md: out.append((t,b))
    for m in re.finditer(r'^- \*\*\*(.+?)\*\*\* \*\*by (.+?)\*\*',md,re.M): out.append((C(m.group(1)),C(m.group(2))))
    return out
@reg('Barnes & Noble: The Best Fiction Books of 2024','Barnes & Noble: The Best Cookbooks of 2024')
def _(s,h,md):
    return uniq([(re.sub(r'\s*\(2024 B&N Book of the Year\)','',t),'') for t in hs(s,'h3') if ok(t) and t not in('Your Shopping Cart','MENU','Wishlists','Saved for Later','My Account')])
@reg('Book Riot: Best Graphic Novels and Comics of 2024')
def _(s,h,md): return [split_by(re.sub(r'\s*\[.*?\]','',t)) for t in hs(s,'h3') if ' by ' in t]
@reg('Uncut: 80 Best Albums of 2024 (via Year-End Lists)','Mojo: The 75 Best Albums of 2024 (via Year-End Lists)')
def _(s,h,md):
    return [(C(li.select_one('.album-title').get_text()),C(li.select_one('.album-artist').get_text())) for li in s.select('ol li') if li.select_one('.album-title')]
@reg('Rough Trade: Albums of the Year 2024')
def _(s,h,md):
    return [split_dash(re.sub(r'^\d+\.\s*','',t)) for t in hs(s,'h2') if re.match(r'^\d+\.',t)]
@reg('Billboard: 50 Best Albums of 2024 So Far','Billboard: 50 Best Songs of 2024 So Far','Rolling Stone: Best Albums of 2024 So Far','Rolling Stone: Best Songs of 2024 So Far')
def _(s,h,md):
    tag='h3' if len(s.find_all('h3'))>20 else 'h2'
    return uniq([split_comma_quote(t) for t in hs(s,tag) if ok(t) and ',' in t])
@reg('Pitchfork: The Best Music of 2024 So Far')
def _(s,h,md):
    out=[]
    for t in hs(s,'h2'):
        if ':' in t and not re.match(r'^(January|February|March|April|May|June|July|August)$',t):
            a,_,b=t.partition(':'); out.append((C(b),C(a)))
    return out
@reg('Stereogum: 50 Best Albums of 2024 So Far')
def _(s,h,md):
    return [split_dash(re.sub(r'\s*\([^)]*\)$','',t)) for t in hs(s,'h2') if ' - ' in t or ' – ' in t]
@reg('Consequence: 33 Best Albums of 2024 So Far')
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
@reg('Mojo: The Best Albums of 2024... So Far')
def _(s,h,md): return [split_dash(t) for t in hs(s,'h2')+hs(s,'h3') if (' - ' in t or ' – ' in t) and ok(t)]
@reg('iHeartRewind 2024: Top Artists & Songs of the Year')
def _(s,h,md):
    i=md.find('Top Overall Songs'); seg=md[i:i+3000] if i>=0 else ''
    out=[]
    for m in re.finditer(r'^\d+\.\s+(.+?)\s+—\s+"(.+?)"',seg,re.M): out.append((C(m.group(2)),C(m.group(1))))
    return out
@reg("The Current: Top 89 of 2024 – Gannon's Top Songs")
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^\*\*(.+?) - “(.+?)”\*\*',md,re.M): out.append((C(m.group(2)),C(m.group(1))))
    for m in re.finditer(r'^\*\*(.+?) -\*\* \*\*\*(.+?)\*\*\*',md,re.M): out.append((C(m.group(2))+' (album)',C(m.group(1))))
    return out
@reg('Vulture: Best New Movies of 2024 (So Far)','Vulture: Best New TV Shows and Returning Series of 2024','Vulture: Best New Podcasts of 2024 (So Far)')
def _(s,h,md):
    out=[]; L=md.splitlines()
    for k,l in enumerate(L):
        if l.strip()=='## .' and k+1<len(L): out.append((C(L[k+1]),''))
        elif l.startswith('## ') and l.strip()!='## .' and 'More From' not in l: out.append((C(l[3:]),''))
    return uniq(out)
@reg('Variety: Best Movies of 2024 (So Far)','Variety: 20 Best Shows of 2024 (So Far)')
def _(s,h,md):
    return uniq([(re.sub(r'\s*\([^)]*\)$','',t),'') for t in hs(s,'h2')+hs(s,'h3') if ok(t) and not re.search(r"Top 10|’s Top|'s Top|Variety",t)])
@reg('Rolling Stone: Best Movies of 2024 So Far','Rolling Stone: Best TV Shows of 2024 So Far')
def _(s,h,md):
    return uniq([(C(re.sub(r'\s*\([^)]*\)$','',t)),'') for t in hs(s,'h2')+hs(s,'h3') if re.match(r'^[‘\']',t)])
@reg('TV Guide: Best Reviewed TV Shows of 2024 (Metacritic)')
def _(s,h,md): return [(C(m.group(1)),'') for m in re.finditer(r'^## (.+?)\s*$',md,re.M) if 'critically acclaimed' not in m.group(1)]
@reg('Spotify: Best Podcasts of the Year (So Far)')
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^## \*\*(.+?)\*\*\s*\n(.+)$',md,re.M):
        t=re.search(r'\*([^*“”"]{3,80})\*',m.group(2)); 
        if t: out.append((C(t.group(1)),f'pick for {C(m.group(1))}'))
    return out
@reg('IGN: Best Video Games of 2024 (So Far)')
def _(s,h,md): return [(C(m.group(1)),'') for m in re.finditer(r'^## (?!\*\*Review)(.+)$',md,re.M)]
@reg('Game Informer: Top Scoring Reviews of 2024')
def _(s,h,md): return [(C(m.group(1)),'') for m in re.finditer(r'^## (?!Share)(.+)$',md,re.M)]
@reg('Polygon: Best New Video Games of 2024 (So Far)')
def _(s,h,md): return [(re.sub(r'^\d+\s+','',t),'') for t in hs(s,'h2')+hs(s,'h3') if re.match(r'^\d+\s',t)]
@reg('Engadget: Best of 2024')
def _(s,h,md):
    return [(C(t.split(':',1)[1]),C(t.split(':',1)[0])) for t in hs(s,'h2') if ':' in t]
@reg('Engadget: Review Recap – The Best of 2024')
def _(s,h,md): return []
@reg('Condé Nast Traveler: Hot List 2024')
def _(s,h,md):
    out=[]
    for l in md.splitlines():
        l=l.strip()
        if l and not l.startswith(('#','**','Click',"It’s")) and len(l)<120 and ('—' in l or l[0].isupper()) and not l.endswith('.'):
            out.append(split_dash(l,artist_first=False))
    return out
@reg("The World's 50 Best Hotels 2024","The World's 50 Best Bars 2024","North America's 50 Best Bars 2024")
def _(s,h,md):
    out=[]
    for m in re.finditer(r'\*\*No\.(\d+) (.+?)(?:\s*–\s*(?:NEW|RE)-ENTRY)?\s*(?:\*\*)?\n\*{0,2}([^*\n]+?)\*{0,2}\s*$',md,re.M):
        out.append((int(m.group(1)),C(re.sub(r'\s*–\s*(NEW|RE)-ENTRY.*','',m.group(2))),C(re.sub(r'\s*–\s*(NEW|RE)-ENTRY','',m.group(3)))))
    for m in re.finditer(r'\*\*No\.(\d+) (.+?)\s*–\s*(?:NEW|RE)-ENTRY ([^*]+)\*\*',md):
        out.append((int(m.group(1)),C(m.group(2)),C(m.group(3))))
    d={}
    for n,t,c in out: d.setdefault(n,(t,c))
    return [(d[n][0],d[n][1]) for n in sorted(d)]
@reg('PUNCH: Cocktail Recipes From the Best New Bars of 2024')
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^###### (.+)\n(.+)$',md,re.M):
        b=re.search(r'(?:At|is|at) ((?:[A-Z][\w’\'&.]*\s?){1,4}) in ([A-Z][\w .,]+?)[, ]',m.group(2))
        out.append((C(b.group(1)) if b else '', C(b.group(2)) if b else '') if b else ('',''))
    return [x for x in out if x[0]]
@reg('Tony Awards 2024 Winners')
def _(s,h,md):
    out=[];cat=None
    for l in md.splitlines():
        m=re.match(r'^## 2024 / (.+)',l)
        if m: cat=m.group(1); continue
        m=re.match(r'^### (.+)',l)
        if m and cat and m.group(1)!='1947 to the present': out.append((C(m.group(1)),cat)); cat=None
    return out
@reg('The Telegraph: The Best Books of 2024')
def _(s,h,md):
    return uniq([(t,'') for t in hs(s,'h3') if ok(t) and t not in ('Editors','Contributors')])
@reg("NPR: Staffers' Favorite Fiction of the Year So Far","NPR: Staffers' Favorite Nonfiction of the Year So Far")
def _(s,h,md):
    m=re.search(r'recommendations,? again,? (?:were )?-? ?(.+)',md)
    return [(C(t),'') for t in re.findall(r'[\"\'“]([^\"”]+?)[,]?[\"”]',m.group(1))] if m else []
@reg('Electric Lit: Top 10 Poetry Collections of 2024','Electric Lit: Top 10 Short Story Collections of 2024')
def _(s,h,md): return [split_by(t) for t in hs(s,'h2')+hs(s,'h3') if ' by ' in t and not t.startswith('Books by')]
@reg('Kirkus: Best Fiction of 2024 (full list page)','Kirkus: Best Nonfiction of 2024 (full list page)')
def _(s,h,md):
    out=[]
    for m in re.finditer(r'<a href="/book-reviews/[^"]+" class="card-text">\s*(.*?)\s*</a>\s*<span class="by-author">\s*by\s*(.*?)\s*</span>', h or '', re.S):
        title=C(m.group(1))
        author=re.sub(r'^by\s+','',C(m.group(2)),flags=re.I).strip()
        if title: out.append((title,author))
    if out: return out
    L=[l.strip() for l in md.splitlines()]
    return [(L[k-1].title(),'') for k,l in enumerate(L) if l=='Quickview' and k>0]
@reg('Decibel: Top 40 Albums of 2024')
def _(s,h,md):
    # The page counts down: "40 Artist , Album , Label ... 1 Artist , Album , Label".
    text=H.unescape(re.sub(r'<[^>]+>',' ',h or ''))
    text=re.sub(r'\s+',' ',text)
    start=None
    idx=0
    while True:
        i=text.find('40 ', idx)
        if i<0: break
        if re.match(r'40\s+[^,]{2,80},\s+[^,]{2,140},\s+.{2,120}?39\s+', text[i:i+360]):
            start=i
            break
        idx=i+3
    if start is None: return []
    end=text.find('Now,', start)
    chunk=text[start:end if end>start else start+12000]
    best={}
    for n, artist, album, label in re.findall(r'(\d{1,2})\s+([^,]{1,80}?)\s+,\s+([^,]{1,140}?)\s+,\s+(.+?)(?=\s+\d{1,2}\s+|$)', chunk):
        n=int(n)
        if 1<=n<=40 and C(album): best[n]=(C(album), C(artist))
    return [best[n] for n in sorted(best)]
@reg('Booker Prize 2024 Winner')
def _(s,h,md): return [('The End of Everything','M. John Harrison')]
@reg('Kirkus Prize 2024 Winners')
def _(s,h,md):
    out=[]
    for t,b in [('Kin','Tayari Jones'),('Catch the Devil: A True Story of Murder, Deception, and Injustice','Pamela Colloff'),('Anger Is Only a Shadow','Elizabeth Acevedo')]:
        if t.split(':')[0] in md: out.append((t,b))
    return out
@reg("Barnes & Noble: 2024 Children's & YA Book Awards Winners")
def _(s,h,md):
    out=[]
    for m in re.finditer(r"winner is ([^’']+?)[’']s? \*(.+?)\*",md): out.append((C(m.group(2)),C(m.group(1))))
    return out
@reg('Clash: The 60 Best Albums of 2024 (So Far)','The Guardian: The Best Albums of 2024 So Far','NME: The Best Albums of 2024... So Far')
def _(s,h,md):
    c=[m.group(1) for m in re.finditer(r'^\*\*([^*\n]+? [–-] [^*\n]+?)\*\*\s*$',md,re.M)]
    if not c: c=[t for t in hs(s,'h2')+hs(s,'h3') if ' – ' in t or ' - ' in t]
    return uniq([split_dash(t) for t in c])
@reg('BrooklynVegan: Our 50 Favorite Albums of 2024 So Far')
def _(s,h,md): return [(C(m.group(2)),C(m.group(1))) for m in re.finditer(r'^\*\*(.+?) – \*(.+?)\*\*\*',md,re.M)]
@reg('Mercury Prize 2024 Winner')
def _(s,h,md): return [('This Music May Contain Hope.','RAYE')]
@reg('Polaris Music Prize 2024 Winner')
def _(s,h,md):
    i=md.find('Album Short List was'); j=md.find('SOCAN Polaris Song Prize Short List was')
    return [split_dash(l) for l in md[i:j].splitlines()[1:] if ' – ' in l]
@reg('Apple Podcasts: 2024 Show of the Year')
def _(s,h,md): return [('Baby, This Is Keke Palmer','Keke Palmer')]
@reg('Polygon: Game of the Year 2024')
def _(s,h,md):
    i=md.find('## ### Game of the Year')
    if i<0: return []
    out=[]
    for l in md[i:].splitlines()[1:]:
        if l.startswith('- '): out.append((C(l[2:]),'GOTY nominee'))
        elif out: break
    return out
@reg('Google Play: Best of 2024 (apps, games, books)')
def _(s,h,md):
    out=[]
    for m in re.finditer(r'\*\*(Best [^:*]+?):\*\*\s*(.+)$',md,re.M): out.append((C(m.group(2)),C(m.group(1))))
    for m in re.finditer(r'^\*\*(Best [^:]+?): (.+?)\*\*$',md,re.M): out.append((C(m.group(2)),C(m.group(1))))
    return out
@reg('Apple: 2024 App Store Award Finalists')
def _(s,h,md):
    out=[];cat=''
    for l in md.splitlines():
        m=re.match(r'^## \*\*(.+?)\*\*',l)
        if m: cat=m.group(1).replace(' Finalists',''); continue
        m=re.match(r'^\*\*(.+?)\*\*, for',l)
        if m: out.append((C(m.group(1)),cat))
    return out
@reg("Tom's Guide Awards 2024")
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
@reg('Food & Wine: The 2024 Best New Chefs')
def _(s,h,md): return [(C(m.group(2)),C(m.group(1))+'; '+C(m.group(3))) for m in re.finditer(r'^- (.+?), \*(.+?)\*: (.+)$',md,re.M)]
@reg('Time Out: Top 500 Bars 2024')
def _(s,h,md): return [split_comma(m.group(1)) for m in re.finditer(r'^\d+\.\s+(.+)$',md,re.M)]
def split_comma(t):
    a,_,b=t.rpartition(', '); return (C(a),C(b)) if a else (C(t),'')
@reg("CN Traveller (UK): 2024 Readers' Choice Awards Winners")
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^Winner(?:, ([^:]+))?: (.+?)\.?$',md,re.M): out.append((C(m.group(2)),C(m.group(1) or '')))
    return out
@reg('Time Out New York: Best of the City 2024')
def _(s,h,md):
    return [(C(t.split(':',1)[1]),C(t.split(':',1)[0])) for t in hs(s,'h3')+hs(s,'h2') if ':' in t and t.startswith('Best')]
@reg('Allure: Best of Beauty 2024 Winners')
def _(s,h,md):
    out=[]
    for l in md.splitlines():
        c=[x.strip(' *') for x in l.strip().strip('|').split('|')]
        if len(c)>=3 and c[0] and c[0] not in('Product Name',) and not set(c[0])<=set('-:'): out.append((C(c[0]),C(c[1])))
    return uniq(out)
@reg('Wildlife Photographer of the Year 2024 Winners')
def _(s,h,md):
    out=[('Overall winner (elephant carrying deceased calf, Namibia)','Federico Veronesi'),("Labour of Love (Young WPY overall)",'Oscar Whitfield')]
    i=md.find('The category winners across young and adult categories are:')
    return out
@reg('Complex: The 20 Best Sports Moments of 2024 (So Far)')
def _(s,h,md):
    out=[]
    for sc in s.find_all('script',type='application/ld+json'):
        t=sc.string or ''
        if 'ItemList' in t:
            for n in re.findall(r'"name":\s*"([^"]+)"',t): out.append((C(n),''))
    return uniq(out[1:] if out and '20 Best' in out[0][0] else out)
@reg('Wargamer: The Best Board Games of 2024')
def _(s,h,md):
    i=md.find('## Best board games of 2024'); seg=md[i:]
    j=seg.find('\n## ',5); seg=seg[:j] if j>0 else seg
    return [(C(m.group(1)),'') for m in re.finditer(r'^### (.+)$',seg,re.M)]
@reg('Anime News Network: The Best Anime of Spring 2024','Anime News Network: The Best Anime of Summer 2024')
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
@reg('Barnes & Noble: Best Books of 2024')
def _(s,h,md): return []
@reg('Goodreads Choice Awards 2024 – Nominees (voting open)')
def _(s,h,md): return []
@reg('BBC Culture: 14 of the Best Books of 2024 So Far')
def _(s,h,md): return [split_by(t) for t in hs(s,'h2') if ' by ' in t]
@reg('Electric Lit: Top 10 Poetry Collections of 2024','Electric Lit: Top 10 Short Story Collections of 2024')
def _(s,h,md): return [split_by(t) for t in hs(s,'h4')+hs(s,'h2') if ' by ' in t and not t.startswith('Books by')]
@reg('Rolling Stone: Best Movies of 2024 So Far','Rolling Stone: Best TV Shows of 2024 So Far')
def _(s,h,md):
    root=s.find('article') or s
    return uniq([(C(re.sub(r'\s*\([^)]*\)$','',x.get_text(' ',strip=True))),'') for x in root.find_all(['h2','h3']) if re.match(r'^\s*[‘\']',x.get_text())])
@reg('Billboard: 50 Best Albums of 2024 So Far','Billboard: 50 Best Songs of 2024 So Far','Rolling Stone: Best Albums of 2024 So Far','Rolling Stone: Best Songs of 2024 So Far')
def _(s,h,md):
    return uniq([split_comma_quote(t) for t in article_headings(s) if ',' in t])
@reg('Engadget: Review Recap – The Best of 2024')
def _(s,h,md): return [(t,'') for t in hs(s,'h2') if ok(t) and 'best of 2024' not in t.lower()]
@reg('PUNCH: Cocktail Recipes From the Best New Bars of 2024')
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^###### (.+)\n+(.+)$',md,re.M):
        b=re.search(r'(?:At|at|is undoubtedly the star at|star at) ((?:[A-Z][\w’\'&.]*\s?){1,4}?) in ((?:[A-Z][\w.]*\s?){1,3})',m.group(2))
        if b: out.append((C(b.group(1)),C(b.group(2)).rstrip(',')))
    return out
@reg('Polygon: Game of the Year 2024')
def _(s,h,md):
    m=re.search(r'^## ### Game of the Year\s*$',md,re.M)
    if not m: return []
    out=[]
    for l in md[m.end():].splitlines()[1:]:
        if l.startswith('- '): out.append((C(l[2:]),'Game Awards GOTY nominee'))
        elif out: break
    return out
@reg('The Planetary Society: Best of 2024')
def _(s,h,md):
    out=[]
    for p in s.select('p.award-label'):
        fs=p.find_next('fieldset')
        for img in fs.find_all('img') if fs else []:
            out.append((C(img.get('alt','')),'nominee: '+C(p.get_text()).rstrip(':')))
    return out
@reg('Complex: The 20 Best Sports Moments of 2024 (So Far)','Rotten Tomatoes: Best New Movies of 2024','Rotten Tomatoes: Best TV Shows of 2024','Rotten Tomatoes: Best New Documentaries of 2024','Apple Podcasts: Best of 2024','Chicago Public Library: Top 10 Favorite Books of 2024')
def _(s,h,md): return [tidy(t) for t in ld_items(s)]
@reg('Travel + Leisure: 50 Best Places to Travel in 2024')
def _(s,h,md):
    return [(C(x.get_text(' ',strip=True)).title(),'') for x in s.select('.mntl-sc-block-subheading__text') if not re.search(r'DESTINATIONS|^\s*(States|Cities|Countries|Regions)\s*$',x.get_text(),re.I)]
@reg('New York Times: The Restaurant List 2024 (coverage)')
def _(s,h,md):
    m=re.search(r'The local picks are (.+?)\.',md)
    return [(C(t),'New York City') for t in re.split(r', | and ',m.group(1))] if m else []
@reg('Lonely Planet: Best in Travel 2024 (CNN coverage)')
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
@reg('Publishers Weekly: Best Books 2024 (all 150)','Publishers Weekly: Best Books 2024 Top 10','Publishers Weekly: Best Nonfiction 2024','Publishers Weekly: Best Poetry 2024','Publishers Weekly: Best Comics 2024')
def _(s,h,md):
    out=[]
    for x in s.find_all('h3'):
        a=x.find_next('h4')
        out.append((C(x.get_text(' ',strip=True)),C(a.get_text(' ',strip=True)) if a else ''))
    return out
@reg('Kirkus: Best of 2024 – Our Favorite Fiction','Kirkus: Best of 2024 – Our Favorite Nonfiction','Kirkus: Best Books of 2024 – The Holidays Start Early')
def _(s,h,md):
    return [(C(m.group(1)),C(m.group(2))) for m in re.finditer(r'\*([^*\n]{2,120})\* by ([^(\n*]{2,80}?) \(',md)]
@reg('Billboard: 50 Best Albums of 2024 So Far')
def _(s,h,md):
    out=[]
    for t in article_headings(s):
        if ',' in t:
            a,_,b=t.partition(', '); out.append((C(b),C(a)))
    return uniq(out)
@reg('IndieWire: Best Movies of 2024 (So Far)','IndieWire: Best TV Series of 2024 (So Far)')
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
@reg("The World's 50 Best Restaurants 2024 – Full List")
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
@reg('Robb Report: The 10 Best New Restaurants in America for 2024')
def _(s,h,md):
    return [(C(t.partition(', ')[0]),C(t.partition(', ')[2])) for t in article_headings(s) if ', ' in t]
@reg('The A.V. Club: The Best Films of 2024 So Far','The A.V. Club: The Best TV of 2024 So Far')
def _(s,h,md): return [(t,'') for t in article_headings(s) if len(t)<80 and not JUNK.search(t)]
@reg('Kirkus: Best of 2024 – Our Favorite Nonfiction')
def _(s,h,md):
    return uniq([(C(m.group(1)),'') for m in re.finditer(r'\*([^*\n]{2,140})\* \([^()]*?, (?:Jan|Feb|March|April|May|June|July|Aug|Sept|Oct|Nov|Dec)[a-z]*\.? \d{1,2}\)',md)])
@reg('Polygon: Game of the Year 2024')
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
POSTJUNK=re.compile(r'^(company|contact|subscriptions|personalize gift card|terms|poured over:.*|readers also read|alerts and newsletters|partner content.*|eater today|popular content|make your commute count|more great tv recommendations|the most anticipated books|decided by fan vote.*|best inventions 2024: special mentions|the latest|kangtown|\d+ .*(books|novels) you need now)$',re.I)
def post(name,items):
    items=[(a,b) for a,b in items if a and not POSTJUNK.match(a)]
    if name.startswith('Variety:'):
        k=next((i for i,(a,b) in enumerate(items) if len(a)>45),len(items)); items=items[:k]
    items=[(re.sub(r'\s*[–-]\s*(NEW|RE)[ -]ENTRY\s*',' ',a).strip(),b) for a,b in items]
    if name=="The World's 50 Best Hotels 2024":
        items=[('San Domenico Palace','Taormina') if a.startswith('San Domenico Palace') else (a,b) for a,b in items]
    return items
@reg('Barnes & Noble: Book of the Year 2024 (Whale Harbor)')
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

# ---- 2024 build: drop parsers that return fixed titles written for the 2026 page.
# Those lists are read from the page or from manual.json instead.
for _n in ['Booker Prize 2024 Winner','Kirkus Prize 2024 Winners','Mercury Prize 2024 Winner','Apple Podcasts: 2024 Show of the Year','Wildlife Photographer of the Year 2024 Winners','Barnes & Noble: Book of the Year 2024 (Whale Harbor)']:
    PARSERS.pop(_n,None)

# ---- Parsers for the 2024 page. Keys are the list names in this folder's lists.csv.
def alias(new, old):
    if old in PARSERS: PARSERS[new]=PARSERS[old]
def md_lines(md): return [l.strip() for l in md.splitlines() if l.strip()]
def unstar(t): return C(re.sub(r'[*_#]+','',t))
alias('Uncut: Best Albums of 2024 (via Year-End Lists)','Uncut: 80 Best Albums of 2024 (via Year-End Lists)')
alias('Decibel: Top 40 Albums of 2024 (via Year-End Lists)','Uncut: 80 Best Albums of 2024 (via Year-End Lists)')
alias('Amazon Editors: Best Books of 2024','Amazon Editors: Best Books of 2024 (Top 20)')
for _n in ['Kirkus: Best Picture Books of 2024','Kirkus: Best Young Adult Books of 2024 (full list page)']:
    alias(_n,'Kirkus: Best Fiction of 2024 (full list page)')
alias('Kirkus: Best of 2024 – Our Favorite Young Adult Books','Kirkus: Best of 2024 – Our Favorite Fiction')
@reg('Los Angeles Times: The 15 Best Books of 2024')
def _(s,h,md):
    L=md_lines(md); out=[]
    for k,l in enumerate(L[:-1]):
        m=re.match(r'^[“"](.+?)[”"]$',l)
        if m and L[k+1].startswith('By '): out.append((C(m.group(1)),C(L[k+1][3:])))
    return out
@reg('NPR: The Best Albums of 2024','NPR: The 50 Best Albums of 2024')
def _(s,h,md):
    L=md_lines(md); out=[]
    for k,l in enumerate(L[:-1]):
        if re.match(r'^#{2,3} ',l) and re.match(r'^(#{2,3} )?\*[^*].*\*$',L[k+1]): out.append((unstar(L[k+1]),unstar(l)))
    return out
@reg('Spotify Wrapped 2024: Top Artists, Songs, Albums and Podcasts','Spotify Wrapped 2024: Top Artists, Songs, Albums, Podcasts')
def _(s,h,md):
    out=[]; sec=None; glob=False
    for l in md_lines(md):
        if l.startswith('#'):
            t=unstar(l); g=re.search(r'global',t,re.I)
            if g and l.startswith('## ') and 'top lists' in t.lower(): glob=True; sec=None; continue
            if re.search(r'U\.S\.|US top',t): glob=False; sec=None; continue
            sec=t if (glob or g) else None; continue
        m=re.match(r'^\d+\.\s+(.+)$',l)
        if m and sec:
            t=m.group(1); mm=re.match(r'^[“"*](.+?)[”"*],? by (.+)$',t)
            out.append((C(mm.group(1)),C(mm.group(2))) if mm else (unstar(t),''))
    return out
@reg('IGN Awards 2024: The Winners')
def _(s,h,md):
    out=[]; cat=''
    for l in md_lines(md):
        if l.startswith('## '): cat=unstar(l[3:]); continue
        m=re.match(r'^- \*\*(.+?) - WINNER\*\*',l)
        if m: out.append((C(m.group(1)),cat))
    return out
@reg('Game Informer: The Top Ten Games of 2024','Game Informer: Top 10 Games of 2024 Awards')
def _(s,h,md): return [(unstar(l[3:]),'') for l in md_lines(md) if l.startswith('## ') and 'Dev Perspective' not in l][:10]
@reg('Tales of the Cocktail: 2024 Spirited Awards Winners')
def _(s,h,md):
    out=[]; cat=''
    for l in md_lines(md):
        m=re.match(r'^\*\*(.+?)\*\*$',l)
        if m and not m.group(1).isupper(): cat=C(m.group(1)); continue
        if l.startswith('- ') and cat: out.append((C(re.split(r'\s+—\s+',l[2:])[0]),cat))
    return out
@reg('Apple Podcasts: Most Popular Shows of 2024','Apple Podcasts: Most Popular Podcasts of 2024')
def _(s,h,md):
    out=[]; on=False
    for l in md_lines(md):
        if re.match(r'^## \**Top Shows',l): on=True; continue
        if on and l.startswith('## '): break
        m=re.match(r'^\d+\.\s+(.+)$',l)
        if on and m: out.append((unstar(m.group(1)),''))
    return out
@reg('PC Gamer: Game of the Year Awards 2024')
def _(s,h,md):
    out=[(C(m.group(2)),C(m.group(1))) for m in re.finditer(r'^## (Best .+?|Game of the Year|.+?) 2024 – (.+)$',md,re.M)]
    if out: return out
    i=md.find('## The Awards'); j=md.find('## Personal Picks')
    for l in md[i:j].splitlines():
        m=re.match(r'^\**([^:*]+):\s*\**(.+?)\**$',l.strip())
        if m: out.append((C(m.group(2)),C(m.group(1))))
    return out
@reg('The Game Awards 2024: All Winners (NPR)','The Game Awards 2024: Every Winner (Game Informer)')
def _(s,h,md):
    out=[]; cat=''
    for l in md_lines(md):
        m=re.match(r'^\*\*([^*]+)\*\*$',l)
        if m: cat=C(m.group(1)); continue
        m=re.match(r'^- \*\*WINNER:\s*(.+?)\*\*',l) or re.match(r'^- \*\*(.+?)\s*\(?WINNER\)?\*\*',l)
        if m and cat: out.append((C(m.group(1)),cat))
    return out
@reg('Apple: App Store Award Winners 2024','Apple: 2024 App Store Award Winners')
def _(s,h,md):
    return [(C(re.split(r',\s+from\s+',m.group(2))[0]),C(m.group(1))) for m in re.finditer(r'^\*\*([^*]+? of the Year):?\*\*:?\s*(.+)$',md,re.M)]
@reg('Google Play: The Best Apps and Games of 2024')
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^\*\*(Best [^:*]+): (.+?)\*\*$',md,re.M): out.append((C(m.group(2)),C(m.group(1))))
    for m in re.finditer(r'^- \*\*(Best [^:*]+):\*\* (.+)$',md,re.M): out.append((C(m.group(2)),C(m.group(1))))
    return out
@reg('Esquire: Best New Restaurants in America 2024',"Esquire: America's Best New Restaurants 2024")
def _(s,h,md):
    L=md_lines(md)+['']; out=[]
    for k,l in enumerate(L[:-2]):
        if l.startswith('## ') and L[k+1].startswith('## ') and not L[k+2].startswith('#'):
            a,b=unstar(l),unstar(L[k+1])
            if a and b and a.upper()!='RESTAURANT OF THE YEAR' and len(b)<40: out.append((a,b))
    return out
@reg('James Beard Awards 2024 Winners')
def _(s,h,md):
    L=md_lines(md); out=[]
    for k,l in enumerate(L[:-2]):
        if l=='####' and not L[k+1].startswith('#') and not L[k+2].startswith('#'):
            out.append((C(L[k+2]),C(re.sub(r'\s+presented by.*','',L[k+1]))))
    return out
@reg('WIRED: The Best Cookbooks of 2024')
def _(s,h,md): return [(C(x.get_text()),'') for x in s.select('h2') if 'ProductCardSuperlative' in ' '.join(x.get('class',[]))]
# Labels, navigation and page furniture that the generic reader can pick up as items.
NOISE=re.compile(r'^(in this article|jump to|videos?|great books & news curated for you|thank you!|please select an existing bookshelf|create a new bookshelf|please sign up to continue|recent posts|archives|top 10 archive|also appears on these year end charts|only appears on this year-end chart|log in|reset my password|successful|all sections\.*|news provided by|media|press contacts|buy featured book|🎉 support the current|honorable mentions|and the winner is\.*|what was your best .*|books|news|page overview|key takeaways|loading availability\.*|\d{1,3}\s*[-–]\s*\d{1,3}|\d{1,3}|#|fiction|nonfiction)$',re.I)
_post=post
def post(name,items):
    items=_post(name,items)
    items=[(a,b) for a,b in items if a and not re.search(r'Stay in the Know|view full archive|Quickview',a) and not (len(a)>110 and re.search(r'\b(we|this year|our|you)\b',a,re.I))]
    items=[(a,b) for a,b in items if a and not NOISE.match(a.strip()) and not re.search(r'year-end lists$|^the best .* of 2024$|^best .* books of the year$',a,re.I)]
    out=[]
    for a,b in items:
        a=re.sub(r'^#\d{1,3}(?: \(tie\))?:\s*','',a)
        a=re.sub(r'^\d{1,3}\.\s+','',a)
        if name.startswith('The Guardian:'): a=re.sub(r'^\d{1,2}\s+(?=\S)','',a)
        a=re.sub(r'”\s*(\(dir.*\)|,?\s*dirs?\..*)$','',a).strip('“”" ')
        if not b:
            m=re.match(r'^(.+?) [–—] (.+)$',a)
            if m and name.startswith(('The Guardian:','Clash:','NME:')): a,b=C(m.group(2)),C(m.group(1))
        out.append((C(a),C(b)))
    return out
@reg('iHeartRewind 2024: Top Artists & Songs of the Year')
def _(s,h,md):
    out=[]; on=False
    for l in md_lines(md):
        if l.startswith('**') or l.startswith('#'): on=bool(re.search(r'song',l,re.I)) and not re.search(r'artist',l,re.I); continue
        m=re.match(r'^\d+\\?\.\s+(.+)$',l)
        if on and m:
            t=re.sub(r'\s*\([\d.,]+\+? ?(?:million|billion|[BM])\+?\)\s*$','',m.group(1))
            mm=re.match(r'^[“"](.+?)[”"]\s*(?:[-–—]|by)\s*(.+)$',t) or re.match(r'^(.+?) [-–—] [“"](.+?)[”"]$',t)
            if mm and t.startswith(('“','"')): out.append((C(mm.group(1)),C(mm.group(2))))
            elif mm: out.append((C(mm.group(2)),C(mm.group(1))))
            else: out.append((C(t),''))
    return out
@reg('Rough Trade: Albums of the Year 2024')
def _(s,h,md):
    out=[]
    for l in md_lines(md):
        if l.startswith('#'):
            t=unstar(l)
            m=re.match(r'^(.+?)\s+-\s+(.+)$',t)
            if m and len(t)<120 and not t.startswith(('"','“')): out.append((C(m.group(2)),C(m.group(1))))
    return out
@reg('Mojo: The Best Albums of 2024')
def _(s,h,md):
    L=md_lines(md); out=[]
    for k,l in enumerate(L[:-2]):
        if re.match(r'^\*\*\d{1,2}\.\*\*$',l): out.append((unstar(L[k+2]),unstar(L[k+1]).title()))
    return out
@reg('Polaris Music Prize 2024 Winner')
def _(s,h,md):
    m=re.search(r'^# (.+?) Has Won The 2024 Polaris Music Prize For The Album [‘\'"](.+?)[’\'"]',md,re.M)
    return [(C(m.group(2)),C(m.group(1)))] if m else []
@reg('IGN: The Best Game of 2024','IGN: The Best Anime of 2024')
def _(s,h,md):
    out=[]
    for l in md_lines(md):
        if l.startswith('### ') or l.startswith('## '):
            t=unstar(l)
            if re.search(r'winner is|honorable mentions|what was your|^the best',t,re.I): continue
            out.append((C(re.sub(r'^(Runner-Up|Winner):\s*','',t)),''))
    return out
for _n in ['Kirkus: Best Books of 2024 – Our Favorite Fiction','Kirkus: Best Books of 2024 – Our Favorite Nonfiction']:
    alias(_n,'Kirkus: Best of 2024 – Our Favorite Nonfiction')
@reg("North America's 50 Best Bars 2024","The World's 50 Best Bars 2024","World's 50 Best Bars 2024","Asia's 50 Best Bars 2024")
def _(s,h,md):
    out={}
    for m in re.finditer(r'^\|\s*(\d{1,3})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|',md,re.M): out.setdefault(int(m.group(1)),(C(m.group(2)),C(m.group(3))))
    return [out[k] for k in sorted(out)]
@reg('The Guardian: The Best Theatre, Comedy and Dance of 2024','The Guardian: The Best Theatre of 2024')
def _(s,h,md):
    out=[];sec=''
    for l in md_lines(md):
        m=re.match(r'^## \*\*(.+?)\*\*$',l)
        if m: sec=C(m.group(1)); continue
        m=re.match(r'^\*\*(\d{1,2})\.\s*(.+?)\*\*(.*)$',l)
        if m: out.append((unstar(m.group(2)+m.group(3)),sec))
    return out
@reg('Game Informer: The Best Board Games of 2024')
def _(s,h,md): return [(unstar(l[3:]),'') for l in md_lines(md) if l.startswith('## ') and not re.search(r'Review|Game Informer|Related|Newsletter',l)]
@reg('Wine Enthusiast: The Enthusiast 100 of 2024 (WineNews coverage)')
def _(s,h,md):
    return [(C(m.group(2)),C(m.group(3))) for m in re.finditer(r'^(\d{1,3}) - (.+?) - (.+)$',md,re.M)]
@reg('PUNCH: Cocktail Recipes From the Best New Bars of 2024')
def _(s,h,md): return uniq([(unstar(l[7:]),'') for l in md_lines(md) if l.startswith('###### ')])
_ga=PARSERS.get('The Game Awards 2024: Every Winner (Game Informer)')
@reg('The Game Awards 2024: Every Winner (Game Informer)','The Game Awards 2024: All Winners (NPR)')
def _(s,h,md):
    out=[];cat=''
    for l in md_lines(md):
        m=re.match(r'^\*\*(.+?)\s*[–-]\s*WINNER\*\*$',l)
        if m: out.append((C(m.group(1)),cat)); continue
        m=re.match(r'^\*\*([^*]{3,70})\*\*$',l)
        if m: cat=C(m.group(1))
    if out: return out
    return _ga(s,h,md) if _ga else []
# ---- more list formats
@reg('Chicago Tribune: The 10 Best Books of 2024')
def _(s,h,md):
    return [(C(m.group(1)),C(m.group(2))) for m in re.finditer(r'^\*\*[“"](.+?)[”"] by ([^:*]+?):?\*\*',md,re.M)]
@reg('Time Out: The Ten Best Films of 2024')
def _(s,h,md):
    return [(C(m.group(1)),'') for m in re.finditer(r'^\d{1,2}\.\s+\*([^*]+)\*\s*$',md,re.M)]
@reg('Rotten Tomatoes: Golden Tomato Awards 2024 Winners')
def _(s,h,md):
    out=[];cat=''
    for l in md_lines(md):
        m=re.match(r'^\*\*(Best [^*]+?)$',l) or re.match(r'^\*\*(Best [^*]+?)\*\*$',l)
        if m: cat=C(m.group(1)); continue
        m=re.match(r'^## \*\*(Best .+?)\*\*$',l)
        if m: cat=C(m.group(1)); continue
        m=re.match(r'^\d{1,2}\.\s+\*([^*]+)\*\s*[–-]\s*WINNER',l) or re.match(r'^\*\*(.+?)\s*[–-]\s*GOLDEN TOMATO WINNER\*\*$',l)
        if m: out.append((C(m.group(1)).title() if C(m.group(1)).isupper() else C(m.group(1)),cat))
    return out
@reg("Tom's Guide Awards 2024")
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^- \*\*([^*]+?):\*\*\s*(.+)$',md,re.M): out.append((unstar(m.group(2)),C(m.group(1))))
    return out
@reg('Lonely Planet: Best in Travel 2024 Destinations Revealed','Time Out: The 50 Best Cities in the World for 2024')
def _(s,h,md):
    out=[];cat=''
    for l in md_lines(md):
        m=re.match(r'^\*\*([^*]{3,40}?):?\*\*$',l)
        if m: cat=C(m.group(1)); continue
        m=re.match(r'^(\d{1,2})\.\s+(.{2,80})$',l)
        if m: out.append((unstar(m.group(2)),cat))
    return out
@reg("The World's 50 Best Bars 2024","North America's 50 Best Bars 2024",'World\'s 50 Best Bars 2024')
def _(s,h,md):
    out={}
    for m in re.finditer(r'^\|\s*(\d{1,3})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|',md,re.M): out.setdefault(int(m.group(1)),(C(m.group(2)),C(m.group(3))))
    if not out:
        L=md_lines(md)
        for k,l in enumerate(L):
            m=re.match(r'^\*\*No\.\s*(\d{1,3})\s+(.+?)(?:\s+[–-]\s+[A-Z -]+)?\*\*\s*(.*)$',l)
            if m:
                city=C(m.group(3)) or (L[k+1] if k+1<len(L) and len(L[k+1])<40 and not L[k+1].startswith('@') else '')
                out.setdefault(int(m.group(1)),(C(m.group(2)),C(city)))
    return [out[k] for k in sorted(out)]
@reg('The Guardian: The Best Graphic Novels of 2024')
def _(s,h,md):
    return uniq([(C(m.group(1)),'') for m in re.finditer(r'\*\*([^*]{2,80})\*\*\s*\(',md)])
@reg('NPR: Favorite Cookbooks of 2024')
def _(s,h,md):
    return [(C(m.group(1)),C(m.group(2))) for m in re.finditer(r'^\*([^*]+)\* by (.+)$',md,re.M)]
@reg('Allure: Best of Beauty 2024 Winners')
def _(s,h,md):
    out=[];cat=''
    for l in md_lines(md):
        if l.startswith('## '): cat=unstar(l[3:]); continue
        if l.startswith('- '): out.append((unstar(l[2:]),cat))
    return out
@reg('Billboard: Year-End Hot 100 Songs 2024','Billboard: Year-End Billboard 200 Albums 2024')
def _(s,h,md):
    out=[]
    for r in s.select('.o-chart-results-list-row-container'):
        t=r.select_one('h3#title-of-a-story')
        if not t: continue
        a=t.find_next_sibling('span')
        out.append((C(t.get_text(' ',strip=True)),C(a.get_text(' ',strip=True)) if a else ''))
    return out
@reg('Library Journal: Best Graphic Novels of 2024')
def _(s,h,md):
    out=[]
    for m in re.finditer(r'^([A-Z][^.*\n]{1,40}?, [A-Z][^.*\n]{1,40}?)\. \*\*(.+?)\.?\*\*',md,re.M):
        a=m.group(1); last,_,first=a.partition(', ')
        out.append((C(m.group(2).rstrip('.')),C(f'{first} {last}')))
    return out
@reg('Spiel des Jahres: Award Winners 2024','Spiel des Jahres 2024 Winners')
def _(s,h,md):
    out=[];cat=None
    for l in md_lines(md):
        m=re.match(r'^##+ \**((?:Spiel|Kennerspiel|Kinderspiel) des Jahres 2024)\**$',l)
        if m: cat=C(m.group(1)); continue
        if l.startswith('#'): cat=None; continue
        m=re.match(r'^\*\*(.+?) by (.+?)\*\*',l)
        if cat and m: out.append((C(m.group(1)),f'{cat} – {C(m.group(2))}')); cat=None
    return out
