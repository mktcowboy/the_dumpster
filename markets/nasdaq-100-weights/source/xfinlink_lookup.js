// Historical constituents lookup pages. One script for all three. The index, its first date, the CSV file name and
// the table's name come from the data attributes on #lk. Desktop and tablet use the panel (.lk-desk), phones their
// own layout (.lk-mob). Both share one state, and only the layout on screen renders its rows.
(function(){
  var d=document,W=window,lk=d.getElementById('lk');
  if(!lk)return;
  function $(id){return d.getElementById(id)}
  var INDEX=lk.dataset.index,MIN=lk.dataset.min,FILE=lk.dataset.file,NAME=lk.dataset.name;
  // Nasdaq-100 only. Members already in the index when its record opens carry the record's first day as their join
  // date, so that day reads "1995 or earlier".
  var FIRST=lk.dataset.founding||'',FIRST_TEXT=FIRST?FIRST.slice(0,4)+' or earlier':'';
  var PHONE=W.matchMedia('(max-width:640px)');

  var form=$('lk-form'),input=$('lk-date'),err=$('lk-err'),todayBtn=$('lk-today'),area=$('lk-area'),live=$('lk-live');
  var q=$('lk-q'),copyBtn=$('lk-copy'),csvBtn=$('lk-csv'),tools=copyBtn.parentNode,xp=$('lk-xp'),xpBtn=null;
  var res=$('lk-res'),head=res.querySelector('.lk-head'),dOut=$('lk-d'),shown=$('lk-shown'),shownN=$('lk-n');
  var body=res.querySelector('.lk-body'),gate=$('lk-gate'),table=$('lk-table'),rowsEl=$('lk-rows'),none=$('lk-none');
  var filter=$('lk-filter'),fn=$('lk-fn'),pop=$('lk-pop');
  var mform=$('lk-mform'),minput=$('lk-mdate'),merr=$('lk-merr'),marea=$('lk-marea'),mq=$('lk-mq'),mres=$('lk-mres');
  var mbar=mres.querySelector('.lk-mbar'),msum=mres.querySelector('.lk-msum'),mbody=$('lk-mbody'),mgate=$('lk-mgate');
  var mlist=$('lk-mlist'),mnone=$('lk-mnone'),mfilter=$('lk-mfilter'),mfn=$('lk-mfn'),msort=$('lk-msort'),mtpl=$('lk-mrow');
  var sheet=$('lk-sheet'),sn=$('lk-sn'),sw=$('lk-sw'),SW_MANY=sw.textContent;
  var views={empty:[$('lk-empty'),$('lk-mempty')],plan:[$('lk-plan'),$('lk-mplan')],nokey:[$('lk-nokey'),$('lk-mnokey')],res:[res,mres]};
  var dates=[input,minput],gos=[form.querySelector('.lk-go'),mform.querySelector('.lk-go')];

  var MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];
  function pad(n){return (n<10?'0':'')+n}
  function dmy(s){return s.slice(8,10)+'/'+s.slice(5,7)+'/'+s.slice(0,4)}
  function longDate(s){return (+s.slice(8,10))+' '+MONTHS[+s.slice(5,7)-1]+' '+s.slice(0,4)}
  var MSG_BAD='That date is not valid.',MSG_RANGE='Pick a date from '+longDate(MIN)+' to today.',MSG_DOWN='The lookup is unavailable right now. Please try again later.';
  // Set to the UTC date when the free lookups ran out. The server's own count is what enforces the limit.
  var FLAG='xfl_lk_used';
  var now=new Date(),today=now.getFullYear()+'-'+pad(now.getMonth()+1)+'-'+pad(now.getDate());
  dates.forEach(function(el){el.max=el.value=today});

  // exportOk is true or false once a signed-in lookup has said, and null until then. open is the phone row shown open.
  var S={rows:[],date:'',exportOk:null,sort:'name',dir:1,status:'all',q:'',open:null};
  var signedIn=false,apiKey=null,busy=false;

  function show(v){for(var k in views)views[k].forEach(function(el){el.hidden=k!==v})}
  function setErr(t){err.textContent=merr.textContent=t}
  function joined(r){return FIRST&&r.added_date===FIRST?FIRST_TEXT:r.added_date?dmy(r.added_date):''}
  function status(r){return r.status==='active'?'Active':r.status==='left'?'Left · '+r.left_year:''}

  // Sorting. Empty cells go last in both directions, and ties fall back to the company name.
  function key(r,k){
    if(k==='status')return r.status==='active'?0:r.status==='left'?r.left_year:null;
    return k==='name'?r.name:k==='ticker'?r.ticker:r.added_date;
  }
  function order(k,dir){return function(a,b){
    var x=key(a,k),y=key(b,k),c;
    if(x==null||y==null)c=x==y?0:x==null?1:-1;
    else c=dir*(typeof x==='number'?x-y:k==='joined'?(x<y?-1:x>y?1:0):x.localeCompare(y));
    return c||(k!=='name'?order('name',1)(a,b):0);
  }}
  // The rows shown, after the search on company or ticker, the status filter and the sort.
  function visible(){
    var t=S.q.trim().toLowerCase();
    return S.rows.filter(function(r){
      return (!t||(r.name||'').toLowerCase().indexOf(t)>-1||(r.ticker||'').toLowerCase().indexOf(t)>-1)
        &&(S.status==='all'||r.status===S.status);
    }).sort(order(S.sort,S.dir));
  }

  function cell(text,cls){var c=d.createElement('div');c.setAttribute('role','cell');if(cls)c.className=cls;c.textContent=text;return c}
  function renderDesk(list){
    var f=d.createDocumentFragment();
    list.forEach(function(r){
      var row=d.createElement('div');row.className='lk-row';row.setAttribute('role','row');
      row.appendChild(cell(r.name));
      row.appendChild(cell(r.ticker||''));
      row.appendChild(cell(joined(r)));
      row.appendChild(r.status?cell(status(r),'lk-st'+(r.status==='left'?' lk-left':'')):cell(''));
      f.appendChild(row);
    });
    rowsEl.textContent='';rowsEl.appendChild(f);
    none.hidden=list.length>0||!S.rows.length;
  }
  // A phone row is a button. It opens a strip below it with the join date and the full status.
  function renderPhone(list){
    var f=d.createDocumentFragment();
    list.forEach(function(r){
      var row=mtpl.content.firstElementChild.cloneNode(true),b=row.firstElementChild,st=b.children[1],strip=row.lastElementChild,open=r===S.open;
      b.querySelector('.lk-mrow-n').textContent=r.name;
      b.querySelector('.lk-mrow-t').textContent=r.ticker||'';
      st.textContent=r.status==='active'?'Active':r.status==='left'?'Left '+r.left_year:'';
      if(r.status)st.classList.add(r.status==='active'?'lk-st-a':'lk-st-l');
      strip.children[0].lastElementChild.textContent=joined(r);
      strip.children[1].lastElementChild.textContent=status(r);
      b.setAttribute('aria-expanded',String(open));strip.hidden=!open;
      row._r=r;f.appendChild(row);
    });
    mlist.textContent='';mlist.appendChild(f);
    mnone.hidden=list.length>0||!S.rows.length;
  }
  function render(){
    var list=visible(),filtered=!!S.q.trim()||S.status!=='all';
    if(PHONE.matches)renderPhone(list);else renderDesk(list);
    shown.hidden=!filtered;shownN.textContent=list.length;
    $('lk-mall').hidden=filtered;$('lk-mshown').hidden=!filtered;$('lk-mn').textContent=list.length;$('lk-mclear').hidden=!filtered;
    $('lk-md').textContent=S.date?dmy(S.date):'';$('lk-mt').textContent=S.rows.length;
    table.querySelectorAll('[role=columnheader]').forEach(function(h){
      var k=h.querySelector('.lk-sort').dataset.sort;
      h.setAttribute('aria-sort',k===S.sort?(S.dir===1?'ascending':'descending'):'none');
    });
    var n={all:S.rows.length,active:0,left:0};
    S.rows.forEach(function(r){if(r.status)n[r.status]++});
    pop.querySelectorAll('[data-status]').forEach(function(b){
      b.setAttribute('aria-checked',String(b.dataset.status===S.status));
      b.querySelector('.lk-c').textContent=n[b.dataset.status];
    });
    fn.textContent=S.status==='all'?'':'1';
    filter.classList.toggle('lk-on',S.status!=='all'||!pop.hidden);
    mfn.textContent=S.status==='all'?'':' · 1';
    mfilter.classList.toggle('lk-on',S.status!=='all');
    sheet.querySelectorAll('[data-status]').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.status===S.status))});
    sn.textContent=list.length;sw.textContent=list.length===1?sw.dataset.one:SW_MANY;
    var v=S.sort+':'+S.dir;
    if([].some.call(msort.options,function(o){return o.value===v}))msort.value=v;
  }
  PHONE.addEventListener('change',function(){closeSheet(false);render()});

  function load(b,exportOk){
    S.rows=b.members;S.date=b.date;S.exportOk=exportOk;S.open=null;
    dOut.textContent=dmy(b.date);
    table.setAttribute('aria-label',NAME+' members on '+dmy(b.date));
    head.hidden=mbar.hidden=msum.hidden=false;
    gate.hidden=mgate.hidden=true;body.classList.remove('lk-gated');mbody.classList.remove('lk-gated');
    show('res');render();
  }
  // Free lookups used up. The list that is loaded stays, blurred, under the card.
  function showGate(){
    head.hidden=mbar.hidden=msum.hidden=!S.date;
    gate.hidden=mgate.hidden=false;body.classList.add('lk-gated');mbody.classList.add('lk-gated');
    show('res');render();
  }
  function showNo(v){S.rows=[];S.date='';show(v)}

  function utcDay(){return new Date().toISOString().slice(0,10)}
  function usedUp(){try{return localStorage.getItem(FLAG)===utcDay()}catch(e){return false}}
  function markUsed(){try{localStorage.setItem(FLAG,utcDay())}catch(e){}}

  // The header's shared auth client, as the dashboard reads it. No client means signed out.
  function session(){
    var c=W.__xflSb?Promise.resolve(W.__xflSb):W.__xflSbLoading?W.__xflSbLoading.then(function(){return W.__xflSb}):Promise.resolve(null);
    return c.then(function(sb){return sb?sb.auth.getSession():null}).then(function(r){return (r&&r.data&&r.data.session)||null}).catch(function(){return null});
  }
  // A signed-in visitor's own API key, kept in memory only.
  function getKey(s){
    if(apiKey)return Promise.resolve(apiKey);
    return fetch('/v1/auth/key',{headers:{'Authorization':'Bearer '+s.access_token},cache:'no-store'}).then(function(r){
      if(!r.ok)throw new Error('key');
      return r.json();
    }).then(function(b){var f=(b.keys||[]).filter(function(x){return x.key})[0];return apiKey=f?f.key:null});
  }

  // Signed out, the free lookup counted by the server. Signed in, the visitor's own key and plan limits.
  function ask(date,key){
    return fetch('/lookup/'+INDEX+'?date='+date,{headers:key?{'X-API-Key':key}:{},cache:'no-store',credentials:'same-origin'}).then(function(r){
      return r.json().catch(function(){return {}}).then(function(b){
        if(r.ok){load(b,key?!!b.export_allowed:null);if(b.limit_reached)markUsed();return}
        if(b.error==='lookup_limit'){markUsed();return showGate()}
        if(b.error==='plan_limit')return showNo('plan');
        if(b.error==='no_key'){apiKey=null;return showNo('nokey')}
        setErr(b.error==='invalid_date'?MSG_BAD:b.error==='date_out_of_range'?MSG_RANGE:MSG_DOWN);
      });
    });
  }
  function lookup(date){
    return session().then(function(s){
      signedIn=!!s;
      if(!s)return usedUp()?showGate():ask(date,null);
      return getKey(s).then(function(k){return k?ask(date,k):showNo('nokey')});
    });
  }

  // While a lookup is out the controls are disabled, a list on screen dims under a spinner, and a polite live region
  // says Loading. Every outcome ends it.
  function setBusy(on){
    busy=on;
    gos.concat(dates,[todayBtn]).forEach(function(el){el.disabled=on});
    [area,marea].forEach(function(a){a.classList.toggle('lk-busy',on);a.setAttribute('aria-busy',String(on))});
    live.textContent=on?'Loading':'';
  }
  function submit(e){
    e.preventDefault();
    if(busy)return;
    var date=e.currentTarget.querySelector('.lk-date').value;
    setErr('');closeXp(false);
    if(!/^\d{4}-\d{2}-\d{2}$/.test(date)){setErr(MSG_BAD);return}
    if(date<MIN||date>today){setErr(MSG_RANGE);return}
    setBusy(true);
    lookup(date).catch(function(){setErr(MSG_DOWN)}).then(function(){setBusy(false)});
  }
  [form,mform].forEach(function(f){f.addEventListener('submit',submit)});
  // The two date boxes and the two search boxes hold the same value, so a resize keeps what was typed.
  dates.forEach(function(el){el.addEventListener('input',function(){dates.forEach(function(o){if(o!==el)o.value=el.value})})});
  todayBtn.addEventListener('click',function(){dates.forEach(function(el){el.value=today})});
  [q,mq].forEach(function(el){el.addEventListener('input',function(){S.q=el.value;(el===q?mq:q).value=el.value;render()})});
  function clearFilters(){S.q=q.value=mq.value='';S.status='all';render()}
  $('lk-clear').addEventListener('click',clearFilters);
  $('lk-mclear').addEventListener('click',clearFilters);
  table.querySelector('.lk-hd').addEventListener('click',function(e){
    var b=e.target.closest('.lk-sort');
    if(!b)return;
    var k=b.dataset.sort;S.dir=S.sort===k?-S.dir:1;S.sort=k;render();
  });
  msort.addEventListener('change',function(){var p=msort.value.split(':');S.sort=p[0];S.dir=+p[1];render()});
  // Phone rows open one at a time.
  mlist.addEventListener('click',function(e){
    var b=e.target.closest('.lk-mrow-b');
    if(!b)return;
    var r=b.parentNode._r,open=S.open!==r,was=mlist.querySelector('.lk-mrow-b[aria-expanded=true]');
    if(was){was.setAttribute('aria-expanded','false');was.nextElementSibling.hidden=true}
    S.open=open?r:null;
    if(open){b.setAttribute('aria-expanded','true');b.nextElementSibling.hidden=false}
  });

  // The phone Filters sheet. Focus stays inside it while it is open, Escape or the backdrop closes it, and focus then
  // returns to the Filters button.
  function openSheet(){
    sheet.hidden=false;d.documentElement.style.overflow='hidden';mfilter.setAttribute('aria-expanded','true');
    sheet.querySelector('[data-status][aria-pressed=true]').focus();
  }
  function closeSheet(refocus){
    if(sheet.hidden)return;
    sheet.hidden=true;d.documentElement.style.overflow='';mfilter.setAttribute('aria-expanded','false');
    if(refocus)mfilter.focus();
  }
  mfilter.addEventListener('click',openSheet);
  sheet.addEventListener('click',function(e){
    var s=e.target.closest('[data-status]');
    if(s){S.status=s.dataset.status;render();return}
    if(e.target.closest('#lk-sclear')){S.status='all';render();return}
    if(e.target.closest('[data-close]'))closeSheet(true);
  });
  sheet.addEventListener('keydown',function(e){
    if(e.key==='Escape'){e.stopPropagation();closeSheet(true);return}
    if(e.key!=='Tab')return;
    var f=sheet.querySelectorAll('button'),first=f[0],last=f[f.length-1];
    if(e.shiftKey&&d.activeElement===first){e.preventDefault();last.focus()}
    else if(!e.shiftKey&&d.activeElement===last){e.preventDefault();first.focus()}
  });

  // The status filter closes on a pick, a press outside it or Escape.
  function setPop(open){pop.hidden=!open;filter.setAttribute('aria-expanded',String(open));filter.classList.toggle('lk-on',open||S.status!=='all')}
  filter.addEventListener('click',function(){setPop(pop.hidden)});
  pop.addEventListener('click',function(e){
    var b=e.target.closest('[data-status]');
    if(!b)return;
    S.status=b.dataset.status;setPop(false);render();
  });
  d.addEventListener('pointerdown',function(e){
    if(!pop.hidden&&!e.target.closest('[data-pop]'))setPop(false);
    // A press on the button that opened the popup is left to its own click, which closes it.
    if(!xp.hidden&&!xp.contains(e.target)&&!xpBtn.contains(e.target)){
      var b=xpBtn;closeXp(false);
      setTimeout(function(){if(!d.activeElement||d.activeElement===d.body)b.focus()},0);
    }
  });
  d.addEventListener('keydown',function(e){
    if(e.key!=='Escape')return;
    if(!pop.hidden){setPop(false);filter.focus()}
    closeXp(true);
  });

  // Rows cannot be selected, copied or dragged out.
  ['copy','cut','contextmenu','selectstart','dragstart'].forEach(function(t){[table,mlist].forEach(function(el){el.addEventListener(t,function(e){e.preventDefault()})})});

  // Copy and Download CSV act on the rows shown, on a paid plan. Anyone else gets the export popup under the button.
  var HEAD=['Company','Ticker','Joined','Status today','Year left'];
  // A cell a spreadsheet would read as a formula (one starting with = + - @, a tab or a carriage return) starts with a
  // single quote instead, in both Copy and Download CSV.
  function safe(v){return /^[=+\-@\t\r]/.test(v)?"'"+v:v}
  function lines(){
    return [HEAD].concat(visible().map(function(r){
      return [r.name||'',r.ticker||'',FIRST&&r.added_date===FIRST?FIRST_TEXT:r.added_date||'',
        r.status==='active'?'Active':r.status==='left'?'Left':'',r.status==='left'?String(r.left_year):''].map(safe);
    }));
  }
  function openXp(btn,kind){
    xp.querySelectorAll('[data-xp]').forEach(function(el){el.hidden=el.dataset.xp!==kind});
    xp.hidden=false;xpBtn=btn;btn.setAttribute('aria-expanded','true');
    var w=xp.offsetWidth,right=btn.offsetLeft+btn.offsetWidth;
    xp.style.left=Math.max(0,Math.min(right-w,tools.clientWidth-w))+'px';
    xp.style.top=(btn.offsetTop+btn.offsetHeight+8)+'px';
    xp.querySelector('.lk-cta:not([hidden])').focus();
  }
  function closeXp(refocus){
    if(xp.hidden)return;
    xp.hidden=true;xpBtn.setAttribute('aria-expanded','false');
    if(refocus)xpBtn.focus();
  }
  // Signed out, or signed in on the free plan, the popup shows whether or not a list is loaded. On a paid plan the
  // buttons wait for a list. A signed-in visitor's plan is known from their first lookup.
  function exporter(run){return function(e){
    var btn=e.currentTarget;
    if(!xp.hidden&&xpBtn===btn)return closeXp(true);
    if(!signedIn)return openXp(btn,'out');
    if(S.exportOk===false)return openXp(btn,'free');
    if(!S.rows.length||!S.exportOk)return;
    run();
  }}
  copyBtn.addEventListener('click',exporter(function(){
    var tsv=lines().map(function(c){return c.map(function(v){return v.replace(/[\t\r\n]+/g,' ')}).join('\t')}).join('\n')+'\n';
    var label=copyBtn.querySelector('span');
    navigator.clipboard.writeText(tsv).then(function(){label.textContent='Copied';setTimeout(function(){label.textContent='Copy'},1500)},function(){});
  }));
  csvBtn.addEventListener('click',exporter(function(){
    var csv=lines().map(function(c){return c.map(function(v){return /[",\r\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v}).join(',')}).join('\r\n')+'\r\n';
    var a=d.createElement('a');
    a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
    a.download=FILE+'-constituents-'+S.date+'.csv';
    d.body.appendChild(a);a.click();a.remove();
    setTimeout(function(){URL.revokeObjectURL(a.href)},0);
  }));

  show('empty');
  session().then(function(s){signedIn=!!s});
})();

// The API card. It types the page's own query, shows four rows of the answer, highlights the date and moves on to the
// next index. It runs while the card is at least 35% in view, follows the mouse slightly, and stays still under reduced
// motion (the page's HTML holds its first frame). The rows are real: GET /v1/index/{index}?as_of=DATE answered with
// these tickers, names and added dates on 2026-10-09, the last column is the year of the removed_date it served, and
// the totals are its meta.total for that date.
(function(){
  var d=document,W=window,card=d.getElementById('lk-api');
  if(!card||!W.IntersectionObserver||W.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  var SC=[
    {ix:'sp500',label:'S&P 500',iso:'2008-09-15',total:500,rows:[['AAPL','APPLE INC','1982-11-18',''],['LEH','LEHMAN BROTHERS HOLDINGS INC','1998-01-12','2008'],['MER','MERRILL LYNCH & CO INC','1982-04-08','2008'],['MSFT','MICROSOFT CORP','1994-06-07','']]},
    {ix:'ndx100',label:'Nasdaq-100',iso:'2000-03-10',total:100,rows:[['AMZN','AMAZON COM INC','1998-12-21',''],['EBAY','EBAY INC','1999-10-06','2023'],['PSFT','PEOPLESOFT INC','1995-12-18','2004'],['SBUX','STARBUCKS CORP','1996-11-25','']]},
    {ix:'djia',label:'Dow Jones',iso:'1999-11-01',total:30,rows:[['KO','COCA COLA CO','1932-05-26',''],['GE','GENERAL ELECTRIC CO','1907-11-07','2018'],['HD','HOME DEPOT INC','1999-11-01',''],['INTC','INTEL CORP','1999-11-01','2024']]}
  ];
  function $(id){return d.getElementById(id)}
  var res=$('lk-ares'),aq=$('lk-aq'),tabs=$('lk-atabs').children,ix=$('lk-aix'),url=$('lk-aurl'),date=$('lk-adate');
  var headEl=$('lk-ahead'),count=$('lk-acount'),more=$('lk-amore'),rows=$('lk-arows').children,t=0;
  function dmy(s){return s.slice(8,10)+'/'+s.slice(5,7)+'/'+s.slice(0,4)}
  function run(i){
    var sc=SC[i],n=0;
    cur=i;
    clearTimeout(t);
    res.classList.remove('lk-ares');aq.classList.remove('lk-asel');aq.classList.add('lk-typing');
    for(var k=0;k<tabs.length;k++)tabs[k].classList.toggle('lk-cur',k===i);
    ix.textContent=url.textContent=sc.ix;date.textContent='';headEl.textContent=sc.label+' · '+dmy(sc.iso);
    function type(){
      date.textContent=sc.iso.slice(0,++n);
      if(n<sc.iso.length){t=setTimeout(type,65);return}
      t=setTimeout(function(){
        aq.classList.remove('lk-typing');res.classList.add('lk-ares');
        t=setTimeout(function(){aq.classList.add('lk-asel');t=setTimeout(function(){run((i+1)%SC.length)},650)},4200);
      },280);
    }
    // The answer changes while it is faded out.
    t=setTimeout(function(){
      count.textContent=sc.total;more.textContent=sc.total-4;
      sc.rows.forEach(function(r,k){for(var j=0;j<4;j++)rows[k].children[j].textContent=r[j]});
      type();
    },450);
  }
  // It runs only while the card is in view and the tab is showing, and restarts the current index when it returns.
  var cur=+card.dataset.tab,on=false,seen=false;
  function go(){if(!on&&seen&&!d.hidden){on=true;run(cur)}}
  function stop(){on=false;clearTimeout(t)}
  new IntersectionObserver(function(es){seen=es[0].isIntersecting;if(seen)go();else stop()},{threshold:.35}).observe(card);
  d.addEventListener('visibilitychange',function(){if(d.hidden)stop();else go()});
  card.addEventListener('mousemove',function(e){
    var r=card.getBoundingClientRect();
    card.style.setProperty('--px',((e.clientX-r.left)/r.width-.5)*2);card.style.setProperty('--py',((e.clientY-r.top)/r.height-.5)*2);
  });
  card.addEventListener('mouseleave',function(){card.style.setProperty('--px',0);card.style.setProperty('--py',0)});
})();
