"""Classify every company's ownership type from sourced evidence only. Adds own/ownLabel/ownDetail/ownEv to data/companies.json.
Evidence: Fortune company type + exchange + description + industry label; SEC submissions (deregistration forms, exchanges);
Wikipedia infobox 'type' + lead paragraph; Wikidata instance-of (P31) / legal form (P1454)."""
import json, re
C = json.load(open('data/companies.json'))
EV = json.load(open('data/ownership_evidence.json'))
WO = json.load(open('data/wikidata_ownership.json'))
LABEL = {'public': 'Publicly traded', 'gse': 'Government-sponsored enterprise', 'delisted': 'Acquired / delisted since list', 'mutual': 'Mutual / policyholder-owned',
         'coop': 'Cooperative', 'employee': 'Employee- / partner-owned', 'nonprofit': 'Nonprofit-owned', 'private': 'Private (other / unspecified)', 'unknown': 'Unknown'}
EXN = {'NYSE': 'NYSE', 'NASDAQ': 'Nasdaq', 'Nasdaq': 'Nasdaq', 'NYSEAM': 'NYSE American', 'OTC': 'OTC', 'TXSE': 'Texas Stock Exchange'}
def snip(text, m, w=110):
    s = max(0, m.start() - w); e = min(len(text), m.end() + w)
    return ('…' if s else '') + text[s:e].strip() + ('…' if e < len(text) else '')
def find(texts, pat, cs=False):
    for src, t, url in texts:
        if not t: continue
        # case-sensitive patterns skip proper nouns in names (e.g. 'Liberty Mutual'); structured fields are lower-cased first
        tt = t.lower() if cs and src.startswith(('Wikipedia infobox', 'Wikidata')) else t
        m = re.search(pat, tt) if cs else re.search(pat, tt, re.I)
        if m: return {'src': src, 'text': snip(t, m), 'url': url}
def norm(s): return re.sub(r'[^a-z]', '', re.sub(r'\b(inc|corp|corporation|co|company|the)\b', '', s.lower()))
for c in C:
    ev = EV[str(c['id'])]; wo = WO.get(c['qid'] or '', {})
    fort = ('Fortune company page', f"Company type: {c['type']}" + (f"; exchange {c['exchange']}" if c['exchange'] else ''), c['fortuneUrl'])
    texts = [('Fortune description', c.get('desc') or '', c['fortuneUrl']), ('Fortune industry label', c['industry'], c['fortuneUrl']),
             ('Wikipedia infobox type', ev.get('wiki_type') or '', c.get('wiki')), ('Wikipedia lead', ev.get('wiki_intro') or '', c.get('wiki')),
             ('Wikidata instance of / legal form', '; '.join(x['label'] or '' for x in wo.get('p31', []) + wo.get('legal', [])), f"https://www.wikidata.org/wiki/{c['qid']}" if c['qid'] else None)]
    # SEC evidence only from our ticker->CIK map or an exact SEC name match
    sec_ok = bool(c['cik']) or (ev.get('sec_name') and norm(ev['sec_name']) == norm(c['name']))
    cik = ev.get('cik') if sec_ok else None
    secu = f'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}' if cik else None
    dereg = [d for d in (ev.get('dereg') or []) if d['date'] >= '2026-01-01'] if sec_ok else []
    own, detail, evid = None, None, [{'src': fort[0], 'text': fort[1], 'url': fort[2]}]
    gse = find(texts, r'government[- ]sponsored|government-backed enterprise|conservatorship|state-owned enterprise of the United States')
    if c['type'] == 'Public':
        if gse: own, detail = 'gse', 'Shares trade OTC; under FHFA conservatorship' if c['exchange'] == 'OTC' else None; evid.append(gse)
        else:
            own = 'public'; ex = c['exchange'] or next(iter(ev.get('exchanges') or []), None); detail = EXN.get(ex, ex) if ex else 'Exchange n/a'
            if not c['exchange'] and ex: evid.append({'src': 'SEC submissions (exchanges)', 'text': ', '.join(ev['exchanges']), 'url': secu})
    elif c['type'] in ('Private',):
        was_public = sec_ok and (ev.get('last10k') or c.get('ticker'))
        acq = find(texts, r'(was )?acquired by [A-Z][\w ]+ in \w+ 20\d\d|merged with [A-Z][\w ]+|\bwas an American')
        if was_public and dereg and not re.search(r'taken private in 20(1|2[0-4])', c.get('desc') or ''):
            own = 'delisted'; detail = 'Public at list time; ' + ', '.join(f"SEC {d['form']} {d['date']}" for d in dereg[:2])
            evid.append({'src': 'SEC EDGAR filings', 'text': '; '.join(f"Form {d['form']} filed {d['date']}" for d in dereg), 'url': secu})
            if acq: evid.append(acq)
        else:
            rules = [('nonprofit', r'non-?profit corporation|founded as a nonprofit', 'Nonprofit parent'),
                     ('coop', r"cooperative|\bco-op\b|owned by (ranchers, farmers|these same independent owners)|owned solely by", 'Cooperative'),
                     ('mutual', r'\bmutual (insurance|life|holding|organization|company|ownership|structure)|reciprocal inter-insurance|owned by its policyholders|\(Mutual\)', None),
                     ('employee', r'employee[- ]owned|owned by (present and past )?employees|wholly owned by present and past employees|limited partnership|\bL\.P\.', None),
                     ('private', r'privately held|private corporation|taken private|^Private', None)]
            for key, pat, d in rules:
                h = find(texts, pat, cs=(key == 'mutual'))
                if h:
                    own = key; evid.append(h)
                    t = h['text'].lower()
                    detail = d or ('Reciprocal exchange' if 'reciprocal' in t else 'Mutual (Fortune industry label)' if h['src'] == 'Fortune industry label' else 'Mutual holding company' if 'holding' in t else 'Mutual insurer' if key == 'mutual' else
                                   'Partnership' if key == 'employee' and ('l.p.' in t or 'partnership' in t) else 'Employee-owned' if key == 'employee' else
                                   'Taken private' if 'taken private' in t else 'Privately held')
                    break
            if not own: own, detail = 'private', 'Fortune lists as private; form not stated in sources'
    else: own, detail = 'unknown', 'n/a'
    c['own'], c['ownLabel'], c['ownDetail'], c['ownEv'] = own, LABEL[own], detail, evid
    c['secExchanges'] = sorted(set(ev.get('exchanges') or [])) if sec_ok else []
json.dump(C, open('data/companies.json', 'w'), indent=0)
from collections import Counter
print(Counter(c['own'] for c in C)); print(Counter((c['own'], c['ownDetail']) for c in C if c['own'] != 'public'))
print(Counter(c['ownDetail'] for c in C if c['own'] == 'public'))
for c in C:
    if c['own'] != 'public': print(c['rank'], c['name'], '->', c['own'], '|', c['ownDetail'], '|', c['ownEv'][-1]['src'], '|', c['ownEv'][-1]['text'][:140])
s = json.load(open('data/stats.json')); s['ownership'] = dict(Counter(c['own'] for c in C)); json.dump(s, open('data/stats.json', 'w'), indent=1)
