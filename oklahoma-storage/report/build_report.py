"""Build the self-contained report using only the standard library. No network calls."""
from pathlib import Path
from collections import Counter, defaultdict
from urllib.parse import urlparse
import hashlib, json, re
ROOT = Path(__file__).resolve().parent.parent
R = json.loads((ROOT / 'report/research.json').read_text())
raw = json.loads((ROOT / 'oklahoma-storage-master.json').read_text())
def norm(s): return re.sub(r'[^a-z0-9]', '', s.lower())
def ident(s): return hashlib.sha256(s.encode()).hexdigest()[:12]
def domain(url): return urlparse(url).netloc.lower().removeprefix('www.')
def addr(s, city):
 s=s.lower().split(',')[0]
 for a,b in [('northwest','nw'),('northeast','ne'),('southwest','sw'),('southeast','se'),('north','n'),('south','s'),('east','e'),('west','w'),('street','st'),('avenue','ave'),('boulevard','blvd'),('road','rd'),('highway','hwy'),('drive','dr'),('lane','ln')]: s=re.sub(r'\b'+a+r'\b',b,s)
 return norm(city)+'|'+norm(s)
aliases={'Extra Space':'Extra Space Storage','Extra Space (Life Storage)':'Extra Space Storage','SecurCare':'Public Storage','SecurCare Self Storage':'Public Storage','Arborstone':'Arborstone Storage','SpareBox':'SpareBox Storage','StoreLocal':'Storelocal',"Storage 'R' Us":'Storage R Us','Shift Self Storage':'Shift Storage'}
domains={'americanselfstorageok.com':'American Self Storage','arborstonestorage.com':'Arborstone Storage','click4storage.com':'Click Storage','storage-r-us.net':'Storage R Us','mylockerstorage.com':'Locker Storage','economystoragepark.com':'Economy Storage Park','haydenslockup.com':"Hayden’s Lock-Up",'edmondnorthstorage.com':'Edmond North / Bryant Square / Cross Timbers','ftstorage.com':'Fortress Storage Solutions','sunshineatnorman.com':'Sunshine Self Storage','primevaultselfstoragenoble.com':'Prime Vault Self Storage','nobleselfstorageok.com':'Noble Self Storage','diamondselfstorage.net':'Diamond Self Storage','enid-storage.com':'Attic Annex / West Willow','ministorageblackwell.com':'Blackwell / Downtown Mini Storage','donner-springs.com':'Donner-Springs Storage','valueplusstorage.com':'Value Plus Storage','astorageclosetok.com':'A Storage Closet','1010storage.com':'1010 Storage','hwy92storage.com':'Highway 92 Storage','benbrookstorage.com':'Benbrook Storage','tagstorageok.com':'TAG Storage','bjstorage.com':'B & J Storage','thunderalleystorage.com':'Thunder Alley Storage','msmstorage.com':'Mini Storage & More','aaaministoragealtus.com':'AAA Mini Storage — Altus','ezstoragestillwater.com':'EZ Storage','durantselfstoragellc.com':'Durant Self Storage'}
facilities=[]; groups={}; addresses=defaultdict(list); names=defaultdict(list)
for i,r in enumerate(raw):
 f=dict(r); f['id']='f-'+ident(f"{r['name']}|{r['address']}|{r['city']}|{i}");f['raw_index']=i;f['flags']=[]
 host=domain(r.get('website',''));brand=r.get('brand','')
 if host in domains: name=domains[host];basis='Shared operator domain / normalized brand; legal ownership unverified'
 elif brand and brand!='independent':name=aliases.get(brand,brand);basis='Directory brand assignment; property affiliation not independently verified'
 else:name=r['name'];basis='Single directory record; ownership not researched'
 # Unknown independent same-name businesses are never merged across towns on name alone.
 key=name if host in domains or brand not in ('','independent') else name+'|'+r['city']+'|'+f['id']
 cid='c-'+ident(key);f['company_id']=cid;f['company_name']=name;f['grouping_basis']=basis
 if cid not in groups:
  meta=R['companies'].get(name,{'category':'Ownership unverified','parent':'Not established','ownership_note':'No public REIT parent or PE sponsor has been established for this profile. Unknown does not mean independently owned.','sources':[],'ticker':'','private_capital':'Not established'})
  groups[cid]={'id':cid,'name':name,**meta,'facility_ids':[],'grouping_basis':basis,'research_only':False}
 groups[cid]['facility_ids'].append(f['id'])
 if r.get('address') and re.match(r'^\d',r['address']):addresses[addr(r['address'],r['city'])].append(f)
 names[norm(r['name'])].append(f)
 if f.get('geo_approx'):f['flags'].append('Approximate coordinates')
 if f.get('lat') is None or f.get('lng') is None:f['flags'].append('No coordinates')
 for field in ['address','phone','website']:
  if not f.get(field):f['flags'].append('Missing '+field)
 if any(w in f.get('notes','').lower() for w in ['duplicate','rebrand','same address']):f['flags'].append('Source notes require identity review')
 facilities.append(f)
collisions=[]
for key,fs in addresses.items():
 if len(fs)>1:
  for f in fs:f['flags'].append('Shared normalized address — possible duplicate / rebrand')
  collisions.append({'address':fs[0]['address'],'city':fs[0]['city'],'facility_ids':[f['id'] for f in fs]})
name_candidates=[]
for k,fs in names.items():
 if len(set(f['company_id'] for f in fs))>1 and len(fs)>1:
  name_candidates.append({'name':fs[0]['name'],'facility_ids':[f['id'] for f in fs]})
byid={f['id']:f for f in facilities}
def match(city,address,name):
 candidates=[f for f in facilities if f['city'].lower()==city.lower()]
 result=[f for f in candidates if re.match(r'^\d',address) and addr(f['address'],city)==addr(address,city)]
 if not result:result=[f for f in candidates if norm(name)==norm(f['name'])]
 return result
for s in R['sales']:
 fs=[]
 for a in s['address'].split('; '):fs.extend(match(s['city'],a,s['name']))
 s['facility_ids']=sorted(set(f['id'] for f in fs));s['company_ids']=sorted(set(f['company_id'] for f in fs));s['match_basis']='Address/name candidate; verify parcel and seller' if fs else 'Not matched to baseline directory'
 s['id']='s-'+ident(s['name']+'|'+s['city'])
 if not s['company_ids']:
  cid='c-'+ident('sale|'+s['name']);groups[cid]={'id':cid,'name':s['name'],'category':'Ownership unverified','parent':'Seller / beneficial owner not established','ownership_note':'Property-offering profile, not a verified corporate entity. The property was not matched to the baseline directory.','sources':[s['source']],'ticker':'','private_capital':'Not established','facility_ids':[],'grouping_basis':'Research-only offering profile','research_only':True};s['company_ids']=[cid]
for n,r in enumerate(R['rates']):
 r['id']='r-'+str(n+1);fs=match(r['city'],r['address'],r['facility']);r['facility_ids']=[f['id'] for f in fs]
 r['company_ids']=sorted(set(f['company_id'] for f in fs)) or [c['id'] for c in groups.values() if c['name']==r['company']]
 if not r['company_ids']:
  cid='c-'+ident('rate|'+r['company']);groups[cid]={'id':cid,'name':r['company'],'category':'Ownership unverified','parent':'Not established','ownership_note':'Operator rental page researched; corporate ownership not established. Not matched to the baseline directory.','sources':[r['source']],'ticker':'','private_capital':'Not established','facility_ids':[],'grouping_basis':'Research-only rental profile','research_only':True};r['company_ids']=[cid]
for c in groups.values():
 fs=[byid[i] for i in c['facility_ids']];c['record_count']=len(fs);c['cities']=sorted(set(f['city'] for f in fs));c['regions']=dict(Counter(f['region'] for f in fs));c['types']=dict(Counter(f['type'] for f in fs));c['brands']=sorted(set(f['brand'] for f in fs));c['websites']=sorted(set(f['website'] for f in fs if f['website']));c['flagged_records']=sum(bool(f['flags']) for f in fs)
 c['rate_ids']=[r['id'] for r in R['rates'] if c['id'] in r['company_ids']];c['sale_ids']=[s['id'] for s in R['sales'] if c['id'] in s['company_ids']]
 c['baseline_evidence']='Supplied directory. Collection date stated as 2026-10-19; original per-record collection citations and dates unavailable.'
companies=sorted(groups.values(),key=lambda c:(-c['record_count'],c['name'].lower()))
summary={'records':len(raw),'cities':len(set(f['city'] for f in facilities)),'company_profiles':len(companies),'multi_record_profiles':sum(c['record_count']>1 for c in companies),'research_only_profiles':sum(c['research_only'] for c in companies),'approximate':sum(bool(f.get('geo_approx')) for f in facilities),'missing':{k:sum(not f.get(k) for f in facilities) for k in ['address','phone','website','zip','lat','lng']},'address_collision_groups':len(collisions),'city_counts':dict(Counter(f['city'] for f in facilities).most_common()),'regions':dict(Counter(f['region'] for f in facilities)),'types':dict(Counter(f['type'] for f in facilities)),'categories':dict(Counter(f and groups[f['company_id']]['category'] for f in facilities))}
D={**R,'facilities':facilities,'companies':companies,'summary':summary,'address_collisions':collisions,'name_candidates':name_candidates}
assert len({f['id'] for f in facilities})==len(raw)
assert sum(c['record_count'] for c in companies)==len(raw)
assert all(s in R['sources'] for c in companies for s in c['sources'])
assert all(r['source'] in R['sources'] for r in R['rates']+R['sales']+R['benchmarks'])
# Reuse the established directory's bundled Leaflet assets, retaining their license headers.
old=(ROOT/'oklahoma-storage-directory.html').read_text()
scripts=re.findall(r'<script[^>]*>(.*?)</script>',old,re.S)
leaflet_css=re.search(r'<style>(.*?)</style>',old,re.S).group(1).split(':root{')[0]
template=(ROOT/'report/report.template.html').read_text()
packed=json.dumps(D,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
html=template.replace('<!--LEAFLET_CSS-->',leaflet_css).replace('<!--LEAFLET_JS-->','\n'.join('<script>'+s+'</script>' for s in scripts[:2])).replace('/*REPORT_DATA*/',packed)
(ROOT/'oklahoma-storage-market-report.html').write_text(html)
(ROOT/'report/report-data.json').write_text(json.dumps(D,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(summary,indent=2))
