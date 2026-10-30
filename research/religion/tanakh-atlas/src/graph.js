/* ============================================================
   THE CONSTELLATION — hand-rolled force graph
   ============================================================ */
const G={token:0,nodes:[],links:[],types:{work:true,person:false,place:false,theme:false},scale:1,ox:0,oy:0,alpha:1,hover:null,sel:null,drag:null,pan:null,canvas:null,ctx:null,w:0,h:0,dpr:1,search:''};

function allGraphNodes(){
  const out=[];
  DATA.works.forEach(w=>out.push({id:w.id,type:'work',label:w.title,he:w.he,color:COLORS.work,sub:corpusName(w.corpus),summary:w.summary,corpus:w.corpus}));
  DATA.people.forEach(p=>out.push({id:p.id,type:'person',label:p.name,he:p.he_name,color:COLORS.person,sub:p.era||'Person',summary:p.key_idea||p.bio}));
  DATA.places.forEach(p=>out.push({id:p.id,type:'place',label:p.name,he:p.he_name,color:COLORS.place,sub:p.region||'Place',summary:p.bio}));
  DATA.themes.forEach(t=>out.push({id:t.id,type:'theme',label:t.name,he:t.he_name,color:COLORS.theme,sub:t.kind||'Idea',summary:t.short}));
  return out;
}
function buildGraph(){
  const all=allGraphNodes();
  G.nodes=all.filter(n=>G.types[n.type]);
  const ids=new Set(G.nodes.map(n=>n.id));
  const seen=new Set(); const links=[];
  const add=(a,b,kind)=>{if(!ids.has(a)||!ids.has(b)||a===b)return;const k=[a,b].sort().join('|');if(seen.has(k))return;seen.add(k);links.push({source:a,target:b,kind});};
  DATA.works.forEach(w=>{
    (w.connections||[]).forEach(c=>add(w.id,c.to,'conn'));
    (w.people||[]).forEach(p=>add(w.id,p,'member'));
    (w.places||[]).forEach(p=>add(w.id,p,'member'));
    (w.themes||[]).forEach(t=>add(w.id,t,'member'));
  });
  DATA.people.forEach(p=>(p.connections||[]).forEach(c=>add(p.id,c.to,'conn')));
  DATA.places.forEach(p=>(p.connections||[]).forEach(c=>add(p.id,c.to,'conn')));
  DATA.themes.forEach(t=>(t.connections||[]).forEach(c=>add(t.id,c.to,'conn')));
  G.links=links;
  const deg={}; links.forEach(l=>{deg[l.source]=(deg[l.source]||0)+1;deg[l.target]=(deg[l.target]||0)+1;});
  G.nodes.forEach(n=>{n.deg=deg[n.id]||0;n.r=(n.type==='work'?7.5:5.2)+Math.min(4.5,Math.sqrt(n.deg)*.9);});
  // initial positions
  const cx=G.w/2,cy=G.h/2; const rings={work:.16,person:.29,place:.37,theme:.44};
  const groups={}; G.nodes.forEach(n=>(groups[n.type]=groups[n.type]||[]).push(n));
  Object.entries(groups).forEach(([type,arr])=>{
    const rad=Math.min(G.w,G.h)*rings[type];
    arr.forEach((n,i)=>{const a=(i/arr.length)*Math.PI*2 + (type==='person'?.5:type==='place'?1.1:type==='theme'?1.7:0);
      n.x=cx+Math.cos(a)*rad+(Math.random()-.5)*28; n.y=cy+Math.sin(a)*rad+(Math.random()-.5)*28; n.vx=0;n.vy=0;});
  });
  // keep old positions when possible
  const old=new Map(G.nodes.map(n=>[n.id,n]));
  G.nodes=G.nodes.map(n=>{const o=old.get(n.id);return o?Object.assign(o,{deg:n.deg,r:n.r}):n;});
  G.alpha=1;
}
function graphStep(){
  const ns=G.nodes, links=G.links, cx=G.w/2, cy=G.h/2;
  for(let i=0;i<ns.length;i++){
    const a=ns[i];
    for(let j=i+1;j<ns.length;j++){
      const b=ns[j]; let dx=b.x-a.x,dy=b.y-a.y; let d2=dx*dx+dy*dy;
      if(d2<1)d2=1; if(d2>90000)continue;
      const d=Math.sqrt(d2); const f=Math.min(4.0,4200/d2);
      const fx=dx/d*f,fy=dy/d*f;
      a.vx-=fx;a.vy-=fy;b.vx+=fx;b.vy+=fy;
    }
  }
  links.forEach(l=>{
    const a=ns.find(n=>n.id===l.source),b=ns.find(n=>n.id===l.target); if(!a||!b)return;
    const dx=b.x-a.x,dy=b.y-a.y; const d=Math.hypot(dx,dy)||1;
    const rest=l.kind==='conn'?105:145;
    const f=(d-rest)*(l.kind==='conn'?.0055:.0035);
    const fx=dx/d*f,fy=dy/d*f;
    a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;
  });
  ns.forEach(n=>{
    n.vx+=(cx-n.x)*.0022; n.vy+=(cy-n.y)*.0022;
    if(n.fixed){n.vx=0;n.vy=0;return;}
    n.vx*=.86;n.vy*=.86;
    n.x+=n.vx*G.alpha; n.y+=n.vy*G.alpha;
  });
  // collision
  for(let i=0;i<ns.length;i++){for(let j=i+1;j<ns.length;j++){const a=ns[i],b=ns[j];const dx=b.x-a.x,dy=b.y-a.y;const d=Math.hypot(dx,dy)||1;const min=a.r+b.r+10;if(d<min){const f=(min-d)/d*.5;a.x-=dx*f;a.y-=dy*f;b.x+=dx*f;b.y+=dy*f;}}}
  G.alpha*=.985;
}
function graphFit(){
  if(!G.nodes.length)return;
  const xs=G.nodes.map(n=>n.x),ys=G.nodes.map(n=>n.y);
  const minx=Math.min(...xs),maxx=Math.max(...xs),miny=Math.min(...ys),maxy=Math.max(...ys);
  const bw=Math.max(1,maxx-minx),bh=Math.max(1,maxy-miny);
  G.scale=Math.min((G.w-80)/bw,(G.h-80)/bh,1.5); G.scale=Math.max(.22,G.scale);
  G.ox=G.w/2-((minx+maxx)/2)*G.scale; G.oy=G.h/2-((miny+maxy)/2)*G.scale;
}
function graphReset(){buildGraph();graphFit();G.alpha=1;G.sel=null;G.hover=null;$('#graph-panel').classList.remove('open');}
function graphToggle(type,btn){
  G.types[type]=!G.types[type]; if(btn)btn.classList.toggle('on',G.types[type]);
  if(!Object.values(G.types).some(Boolean)){G.types[type]=true;if(btn)btn.classList.add('on');toast('Keep at least one layer visible');return;}
  buildGraph();graphFit();G.alpha=1;
}
function graphSelect(id){
  const n=G.nodes.find(x=>x.id===id); if(!n)return;
  G.sel=id;
  const t=n.type;
  const link=routeFor(t,id)||'#/library';
  const nb=G.links.filter(l=>l.source===id||l.target===id).map(l=>l.source===id?l.target:l.source).map(x=>G.nodes.find(n=>n.id===x)).filter(Boolean).slice(0,7);
  $('#graph-panel-body').innerHTML=`<div class="gp-type">${esc(n.sub||t)}</div><h4>${esc(n.label)}</h4>${n.he?`<div class="he" style="color:var(--gold);font-size:1.05rem;margin-bottom:.7rem">${esc(n.he)}</div>`:''}
    <p>${esc(trunc(n.summary||'',240))}</p>
    <a class="btn sm" href="${link}" style="margin-top:.6rem">Open ${t==='theme'?'idea':t} ${ICONS.arrow}</a>
    ${nb.length?`<div class="gp-type" style="margin-top:1.4rem">Connected to</div><div class="chips">${nb.map(x=>`<a class="chip" href="#" onclick="graphSelect('${x.id}');return false">${esc(x.label)}</a>`).join('')}</div>`:''}`;
  $('#graph-panel').classList.add('open');
}
function graphScreen(e){
  const r=G.canvas.getBoundingClientRect(); return {x:e.clientX-r.left,y:e.clientY-r.top};
}
function graphPick(x,y){
  const wx=(x-G.ox)/G.scale,wy=(y-G.oy)/G.scale;
  for(let i=G.nodes.length-1;i>=0;i--){const n=G.nodes[i];if(Math.hypot(n.x-wx,n.y-wy)<n.r+8)return n;}
  return null;
}
function graphDraw(){
  const {ctx,w,h,dpr}=G;
  ctx.setTransform(dpr,0,0,dpr,0,0); ctx.clearRect(0,0,w,h);
  ctx.fillStyle='#0a0c11'; ctx.fillRect(0,0,w,h);
  // subtle vignette
  const grd=ctx.createRadialGradient(w*.5,h*.45,0,w*.5,h*.45,Math.max(w,h)*.7);
  grd.addColorStop(0,'rgba(201,164,92,.035)');grd.addColorStop(1,'rgba(0,0,0,0)');
  ctx.fillStyle=grd;ctx.fillRect(0,0,w,h);
  ctx.save();ctx.translate(G.ox,G.oy);ctx.scale(G.scale,G.scale);
  const sel=G.sel,hover=G.hover;
  const connected=new Set();
  if(sel||hover){const id=sel||hover;G.links.forEach(l=>{if(l.source===id)connected.add(l.target);if(l.target===id)connected.add(l.source);});}
  // edges
  G.links.forEach(l=>{
    const a=G.nodes.find(n=>n.id===l.source),b=G.nodes.find(n=>n.id===l.target);if(!a||!b)return;
    const active=(sel&&(l.source===sel||l.target===sel))||(hover&&(l.source===hover||l.target===hover));
    const dim=(sel||hover)&&!active;
    ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);
    ctx.strokeStyle=l.kind==='conn'?`rgba(201,164,92,${active?.55:dim?.04:.13})`:`rgba(180,190,210,${active?.28:dim?.025:.055})`;
    ctx.lineWidth=active?1.2:.7;ctx.stroke();
  });
  // nodes
  G.nodes.forEach(n=>{
    const active=n.id===sel||n.id===hover;
    const near=connected.has(n.id);
    const dim=(sel||hover)&&!active&&!near;
    ctx.beginPath();ctx.arc(n.x,n.y,n.r*(active?1.35:1),0,Math.PI*2);
    ctx.fillStyle=dim?'rgba(80,85,95,.25)':n.color;
    ctx.globalAlpha=dim?.45:1;ctx.fill();
    if(active){ctx.shadowColor=n.color;ctx.shadowBlur=18;ctx.fill();ctx.shadowBlur=0;}
    ctx.globalAlpha=1;
    if(active){ctx.beginPath();ctx.arc(n.x,n.y,n.r+5,0,Math.PI*2);ctx.strokeStyle=n.color;ctx.lineWidth=.8;ctx.stroke();}
  });
  // labels (collision-aware, works first)
  const showAll=G.scale>1.55;
  const boxes=[];
  const ordered=[...G.nodes].sort((a,b)=>(b.type==='work')-(a.type==='work')||b.deg-a.deg);
  ordered.forEach(n=>{
    const active=n.id===sel||n.id===hover;
    const isWork=n.type==='work';
    const near=connected.has(n.id);
    if(!(showAll||isWork||active||near))return;
    if((sel||hover)&&!active&&!near&&!isWork)return;
    ctx.font=`${active?'600':'400'} ${Math.max(9,11/G.scale)}px "Spectral", Georgia, serif`;
    ctx.textAlign='center';ctx.textBaseline='top';
    const label=n.label; const tw=ctx.measureText(label).width; const th=12/G.scale;
    const bx=n.x-tw/2-3, by=n.y+n.r+4, bw=tw+6;
    if(!active&&boxes.some(b=>bx<b.x+b.w&&bx+bw>b.x&&by<b.y+b.h&&by+th>b.y))return;
    boxes.push({x:bx,y:by,w:bw,h:th+1});
    ctx.fillStyle='rgba(10,12,17,.72)';ctx.fillRect(bx,by,bw,th+1);
    ctx.fillStyle=active?'#fff':(isWork?'rgba(236,229,214,.9)':'rgba(200,195,184,.7)');
    ctx.fillText(label,n.x,by);
  });
  ctx.restore();
}
function initGraph(){
  const canvas=$('#graph-canvas'); if(!canvas)return;
  const token=++G.token;
  G.canvas=canvas;G.ctx=canvas.getContext('2d');
  const parent=canvas.parentElement;
  const resize=()=>{
    G.dpr=Math.min(2,window.devicePixelRatio||1);
    G.w=parent.clientWidth;G.h=parent.clientHeight;
    canvas.width=Math.round(G.w*G.dpr);canvas.height=Math.round(G.h*G.dpr);
    canvas.style.width=G.w+'px';canvas.style.height=G.h+'px';
  };
  resize();
  buildGraph(); graphFit();
  for(let i=0;i<150;i++)graphStep();
  graphFit();
  G.alpha=.8;
  const loop=()=>{
    if(token!==G.token)return;
    if(G.alpha>.004){graphStep();graphDraw();}
    else if(G.dirty){graphDraw();G.dirty=false;}
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
  const ro=new ResizeObserver(()=>{resize();graphFit();G.dirty=true;});
  ro.observe(parent);
  let down=null,moved=false;
  canvas.addEventListener('pointerdown',e=>{
    const p=graphScreen(e); const n=graphPick(p.x,p.y); down={p,n,ox:G.ox,oy:G.oy}; moved=false;
    if(n){n.fixed=true;G.drag=n;canvas.setPointerCapture(e.pointerId);}
    else G.pan={x:p.x,y:p.y};
  });
  canvas.addEventListener('pointermove',e=>{
    const p=graphScreen(e);
    if(G.drag){const wx=(p.x-G.ox)/G.scale,wy=(p.y-G.oy)/G.scale;G.drag.x=wx;G.drag.y=wy;G.alpha=Math.max(G.alpha,.35);G.dirty=true;moved=true;return;}
    if(G.pan){const dx=p.x-G.pan.x,dy=p.y-G.pan.y;if(Math.abs(dx)+Math.abs(dy)>3)moved=true;G.ox=down.ox+dx;G.oy=down.oy+dy;G.dirty=true;return;}
    const n=graphPick(p.x,p.y);
    if((n&&n.id)!==G.hover){G.hover=n?n.id:null;G.dirty=true;canvas.style.cursor=n?'pointer':'grab';}
  });
  const up=e=>{
    if(G.drag){G.drag.fixed=false;G.drag=null;}
    if(down&&!moved&&down.n){graphSelect(down.n.id);G.dirty=true;}
    if(down&&!moved&&!down.n){G.sel=null;$('#graph-panel').classList.remove('open');}
    down=null;G.pan=null;
  };
  canvas.addEventListener('pointerup',up);
  canvas.addEventListener('pointercancel',up);
  canvas.addEventListener('wheel',e=>{
    e.preventDefault();const p=graphScreen(e);const f=e.deltaY<0?1.1:.9;
    const ns=Math.max(.2,Math.min(3,G.scale*f));const k=ns/G.scale;
    G.ox=p.x-(p.x-G.ox)*k;G.oy=p.y-(p.y-G.oy)*k;G.scale=ns;G.dirty=true;
  },{passive:false});
  const si=$('#graph-search');
  if(si)si.addEventListener('input',()=>{
    const q=si.value.toLowerCase().trim();G.search=q;
    const hit=G.nodes.find(n=>n.label.toLowerCase().includes(q)||(n.he||'').includes(q));
    if(q&&hit){G.sel=hit.id;G.ox=G.w/2-hit.x*G.scale;G.oy=G.h/2-hit.y*G.scale;graphSelect(hit.id);G.dirty=true;}
    else if(!q){G.sel=null;$('#graph-panel').classList.remove('open');G.dirty=true;}
  });
}
