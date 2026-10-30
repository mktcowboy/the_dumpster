/* ============================================================
   CORE — data, helpers, router, shell, global search
   ============================================================ */
'use strict';

const RAW = JSON.parse(document.getElementById('site-data').textContent);
const TANAKH = JSON.parse(document.getElementById('tanakh-text').textContent);

const DATA = {
  works: (RAW.works || []).map(w => ({
    ...w,
    he: w.he || w.he_title || '',
    also: w.also || [],
    themes: w.themes || [],
    people: w.people || [],
    places: w.places || [],
    connections: w.connections || [],
    key_passages: w.key_passages || [],
    structure: w.structure || [],
    sources: w.sources || []
  })),
  people: (RAW.people || []).map(p => ({...p, works:p.works||[], places:p.places||[], themes:p.themes||[], connections:p.connections||[], sources:p.sources||[]})),
  places: (RAW.places || []).map(p => ({...p, works:p.works||[], people:p.people||[], themes:p.themes||[], connections:p.connections||[]})),
  themes: (RAW.themes || []).map(t => ({...t, works:t.works||[], people:t.people||[], places:t.places||[], connections:t.connections||[]})),
  timeline: RAW.timeline || [],
  essays: RAW.essays || [],
  pathways: RAW.pathways || [],
  corpora: RAW.corpora || [],
  map: RAW.map || {w:1000,h:750,paths:[]}
};

const BY = {work:new Map(), person:new Map(), place:new Map(), theme:new Map(), essay:new Map(), path:new Map()};
DATA.works.forEach(x=>BY.work.set(x.id,x));
DATA.people.forEach(x=>BY.person.set(x.id,x));
DATA.places.forEach(x=>BY.place.set(x.id,x));
DATA.themes.forEach(x=>BY.theme.set(x.id,x));
DATA.essays.forEach(x=>BY.essay.set(x.id,x));
DATA.pathways.forEach(x=>BY.path.set(x.id,x));

const COLORS = {
  work:'#d6b36a', person:'#cf7b55', place:'#83a98f', theme:'#b58cc4',
  tanakh:'#d6b36a', oral:'#cf7b55', commentary:'#83a98f', law:'#8fa2c9',
  philosophy:'#b58cc4', mysticism:'#67b0c4', prayer:'#d98fa3'
};
const CORPUS_NAMES = {tanakh:'Tanakh',oral:'Oral Torah',commentary:'Commentary',law:'Law',philosophy:'Philosophy',mysticism:'Mysticism',prayer:'Prayer'};
const DIVISION_NAMES = {torah:'Torah',neviim:"Nevi'im",ketuvim:'Ketuvim',mishnah:'Mishnah',talmud:'Talmud',midrash:'Midrash',commentary:'Commentary',code:'Code',philosophy:'Philosophy',kabbalah:'Kabbalah',liturgy:'Liturgy'};

const $ = (s,el=document)=>el.querySelector(s);
const $$ = (s,el=document)=>[...el.querySelectorAll(s)];
const esc = s => String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const strip = s => String(s||'').replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
const trunc = (s,n=160)=>{s=strip(s);return s.length>n?s.slice(0,n-1).replace(/\s+\S*$/,'')+'…':s;};
const slug = s => String(s||'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
const colorOf = c => COLORS[c] || COLORS.work;
const typeOf = id => BY.work.has(id)?'work':BY.person.has(id)?'person':BY.place.has(id)?'place':BY.theme.has(id)?'theme':null;
const labelOf = id => {const x=BY.work.get(id)||BY.person.get(id)||BY.place.get(id)||BY.theme.get(id);return x?(x.title||x.name):id;};
const heOf = id => {const x=BY.work.get(id)||BY.person.get(id)||BY.place.get(id)||BY.theme.get(id);return x?(x.he||x.he_name||x.he_title||''):'';};
const routeFor = (type,id) => ({work:`#/work/${id}`,person:`#/person/${id}`,place:`#/place/${id}`,theme:`#/idea/${id}`}[type]||'#/library');
const workColor = w => colorOf(w.corpus);
const corpusName = c => CORPUS_NAMES[c]||c||'';
const divisionName = d => DIVISION_NAMES[d]||d||'';
const fmt = n => new Intl.NumberFormat('en-US').format(n);
const todayKey = () => new Date().toISOString().slice(0,10);

function corpusCount(c){return DATA.works.filter(w=>c==='all'||w.corpus===c).length;}
function worksIn(corpus){return DATA.works.filter(w=>w.corpus===corpus);}

/* ---------- Tanakh reference resolution ---------- */
const BOOK_ALIASES = {
  'genesis':'genesis','gen':'genesis','exodus':'exodus','exod':'exodus','ex':'exodus','leviticus':'leviticus','lev':'leviticus',
  'numbers':'numbers','num':'numbers','deuteronomy':'deuteronomy','deut':'deuteronomy','joshua':'joshua','josh':'joshua',
  'judges':'judges','judg':'judges','samuel':'samuel','1 samuel':'samuel','2 samuel':'samuel','1samuel':'samuel','2samuel':'samuel',
  'kings':'kings','1 kings':'kings','2 kings':'kings','isaiah':'isaiah','isa':'isaiah','jeremiah':'jeremiah','jer':'jeremiah',
  'ezekiel':'ezekiel','ezek':'ezekiel','the twelve':'twelve','twelve':'twelve','hosea':'twelve','joel':'twelve','amos':'twelve',
  'obadiah':'twelve','jonah':'twelve','micah':'twelve','nahum':'twelve','habakkuk':'twelve','zephaniah':'twelve','haggai':'twelve',
  'zechariah':'twelve','malachi':'twelve','psalms':'psalms','psalm':'psalms','psa':'psalms','proverbs':'proverbs','prov':'proverbs',
  'job':'job','song of songs':'song','song':'song','ruth':'ruth','lamentations':'lamentations','lam':'lamentations',
  'ecclesiastes':'ecclesiastes','eccles':'ecclesiastes','esther':'esther','daniel':'daniel','dan':'daniel',
  'ezra':'ezra','nehemiah':'ezra','ezra-nehemiah':'ezra','chronicles':'chronicles','1 chronicles':'chronicles','2 chronicles':'chronicles'
};
const MULTI = {
  samuel:{parts:['1 Samuel','2 Samuel'],offsets:[0,31]},
  kings:{parts:['1 Kings','2 Kings'],offsets:[0,22]},
  ezra:{parts:['Ezra','Nehemiah'],offsets:[0,10]},
  chronicles:{parts:['1 Chronicles','2 Chronicles'],offsets:[0,29]},
  twelve:{parts:['Hosea','Joel','Amos','Obadiah','Jonah','Micah','Nahum','Habakkuk','Zephaniah','Haggai','Zechariah','Malachi'],offsets:[0,14,17,26,27,31,38,41,44,47,49,63]}
};
function bookNameFor(bookId,chapterIdx){
  const m=MULTI[bookId]; if(!m) return (BY.work.get(bookId)||{}).title||bookId;
  let i=0; for(let k=0;k<m.offsets.length;k++){if(chapterIdx>=m.offsets[k]) i=k;}
  return m.parts[i];
}
function globalChapter(bookId,partName,ch){
  const m=MULTI[bookId]; if(!m) return ch;
  const i=m.parts.indexOf(partName); return i<0?ch:m.offsets[i]+ch;
}
function parseRef(ref){
  const s=String(ref||'').replace(/[–—]/g,'-').replace(/\s+/g,' ').trim();
  // Book C1:V1-C2:V2 | Book C1-C2 | Book C:V-V | Book C
  const m=s.match(/^(.+?)\s+(\d+)(?::(\d+))?(?:\s*-\s*(?:(\d+):)?(\d+))?$/);
  if(!m) return null;
  const name=m[1].toLowerCase().replace(/^i /,'1 ').replace(/^ii /,'2 ');
  const bookId=BOOK_ALIASES[name]; if(!bookId) return null;
  const part=MULTI[bookId]?MULTI[bookId].parts.find(p=>p.toLowerCase()===name)||null:null;
  const c1=+m[2], v1=m[3]?+m[3]:null;
  let c2=c1, v2=null;
  if(m[4]!==undefined && m[5]!==undefined){ c2=+m[4]; v2=+m[5]; }
  else if(m[5]!==undefined){ v2=+m[5]; }
  else if(m[3]===undefined && m[5]!==undefined){ c2=+m[5]; }
  if(v1!==null && v2===null) v2=v1;
  return {bookId,part,c1,c2,v1,v2,raw:ref};
}
function resolveRef(ref){
  const p=parseRef(ref); if(!p) return null;
  const book=BY.work.get(p.bookId); if(!book) return null;
  const tbook=TANAKH.books.find(b=>b.id===p.bookId); if(!tbook) return null;
  const start=p.part?globalChapter(p.bookId,p.part,p.c1):p.c1;
  const end=p.part?globalChapter(p.bookId,p.part,p.c2):p.c2;
  if(!tbook.chapters[start-1]) return null;
  const out=[]; const plain=[];
  for(let gi=start;gi<=Math.min(end,tbook.chapters.length);gi++){
    const chapter=tbook.chapters[gi-1];
    const local=chapter.verses.filter(v=>{
      const n=parseInt(v.n,10); const endv=parseInt(String(v.n).split('-').pop(),10)||n;
      if(gi===start&&p.v1!==null&&endv<p.v1) return false;
      if(gi===end&&p.v2!==null&&n>p.v2) return false;
      return true;
    });
    if(local.length){
      out.push(local.map(v=>`<sup class="v">${esc(v.n)}</sup>${esc(v.t)}`).join(' '));
      plain.push(local.map(v=>v.t).join(' '));
    }
  }
  if(!out.length) return null;
  return {html:out.join('<span class="chsep"> · </span>'),plain:plain.join(' '),book:tbook,chapter:tbook.chapters[start-1],part:p.part,ch:p.c1,ref:ref};
}
function chapterCount(bookId){const b=TANAKH.books.find(x=>x.id===bookId);return b?b.chapters.length:0;}
function readerHref(bookId,ch=1,verse=null){return `#/read/${bookId}/${ch}${verse?'?v='+verse:''}`;}

/* ---------- verse index (lazy) ---------- */
let VERSE_INDEX=null;
function verseIndex(){
  if(VERSE_INDEX) return VERSE_INDEX;
  VERSE_INDEX=[];
  for(const b of TANAKH.books){
    b.chapters.forEach((c,ci)=>{
      const part=bookNameFor(b.id,ci+1);
      c.verses.forEach(v=>VERSE_INDEX.push({b:b.id,bt:b.title,c:ci+1,part,v:v.n,t:v.t}));
    });
  }
  return VERSE_INDEX;
}

/* ---------- router ---------- */
const routes = [
  [/^\/?$/, ()=>homeView()],
  [/^\/library/, (m,params)=>libraryView(params)],
  [/^\/work\/([^/]+)/, (m)=>workView(m[1])],
  [/^\/read\/([^/]+)(?:\/(\d+))?/, (m)=>readerView(m[1],m[2]?+m[2]:1)],
  [/^\/timeline/, ()=>timelineView()],
  [/^\/people/, ()=>peopleView()],
  [/^\/person\/([^/]+)/, (m)=>personView(m[1])],
  [/^\/places/, ()=>placesView()],
  [/^\/place\/([^/]+)/, (m)=>placeView(m[1])],
  [/^\/ideas/, ()=>ideasView()],
  [/^\/idea\/([^/]+)/, (m)=>ideaView(m[1])],
  [/^\/essays/, ()=>essaysView()],
  [/^\/essay\/([^/]+)/, (m)=>essayView(m[1])],
  [/^\/paths/, ()=>pathsView()],
  [/^\/path\/([^/]+)/, (m)=>pathView(m[1])],
  [/^\/graph/, ()=>graphView()],
  [/^\/sources/, ()=>sourcesView()],
  [/^\/about/, ()=>sourcesView()]
];
function parseHash(){
  const h=location.hash.replace(/^#/,'')||'/';
  const [path,q]=h.split('?');
  return {path,params:new URLSearchParams(q||'')};
}
function navigate(path){ if(('#'+path)===location.hash) render(); else location.hash=path; }
let CURRENT=null;
function render(){
  const {path,params}=parseHash();
  let view=null,match=null;
  for(const [re,fn] of routes){const m=path.match(re);if(m){view=fn;match=m;break;}}
  if(!view){ $('#main').innerHTML=notFoundView(); }
  else { $('#main').innerHTML=view(match,params); }
  CURRENT={path,params};
  updateNav(path);
  window.scrollTo({top:0,behavior:'instant'});
  document.body.classList.toggle('is-graph',path.startsWith('/graph'));
  afterRender(path,params);
  const h=$('#main h1'); if(h){h.setAttribute('tabindex','-1'); h.focus({preventScroll:true});}
}
function updateNav(path){
  const root='/'+path.split('/')[1];
  $$('.nav a').forEach(a=>{
    const r=a.getAttribute('data-route');
    a.classList.toggle('active', r===root || (root==='/'&&r==='/'));
  });
}

/* ---------- shell ---------- */
const ICONS={
  search:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  menu:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 6h18M3 12h18M3 18h18"/></svg>',
  close:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M5 5l14 14M19 5L5 19"/></svg>',
  arrow:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  chain:'<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.1"><circle cx="16" cy="6" r="2.6"/><circle cx="7" cy="20" r="2.6"/><circle cx="25" cy="20" r="2.6"/><circle cx="16" cy="27" r="2.6"/><path d="M16 8.6v16M8.7 21.6l5.7-3.2M23.3 21.6l-5.7-3.2"/></svg>',
  random:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M16 3h5v5M4 20 21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/></svg>'
};
function shell(){
  document.body.insertAdjacentHTML('afterbegin',`
  <a class="skip" href="#main">Skip to content</a>
  <header class="topbar">
    <div class="wrap">
      <a class="brand" href="#/" aria-label="The Chain of Tradition, home">
        <span class="brand-mark">${ICONS.chain}</span>
        <span class="brand-text"><b>The Chain of Tradition</b><span>An atlas of the Jewish library</span></span>
      </a>
      <nav class="nav" aria-label="Main">
        <a href="#/library" data-route="/library">Library</a>
        <a href="#/graph" data-route="/graph">Map</a>
        <a href="#/timeline" data-route="/timeline">Timeline</a>
        <a href="#/people" data-route="/people">People</a>
        <a href="#/places" data-route="/places">Places</a>
        <a href="#/ideas" data-route="/ideas">Ideas</a>
        <a href="#/essays" data-route="/essays">Essays</a>
        <a href="#/read/genesis/1" data-route="/read">Reader</a>
      </nav>
      <div class="top-actions">
        <button class="search-btn" id="search-open" aria-label="Search the atlas">${ICONS.search}<span>Search</span><kbd>⌘K</kbd></button>
        <button class="icon-btn" id="random-btn" aria-label="Open a random passage" title="Open a random passage">${ICONS.random}</button>
        <button class="icon-btn menu-btn" id="menu-btn" aria-label="Menu">${ICONS.menu}</button>
      </div>
    </div>
  </header>
  <div id="progress" class="progress-bar"></div>
  <main id="main"></main>
  <footer class="footer">
    <div class="wrap">
      <div class="footer-grid">
        <div>
          <div class="fbrand">The Chain of Tradition</div>
          <div class="fhe">שַׁלְשֶׁלֶת הַקַּבָּלָה</div>
          <p class="fnote">A linked atlas of the Tanakh, the Oral Torah, and the library that grew around them. Built as a single, self-contained page.</p>
        </div>
        <div><h4>The Library</h4><ul>
          <li><a href="#/library?corpus=tanakh">Tanakh</a></li>
          <li><a href="#/library?corpus=oral">Oral Torah</a></li>
          <li><a href="#/library?corpus=commentary">Commentary</a></li>
          <li><a href="#/library?corpus=law">Law</a></li>
          <li><a href="#/library?corpus=philosophy">Philosophy</a></li>
          <li><a href="#/library?corpus=mysticism">Mysticism</a></li>
          <li><a href="#/library?corpus=prayer">Prayer</a></li>
        </ul></div>
        <div><h4>Ways In</h4><ul>
          <li><a href="#/paths">Guided paths</a></li>
          <li><a href="#/graph">The constellation</a></li>
          <li><a href="#/timeline">Timeline</a></li>
          <li><a href="#/people">People</a></li>
          <li><a href="#/places">Places</a></li>
          <li><a href="#/ideas">Ideas</a></li>
        </ul></div>
        <div><h4>About</h4><ul>
          <li><a href="#/sources">Sources & method</a></li>
          <li><a href="#/essays">Essays</a></li>
          <li><a href="#/read/genesis/1">Read the Tanakh</a></li>
        </ul>
        <p class="fnote" style="margin-top:1.2rem">JPS 1917 translation, public domain. Built for study, not as a substitute for a living tradition.</p>
        </div>
      </div>
      <div class="footer-bottom"><span>24 books · 929 chapters · 23,145 verses</span><span>Inherited, argued, and still being read</span></div>
    </div>
  </footer>
  <div class="overlay" id="search-overlay" role="dialog" aria-modal="true" aria-label="Search">
    <div class="search-panel">
      <div class="search-head">${ICONS.search}<input id="search-input" placeholder="Search the library, people, places, ideas, verses…" autocomplete="off" spellcheck="false"><kbd>ESC</kbd></div>
      <div class="search-results" id="search-results"></div>
      <div class="search-foot"><span>↑↓ to move</span><span>↵ to open</span><span>Type at least 3 letters to search verses</span></div>
    </div>
  </div>
  <div class="toast" id="toast"></div>
  `);
}

/* ---------- global search ---------- */
let searchSel=0, searchItems=[];
function openSearch(prefill=''){
  const ov=$('#search-overlay'); ov.classList.add('open');
  const inp=$('#search-input'); inp.value=prefill; setTimeout(()=>inp.focus(),30);
  runSearch(prefill);
}
function closeSearch(){ $('#search-overlay').classList.remove('open'); }
function searchCorpus(type,items,q){
  const ql=q.toLowerCase();
  return items.map(x=>{
    const title=(x.title||x.name||'').toLowerCase();
    const he=(x.he||x.he_name||x.he_title||'').toLowerCase();
    const body=strip(x.summary||x.bio||x.short||x.essay||x.dek||'').toLowerCase();
    let score=0;
    if(title===ql) score=100; else if(title.startsWith(ql)) score=80; else if(title.includes(ql)) score=55;
    else if(he.includes(ql)) score=45; else if(body.includes(ql)) score=25;
    if(!score) return null;
    return {...x,_type:type,_score:score};
  }).filter(Boolean).sort((a,b)=>b._score-a._score).slice(0,6);
}
function runSearch(q){
  const res=$('#search-results'); q=(q||'').trim();
  searchSel=0; searchItems=[];
  if(!q){ res.innerHTML=`<div class="sr-group"><div class="sr-label">Try</div>${['covenant','Rashi','Talmud','Jerusalem','exile','shabbat','Maimonides'].map(t=>`<div class="sr-item" data-q="${t}"><span class="st" style="--c:var(--gold)"></span><b>${t}</b><span>search</span></div>`).join('')}</div>`; bindSearchItems(); return; }
  const groups=[
    ['Works',searchCorpus('work',DATA.works,q)],
    ['People',searchCorpus('person',DATA.people,q)],
    ['Places',searchCorpus('place',DATA.places,q)],
    ['Ideas',searchCorpus('theme',DATA.themes,q)],
    ['Essays',searchCorpus('essay',DATA.essays,q)],
    ['Paths',searchCorpus('path',DATA.pathways,q)]
  ];
  let html='';
  for(const [label,items] of groups){
    if(!items.length) continue;
    html+=`<div class="sr-group"><div class="sr-label">${label}</div>`+
      items.map(x=>{
        const type=x._type; const href=routeFor(type,x.id)||`#/essay/${x.id}`;
        searchItems.push({href,label:x.title||x.name,type});
        return `<a class="sr-item" href="${href}" data-idx="${searchItems.length-1}"><span class="st" style="--c:${colorOf(x.corpus||type)}"></span><b>${esc(x.title||x.name)}</b>${x.he?`<span class="she">${esc(x.he||x.he_name||'')}</span>`:''}<span>${esc(trunc(x.summary||x.bio||x.short||x.dek||'',90))}</span></a>`;
      }).join('')+'</div>';
  }
  if(q.length>=3){
    const ql=q.toLowerCase(); const hits=[];
    for(const v of verseIndex()){
      if(v.t.toLowerCase().includes(ql)){hits.push(v); if(hits.length>=8) break;}
    }
    if(hits.length){
      html+=`<div class="sr-group"><div class="sr-label">Verses</div>`+hits.map(v=>{
        const href=`#/read/${v.b}/${v.c}?v=${encodeURIComponent(v.v)}`;
        searchItems.push({href,label:`${v.part} ${v.c}:${v.v}`,type:'verse'});
        return `<a class="sr-item" href="${href}" data-idx="${searchItems.length-1}"><span class="st" style="--c:var(--tanakh)"></span><b>${esc(v.part)} ${v.c}:${v.v}</b><span>${esc(trunc(v.t,100))}</span></a>`;
      }).join('')+'</div>';
    }
  }
  if(!html) html=`<div class="sr-group"><div class="sr-label">No results</div><div class="sr-item"><b>Nothing found for “${esc(q)}”</b></div></div>`;
  res.innerHTML=html; bindSearchItems(); markSearchSel();
}
function bindSearchItems(){
  $$('.sr-item', $('#search-results')).forEach(el=>{
    el.addEventListener('click',e=>{ if(el.dataset.q){e.preventDefault();$('#search-input').value=el.dataset.q;runSearch(el.dataset.q);} });
  });
}
function markSearchSel(){
  $$('.sr-item',$('#search-results')).forEach(el=>el.classList.remove('sel'));
  const items=$$('.sr-item[data-idx]',$('#search-results'));
  if(items[searchSel]) items[searchSel].classList.add('sel');
}
function moveSearch(d){
  const items=$$('.sr-item[data-idx]',$('#search-results')); if(!items.length)return;
  searchSel=(searchSel+d+items.length)%items.length; markSearchSel();
  items[searchSel].scrollIntoView({block:'nearest'});
}
function goSearch(){
  const items=$$('.sr-item[data-idx]',$('#search-results'));
  if(items[searchSel]){ location.hash=items[searchSel].getAttribute('href'); closeSearch(); }
}

/* ---------- toast / random ---------- */
let toastT;
function toast(msg){const t=$('#toast');t.textContent=msg;t.classList.add('on');clearTimeout(toastT);toastT=setTimeout(()=>t.classList.remove('on'),2200);}
function randomPassage(){
  const b=TANAKH.books[Math.floor(Math.random()*TANAKH.books.length)];
  const c=b.chapters[Math.floor(Math.random()*b.chapters.length)];
  const v=c.verses[Math.floor(Math.random()*c.verses.length)];
  const html=`<div class="overlay open" id="random-overlay" role="dialog" aria-modal="true"><div class="search-panel random-card" style="position:relative;padding:3rem 2.4rem">
    <button class="modal-close" onclick="this.closest('.overlay').remove()">×</button>
    <div class="eyebrow no-rule center" style="justify-content:center">Open at random</div>
    <div class="rtext">“${esc(v.t)}”</div>
    <div class="rref">${esc(bookNameFor(b.id,c.n))} ${c.n}:${v.n}</div>
    <div style="margin-top:2rem;display:flex;gap:.7rem;justify-content:center;flex-wrap:wrap">
      <a class="btn sm" href="${readerHref(b.id,c.n)}">Read the chapter</a>
      <button class="btn sm ghost" onclick="randomPassage()">Another</button>
    </div></div></div>`;
  const old=$('#random-overlay'); if(old) old.remove();
  document.body.insertAdjacentHTML('beforeend',html);
}

/* ---------- after render ---------- */
function afterRender(path,params){
  // reveal
  const io=new IntersectionObserver(ents=>ents.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}}),{rootMargin:'0px 0px -8% 0px'});
  $$('.reveal').forEach(el=>io.observe(el));
  // reader sidebar
  $$('.rs-book>button').forEach(btn=>btn.addEventListener('click',()=>btn.parentElement.classList.toggle('on')));
  // reader progress
  if(path.startsWith('/read')){
    const bar=$('#progress');
    const upd=()=>{const h=document.documentElement;const max=h.scrollHeight-h.clientHeight;bar.style.width=(max>0?h.scrollTop/max*100:0)+'%';};
    window.removeEventListener('scroll',upd);window.addEventListener('scroll',upd,{passive:true});upd();
    if(params.get('v')){const el=$('#v'+CSS.escape(params.get('v')));if(el){el.classList.add('target');setTimeout(()=>el.scrollIntoView({block:'center'}),120);}}
  } else { const bar=$('#progress'); if(bar) bar.style.width='0'; }
  // library filter
  if(path.startsWith('/library')) bindLibrary();
  // reader settings
  if(path.startsWith('/read')){
    const saved=parseFloat(localStorage.getItem('readerSize')||'0'); const vs=$('#verses'); if(saved&&vs) vs.style.fontSize=saved+'px';
    const st=$('#side-toggle'); if(st){st.style.display='inline-block';st.addEventListener('click',()=>$('#reader-side').classList.toggle('open'));}
  }
  // init graph
  if(path.startsWith('/graph')) initGraph();
  // init map pins
  $$('.pin[data-id]').forEach(p=>p.addEventListener('click',()=>{location.hash='#/place/'+p.dataset.id;}));
}
function notFoundView(){return `<div class="page wrap"><div class="empty"><h2>This page is not in the library.</h2><p><a class="btn" href="#/">Return to the beginning</a></p></div></div>`;}

/* ---------- shared view fragments ---------- */
function breadcrumb(items){return `<div class="breadcrumb">${items.map((x,i)=>`${i?'<span class="sep">/</span>':''}${x.href?`<a href="${x.href}">${esc(x.label)}</a>`:`<span>${esc(x.label)}</span>`}`).join('')}</div>`;}
function tagFor(type,id,label=null){
  const t=type||typeOf(id); const color=type==='work'?colorOf((BY.work.get(id)||{}).corpus):COLORS[t]||COLORS.work;
  return `<a class="tag" href="${routeFor(t,id)}" style="--c:${color}"><span class="dot"></span>${esc(label||labelOf(id))}</a>`;
}
function chipLink(id){
  const t=typeOf(id); if(!t) return '';
  return `<a class="chip" href="${routeFor(t,id)}"><span class="dot" style="--c:${type==='work'?colorOf(BY.work.get(id).corpus):COLORS[t]}"></span>${esc(labelOf(id))}</a>`;
}
function workCard(w){
  return `<a class="cover" href="#/work/${w.id}" style="--c:${workColor(w)}">
    <span class="c-corpus">${esc(corpusName(w.corpus))}</span>
    <span class="c-he he">${esc(w.he||'')}</span>
    <span class="c-title">${esc(w.title)}</span>
    <span class="c-date">${esc(w.date||'')}</span>
    <span class="c-num">${String(w.order||'').padStart(2,'0')}</span>
  </a>`;
}
function personCard(p){
  return `<a class="person-card" href="#/person/${p.id}" style="--c:${COLORS.person}">
    <span class="medallion">${esc((p.he_name||p.name||'?').replace(/[^\u0590-\u05FF]/g,'').slice(0,1)||p.name.slice(0,1))}</span>
    <span><span class="pd">${esc(p.era||'')}${p.dates?' · '+esc(p.dates):''}</span><h4>${esc(p.name)}</h4><p>${esc(trunc(p.key_idea||p.bio||'',92))}</p></span>
  </a>`;
}
function ideaCard(t){
  return `<a class="idea-card" href="#/idea/${t.id}">
    <span class="ihe he">${esc(t.he_name||'')}</span>
    <h4>${esc(t.name)}</h4>
    <p>${esc(t.short||'')}</p>
    <span class="ik">${esc(t.kind||'idea')}</span>
  </a>`;
}
function placeCard(p){
  return `<a class="place-card" href="#/place/${p.id}">
    <h4>${esc(p.name)}</h4>
    <div class="pr">${esc(p.region||'')}</div>
    <p>${esc(trunc(p.bio||'',140))}</p>
  </a>`;
}
function essayRow(e,i){
  return `<a class="essay-row" href="#/essay/${e.id}"><span class="en">${String(i+1).padStart(2,'0')}</span><span><h3>${esc(e.title)}</h3><p>${esc(e.dek||'')}</p></span><span class="ea">Read essay →</span></a>`;
}
