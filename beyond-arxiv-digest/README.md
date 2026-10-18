# Beyond-arXiv Digest

Top papers from six preprint servers beyond arXiv, inspired by the Paradigm chart
"Beyond arXiv many fields are booming" (preprint postings/year, 2017–2026).

## This edition

- Window: September 18 – October 18, 2026
- 105 papers: 20 each from PsyArXiv, SocArXiv, PhilArchive, IACR ePrint, ChemRxiv;
  5 verified from SSRN (fresh SSRN pages weren't search-indexed yet — retry later)
- `beyond-arxiv-top-papers.html` — tabbed page, one tab per server.
  Self-contained (no CDN scripts); open it in a browser.

## The stats question

Only SocArXiv had measurable per-paper download counts (partial — 65 of 100
papers before a rate limit stopped the sweep). SSRN retired its download
leaderboards on July 15, 2026. IACR's last "Top 20 Downloads" ran in 2011
newsletters. PsyArXiv/OSF, PhilArchive, and ChemRxiv publish no public ranking
at all. Where no ranking exists, each tab documents exactly how its 20 were
picked — judge the method yourself.

## Reproduce

1. Scout each server for the window; save results to the six `*.md` files,
   one paper per line, exactly: `1. [Title](URL) — authors — date. One-line note.`
2. `python3 build_html.py --daterange "October 18 – October 24, 2026"`
3. Open `beyond-arxiv-top-papers.html`.

`NOTES.md` has the full background, stats findings per server, and known gaps.

## Cadence

Weekly, Saturdays ~9am CT, covering the trailing 7 days
(cron `beyond-arxiv-weekly-digest`).
