# Beyond-arXiv digest — project notes

Resume file. Everything needed to pick this back up later.

## Background
- Oct 18, 2026: the Paradigm chart "Beyond arXiv many fields are booming" (preprint postings/year 2017–2026 across six servers) prompted a request for the top 20 papers from each server for the past month (Sep 18–Oct 18, 2026).
- Follow-up requests: deliver it as an HTML file with one tab per source, and run it weekly.
- Standing rule for this digest: where no download ranking exists, each tab must state exactly how its 20 were picked.

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
- `beyond-arxiv-top-papers.html` — tabbed, self-contained page. No CDN scripts (the hosted file viewer blocks them — vendor libs must be inlined). Never use `target="_blank"` (the viewer blocks new-tab navigation; plain `<a href>` works).
- Builder: `build_html.py` (stdlib only). Reads the six reports from its own folder by default; `--src` / `--out` point it elsewhere (e.g. a hosted workspace).
  - Parses the six scout reports (`psyarxiv.md`, `socarxiv.md`, `ssrn.md`, `philarchive.md`, `iacr.md`, `chemrxiv.md`).
  - Paper lines must start `N. [Title](URL) — ` ; the rest is parsed tolerantly (authors, date, ePrint id, venue, download/view counts, "not verified" flags). Lines that look like papers but don't match are reported as warnings, not silently dropped.
  - Everything else in a report (stats hunt, methodology, caveats, near-misses) is rendered into each tab's collapsible "Scout notes".
  - Optional front matter (`ranking`, `stats`, `method`) in a report overrides the builder's per-tab defaults — use it on weekly runs so the method text matches the new window.
  - Indented `- corroboration:` lines directly under a paper render as a "Corroborated by" line on its card.
  - `sources.json` drives each tab's "Check & explore" panel, the Methods & sources tab, and the generated `SOURCES.md`. Edit the JSON, never `SOURCES.md`. `verified: false` marks descriptions taken from general knowledge rather than a fresh web check.
  - Rebuild: `python3 build_html.py --daterange "October 18 – October 24, 2026" --archive 2026-10-24`; validate: `--check --strict`; links: `--check-links`.
- Editions: `--archive` snapshots reports, `sources.json` and the page to `editions/<slug>/` and regenerates `editions/README.md`. First edition archived as `editions/2026-10-18/`.

## Stats landscape (as established Oct 18, 2026)
- **SocArXiv**: per-paper OSF view/download counters are public on each page, but there is no API and no ranking page. Only server with measurable stats. First sweep measured 65/100 papers before a 429 rate limit stopped it.
- **SSRN**: download leaderboards sunset Jul 15, 2026 (per the SSRN blog) — gone permanently. Per-paper counts still show on abstract pages; nothing aggregates them.
- **IACR ePrint**: last "Top 20 Downloads" reports ran in 2010–2011 newsletters. Now publishes submission counts per year only.
- **PsyArXiv/OSF**: the v2 API exposes no view/download counters; metrics endpoints 404; Altmetric API needs a key.
- **PhilArchive**: download counts are author-only. The only public quality signal is the "Selected recent additions" feed, capped at 100 items (no pagination).
- **ChemRxiv**: article pages show "N views / M downloads" but are bot-blocked (403); dashboard Most read/Most cited is all-time only.

## Corroboration and outside sources (researched Oct 18, 2026)
Full annotated list: `SOURCES.md` (generated from `sources.json`). Key findings:
- **Altmetric** is the best attention signal, but its Details Page API has required a key since Nov 10, 2025. Free for non-commercial research by application (review targets ~30 business days). Biggest single upgrade for the editorial tabs.
- **Crossref Event Data** is discontinued (public API reported gone from April 2026; only an archive remains). Don't build on it.
- **OpenAlex / Semantic Scholar**: citation counts exist, but month-old preprints have none. Right tool for a 3–6 month retrospective of each edition's picks, not for the weekly run.
- **PREreview** explicitly supports PsyArXiv and SocArXiv (also OSF, medRxiv, bioRxiv). **Sciety** aggregates evaluations; PsyArXiv coverage unconfirmed. Use both per paper.
- **Economics fix**: RePEc's **LogEc** publishes real monthly download/abstract-view counts (CSV via `format=csv`; IDEAS ranking pages refresh early each month), and **NEP** sends 90+ weekly field reports, each hand-picked by an editor from 500–1,000 new papers. Together they can replace SSRN's dead leaderboard. LogEc's TLS chain fails Python's default trust store, so the link checker reports it as "blocked TLS"; it works in browsers and curl.
- **Philosophy**: journal acceptance is the real quality signal (most first-edition picks have one). The Philosopher's Annual (ten best articles per year; 2025 edition announced Aug 2026) is a yearly cross-check.
- **Cryptography**: ePrint is the field's primary venue. Corroborate via later acceptance at IACR conferences or IACR Communications in Cryptology, IACR news highlights, and NIST PQC forum threads for attacks on candidate schemes.
- **Chemistry**: ChemRxiv is a side channel (top work goes journal-first). C&EN, Chemistry World and Synfacts (monthly expert-selected synthesis highlights) are better guides. Faculty Opinions was considered and dropped because its coverage is biomedical.
- **Political science**: APSA Preprints (APSA + Cambridge) is the natural partner for SocArXiv; the first edition's #1 sociology paper is really an IR paper.
- **OSF**: the generalist OSF Preprints server has paused new submissions since Aug 25, 2025. Community servers (PsyArXiv, SocArXiv) are unaffected. The old OSF help URL for preprint analytics (article 408) now returns 404.
- **Finding servers for a new field**: SPI-Hub's preprint service browser and the ASAPbio Preprint Resource Center.
- The six servers came from a chart of posting volume. For each field the question is where its best work appears, which is not always the preprint server: primary venue (crypto), right world but wrong pipe (econ), useful but partial (psych), small pool (soc), journal-driven (phil), side channel (chem).

## Corroboration pass (Oct 18, 2026)
- Method: for each pick, searched for press coverage, public code, reviews, venue acceptance, forum threads and published versions; recorded as indented sub-lines in the scout reports (`corroboration:` independent signal; `related:` context, not endorsement; `correction:`; `flag:`). Per-tab `checked:` front matter summarises what was searched. Same-window work from outside the servers lives in `beyond.md`.
- Search notes: exact-title quoted searches returned nothing for month-old papers; descriptive unquoted queries in extended mode found coverage. Standard mode mostly finds the paper's own listing.
- Corrections: crypto #5 (Dilithium superposition attack does not apply to final ML-DSA, per the abstract) and #9 (Argo is a randomized-encoding protocol for permissionless Groth16 verification on Bitcoin, not an attack); notes rewritten and marked. The RSA-896 record (Sep 19, 2026) was by Stephen A. Weis (saweis.net), not the person the crypto scout named.
- IACR's news feed reposts every ePrint paper automatically (ePrint Report channel), so it is not corroboration; `sources.json` corrected.
- Version problem: OSF counts a new version as a new posting. Psychology #3, #4, #5, #6, #9, #11, #15, #18 and sociology #6, #18 were first posted between Mar 2025 and Aug 2026; flagged on cards. Next editions should filter by each preprint's first-version date (OSF API `/v2/preprints/<id>_v1/`; versions endpoint when v1 is not public).
- Already published: psychology #12 appeared in J. Psychopharmacol. on Aug 28, 2026. Economics #5 first circulated on arXiv in Jan 2024; philosophy #2 on arXiv in Jul 2022; philosophy #3 is a revision of a 2019 SEP entry.
- Chemistry: Crossref filled authors and exact dates for #12, #15, #16, #18, #19, #20; #17's record lists no authors (companion code: github.com/adambaskerville/flake-helium).
- No independent evidence found yet for most psychology, sociology and chemistry picks — expected for month-old preprints; re-check in later editions.

## Decision log
- Oct 18, 2026: builder made repo-relative and tolerant of the scouts' line variants. Scout prose is kept on the page as "Scout notes" instead of being dropped.
- Oct 18, 2026: ran the first corroboration pass; added `related`/`correction`/`flag` sub-lines, `checked:` front matter, `beyond.md`, the redesigned title area (stats strip + ranking legend), and a Corroborated column in the Methods table.
- Oct 18, 2026: added the corroboration line format, `sources.json`, the Methods & sources tab, `SOURCES.md`, `--check-links`, and `--archive`. Dropped the "approx. date" chip (it appeared on 19 of 20 crypto cards); a `~` prefix with a tooltip marks estimated dates instead.

## Methodology rule
No public ranking → editorial curation, and the tab must document the method (an explicit requirement). First edition: SocArXiv ranked by measured downloads; SSRN ordered by per-page downloads where visible; the other four curated (venue prestige / breaks-on-deployed-systems / novelty / subfield mix).

## Known gaps from the first edition
- Economics: only 5 verified papers — fresh SSRN pages weren't search-indexed yet. Retry indexing on later runs.
- Philosophy: Oct 12–18 only (PhilArchive feed cap).
- Chemistry: 7 papers needed author/date confirmation (Crossref rate-limited mid-run); 6 resolved Oct 18, 2026, #17 has no authors in Crossref.

## Weekly cadence
- Cron `beyond-arxiv-weekly-digest` ("Beyond-arXiv weekly digest"), Saturdays ~9am CT (flexible), covering the trailing 7 days. First run: Sat Oct 24, 2026. Delivers the rebuilt HTML in the side chat where it was requested.
- First edition covered Sep 18–Oct 18, 2026 (a full month, as originally asked); weekly editions cover 7-day windows.

## How to resume / regenerate manually
1. Run six scouts (one per server) for the window; save results to the six `.md` files (paper lines as above; add front matter if the stats/method changed).
2. For each pick, look for one corroborating signal (see `SOURCES.md`) and add it as an indented `- corroboration:` line.
3. `python3 build_html.py --check` and `--check-links`; fix any warnings (unmatched lines, duplicate URLs, short tabs, broken links).
4. `python3 build_html.py --daterange "<start> – <end>, YYYY" --archive <YYYY-MM-DD>`.
5. Re-review `sources.json` roughly monthly (statuses change: Altmetric access, LogEc, server policies) and bump `last_reviewed`.
6. Share the HTML with a 2–3 sentence rundown per tab, including stats/methodology caveats.
