#!/usr/bin/env python3
"""Build the tabbed Beyond-arXiv digest HTML from the six scout markdown files."""
import re, html, pathlib, argparse

ap = argparse.ArgumentParser(description="Build the tabbed Beyond-arXiv digest HTML.")
ap.add_argument("--daterange", default="September 18 \u2013 October 18, 2026",
                help='Date range shown in the header, e.g. "October 18 \u2013 October 24, 2026"')
ARGS = ap.parse_args()

BASE = pathlib.Path.home() / "workspace" / "preprint-digest"
OUT = pathlib.Path.home() / "workspace" / "your_files" / "beyond-arxiv-top-papers.html"

TABS = [
    {
        "id": "psychology", "label": "Psychology", "source": "PsyArXiv",
        "file": "psyarxiv.md",
        "stats": "No public download ranking exists. OSF's API exposes no view/download counters (verified in the raw JSON), the metrics endpoints 404, and Altmetric now needs an API key.",
        "method": "All 1,222 PsyArXiv preprints from Sep 18–Oct 18, 2026 were enumerated via the OSF API. The 20 below are an editorial ranking by estimated impact \u2014 landmark formats (consensus statements, megastudies, large meta-analyses, preregistered reports), data scale, novelty, and subfield diversity \u2014 not a measured leaderboard.",
    },
    {
        "id": "sociology", "label": "Sociology", "source": "SocArXiv",
        "file": "socarxiv.md",
        "stats": "Ranked by REAL per-paper download counts. Each OSF preprint page shows public view/download counters; 65 of the 100 papers in-window were measured (a 429 rate limit stopped the sweep). No public trending page or metrics API exists.",
        "method": "All 100 SocArXiv preprints from Sep 18–Oct 18, 2026 pulled via the OSF API; each page's counters read Oct 18. Sorted by downloads desc, ties by views. Partial ranking \u2014 35 papers unmeasured, and earlier papers had more days to accumulate downloads.",
    },
    {
        "id": "economics", "label": "Economics", "source": "SSRN",
        "file": "ssrn.md",
        "stats": "SSRN sunset its download rankings on July 15, 2026 \u2014 the Top Papers leaderboards are gone permanently. Per-paper download counts still show on individual abstract pages, but nothing aggregates them.",
        "method": "Candidates drawn from NBER weekly releases Sep 18–Oct 18, 2026 (nearly all cross-posted to SSRN). Only 5 could be verified with a live SSRN abstract page in-window \u2014 fresh SSRN pages aren't search-indexed yet. Ordered by per-page downloads where visible. A retry in a week or two should fill out the 20.",
    },
    {
        "id": "philosophy", "label": "Philosophy", "source": "PhilArchive",
        "file": "philarchive.md",
        "stats": "No public stats source exists. Download counts are tracked but shown only to authors; no most-downloaded page, no public API, no per-item public counts.",
        "method": "Drawn from PhilArchive's \u201cSelected recent additions\u201d feed (the archive's own quality-filtered list). The public feed caps at 100 items, so coverage is Oct 12–18 only. Ranked by venue prestige, author prominence, novelty, and area diversity \u2014 editorial judgment, not metrics.",
    },
    {
        "id": "cryptography", "label": "Cryptography", "source": "IACR ePrint",
        "file": "iacr.md",
        "stats": "No current download ranking exists \u2014 IACR's last \u201cTop 20 Downloads\u201d reports were in 2010–2011 newsletters. The archive publishes submission counts per year only.",
        "method": "Every listing Sep 18–Oct 18, 2026 (ePrint 2026/2060\u20132522) was read; 24 nominated, ranked to 20 by: (1) breaks on deployed systems or standards-track PQC, (2) new primitives/models, (3) major efficiency gains, (4) notable teams/community pickup, (5) subfield diversity. ePrint is unrefereed \u2014 attack claims are as-claimed.",
    },
    {
        "id": "chemistry", "label": "Chemistry", "source": "ChemRxiv",
        "file": "chemrxiv.md",
        "stats": "Article pages show public \u201cN views / M downloads\u201d, but pages are bot-blocked (403) and there is no sortable, date-filtered, or API-exposed ranking. The dashboard's Most read/Most cited are all-time only.",
        "method": "All 1,431 ChemRxiv preprints in-window enumerated via the Crossref API; every title scanned. Editorial ranking on novelty, potential impact, and subfield mix. 13 of 20 fully verified; 7 have titles/DOIs confirmed with authors approximate (rate-limited) \u2014 flagged inline.",
    },
]

ITEM_RE = re.compile(r"^(\d+)\.\s+\[(.*?)\]\((.*?)\)\s+\u2014\s+(.*)$")

def parse_items(path):
    items = []
    for line in path.read_text().splitlines():
        m = ITEM_RE.match(line.strip())
        if m:
            num, title, url, rest = m.groups()
            items.append({"title": title.strip(), "url": url.strip(), "rest": rest.strip()})
    return items

def esc(s):
    return html.escape(s, quote=False)

sections_html = []
tab_buttons = []
for i, tab in enumerate(TABS):
    items = parse_items(BASE / tab["file"])
    cards = []
    for n, it in enumerate(items, 1):
        cards.append(
            f'<article class="paper"><div class="rank">{n}</div>'
            f'<div class="body"><a class="title" href="{esc(it["url"])}">{esc(it["title"])}</a>'
            f'<p class="meta">{esc(it["rest"])}</p></div></article>'
        )
    pane = (
        f'<section class="pane" id="pane-{tab["id"]}" {"hidden" if i else ""}>'
        f'<div class="method"><p><strong>Stats:</strong> {esc(tab["stats"])}</p>'
        f'<p><strong>Method:</strong> {esc(tab["method"])}</p></div>'
        f'<div class="count">{len(items)} papers</div>'
        + "\n".join(cards) +
        '</section>'
    )
    sections_html.append(pane)
    tab_buttons.append(
        f'<button class="tab{" active" if i == 0 else ""}" data-pane="pane-{tab["id"]}" '
        f'role="tab" aria-selected="{"true" if i == 0 else "false"}">'
        f'{esc(tab["label"])}<span class="src">{esc(tab["source"])}</span></button>'
    )

page = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Beyond arXiv &mdash; Top Papers</title>
<style>
  :root { --ink:#1a1a1a; --muted:#6b6b6b; --line:#e3e3e3; --accent:#1f4e79; --bg:#fafafa; }
  * { box-sizing:border-box; }
  body { font-family: Georgia, 'Times New Roman', serif; color:var(--ink); background:var(--bg);
         margin:0; padding:0; line-height:1.55; }
  header { padding:2.2rem 1.5rem 1.2rem; max-width:880px; margin:0 auto; }
  header h1 { font-size:2rem; margin:0 0 .4rem; letter-spacing:-.01em; }
  header p.sub { color:var(--muted); margin:.2rem 0; font-size:.95rem; }
  .stats-note { max-width:880px; margin:0 auto 1rem; padding:0 1.5rem; font-size:.9rem; color:#3d3d3d;
                border-left:3px solid var(--accent); padding-left:1rem; }
  nav.tabs { position:sticky; top:0; z-index:10; background:#fff; border-top:1px solid var(--line);
              border-bottom:1px solid var(--line); display:flex; flex-wrap:wrap; }
  nav.tabs .wrap { max-width:880px; margin:0 auto; display:flex; flex-wrap:wrap; width:100%; }
  .tab { flex:1 1 auto; font-family:inherit; background:none; border:none; border-bottom:3px solid transparent;
         padding:.8rem .6rem .6rem; cursor:pointer; font-size:.95rem; color:var(--muted); text-align:center; }
  .tab .src { display:block; font-size:.72rem; letter-spacing:.04em; text-transform:uppercase; }
  .tab.active { color:var(--ink); border-bottom-color:var(--accent); font-weight:bold; }
  .tab:hover { color:var(--ink); }
  main { max-width:880px; margin:0 auto; padding:1.5rem 1.5rem 4rem; }
  .pane[hidden] { display:none; }
  .method { background:#fff; border:1px solid var(--line); border-radius:6px; padding:.9rem 1.1rem;
            font-size:.88rem; color:#3d3d3d; margin-bottom:1.2rem; }
  .method p { margin:.35rem 0; }
  .count { font-size:.8rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); margin-bottom:.8rem; }
  .paper { display:flex; gap:.9rem; background:#fff; border:1px solid var(--line); border-radius:6px;
           padding:.9rem 1.1rem; margin-bottom:.7rem; }
  .rank { font-size:1.4rem; color:var(--accent); min-width:2rem; text-align:right; font-variant-numeric:tabular-nums; }
  .paper .title { font-size:1.02rem; font-weight:bold; color:var(--ink); text-decoration:none; }
  .paper .title:hover { color:var(--accent); text-decoration:underline; }
  .paper .meta { margin:.3rem 0 0; font-size:.9rem; color:#3d3d3d; }
  footer { max-width:880px; margin:0 auto; padding:0 1.5rem 3rem; color:var(--muted); font-size:.82rem; }
</style>
</head>
<body>
<header>
  <h1>Beyond arXiv &mdash; many fields are booming</h1>
  <p class="sub">Top papers from six preprint servers &middot; __DATERANGE__ &middot; __TOTAL__ papers</p>
  <p class="sub">Where a real download ranking exists, the list uses it. Where none exists, the tab says exactly how its 20 were picked.</p>
</header>
<div class="stats-note">
  <strong>On the stats question:</strong> only SocArXiv had measurable per-paper download counts (partial &mdash; 65 of 100 papers).
  SSRN retired its download leaderboards on July 15, 2026; IACR's last download ranking ran in 2011;
  PsyArXiv/OSF, PhilArchive, and ChemRxiv publish no public ranking at all.
</div>
<nav class="tabs" role="tablist"><div class="wrap">
""" + "\n".join(tab_buttons) + """
</div></nav>
<main>
""" + "\n".join(sections_html) + """
</main>
<footer>
  Compiled Oct 18, 2026. Rankings mix measured downloads (SocArXiv, partly SSRN) with editorial curation where no public
  metrics exist &mdash; each tab documents its method. Preprint servers are unrefereed; treat claims accordingly.
</footer>
<script>
  document.querySelectorAll('.tab').forEach(function(btn){
    btn.addEventListener('click', function(){
      document.querySelectorAll('.tab').forEach(function(b){
        b.classList.remove('active'); b.setAttribute('aria-selected','false');
      });
      document.querySelectorAll('.pane').forEach(function(p){ p.hidden = true; });
      btn.classList.add('active'); btn.setAttribute('aria-selected','true');
      document.getElementById(btn.dataset.pane).hidden = false;
      window.scrollTo({top:0, behavior:'smooth'});
    });
  });
</script>
</body>
</html>
"""

total_papers = sum(s.count('<article class="paper">') for s in sections_html)
page = page.replace("__DATERANGE__", html.escape(ARGS.daterange)).replace("__TOTAL__", str(total_papers))

OUT.write_text(page)
print(f"wrote {OUT} ({len(page)//1024} KB)")
