"""Build Best_of_2026.html from lists.csv and master_rank.json.

The Lists tab is the directory. The Master list tab is every extracted title,
merged by category, from master_rank.json (written by build_master.py).
"""
import csv, json, calendar, datetime, re
from pathlib import Path
rows = list(csv.DictReader(open('lists.csv')))
TYPE = {
 'Retailer & platform': ['Amazon','Apple','Apple Podcasts','Audible','Barnes & Noble','Google','Rough Trade','Spotify','Waterstones','iHeartRadio','Goodreads','Letterboxd'],
 'Newspaper & broadcaster': ['BBC','Financial Times','NPR','New York Times','The Economist','The Guardian','The Telegraph','CNN (on Lonely Planet)','NPR (via WBUR)','The Current (MPR)','Time Out (on NYT list)'],
 'Library': ['New York Public Library','Chicago Public Library'],
 'Aggregator & scores': ['AlbumOfTheYear.org','Metacritic','Rotten Tomatoes','TV Guide','Broadway Scorecard'],
 'Awards body': ['Mercury Prize','National Book Foundation','Natural History Museum','Polaris Music Prize','The Booker Prizes','The Game Awards','Tony Awards',"The World's 50 Best"],
}
def srctype(o):
    for k,v in TYPE.items():
        if o in v: return k
    return 'Magazine & web outlet'
def kind(r):
    n = r['list']
    if re.search(r'so far', n, re.I): return 'So far'
    if re.search(r'award|nominee|\bwinners?\b|\bprize\b|book of the year|game of the year|show of the year', n, re.I): return 'Awards'
    if r['outlet'] in ('AlbumOfTheYear.org','Metacritic','Rotten Tomatoes','TV Guide','Game Informer') or 'Critical Gold' in n: return 'Tracker'
    return 'Annual list'
GROUP = {'Annual list':'Annual lists','So far':'So far · mid-year','Awards':'Awards & nominees','Tracker':'Trackers & aggregates'}
ORDER = ['Annual list','Awards','Tracker','So far']
def stamp(value):
    value = (value or '').strip()
    if not value: return 0
    # Month-only dates (Apple newsroom uses YYYY-MM) sort as the 1st of that month.
    if re.fullmatch(r'\d{4}-\d{2}', value): value += '-01'
    return calendar.timegm(datetime.date.fromisoformat(value).timetuple())
items = []
for r in rows:
    k = kind(r)
    ts = stamp(r['date'])
    items.append(dict(line=r['topic'], topic=[GROUP[k]], title=r['list'], desc=r['outlet'], kind=k, tags=[srctype(r['outlet'])], href=r['url'], date=ts))
items.sort(key=lambda i: (i['line'], ORDER.index(i['kind']), -i['date'], i['title']))
for i in items: del i['date']
TAGS = ['Magazine & web outlet','Newspaper & broadcaster','Retailer & platform','Library','Aggregator & scores','Awards body']
PENDING = [
 ['Books','NYT 10 Best Books and 100 Notable Books, Washington Post 10 Best, New Yorker and Guardian year-end lists; Goodreads Choice winners on Dec 3 (nominees only so far).'],
 ['Albums','Pitchfork, Rolling Stone, Billboard, Stereogum, Paste, NPR and Consequence year-end lists (only mid-year versions so far); Apple Music year-end.'],
 ['Songs','Spotify Wrapped (expected early Dec); Pitchfork, Rolling Stone and Billboard year-end song lists.'],
 ['Movies','TIME, NYT, Variety, IndieWire, Vulture, Rolling Stone, Guardian and AV Club year-end lists; Sight and Sound poll.'],
 ['TV','TIME, NYT, Variety, IndieWire, Vulture, Rolling Stone and Guardian year-end lists.'],
 ['Podcasts','Vulture, Guardian, New Yorker and Esquire year-end lists; Spotify Wrapped top podcasts.'],
 ['Video Games','The Game Awards winners on Dec 10; IGN, Polygon, GameSpot and TIME Game of the Year lists.'],
 ['Tech & Gadgets','Popular Science Best of What\u2019s New (by Dec 10); Wired and CNET year-end picks.'],
 ['Restaurants & Food','Esquire Best New Restaurants (early Dec).'],
 ['Theater','No full-year 2026 best-of lists yet; NYT and Guardian critics\u2019 picks usually land in December.'],
]
try:
    master_file = json.load(open('master_rank.json'))
except FileNotFoundError:
    raise SystemExit('master_rank.json is missing. Run python3 build_master.py MASTER.md')
if isinstance(master_file, dict):
    source_lists = master_file['lists']
    master = master_file['topics']
else:
    source_lists = []
    master = master_file
def js_json(obj):
    # Keep the payload inside a script element: escape HTML-sensitive characters.
    return (json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
            .replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
            .replace('\u2028', '\\u2028').replace('\u2029', '\\u2029'))
n_titles = sum(len(topic['items']) for topic in master)
ASSETS = Path(__file__).resolve().parents[1] / 'scripts' / 'bestof_assets'
def asset(name): return (ASSETS / name).read_text().replace('__YEAR__', '2026')
css = asset('hub_style.css') + "\n.card.pending { display:block; cursor:default; } .card.pending::before { content:none; } .card.pending .t { font-size:18px; }\n"
js = asset('hub_logic.js').replace('__TAGS__', json.dumps(TAGS))
master_js = asset('master_logic.js')
built = datetime.date.today().strftime('%b %-d, %Y')
html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Best of 2026</title>
<script>
(function () {{
  let theme;
  try {{ theme = localStorage.getItem("best-2026-theme"); }} catch (e) {{}}
  document.documentElement.dataset.theme = theme === "light" || theme === "dark"
    ? theme : (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  if (/[?&]view=master(?:&|$)/.test(location.search)) document.documentElement.dataset.view = "master";
}})();
</script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Libre+Caslon+Display&family=Newsreader:ital,opsz,wght@0,6..72,400;1,6..72,400&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<div class="wrap">
<header class="hero">
  <div class="eyebrow"><span id="eyebrow-label">Best of 2026 · List directory</span><div class="header-actions"><span class="updated">Last built {built}</span><button type="button" class="theme-toggle" id="theme-toggle" aria-label="Dark mode" aria-pressed="false">Dark mode</button></div></div>
  <h1>Best of <em>2026</em></h1>
  <p class="sub" id="hero-sub">Every published best-of-2026 list found so far, with a checked link to each. Pick a topic to open its lists, or search.</p>
  <div class="stats" id="stats"></div>
</header>

<div class="viewtabs" role="tablist" aria-label="Views">
  <button type="button" class="tab" id="tab-lists" role="tab" data-view="lists" aria-selected="true" aria-controls="panel-lists" tabindex="0">Lists</button>
  <button type="button" class="tab" id="tab-master" role="tab" data-view="master" aria-selected="false" aria-controls="panel-master" tabindex="-1">Master list</button>
</div>

<div id="panel-lists" role="tabpanel" aria-labelledby="tab-lists">
<div class="controls" id="controls">
  <div class="searchrow">
    <div class="search">
      <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
      <input id="q" type="search" aria-label="Search lists" placeholder="Search lists, outlets, topics…" autocomplete="off" aria-describedby="search-help">
      <button type="button" class="search-clear" id="search-clear" data-clear="q" hidden>Clear search</button>
      <kbd>/</kbd>
    </div>
    <select id="kind" aria-label="List type"></select>
    <select id="sort" aria-label="Sort">
      <option value="topic">Group by topic</option>
      <option value="outlet">Outlet A–Z</option>
      <option value="title">List name A–Z</option>
    </select>
  </div>
  <div class="filterbar" aria-label="Active filters">
    <div class="pills" id="active-filters"></div>
    <div class="filter-actions">
      <button type="button" class="clear-all" id="clear-all" data-clear="all" aria-keyshortcuts="Escape" disabled>Clear all filters</button>
      <span class="filter-hint" id="filter-hint" hidden>or press <kbd>Esc</kbd></span>
    </div>
  </div>
</div>
<p id="search-help" class="file-path">Search list names, outlets, topics and links. Common abbreviations (NYT, PW, RS, GOTY, LP) and small typos are supported.</p>
<div class="chips" id="chips"></div>

<div class="layout">
  <details class="index" id="index" open>
    <summary>Browse by topic</summary>
    <nav id="tree"></nav>
  </details>
  <main>
    <div class="results" id="results" aria-live="polite" aria-atomic="true"></div>
    <div id="app"></div>
  </main>
</div>
</div>

<div id="panel-master" role="tabpanel" aria-labelledby="tab-master" hidden>
  <p class="file-path master-note">Each row is one work named inside the lists. The × badge is how many outlets mention it (each outlet counts at most once per work), and higher counts rank first. Open a badge for links to those lists. Titles are matched within a category. Case, punctuation, diacritics, a leading The, A, or An, edition notes, and season labels are ignored, and close spellings merge when the creators agree.</p>
  <div class="controls" id="m-controls">
    <div class="searchrow">
      <div class="search">
        <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
        <input id="mq" type="search" aria-label="Search titles" placeholder="Search titles, creators, lists…" autocomplete="off">
        <button type="button" class="search-clear" id="m-clear" hidden>Clear search</button>
        <kbd>/</kbd>
      </div>
      <select id="m-topic" aria-label="Category"></select>
    </div>
  </div>
  <div class="chips scroll" id="m-chips"></div>
  <div class="results" id="m-results" aria-live="polite" aria-atomic="true"></div>
  <div id="m-app"></div>
</div>

<footer>
  <div>Built {built} · <span id="foot-n"></span> lists · {n_titles:,} titles on the master list · opens each list in a new tab</div>
  <div>To refresh: edit lists.csv, then run python3 build_html.py. Master list: python3 build_master.py MASTER.md, then build_html.py.</div>
</footer>
</div>
<button class="top" id="top" title="Back to top">↑</button>

<script>
const ITEMS = {json.dumps(items, ensure_ascii=False)};
const PENDING = {json.dumps(PENDING, ensure_ascii=False)};
{js}
const LISTS = {js_json(source_lists)};
const MASTER = {js_json(master)};
{master_js}
</script>
</body>
</html>
'''
open('Best_of_2026.html','w').write(html)
from collections import Counter
print(len(items), Counter(i['kind'] for i in items))
