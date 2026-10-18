# Beyond-arXiv digest — project notes

Resume file. Everything needed to pick this back up later.

## Background
- Oct 18, 2026: redacted shared the Paradigm chart "Beyond arXiv many fields are booming" (preprint postings/year 2017–2026 across six servers) and asked for the top 20 papers from each for the past month (Sep 18–Oct 18, 2026).
- He then asked for it as an HTML file with one tab per source, and for it to run weekly.
- His standing rule for this digest: where no download ranking exists, each tab must state exactly how its 20 were picked.

## Sources
| Tab | Server | Field | URL |
|---|---|---|---|
| Psychology | PsyArXiv | psychology | https://psyarxiv.com |
| Sociology | SocArXiv | sociology | https://osf.io/preprints/socarxiv |
| Economics | SSRN | economics | https://www.ssrn.com |
| Philosophy | PhilArchive | philosophy | https://philarchive.org |
| Cryptography | IACR ePrint | cryptography | https://eprint.iacr.org |
| Chemistry | ChemRxiv | chemistry | https://chemrxiv.org |

## Deliverable
- `~/workspace/your_files/beyond-arxiv-top-papers.html` — tabbed, self-contained page. No CDN scripts (the app's file viewer blocks them — vendor libs must be inlined; only map tiles may need network). Never use `target="_blank"` (viewer blocks new-tab navigation; plain `<a href>` works).
- Builder: `~/workspace/preprint-digest/build_html.py`
  - Parses the six scout reports (`psyarxiv.md`, `socarxiv.md`, `ssrn.md`, `philarchive.md`, `iacr.md`, `chemrxiv.md`).
  - Each report is a numbered list with one paper per line in exactly this format: `1. [Title](URL) — authors — date. One-line note.` (the builder's regex depends on it)
  - Rebuild: `python3 ~/workspace/preprint-digest/build_html.py --daterange "October 18 – October 24, 2026"`

## Stats landscape (as established Oct 18, 2026)
- **SocArXiv**: per-paper OSF view/download counters are public on each page, but there is no API and no ranking page. Only server with measurable stats. First sweep measured 65/100 papers before a 429 rate limit stopped it.
- **SSRN**: download leaderboards sunset Jul 15, 2026 (per the SSRN blog) — gone permanently. Per-paper counts still show on abstract pages; nothing aggregates them.
- **IACR ePrint**: last "Top 20 Downloads" reports ran in 2010–2011 newsletters. Now publishes submission counts per year only.
- **PsyArXiv/OSF**: the v2 API exposes no view/download counters; metrics endpoints 404; Altmetric API needs a key.
- **PhilArchive**: download counts are author-only. The only public quality signal is the "Selected recent additions" feed, capped at 100 items (no pagination).
- **ChemRxiv**: article pages show "N views / M downloads" but are bot-blocked (403); dashboard Most read/Most cited is all-time only.

## Methodology rule
No public ranking → editorial curation, and the tab must document the method (his explicit ask). First edition: SocArXiv ranked by measured downloads; SSRN ordered by per-page downloads where visible; the other four curated (venue prestige / breaks-on-deployed-systems / novelty / subfield mix).

## Known gaps from the first edition
- Economics: only 5 verified papers — fresh SSRN pages weren't search-indexed yet. Retry indexing on later runs.
- Philosophy: Oct 12–18 only (PhilArchive feed cap).
- Chemistry: 7 papers need author/date confirmation (Crossref rate-limited mid-run).

## Weekly cadence
- Cron `beyond-arxiv-weekly-digest` ("Beyond-arXiv weekly digest"), Saturdays ~9am CT (flexible), covering the trailing 7 days. First run: Sat Oct 24, 2026. Delivers the rebuilt HTML in the side chat where it was requested.
- First edition covered Sep 18–Oct 18, 2026 (a full month, as originally asked); weekly editions cover 7-day windows.

## How to resume / regenerate manually
1. Run six scouts (one per server) for the window; save results to the six `.md` files in the line format above.
2. `python3 ~/workspace/preprint-digest/build_html.py --daterange "<start> – <end>, YYYY"`.
3. Attach the HTML in chat with a 2–3 sentence rundown per tab, including stats/methodology caveats.
