"""Build Best_of_2026.html from lists.csv, using the HTML Hub layout (hub_style.css + hub_logic.js)."""
import csv, json, calendar, datetime, re
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
css = open('hub_style.css').read() + "\n.card.pending { display:block; cursor:default; } .card.pending::before { content:none; } .card.pending .t { font-size:18px; }\n"
js = open('hub_logic.js').read().replace('__TAGS__', json.dumps(TAGS))
built = datetime.date.today().strftime('%b %-d, %Y')
html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Best of 2026 — List Directory</title>
<script>
(function () {{
  let theme;
  try {{ theme = localStorage.getItem("best-2026-theme"); }} catch (e) {{}}
  document.documentElement.dataset.theme = theme === "light" || theme === "dark"
    ? theme : (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}})();
</script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Libre+Caslon+Display&family=Newsreader:ital,opsz,wght@0,6..72,400;1,6..72,400&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<div class="wrap">
<header class="hero">
  <div class="eyebrow"><span>Best of 2026 · List directory</span><div class="header-actions"><span class="updated">Last built {built}</span><button type="button" class="theme-toggle" id="theme-toggle" aria-label="Dark mode" aria-pressed="false">Dark mode</button></div></div>
  <h1>Best of <em>2026</em></h1>
  <p class="sub">Every published best-of-2026 list found so far, with a checked link to each. Pick a topic to open its lists, or search.</p>
  <div class="stats" id="stats"></div>
</header>

<div class="controls" id="controls">
  <div class="searchrow">
    <div class="search">
      <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
      <input id="q" type="search" aria-label="Search lists" placeholder="Search lists, outlets, topics…" autocomplete="off" aria-describedby="search-help">
      <button type="button" class="search-clear" id="search-clear" data-clear="q" hidden>Clear search</button>
      <kbd>/</kbd>
    </div>
    <select id="when" aria-label="Date">
      <option value="">Any date</option>
      <option value="7">Past 7 days</option>
      <option value="30">Past 30 days</option>
      <option value="90">Past 90 days</option>
      <option value="dated">Dated lists only</option>
      <option value="custom">Custom range…</option>
    </select>
    <select id="kind" aria-label="List type"></select>
    <select id="sort" aria-label="Sort">
      <option value="topic">Group by topic</option>
      <option value="recent">Newest first</option>
      <option value="outlet">Outlet A–Z</option>
      <option value="title">List name A–Z</option>
    </select>
  </div>
  <div class="range" id="range" hidden>
    <span>From</span><input type="date" id="from" aria-label="From date"><span>to</span><input type="date" id="to" aria-label="To date">
  </div>
  <div class="filterbar" aria-label="Active filters">
    <div class="pills" id="active-filters"></div>
    <div class="filter-actions">
      <button type="button" class="clear-all" id="clear-all" data-clear="all" aria-keyshortcuts="Escape" disabled>Clear all filters</button>
      <span class="filter-hint" id="filter-hint" hidden>or press <kbd>Esc</kbd></span>
    </div>
  </div>
</div>
<p id="search-help" class="file-path">Search list names, outlets, topics and links. Common abbreviations (NYT, PW, RS, GOTY, LP) and small typos are supported. Dates are shown only where the outlet states one.</p>
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

<footer>
  <div>Built {built} · <span id="foot-n"></span> lists · opens each list in a new tab</div>
  <div>To refresh: edit lists.csv, then run python3 build_html.py in /workspace/best-2026</div>
</footer>
</div>
<button class="top" id="top" title="Back to top">↑</button>

<script>
const ITEMS = {json.dumps(items, ensure_ascii=False)};
const PENDING = {json.dumps(PENDING, ensure_ascii=False)};
{js}
</script>
</body>
</html>
'''
open('Best_of_2026.html','w').write(html)
from collections import Counter
print(len(items), Counter(i['kind'] for i in items))
