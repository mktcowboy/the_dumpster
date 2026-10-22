/* ============================================================
   VIEWS
   ============================================================ */

/* ---------------- HOME ---------------- */
function homeView(){
  const tanakh=worksIn('tanakh').sort((a,b)=>a.order-b.order);
  const groups=[['torah',"Torah",'תּוֹרָה'],['neviim',"Nevi'im",'נְבִיאִים'],['ketuvim','Ketuvim','כְּתוּבִים']];
  const maxCh=Math.max(...tanakh.map(w=>chapterCount(w.id)));
  const spines=groups.map(([div,name,he])=>{
    const ws=tanakh.filter(w=>w.division===div);
    return `<div class="spine-group" style="--c:${COLORS.tanakh}">
      <div class="spine-set">${ws.map(w=>{const h=100+Math.round((chapterCount(w.id)/maxCh)*245);return `<div class="spine" style="--c:${COLORS.tanakh};height:${h}px" title="${esc(w.title)} · ${chapterCount(w.id)} chapters" data-href="#/work/${w.id}"><em>${esc(w.he.replace(/[^\u0590-\u05FF]/g,'').slice(0,10))}</em></div>`;}).join('')}</div>
      <div class="sg-label"><b>${name}</b>${ws.length} books</div>
    </div>`;
  }).join('');

  const layers=[
    {n:'01',name:'Tanakh',he:'תַּנַ״ךְ',c:'tanakh',count:24,desc:'The Hebrew Bible in twenty-four books: Teaching, Prophets, Writings. The core to which everything else returns.',items:['Torah — 5 books','Nevi’im — 8 books','Ketuvim — 11 books','929 chapters']},
    {n:'02',name:'Oral Torah',he:'תּוֹרָה שֶׁבְּעַל פֶּה',c:'oral',count:11,desc:'The Mishnah, the two Talmuds, and Midrash: the text as it is argued, lived, and imagined.',items:['Mishnah — 6 orders','Talmud Bavli','Talmud Yerushalmi','Midrash & Pirkei Avot']},
    {n:'03',name:'Commentary & Law',he:'פֵּרוּשׁ וַהֲלָכָה',c:'commentary',count:3,desc:'Rashi on the page, Maimonides’ code, Karo’s set table: the apparatus that made the library usable.',items:['Rashi on the Torah','Mishneh Torah','Shulchan Aruch']},
    {n:'04',name:'Philosophy, Mysticism, Prayer',he:'מַחְשָׁבָה וְתְפִלָּה',c:'philosophy',count:4,desc:'Reason, the hidden life of the text, and the book most Jews actually hold in their hands.',items:['Guide for the Perplexed','Kuzari','Zohar','Siddur']}
  ];
  const paths=DATA.pathways.slice(0,6);
  const essays=DATA.essays.slice(0,3);
  const last=(()=>{try{return JSON.parse(localStorage.getItem('lastRead')||'null')}catch(e){return null}})();
  return `<section class="hero"><div class="wrap"><div class="hero-grid">
    <div>
      <div class="hero-kicker"><i></i><span>An atlas of the Jewish library</span></div>
      <h1>The Chain<span class="l2">of Tradition</span></h1>
      <p class="lede">Twenty-four books. Six orders of Mishnah. Two Talmuds. A commentary on every page. This is the library that grew from Sinai — and the argument that keeps it alive.</p>
      <div class="hero-cta"><a class="btn solid" href="#/library">Enter the library ${ICONS.arrow}</a><a class="btn ghost" href="#/graph">See the constellation</a></div>
      <div class="hero-meta">
        <div><b>24</b><span>books of Tanakh</span></div>
        <div><b>${fmt(TANAKH.stats.chapters)}</b><span>chapters</span></div>
        <div><b>${fmt(TANAKH.stats.verses)}</b><span>verses</span></div>
        <div><b>${DATA.works.length}</b><span>works mapped</span></div>
      </div>
    </div>
    <div class="spines" aria-label="The twenty-four books of the Tanakh">${spines}</div>
  </div></div></section>

  <section class="section"><div class="wrap">
    <div class="section-head"><div><div class="eyebrow">The shape of the library</div><h2>Four layers, one argument</h2></div><p class="lede">The canon is not a shelf of equal books. It is a hierarchy of proximity to revelation — and a set of tools for reading it.</p></div>
    <div class="layer-stack">${layers.map(l=>`<div class="layer" style="--c:${COLORS[l.c]}"><span class="bar"></span><span class="lnum">${l.n}</span><div class="he">${l.he}</div><h4>${esc(l.name)}</h4><p>${esc(l.desc)}</p><ul>${l.items.map(i=>`<li>${esc(i)}</li>`).join('')}</ul></div>`).join('')}</div>
  </div></section>

  <section class="section"><div class="wrap">
    <div class="section-head"><div><div class="eyebrow">Ways in</div><h2>Begin anywhere</h2></div><p class="lede">Seven guided trails through the library, each answering a question rather than covering a syllabus.</p></div>
    <div class="path-grid">${paths.map((p,i)=>`<a class="path-card" href="#/path/${p.id}"><span class="pnum">Path ${String(i+1).padStart(2,'0')}</span><h3>${esc(p.title)}</h3><p>${esc(p.dek||'')}</p><span class="pfoot">Follow the trail →</span><span class="arrow">${ICONS.arrow}</span></a>`).join('')}</div>
    ${last?`<div style="margin-top:1.4rem"><a class="card" style="display:flex;justify-content:space-between;align-items:center;gap:1rem" href="#/read/${last.book}/${last.ch}"><span><span class="tiny">Continue reading</span><br><b style="font-family:var(--display);font-size:1.4rem;font-weight:400">${esc(last.label||'')}</b></span><span class="btn sm ghost">Open ${ICONS.arrow}</span></a></div>`:''}
  </div></section>

  <section class="section"><div class="wrap">
    <div class="section-head"><div><div class="eyebrow">The canon</div><h2>Twenty-four books</h2></div><p class="lede">Jews count the same content as the Protestant Old Testament, but arrange it differently: the Prophets close with the Twelve, and the Writings end with Chronicles returning to Adam.</p></div>
    <div class="canon-cols">${groups.map(([div,name,he])=>{const ws=tanakh.filter(w=>w.division===div);return `<div class="canon-col"><h4>${name}</h4><div class="he">${he}</div><p>${div==='torah'?'The Five Books of Moses: the direct revelation at Sinai, the holiest part of the library.':div==='neviim'?'The Former Prophets tell the story from Joshua to the fall of Jerusalem; the Latter Prophets speak into that story.':'Psalms, wisdom, the five scrolls, Daniel, and the historiographical retelling that ends with a genealogy back to Adam.'}</p><ul class="book-list">${ws.map(w=>`<li><a href="#/work/${w.id}"><span class="bt">${esc(w.title)}</span><span class="bh">${esc(w.he)}</span></a></li>`).join('')}</ul></div>`;}).join('')}</div>
  </div></section>

  <section class="quote-band"><div class="wrap"><blockquote>“Moses received the Torah at Sinai and transmitted it to Joshua, and Joshua to the elders, and the elders to the prophets, and the prophets to the Men of the Great Assembly.”</blockquote><cite>Pirkei Avot 1:1 · the chain that authorizes the library</cite></div></section>

  <section class="section"><div class="wrap">
    <div class="section-head"><div><div class="eyebrow">The argument</div><h2>Why it is shaped this way</h2></div><p class="lede">Ten essays on canon, commentary, law, reason, mysticism, and the book in the hand.</p></div>
    <div class="essay-list">${essays.map((e,i)=>essayRow(e,i)).join('')}</div>
    <div style="margin-top:2rem"><a class="btn ghost" href="#/essays">All ten essays ${ICONS.arrow}</a></div>
  </div></section>`;
}

/* ---------------- LIBRARY ---------------- */
function libraryView(params){
  const corpus=params.get('corpus')||'all';
  const order=['tanakh','oral','commentary','law','philosophy','mysticism','prayer'];
  const groups=corpus==='all'?order:[corpus];
  const counts=DATA.corpora.map(c=>({...c,n:corpusCount(c.id)}));
  const filters=`<div class="filters"><div class="wrap"><div class="filter-row">
    <div class="chips"><a class="chip ${corpus==='all'?'on':''}" href="#/library">All <span style="color:var(--faint)">${DATA.works.length}</span></a>
    ${counts.map(c=>`<a class="chip ${corpus===c.id?'on':''}" href="#/library?corpus=${c.id}"><span class="dot" style="--c:${COLORS[c.id]}"></span>${esc(c.name)} <span style="color:var(--faint)">${c.n}</span></a>`).join('')}</div>
    <div class="search-inline">${ICONS.search}<input id="lib-search" placeholder="Filter titles…" aria-label="Filter titles"></div>
    <span class="result-count" id="lib-count">${DATA.works.length} works</span>
  </div></div></div>`;
  let body='';
  for(const c of groups){
    const ws=DATA.works.filter(w=>w.corpus===c).sort((a,b)=>(a.order||0)-(b.order||0));
    if(!ws.length) continue;
    const meta=DATA.corpora.find(x=>x.id===c)||{name:c,he:'',blurb:''};
    body+=`<section class="library-group" data-corpus="${c}" style="margin-bottom:3.4rem">
      <div class="section-head" style="margin-bottom:1.4rem"><div><div class="eyebrow">${esc(meta.name)}</div><h2 style="font-size:clamp(1.8rem,3.4vw,2.7rem)">${esc(meta.he||'')}</h2></div><p class="muted" style="max-width:460px">${esc(meta.blurb||'')}</p></div>
      ${c==='tanakh'?[['torah','Torah','The Five Books of Moses'],['neviim',"Nevi'im",'The Prophets'],['ketuvim','Ketuvim','The Writings']].map(([d,n,b])=>`<div class="hr-label" style="margin-top:2rem"><span>${n} · ${ws.filter(w=>w.division===d).length}</span></div><div class="covers">${ws.filter(w=>w.division===d).map(workCard).join('')}</div>`).join(''):`<div class="covers">${ws.map(workCard).join('')}</div>`}
    </section>`;
  }
  return `<div class="page"><div class="wrap" style="padding-top:2rem">
    <div class="eyebrow">The library</div><h1 style="font-size:clamp(2.6rem,6vw,5rem);margin-bottom:.6rem">Every book in the chain</h1>
    <p class="lede" style="max-width:720px;margin-bottom:2.4rem">Forty-two works, from the five books of Moses to the prayerbook in the hand. The Tanakh is here in full; the rest are mapped with their structure, arguments, and essential passages.</p>
  </div>${filters}<div class="wrap">${body}<div class="empty" id="lib-empty" style="display:none">No works match that filter.</div></div></div>`;
}
function bindLibrary(){
  const inp=$('#lib-search'); if(!inp) return;
  const apply=()=>{
    const q=inp.value.toLowerCase().trim(); let n=0;
    $$('.library-group').forEach(g=>{
      let shown=0;
      $$('.cover',g).forEach(c=>{
        const txt=c.textContent.toLowerCase();
        const ok=!q||txt.includes(q);
        c.style.display=ok?'':'none'; if(ok){shown++;n++;}
      });
      g.style.display=shown?'':'none';
    });
    const cnt=$('#lib-count'); if(cnt) cnt.textContent=n+' works';
    const empty=$('#lib-empty'); if(empty) empty.style.display=n?'none':'block';
  };
  inp.addEventListener('input',apply);
}

/* ---------------- WORK ---------------- */
function workView(id){
  const w=BY.work.get(id); if(!w) return notFoundView();
  const c=workColor(w);
  const isTanakh=w.corpus==='tanakh';
  const passages=(w.key_passages||[]).map(p=>{
    let html='', ref=p.ref||'', src=p.source||'';
    if(p.text){ html=`<div class="ptext">“${esc(p.text)}”</div>`; }
    else if(p.ref){ const r=resolveRef(p.ref); if(r){html=`<div class="ptext">“${r.html}”</div>`;} }
    return `<div class="passage" style="--c:${c}"><div class="pref">${esc(ref)}${src?' · '+esc(src):''}</div>${html||'<div class="ptext muted">Passage unavailable.</div>'}<div class="pnote">${esc(p.note||'')}${isTanakh&&ref?` · <a href="${refLink(ref)}" style="color:var(--gold)">Open in reader →</a>`:''}</div></div>`;
  }).join('');
  const conns=(w.connections||[]).filter(x=>typeOf(x.to)).map(x=>{
    const t=typeOf(x.to); const col=t==='work'?colorOf(BY.work.get(x.to).corpus):COLORS[t];
    return `<a class="conn" href="${routeFor(t,x.to)}"><span class="cdot" style="--c:${col}"></span><span><b>${esc(labelOf(x.to))}</b><span>${esc(x.why)}</span></span></a>`;
  }).join('');
  const paths=DATA.pathways.filter(p=>(p.stops||[]).some(s=>s.work===w.id));
  const themeLinks=(w.themes||[]).map(id=>BY.theme.get(id)).filter(Boolean);
  const peopleLinks=(w.people||[]).map(id=>BY.person.get(id)).filter(Boolean);
  const placeLinks=(w.places||[]).map(id=>BY.place.get(id)).filter(Boolean);
  return `<div class="page" style="padding-top:84px">
    <div class="work-hero" style="--c:${c}"><div class="ghost-he">${esc(w.he||'')}</div><div class="wrap">
      ${breadcrumb([{label:'Library',href:'#/library'},{label:corpusName(w.corpus),href:'#/library?corpus='+w.corpus},{label:w.title}])}
      <div class="work-hero-grid"><div>
        <div class="corpus-badge"><span class="dot"></span>${esc(corpusName(w.corpus))} · ${esc(divisionName(w.division))}</div>
        <h1>${esc(w.title)}</h1>
        <div class="he-title he">${esc(w.he||'')}</div>
        <p class="lede" style="max-width:700px">${esc(w.summary||'')}</p>
        <div class="work-meta"><span><b>Date</b> ${esc(w.date||'—')}</span><span><b>Language</b> ${esc(w.language||'—')}</span>${isTanakh?`<span><b>Chapters</b> ${chapterCount(w.id)}</span><span><b>Verses</b> ${fmt((TANAKH.books.find(b=>b.id===w.id)||{}).verses||0)}</span>`:''}</div>
        <div class="hero-cta">${isTanakh?`<a class="btn solid" href="#/read/${w.id}/1">Read the full book ${ICONS.arrow}</a>`:''}${(w.sources&&w.sources[0])?`<a class="btn ghost" href="${esc(w.sources[0].url)}" target="_blank" rel="noopener">Source</a>`:''}</div>
      </div></div>
    </div></div>
    <div class="wrap"><div class="work-body"><div class="split"><div>
      <div class="hr-label"><span>Why it matters</span></div>
      <div class="prose"><p>${esc(w.why||'')}</p></div>
      ${(w.structure||[]).length?`<div class="hr-label"><span>How it is built</span></div><ul class="struct-list">${w.structure.map(s=>`<li><span class="sn">${esc(s.name)}</span><span class="sd">${esc(s.note||'')}</span></li>`).join('')}</ul>`:''}
      ${passages?`<div class="hr-label"><span>Passages to begin with</span></div>${passages}`:''}
      ${conns?`<div class="hr-label"><span>Connections</span></div><div class="conn-grid">${conns}</div>`:''}
      ${(w.sources||[]).length?`<div class="hr-label"><span>Sources</span></div><ul class="side-list">${w.sources.map(s=>`<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)}</a></li>`).join('')}</ul>`:''}
    </div><aside class="sidebar">
      <div class="side-block"><h4>At a glance</h4><ul class="side-list">
        <li><span>Corpus</span><span style="margin-left:auto">${esc(corpusName(w.corpus))}</span></li>
        <li><span>Division</span><span style="margin-left:auto">${esc(divisionName(w.division))}</span></li>
        <li><span>Date</span><span style="margin-left:auto;text-align:right;max-width:60%">${esc(w.date||'—')}</span></li>
        <li><span>Language</span><span style="margin-left:auto;text-align:right;max-width:60%">${esc(w.language||'—')}</span></li>
      </ul></div>
      ${themeLinks.length?`<div class="side-block"><h4>Ideas</h4><div class="chips">${themeLinks.map(t=>`<a class="chip" href="#/idea/${t.id}">${esc(t.name)}</a>`).join('')}</div></div>`:''}
      ${peopleLinks.length?`<div class="side-block"><h4>People</h4><ul class="side-list">${peopleLinks.map(p=>`<li><a href="#/person/${p.id}">${esc(p.name)}</a><span class="he">${esc(p.he_name||'')}</span></li>`).join('')}</ul></div>`:''}
      ${placeLinks.length?`<div class="side-block"><h4>Places</h4><ul class="side-list">${placeLinks.map(p=>`<li><a href="#/place/${p.id}">${esc(p.name)}</a></li>`).join('')}</ul></div>`:''}
      ${paths.length?`<div class="side-block"><h4>Reading paths</h4><ul class="side-list">${paths.map(p=>`<li><a href="#/path/${p.id}">${esc(p.title)}</a></li>`).join('')}</ul></div>`:''}
    </aside></div></div></div>
  </div>`;
}
function refLink(ref){const p=parseRef(ref);if(!p)return '#/library';const gi=p.part?globalChapter(p.bookId,p.part,p.ch):p.ch;return readerHref(p.bookId,gi,p.v1||null);}

/* ---------------- READER ---------------- */
function chapterMeta(bookId,idx){
  const m=MULTI[bookId];
  if(!m) return {part:(BY.work.get(bookId)||{}).title||bookId,local:idx,total:chapterCount(bookId),multi:false};
  let i=0; for(let k=0;k<m.offsets.length;k++){if(idx>m.offsets[k]) i=k;}
  return {part:m.parts[i],local:idx-m.offsets[i],total:chapterCount(bookId),multi:true,partIndex:i};
}
function readerView(bookId,ch){
  const book=TANAKH.books.find(b=>b.id===bookId); if(!book) return notFoundView();
  ch=Math.max(1,Math.min(ch,book.chapters.length));
  const meta=chapterMeta(bookId,ch); const chapter=book.chapters[ch-1];
  const w=BY.work.get(bookId)||{title:book.title};
  const divisions=[['torah','Torah'],['neviim',"Nevi'im"],['ketuvim','Ketuvim']];
  const sidebar=divisions.map(([div,name])=>{
    const bs=TANAKH.books.filter(b=>(BY.work.get(b.id)||{}).division===div);
    return `<div class="rs-head">${name}</div>${bs.map(b=>{
      const on=b.id===bookId;
      return `<div class="rs-book ${on?'on':''}"><button type="button"><span>${esc((BY.work.get(b.id)||{}).title||b.title)}</span><span class="he">${esc((BY.work.get(b.id)||{}).he||'')}</span></button><div class="rs-chapters">${b.chapters.map((c,i)=>`<a class="${on&&i+1===ch?'on':''}" href="${readerHref(b.id,i+1)}">${chapterMeta(b.id,i+1).local}</a>`).join('')}</div></div>`;
    }).join('')}`;
  }).join('');
  const flat=[]; TANAKH.books.forEach(b=>b.chapters.forEach((c,i)=>flat.push({b:b.id,ch:i+1})));
  const idx=flat.findIndex(x=>x.b===bookId&&x.ch===ch);
  const prev=flat[idx-1],next=flat[idx+1];
  const pmeta=prev?chapterMeta(prev.b,prev.ch):null,nmeta=next?chapterMeta(next.b,next.ch):null;
  // save progress
  try{localStorage.setItem('lastRead',JSON.stringify({book:bookId,ch,label:`${meta.part} ${meta.local}`}));}catch(e){}
  const verses=chapter.verses.map(v=>`<span class="verse" id="v${esc(v.n)}"><sup class="v" data-v="${esc(v.n)}" title="Link to this verse">${esc(v.n)}</sup>${esc(v.t)}</span>`).join(' ');
  return `<div class="page" style="padding:0"><div class="wrap reader">
    <aside class="reader-side" id="reader-side">
      <div class="rs-head" style="margin-top:0">The Tanakh</div>
      <p style="font-size:.72rem;color:var(--muted);line-height:1.5;margin-bottom:1rem">JPS 1917 · ${fmt(TANAKH.stats.verses)} verses</p>
      ${sidebar}
      <div class="rs-head">Elsewhere</div>
      <ul class="side-list" style="font-size:.8rem"><li><a href="#/work/${bookId}">About ${esc(w.title)}</a></li><li><a href="#/library">The whole library</a></li><li><a href="#/sources">Text & sources</a></li></ul>
    </aside>
    <main class="reader-main">
      <div class="reader-top"><div>
        <div class="breadcrumb"><a href="#/library">Library</a><span class="sep">/</span><a href="#/work/${bookId}">${esc(w.title||book.title)}</a><span class="sep">/</span><span>${esc(meta.part)} ${meta.local}</span></div>
        <div class="reader-title">${esc(meta.part)} <span style="color:var(--muted);font-size:.55em">${meta.local}</span><span class="he">${esc(w.he||'')}</span></div>
      </div><div class="reader-tools">
        <button type="button" id="side-toggle">Contents</button>
        <button type="button" onclick="setReaderSize(-1)" aria-label="Smaller text">A−</button>
        <button type="button" onclick="setReaderSize(1)" aria-label="Larger text">A+</button>
      </div></div>
      <article class="chapter"><div class="chnum">${meta.local}</div><h2>${esc(meta.part)} <span style="color:var(--faint);font-size:.6em">Chapter ${meta.local}</span></h2>
        <div class="verses" id="verses">${verses}</div>
      </article>
      <nav class="reader-nav">${prev?`<a href="${readerHref(prev.b,prev.ch)}"><small>Previous</small><b>← ${esc(pmeta.part)} ${pmeta.local}</b></a>`:'<span></span>'}${next?`<a href="${readerHref(next.b,next.ch)}" style="text-align:right"><small>Next</small><b>${esc(nmeta.part)} ${nmeta.local} →</b></a>`:''}</nav>
    </main>
  </div></div>`;
}
function setReaderSize(d){
  const el=$('#verses'); if(!el)return;
  let s=parseFloat(getComputedStyle(el).fontSize)||17;
  s=Math.max(14,Math.min(24,s+d));
  el.style.fontSize=s+'px'; try{localStorage.setItem('readerSize',s)}catch(e){}
}

/* ---------------- TIMELINE ---------------- */
const ERAS=[
  {id:'beginnings',name:'Beginnings',range:'c. 1800–1200 BCE',from:-9999,to:-1201},
  {id:'settlement',name:'Settlement & Judges',range:'c. 1200–1020 BCE',from:-1200,to:-1021},
  {id:'monarchy',name:'Monarchy & Prophets',range:'c. 1020–586 BCE',from:-1020,to:-587},
  {id:'exile',name:'Exile & Return',range:'586–332 BCE',from:-586,to:-333},
  {id:'second-temple',name:'Second Temple',range:'332 BCE–70 CE',from:-332,to:70},
  {id:'talmudic',name:'Yavneh & the Talmud',range:'70–500 CE',from:71,to:500},
  {id:'geonim',name:'Geonim & Rishonim',range:'500–1096',from:501,to:1096},
  {id:'medieval',name:'The Medieval World',range:'1096–1492',from:1097,to:1492},
  {id:'early-modern',name:'Early Modern',range:'1492–1800',from:1493,to:1800},
  {id:'modern',name:'Modernity',range:'1800–present',from:1801,to:9999}
];
function eraFor(e){
  const y=+e.sort||0;
  if(y<=-1201)return ERAS[0]; if(y<=-1021)return ERAS[1]; if(y<=-587)return ERAS[2]; if(y<=-333)return ERAS[3];
  if(y<=70)return ERAS[4]; if(y<=500)return ERAS[5]; if(y<=1096)return ERAS[6]; if(y<=1492)return ERAS[7]; if(y<=1800)return ERAS[8]; return ERAS[9];
}
function timelineView(){
  const ev=[...DATA.timeline].sort((a,b)=>(a.sort||0)-(b.sort||0));
  const rows=[]; let current=null;
  ev.forEach(e=>{
    const era=eraFor(e);
    if(era.id!==current){
      current=era.id;
      rows.push(`<div class="era-head" id="era-${era.id}" data-era="${era.id}"><span>${esc(era.range)}</span><h3>${esc(era.name)}</h3></div>`);
    }
    const links=[...(e.works||[]),...(e.people||[]),...(e.places||[])].map(id=>{const t=typeOf(id);return t?`<a href="${routeFor(t,id)}">${esc(labelOf(id))}</a>`:''}).join('');
    rows.push(`<div class="tl-item" data-era="${era.id}"><div class="tl-year">${esc(e.year||'')}<small>${esc(e.label||'')}</small></div><div class="tl-body"><h4>${esc(e.title)}</h4><p>${esc(e.text||'')}</p>${links?`<div class="tl-links">${links}</div>`:''}</div></div>`);
  });
  return `<div class="page"><div class="wrap">
    <div class="eyebrow">Timeline</div><h1 style="font-size:clamp(2.6rem,6vw,5rem);margin-bottom:.6rem">Three thousand years, one argument</h1>
    <p class="lede" style="max-width:760px;margin-bottom:2.4rem">From the world of the patriarchs to the printed page. Dates before the Hellenistic period are traditional or approximate; where historians disagree, the entry says so.</p>
    <div class="era-nav" id="era-nav"><button class="chip on" onclick="filterTimeline('all',this)">All eras</button>${ERAS.map(x=>`<button class="chip" onclick="filterTimeline('${x.id}',this)">${esc(x.name)}</button>`).join('')}</div>
    <div class="timeline" id="timeline">${rows.join('')}</div>
  </div></div>`;
}
function filterTimeline(era,btn){
  $$('#era-nav .chip').forEach(c=>c.classList.remove('on')); if(btn)btn.classList.add('on');
  $$('.tl-item').forEach(el=>el.style.display=(era==='all'||el.dataset.era===era)?'':'none');
  $$('.era-head').forEach(el=>el.style.display=(era==='all'||el.dataset.era===era)?'':'none');
}

/* ---------------- PEOPLE ---------------- */
function peopleView(){
  const eras=[...new Set(DATA.people.map(p=>p.era).filter(Boolean))];
  return `<div class="page"><div class="wrap">
    <div class="eyebrow">People</div><h1 style="font-size:clamp(2.6rem,6vw,5rem);margin-bottom:.6rem">The hands that carried it</h1>
    <p class="lede" style="max-width:760px;margin-bottom:2rem">Patriarchs and prophets, editors and rivals, commentators and mystics. The chain is made of people who disagreed with each other.</p>
    <div class="chips" style="margin-bottom:2rem"><button class="chip on" onclick="filterPeople('all',this)">All ${DATA.people.length}</button>${eras.map(e=>`<button class="chip" onclick="filterPeople('${esc(e).replace(/'/g,"\\'")}',this)">${esc(e)}</button>`).join('')}</div>
    <div class="people-grid" id="people-grid">${DATA.people.map(p=>`<div class="person-wrap" data-era="${esc(p.era||'')}">${personCard(p)}</div>`).join('')}</div>
  </div></div>`;
}
function filterPeople(era,btn){$$('#people-grid .person-wrap').forEach(el=>el.style.display=(era==='all'||el.dataset.era===era)?'':'none');$$('.chips .chip').forEach(c=>c.classList.remove('on'));if(btn)btn.classList.add('on');}
function personView(id){
  const p=BY.person.get(id); if(!p) return notFoundView();
  const works=(p.works||[]).map(x=>BY.work.get(x)).filter(Boolean);
  const places=(p.places||[]).map(x=>BY.place.get(x)).filter(Boolean);
  const themes=(p.themes||[]).map(x=>BY.theme.get(x)).filter(Boolean);
  const conns=(p.connections||[]).filter(x=>typeOf(x.to));
  return `<div class="page"><div class="wrap">
    ${breadcrumb([{label:'People',href:'#/people'},{label:p.name}])}
    <div class="person-detail">
      <div><div class="person-portrait"><span class="rings"></span><span class="big-he">${esc((p.he_name||'').replace(/[^\u0590-\u05FF]/g,'').slice(0,2)||p.name.slice(0,1))}</span></div>
      <div style="margin-top:1.3rem"><div class="tiny">${esc(p.era||'')}</div><div class="muted" style="font-family:var(--display);font-size:1.15rem">${esc(p.dates||'')}</div></div></div>
      <div>
        <div class="eyebrow">${esc(p.era||'Person')}</div><h1 style="font-size:clamp(2.4rem,5vw,4.2rem);margin-bottom:.2rem">${esc(p.name)}</h1>
        <div class="he" style="font-size:1.5rem;color:var(--gold);margin-bottom:1.4rem">${esc(p.he_name||'')}</div>
        <div class="pull">${esc(p.key_idea||'')}</div>
        <div class="prose">${(p.bio||'').split(/\n+/).map(x=>`<p>${esc(x)}</p>`).join('')}</div>
        ${works.length?`<div class="hr-label"><span>Works</span></div><div class="conn-grid">${works.map(w=>`<a class="conn" href="#/work/${w.id}"><span class="cdot" style="--c:${workColor(w)}"></span><span><b>${esc(w.title)}</b><span>${esc(trunc(w.summary||'',80))}</span></span></a>`).join('')}</div>`:''}
        ${themes.length?`<div class="hr-label"><span>Ideas</span></div><div class="chips">${themes.map(t=>`<a class="chip" href="#/idea/${t.id}">${esc(t.name)}</a>`).join('')}</div>`:''}
        ${places.length?`<div class="hr-label"><span>Places</span></div><div class="chips">${places.map(x=>`<a class="chip" href="#/place/${x.id}">${esc(x.name)}</a>`).join('')}</div>`:''}
        ${conns.length?`<div class="hr-label"><span>Connections</span></div><div class="conn-grid">${conns.map(c=>{const t=typeOf(c.to);return `<a class="conn" href="${routeFor(t,c.to)}"><span class="cdot" style="--c:${t==='work'?workColor(BY.work.get(c.to)):COLORS[t]}"></span><span><b>${esc(labelOf(c.to))}</b><span>${esc(c.why)}</span></span></a>`}).join('')}</div>`:''}
        ${(p.sources||[]).length?`<div class="hr-label"><span>Sources</span></div><ul class="side-list">${p.sources.map(s=>`<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)}</a></li>`).join('')}</ul>`:''}
      </div>
    </div>
  </div></div>`;
}

/* ---------------- PLACES + MAP ---------------- */
const PIN_OFFSETS={
  eden:[8,-8],ur:[-10,16],haran:[8,-8],canaan:[8,10],hebron:[-10,14],goshen:[-10,8],sinai:[8,14],
  jericho:[8,-6],shiloh:[8,-8],jerusalem:[10,-2],bethlehem:[-10,12],samaria:[8,-8],nineveh:[8,-8],
  babylon:[8,10],susa:[8,10],yavneh:[-8,12],tiberias:[8,-6],sepphoris:[-10,-6],pumbedita:[8,-8],
  sura:[-10,12],troyes:[-8,-8],worms:[8,-8],cairo:[-8,12],safed:[8,-8],vilna:[8,-8]
};
function project(lon,lat){return [(lon-20)/40*1000,(47-lat)/30*750];}
function renderMap(focusId=null){
  const pins=DATA.places.filter(p=>Array.isArray(p.coordinates)&&p.coordinates.length===2);
  const land=(DATA.map.paths||[]).map(d=>`<path class="map-land" d="${d}"/>`).join('');
  const rivers=[
    [[31.2,30.1],[30.1,31.2],[29.1,31.3],[27.2,31.2],[25.7,32.6],[24.1,32.9]],
    [[37.9,37.9],[36.6,39.0],[35.4,40.4],[34.0,41.5],[33.0,43.0],[32.4,44.4],[31.0,47.4],[30.0,48.5]],
    [[38.2,38.5],[37.2,39.6],[36.2,40.8],[35.1,42.0],[34.4,43.2],[33.3,43.8],[32.5,44.4],[31.8,45.8],[31.0,47.4]],
    [[33.2,35.6],[32.9,35.6],[32.6,35.55],[32.2,35.55],[31.8,35.55],[31.5,35.5],[31.2,35.45]]
  ].map(pts=>`<path class="map-river" d="M${pts.map(([la,lo])=>project(lo,la).map(n=>n.toFixed(1)).join(',')).join(' L')}"/>`).join('');
  let vb='0 0 1000 750';
  if(focusId){const p=BY.place.get(focusId);if(p&&p.coordinates){const [x,y]=project(p.coordinates[1],p.coordinates[0]);const w=340,h=255;const vx=Math.max(0,Math.min(1000-w,x-w/2)),vy=Math.max(0,Math.min(750-h,y-h/2));vb=`${vx} ${vy} ${w} ${h}`;}}
  const pinHtml=pins.map(p=>{
    const [x,y]=project(p.coordinates[1],p.coordinates[0]);
    const [dx,dy]=PIN_OFFSETS[p.id]||[8,4];
    const active=focusId===p.id;
    return `<g class="pin ${active?'on':''}" data-id="${p.id}" transform="translate(${x.toFixed(1)},${y.toFixed(1)})" role="link" tabindex="0" aria-label="${esc(p.name)}">
      <circle r="${active?6:4}"></circle><text x="${dx}" y="${dy}" text-anchor="${dx<0?'end':'start'}">${esc(p.name)}</text>
    </g>`;
  }).join('');
  return `<div class="map-card"><svg viewBox="${vb}" xmlns="http://www.w3.org/2000/svg" aria-label="Map of the ancient world">
    <defs><pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse"><path d="M50 0H0V50" fill="none" stroke="rgba(236,229,214,.04)" stroke-width=".5"/></pattern></defs>
    <rect width="1000" height="750" fill="#0a0d13"/><rect width="1000" height="750" fill="url(#grid)"/>
    ${land}${rivers}
    <text class="map-label" x="120" y="330" transform="rotate(-72 120 330)">Mediterranean Sea</text>
    <text class="map-label" x="235" y="610">Egypt</text>
    <text class="map-label" x="505" y="180">Anatolia</text>
    <text class="map-label" x="535" y="420">Levant</text>
    <text class="map-label" x="700" y="330">Mesopotamia</text>
    <text class="map-label" x="640" y="600">Arabian Desert</text>
    ${pinHtml}
  </svg><div class="map-legend"><span>● Canonical place</span><span>— River</span></div></div>`;
}
function placesView(){
  const regions=[...new Set(DATA.places.map(p=>p.region).filter(Boolean))];
  return `<div class="page"><div class="wrap">
    <div class="eyebrow">Places</div><h1 style="font-size:clamp(2.6rem,6vw,5rem);margin-bottom:.6rem">A library with a geography</h1>
    <p class="lede" style="max-width:760px;margin-bottom:2rem">Sinai, Jerusalem, Babylon, Yavneh, Troyes, Cairo, Safed, Vilna. The canon was made in particular rooms, under particular empires.</p>
    ${renderMap()}
    ${regions.map(r=>`<div class="hr-label"><span>${esc(r)}</span></div><div class="place-grid">${DATA.places.filter(p=>p.region===r).map(placeCard).join('')}</div>`).join('')}
  </div></div>`;
}
function placeView(id){
  const p=BY.place.get(id); if(!p) return notFoundView();
  const works=(p.works||[]).map(x=>BY.work.get(x)).filter(Boolean);
  const people=(p.people||[]).map(x=>BY.person.get(x)).filter(Boolean);
  const themes=(p.themes||[]).map(x=>BY.theme.get(x)).filter(Boolean);
  return `<div class="page"><div class="wrap">
    ${breadcrumb([{label:'Places',href:'#/places'},{label:p.name}])}
    <div class="split"><div>
      <div class="eyebrow">${esc(p.region||'Place')}</div><h1 style="font-size:clamp(2.6rem,6vw,4.6rem);margin-bottom:.2rem">${esc(p.name)}</h1>
      <div class="he" style="font-size:1.4rem;color:var(--gold);margin-bottom:1.6rem">${esc(p.he_name||'')}</div>
      <div class="prose">${(p.bio||'').split(/\n+/).map(x=>`<p>${esc(x)}</p>`).join('')}</div>
      ${themes.length?`<div class="hr-label"><span>Ideas</span></div><div class="chips">${themes.map(t=>`<a class="chip" href="#/idea/${t.id}">${esc(t.name)}</a>`).join('')}</div>`:''}
      ${people.length?`<div class="hr-label"><span>People</span></div><div class="chips">${people.map(x=>`<a class="chip" href="#/person/${x.id}">${esc(x.name)}</a>`).join('')}</div>`:''}
      ${works.length?`<div class="hr-label"><span>Works</span></div><div class="conn-grid">${works.map(w=>`<a class="conn" href="#/work/${w.id}"><span class="cdot" style="--c:${workColor(w)}"></span><span><b>${esc(w.title)}</b><span>${esc(trunc(w.summary||'',80))}</span></span></a>`).join('')}</div>`:''}
      ${(p.connections||[]).length?`<div class="hr-label"><span>Connections</span></div><div class="conn-grid">${p.connections.filter(c=>typeOf(c.to)).map(c=>{const t=typeOf(c.to);return `<a class="conn" href="${routeFor(t,c.to)}"><span class="cdot" style="--c:${t==='work'?workColor(BY.work.get(c.to)):COLORS[t]}"></span><span><b>${esc(labelOf(c.to))}</b><span>${esc(c.why)}</span></span></a>`}).join('')}</div>`:''}
      ${(p.sources||[]).length?`<div class="hr-label"><span>Sources</span></div><ul class="side-list">${p.sources.map(s=>`<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)}</a></li>`).join('')}</ul>`:''}
    </div><aside class="sidebar"><div class="side-block"><h4>At a glance</h4><ul class="side-list"><li><span>Region</span><span style="margin-left:auto">${esc(p.region||'—')}</span></li><li><span>Coordinates</span><span style="margin-left:auto">${Array.isArray(p.coordinates)?p.coordinates.join(', '):'—'}</span></li><li><span>Site</span><span style="margin-left:auto">${p.ancient?'Ancient':'Literary / traditional'}</span></li></ul></div></aside></div>
    <div style="margin-top:2.4rem">${renderMap(id)}</div>
  </div></div>`;
}

/* ---------------- IDEAS ---------------- */
function ideasView(){
  const kinds=[...new Set(DATA.themes.map(t=>t.kind).filter(Boolean))];
  return `<div class="page"><div class="wrap">
    <div class="eyebrow">Ideas</div><h1 style="font-size:clamp(2.6rem,6vw,5rem);margin-bottom:.6rem">The arguments underneath</h1>
    <p class="lede" style="max-width:760px;margin-bottom:2rem">Covenant, exile, law, machloket, tzimtzum. Forty-one ideas that recur across the library — and change meaning as they move.</p>
    <div class="chips" style="margin-bottom:2rem"><button class="chip on" onclick="filterIdeas('all',this)">All ${DATA.themes.length}</button>${kinds.map(k=>`<button class="chip" onclick="filterIdeas('${esc(k)}',this)">${esc(k[0].toUpperCase()+k.slice(1))}s</button>`).join('')}</div>
    <div class="idea-grid" id="idea-grid">${DATA.themes.map(t=>`<div class="idea-wrap" data-kind="${esc(t.kind||'')}">${ideaCard(t)}</div>`).join('')}</div>
  </div></div>`;
}
function filterIdeas(kind,btn){$$('#idea-grid .idea-wrap').forEach(el=>el.style.display=(kind==='all'||el.dataset.kind===kind)?'':'none');$$('.chips .chip').forEach(c=>c.classList.remove('on'));if(btn)btn.classList.add('on');}
function ideaView(id){
  const t=BY.theme.get(id); if(!t) return notFoundView();
  const works=(t.works||[]).map(x=>BY.work.get(x)).filter(Boolean);
  const people=(t.people||[]).map(x=>BY.person.get(x)).filter(Boolean);
  const places=(t.places||[]).map(x=>BY.place.get(x)).filter(Boolean);
  return `<div class="page"><div class="wrap">
    ${breadcrumb([{label:'Ideas',href:'#/ideas'},{label:t.name}])}
    <div class="split"><div>
      <div class="eyebrow">${esc(t.kind||'Idea')}</div>
      <h1 style="font-size:clamp(2.6rem,6vw,4.8rem);margin-bottom:.2rem">${esc(t.name)}</h1>
      <div class="he" style="font-size:1.5rem;color:var(--gold);margin-bottom:1.2rem">${esc(t.he_name||'')}</div>
      <p class="lede" style="margin-bottom:1.6rem">${esc(t.short||'')}</p>
      <div class="prose">${(t.essay||'').split(/\n+/).map(x=>`<p>${esc(x)}</p>`).join('')}</div>
      ${(t.connections||[]).length?`<div class="hr-label"><span>In tension with</span></div><div class="conn-grid">${t.connections.filter(c=>typeOf(c.to)).map(c=>{const ty=typeOf(c.to);return `<a class="conn" href="${routeFor(ty,c.to)}"><span class="cdot" style="--c:${ty==='work'?workColor(BY.work.get(c.to)):COLORS[ty]}"></span><span><b>${esc(labelOf(c.to))}</b><span>${esc(c.why)}</span></span></a>`}).join('')}</div>`:''}
      ${(t.sources||[]).length?`<div class="hr-label"><span>Sources</span></div><ul class="side-list">${t.sources.map(s=>`<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)}</a></li>`).join('')}</ul>`:''}
    </div><aside class="sidebar">
      ${works.length?`<div class="side-block"><h4>Where to see it</h4><ul class="side-list">${works.map(w=>`<li><a href="#/work/${w.id}">${esc(w.title)}</a></li>`).join('')}</ul></div>`:''}
      ${people.length?`<div class="side-block"><h4>Who shaped it</h4><ul class="side-list">${people.map(p=>`<li><a href="#/person/${p.id}">${esc(p.name)}</a><span class="he">${esc(p.he_name||'')}</span></li>`).join('')}</ul></div>`:''}
      ${places.length?`<div class="side-block"><h4>Where</h4><ul class="side-list">${places.map(p=>`<li><a href="#/place/${p.id}">${esc(p.name)}</a></li>`).join('')}</ul></div>`:''}
    </aside></div>
  </div></div>`;
}

/* ---------------- ESSAYS ---------------- */
function essaysView(){
  return `<div class="page"><div class="wrap">
    <div class="eyebrow">Essays</div><h1 style="font-size:clamp(2.6rem,6vw,5rem);margin-bottom:.6rem">Why the library looks like this</h1>
    <p class="lede" style="max-width:780px;margin-bottom:2.6rem">Ten arguments about canon, commentary, law, reason, mysticism, and the act of reading. They can be read in order or as standalone pieces.</p>
    <div class="essay-list">${DATA.essays.map((e,i)=>essayRow(e,i)).join('')}</div>
  </div></div>`;
}
function essayView(id){
  const e=BY.essay.get(id); if(!e) return notFoundView();
  const works=(e.works||[]).map(x=>BY.work.get(x)).filter(Boolean);
  const people=(e.people||[]).map(x=>BY.person.get(x)).filter(Boolean);
  const themes=(e.themes||[]).map(x=>BY.theme.get(x)).filter(Boolean);
  const paras=Array.isArray(e.body)?e.body:String(e.body||'').split(/\n\s*\n/);
  return `<div class="page"><div class="wrap">
    ${breadcrumb([{label:'Essays',href:'#/essays'},{label:e.title}])}
    <div class="narrow">
      <div class="eyebrow">Essay</div>
      <h1 style="font-size:clamp(2.4rem,5.4vw,4.4rem);margin-bottom:.5rem">${esc(e.title)}</h1>
      <p class="lede" style="margin-bottom:2.4rem">${esc(e.dek||'')}</p>
      <div class="essay-body">${paras.map(p=>`<p>${esc(p)}</p>`).join('')}</div>
      <div class="hr-label"><span>Read alongside</span></div>
      <div class="conn-grid">${works.slice(0,6).map(w=>`<a class="conn" href="#/work/${w.id}"><span class="cdot" style="--c:${workColor(w)}"></span><span><b>${esc(w.title)}</b><span>${esc(trunc(w.summary||'',80))}</span></span></a>`).join('')}</div>
      <div class="chips" style="margin-top:1.4rem">${themes.map(t=>`<a class="chip" href="#/idea/${t.id}">${esc(t.name)}</a>`).join('')}${people.map(p=>`<a class="chip" href="#/person/${p.id}">${esc(p.name)}</a>`).join('')}</div>
      ${(e.sources||[]).length?`<div class="hr-label"><span>Sources</span></div><ul class="side-list">${e.sources.map(s=>`<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)}</a></li>`).join('')}</ul>`:''}
    </div>
  </div></div>`;
}

/* ---------------- PATHS ---------------- */
function pathsView(){
  return `<div class="page"><div class="wrap">
    <div class="eyebrow">Guided paths</div><h1 style="font-size:clamp(2.6rem,6vw,5rem);margin-bottom:.6rem">Follow a question</h1>
    <p class="lede" style="max-width:760px;margin-bottom:2.6rem">Each path is a sequence of stops through the library. Read them in order, or jump to the text that interests you. Your progress is kept on this device.</p>
    <div class="path-grid">${DATA.pathways.map((p,i)=>`<a class="path-card" href="#/path/${p.id}"><span class="pnum">Path ${String(i+1).padStart(2,'0')}</span><h3>${esc(p.title)}</h3><p>${esc(p.dek||'')}</p><span class="pfoot">${(p.stops||[]).length} stops · ${esc((p.themes||[]).map(x=>(BY.theme.get(x)||{}).name).filter(Boolean).slice(0,2).join(' · '))}</span><span class="arrow">${ICONS.arrow}</span></a>`).join('')}</div>
  </div></div>`;
}
function pathView(id){
  const p=BY.path.get(id); if(!p) return notFoundView();
  let done=[]; try{done=JSON.parse(localStorage.getItem('path:'+id)||'[]')}catch(e){}
  const stops=(p.stops||[]).map((s,i)=>{
    const w=BY.work.get(s.work); const isDone=done.includes(i);
    let href=s.work?`#/work/${s.work}`:'#/library';
    if(s.ref){const link=refLink(s.ref); if(link!=='#/library') href=link;}
    return `<div class="stop"><button class="snum" onclick="location.hash='${href}'" aria-label="Open stop ${i+1}">${String(i+1).padStart(2,'0')}</button><div class="scard"><button class="scheck ${isDone?'done':''}" onclick="toggleStop('${id}',${i},this)" aria-label="Mark stop ${i+1} complete">✓</button><div class="swork">${esc(w?w.title:'The library')}${s.ref?' · '+esc(s.ref):''}</div><h4>${esc(s.title||'')}</h4><p>${esc(s.text||'')}</p><a class="slink" href="${href}">${s.ref?'Read the passage':'Open the work'} →</a></div></div>`;
  }).join('');
  return `<div class="page"><div class="wrap">
    ${breadcrumb([{label:'Guided paths',href:'#/paths'},{label:p.title}])}
    <div class="path-hero"><div class="eyebrow">Guided path</div><h1 style="font-size:clamp(2.4rem,5.4vw,4.4rem);margin-bottom:.6rem">${esc(p.title)}</h1><p class="lede" style="max-width:760px">${esc(p.intro||p.dek||'')}</p><div class="chips" style="margin-top:1.2rem">${(p.themes||[]).map(t=>BY.theme.get(t)?`<a class="chip" href="#/idea/${t}">${esc(BY.theme.get(t).name)}</a>`:'').join('')}</div></div>
    <div class="trail">${stops}</div>
    <div style="margin-top:2rem"><a class="btn ghost" href="#/paths">All paths ${ICONS.arrow}</a></div>
  </div></div>`;
}
function toggleStop(id,i,el){
  let done=[]; try{done=JSON.parse(localStorage.getItem('path:'+id)||'[]')}catch(e){}
  if(done.includes(i)) done=done.filter(x=>x!==i); else done.push(i);
  localStorage.setItem('path:'+id,JSON.stringify(done));
  el.classList.toggle('done',done.includes(i));
  toast(done.includes(i)?'Stop marked complete':'Stop unmarked');
}

/* ---------------- GRAPH ---------------- */
function graphView(){
  return `<div class="graph-page">
    <div class="graph-bar">
      <h2>The constellation</h2>
      <div class="graph-toggles">
        <button class="chip on" data-gtype="work" onclick="graphToggle('work',this)">Works</button>
        <button class="chip" data-gtype="person" onclick="graphToggle('person',this)">People</button>
        <button class="chip" data-gtype="place" onclick="graphToggle('place',this)">Places</button>
        <button class="chip" data-gtype="theme" onclick="graphToggle('theme',this)">Ideas</button>
      </div>
      <div class="search-inline" style="margin-left:auto;min-width:200px">${ICONS.search}<input id="graph-search" placeholder="Find a node…" aria-label="Find a node"></div>
      <button class="btn sm ghost" onclick="graphReset()">Reset view</button>
    </div>
    <div class="graph-main">
      <canvas id="graph-canvas"></canvas>
      <div class="graph-legend"><span><i style="background:${COLORS.work}"></i>Works</span><span><i style="background:${COLORS.person}"></i>People</span><span><i style="background:${COLORS.place}"></i>Places</span><span><i style="background:${COLORS.theme}"></i>Ideas</span></div>
      <div class="graph-hint">Drag to move · scroll to zoom · click a node</div>
      <div class="graph-panel" id="graph-panel"><button class="gp-close" onclick="document.getElementById('graph-panel').classList.remove('open')">×</button><div id="graph-panel-body"></div></div>
    </div>
  </div>`;
}

/* ---------------- SOURCES ---------------- */
function sourcesView(){
  return `<div class="page"><div class="wrap narrow">
    <div class="eyebrow">Sources & method</div><h1 style="font-size:clamp(2.4rem,5.4vw,4.2rem);margin-bottom:1rem">What is in this atlas</h1>
    <p class="lede">One self-contained HTML file. No tracking, no external scripts, no network required after download. The text, the maps, the typefaces, and the arguments all live inside the page.</p>
    <div class="hr-label"><span>The Tanakh</span></div>
    <div class="prose">
      <p>The full text of the <strong>Jewish Publication Society translation of 1917</strong> is embedded: all 24 books, 929 chapters, and 23,145 verses. The JPS 1917 translation is in the public domain. The electronic text was obtained from the <a href="https://ebible.org/find/details.php?id=engjps" target="_blank" rel="noopener">eBible.org USFM edition</a> and parsed into structured JSON. Verse numbers follow the JPS/Christian chapter divisions used by that edition; Hebrew chapter divisions differ in a few books, notably Psalms and Joel.</p>
      <p>The Tanakh is presented in the traditional Jewish order and counted as 24 books: Samuel, Kings, Ezra–Nehemiah, and Chronicles are single works; the Twelve are one work. This is why the Jewish count differs from the 39-book Protestant Old Testament, even though the content is substantially the same.</p>
    </div>
    <div class="hr-label"><span>The rest of the library</span></div>
    <div class="prose">
      <p>The Oral Torah, commentary, law, philosophy, mysticism, and prayer are represented by <strong>structured guides and short primary excerpts</strong>, not complete texts. A complete public-domain English Mishnah, Talmud, Rashi, Mishneh Torah, Shulchan Aruch, or Zohar does not exist; where a work is quoted, the translation is public domain or made for this atlas and identified in the entry. The Talmud excerpts draw on Michael Rodkinson's public-domain selection (1903); Pirkei Avot on Joseph Gorfinkle's public-domain translation (1913); the Siddur on the public-domain Singer tradition. All other summaries and translations are original to this project.</p>
      <p>This is an atlas, not a critical edition. It is designed to show the shape of the library, the arguments that connect its parts, and the passages where the argument becomes visible. For study, always go to a complete edition and a teacher.</p>
    </div>
    <div class="hr-label"><span>Dates and attributions</span></div>
    <div class="prose">
      <p>Biblical dates before the Hellenistic period are traditional or approximate. The documentary hypothesis and the historicity of the Exodus are matters of scholarly debate; the atlas says so where relevant rather than pretending to certainty. Rabbinic dates follow standard scholarly consensus. The Zohar is traditionally ascribed to Rabbi Shimon bar Yochai; most scholars date its main composition to late 13th-century Castile. The atlas presents both claims.</p>
    </div>
    <div class="hr-label"><span>Design</span></div>
    <div class="prose">
      <p>Typefaces: Cormorant Garamond (display), Spectral (text), Frank Ruhl Libre (Hebrew), all under the SIL Open Font License and embedded as WOFF2. The map is drawn from Natural Earth 1:50m land data, simplified and projected for this page. The constellation is a custom force-directed graph. Everything else is hand-written HTML, CSS, and JavaScript.</p>
      <p><strong>License:</strong> the JPS 1917 text is public domain. The original essays, summaries, annotations, and design are offered for personal and educational use. Linked sources remain under their own terms.</p>
    </div>
    <div class="hr-label"><span>Colophon</span></div>
    <div class="prose"><p>Built October 2026. 42 works, 43 people, 25 places, 41 ideas, 10 essays, 7 paths. A single file, meant to be read slowly.</p></div>
  </div></div>`;
}

/* ---------------- INIT ---------------- */
function init(){
  shell();
  // spine clicks
  document.addEventListener('click',e=>{
    const sp=e.target.closest('.spine[data-href]'); if(sp){location.hash=sp.dataset.href;}
    const ov=e.target.closest('.overlay'); if(ov&&e.target===ov){ov.classList.remove('open');}
  });
  $('#search-open').addEventListener('click',()=>openSearch());
  $('#random-btn').addEventListener('click',randomPassage);
  $('#search-input').addEventListener('input',e=>runSearch(e.target.value));
  $('#search-input').addEventListener('keydown',e=>{
    if(e.key==='ArrowDown'){e.preventDefault();moveSearch(1);}
    else if(e.key==='ArrowUp'){e.preventDefault();moveSearch(-1);}
    else if(e.key==='Enter'){e.preventDefault();goSearch();}
  });
  document.addEventListener('keydown',e=>{
    const typing=/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
    if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openSearch();return;}
    if(e.key==='Escape'){closeSearch();const m=$('#menu-drawer');if(m)m.remove();return;}
    if(typing)return;
    if(e.key==='/'){e.preventDefault();openSearch();}
    if(e.key.toLowerCase()==='g'&&!e.metaKey&&!e.ctrlKey){location.hash='#/graph';}
    if(e.key.toLowerCase()==='t'&&!e.metaKey&&!e.ctrlKey){location.hash='#/timeline';}
    if(e.key.toLowerCase()==='r'&&!e.metaKey&&!e.ctrlKey){randomPassage();}
  });
  $('#menu-btn').addEventListener('click',()=>{
    if($('#menu-drawer')){$('#menu-drawer').remove();return;}
    const d=document.createElement('div');d.id='menu-drawer';d.className='overlay open';
    d.innerHTML=`<div class="search-panel" style="max-width:420px"><div class="search-head"><b style="font-family:var(--display);font-size:1.4rem">Menu</b><button class="modal-close" style="position:static;margin-left:auto" aria-label="Close">×</button></div>
    <div style="padding:1rem 1.3rem;display:grid;gap:.4rem">${[['Library','#/library'],['The constellation','#/graph'],['Timeline','#/timeline'],['People','#/people'],['Places','#/places'],['Ideas','#/ideas'],['Essays','#/essays'],['Guided paths','#/paths'],['Reader','#/read/genesis/1'],['Sources','#/sources']].map(([t,h])=>`<a href="${h}" style="padding:.6rem 0;border-bottom:1px solid var(--line-soft);font-family:var(--display);font-size:1.3rem">${t}</a>`).join('')}</div></div>`;
    document.body.append(d);
    d.querySelector('.modal-close').onclick=()=>d.remove();
    d.addEventListener('click',e=>{if(e.target===d)d.remove();});
  });
  window.addEventListener('hashchange',render);
  const saved=parseFloat(localStorage.getItem('readerSize')||'0');
  if(saved){const el=$('#verses');if(el)el.style.fontSize=saved+'px';}
  render();
}
