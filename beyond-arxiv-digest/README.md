# Beyond-arXiv Digest

Top papers from six preprint servers beyond arXiv, inspired by the Paradigm chart
"Beyond arXiv many fields are booming" (preprint postings/year, 2017–2026).

**Open [`beyond-arxiv-top-papers.html`](beyond-arxiv-top-papers.html)** — one self-contained page,
one tab per server, plus a *Methods & sources* tab.
For the full annotated source list, read [`SOURCES.md`](SOURCES.md).

## This edition

- Window: September 18 – October 18, 2026 (archived in [`editions/2026-10-18/`](editions/2026-10-18/))
- 105 papers: 20 each from PsyArXiv, SocArXiv, PhilArchive, IACR ePrint, ChemRxiv;
  5 verified from SSRN (fresh SSRN pages weren't search-indexed yet — retry later)
- **Corroboration pass (Oct 18, 2026):** every tab was checked against outside evidence.

  | Tab | Corroborated | Related work | Corrected | Flagged | Notable elsewhere |
  |---|---|---|---|---|---|
  | Psychology | 1 (already peer-reviewed) | 4 | – | 9 (8 older preprints, 1 already published) | 2 |
  | Sociology | – | 4 | – | 2 older preprints | 2 |
  | Economics | 5 (all NBER; 3 with coverage) | 3 | – | 1 (first circulated 2024) | 4 NBER papers |
  | Philosophy | 2 (spot-checked) | – | – | 2 older drafts | 6 |
  | Cryptography | 6 | 6 | **2** | – | 3 |
  | Chemistry | 1 (+6 authors filled via Crossref) | 4 | – | – | 6 |

  Biggest findings: two crypto notes were wrong (#5 Dilithium doesn't break final ML-DSA; #9 Argo is a
  protocol, not an attack); 8 psychology and 2 sociology "new" picks were revisions of older preprints
  (OSF counts a new version as a new posting); the scouts' RSA-896 credit was misattributed (it was
  Stephen A. Weis).

## How each list was ranked

Where no public ranking existed, the list is an editorial pick: the order is the scout's
judgment of impact, not a measured count, and the tab says exactly how it was made.

| Tab | Server | Ranking | Why | How the list was picked |
|---|---|---|---|---|
| Psychology | [PsyArXiv](https://psyarxiv.com) | Editorial | OSF's API exposes no counters; metrics endpoints 404; Altmetric needs a key | All 1,222 preprints enumerated; picked for landmark formats (consensus statements, megastudies, meta-analyses, preregistered reports), data scale, novelty, max ~2 per subfield |
| Sociology | [SocArXiv](https://osf.io/preprints/socarxiv) | **Measured** (partial) | Per-page view/download counters are public | Sorted by downloads, ties by views; 65 of 100 papers measured before a rate limit |
| Economics | [SSRN](https://www.ssrn.com) | Partly measured | Leaderboards retired [July 15, 2026](https://blog.ssrn.com/2026/07/15/ssrn-to-sunset-rankings-from-15th-july-2026/) | NBER releases cross-checked against live SSRN pages; ordered by page downloads where visible |
| Philosophy | [PhilArchive](https://philarchive.org) | Editorial | Download counts are author-only | From the [Selected recent additions](https://philarchive.org/recent.html?filter=1) feed (Oct 12–18 only, 100-item cap); venue prestige, author prominence, novelty, area spread |
| Cryptography | [IACR ePrint](https://eprint.iacr.org) | Editorial | Last "Top 20 Downloads" ran in 2010–2011 | Every listing read (2026/2060–2522); breaks on deployed/PQC systems first, then new primitives, efficiency, notable teams, subfield mix |
| Chemistry | [ChemRxiv](https://chemrxiv.org) | Editorial | Page counts exist but are bot-blocked; dashboard is all-time | All 1,431 preprints enumerated via Crossref; novelty, impact, subfield mix; 7 authors still unverified |

## Corroborating the editorial picks

No outside service ranks these servers either, but some signals give independent evidence that a paper
mattered:

- [Altmetric](https://www.altmetric.com/research-access/) — the best attention signal; API key required since
  Nov 10, 2025, free for non-commercial research by application. **Biggest available upgrade.**
- [PREreview](https://prereview.org) and [Sciety](https://sciety.org) — open preprint reviews and evaluations;
  check picks individually (PREreview supports PsyArXiv and SocArXiv).
- [OpenAlex](https://openalex.org) / [Semantic Scholar](https://www.semanticscholar.org/product/api) — citation
  counts, useless for month-old papers but right for a 3–6 month retrospective.
- [Crossref Event Data](https://crossref.org/blog/strengthening-support-for-data-citations-and-saying-goodbye-to-event-data)
  is discontinued — don't build on it.

Field-specific corroborators (all linked on each tab's *Check & explore* panel):

| Field | Corroborate with |
|---|---|
| Psychology | [PREreview](https://prereview.org), [BPS Research Digest](https://www.bps.org.uk/research-digest) |
| Sociology | the [SocArXiv](https://osf.io/preprints/socarxiv) page counters themselves, [PREreview](https://prereview.org) |
| Economics | [LogEc](https://logec.repec.org) download counts, [IDEAS rankings](https://ideas.repec.org/top/), [NEP](https://nep.repec.org) human-edited weekly field reports |
| Philosophy | journal acceptance (shown on each card), [The Philosopher's Annual](https://philosophersannual.org), [Daily Nous](https://dailynous.com) |
| Cryptography | [IACR conferences](https://iacr.org/meetings/), [NIST PQC forum](https://groups.google.com/a/list.nist.gov/g/pqc-forum), [IACR CiC](https://cic.iacr.org) (IACR's news feed reposts every ePrint paper, so it isn't evidence) |
| Chemistry | [C&EN](https://cen.acs.org), [Chemistry World](https://www.chemistryworld.com), [Synfacts](https://www.thieme.de/en/synfacts/journal-information-55968.htm) |

## Where else each field publishes

The six servers came from a chart of posting *volume*, which isn't where each field's best work necessarily
appears.

| Field | Server's role | Also look at |
|---|---|---|
| Psychology | Useful but partial | [medRxiv psychiatry](https://www.medrxiv.org/collection/psychiatry-and-clinical-psychology), [bioRxiv neuroscience](https://www.biorxiv.org/collection/neuroscience), [Nature Human Behaviour](https://www.nature.com/nathumbehav/), [Psychological Science](https://journals.sagepub.com/home/pss) |
| Sociology | Small pool (~100/month) | [APSA Preprints](https://preprints.apsanet.org), [Sociological Science](https://sociologicalscience.com), [ASR](https://journals.sagepub.com/home/asr), [IZA DPs](https://www.iza.org/publications/dp) |
| Economics | Right world, wrong pipe | [NBER](https://www.nber.org/papers), [CEPR DPs](https://cepr.org/publications/discussion-papers), [Fed FEDS](https://www.federalreserve.gov/econres/feds/index.htm), [VoxEU](https://cepr.org/voxeu) |
| Philosophy | Journal-driven | [PhilPapers](https://philpapers.org), [SEP What's New](https://plato.stanford.edu/new.html), [Philosophers' Imprint](https://journals.publishing.umich.edu/phimp/) |
| Cryptography | Primary venue | [ePrint RSS](https://eprint.iacr.org/rss), [arXiv cs.CR](https://arxiv.org/list/cs.CR/recent), [USENIX Security](https://www.usenix.org/conferences/byname/108), [ACM CCS](https://www.sigsac.org/ccs.html) |
| Chemistry | Side channel | [JACS ASAP](https://pubs.acs.org/toc/jacsat/0/0), [Angewandte](https://onlinelibrary.wiley.com/journal/15213773), [Nature Chemistry](https://www.nature.com/nchem/) |

To scout a new field, start from a server directory: [SPI-Hub](https://spi-hub.app.vumc.org/pp-service/browse)
or the [ASAPbio Preprint Resource Center](https://asapbio.org/focus-areas/preprints/preprint-resource-center/).

## The page

- Search filters all tabs at once with per-tab hit counts (press `/`); deep links per tab
  (`#cryptography`, `#methods`); arrow keys move between tabs.
- Each tab: ranking badge, stats, method and corroboration-pass summary; download/view chips; evidence lines on
  cards (*Corroborated by*, *Related*, *Correction*) with chips for corroborated / note corrected / older preprint;
  a *Check & explore* panel that opens with *Notable elsewhere, same window*; and the scout's full notes.
- *Methods & sources* tab: ranking table, per-field "why / how picked / where the field publishes",
  corroboration signals with status, server directories, planned improvements.
- Self-contained (no CDN scripts, no `target="_blank"` — the hosted viewer blocks both); dark mode; single-row
  scrolling tabs on phones; printing expands every tab.

## Files

| File | What it is |
|---|---|
| [`beyond-arxiv-top-papers.html`](beyond-arxiv-top-papers.html) | The built page (generated) |
| [`build_html.py`](build_html.py) | Builder, stdlib-only Python |
| [`psyarxiv.md`](psyarxiv.md) … [`chemrxiv.md`](chemrxiv.md) | The six scout reports — the data |
| [`sources.json`](sources.json) | Links and descriptions for the panels, Methods tab and `SOURCES.md` — **edit this** |
| [`beyond.md`](beyond.md) | Notable same-window work from outside the six servers, per tab |
| [`SOURCES.md`](SOURCES.md) | Annotated sources and methods (generated from `sources.json`) |
| [`NOTES.md`](NOTES.md) | Background, stats findings per server, known gaps, decisions |
| [`editions/`](editions/README.md) | Snapshots of past editions |

## Reproduce / weekly run

1. Scout each server for the window and save the six `*.md` reports. Paper lines start
   `N. [Title](URL) — ` followed by `authors — date — note`. The builder also accepts the variants the first
   scouts produced (`Authors. Posted Oct 5, 2026. Note`, `Authors (2026/2131, Sep 20) — Note`,
   a leading `N views / M downloads.` or `*Venue*, forthcoming.`).
2. Add evidence under any paper (indented, directly below it). Four kinds:
   ```
   3. [Title](https://...) — Authors — Oct 12 — Note.
      - corroboration: [C&EN story](https://...) · accepted at CRYPTO 2026   (independent signal)
      - related: [same-window paper](https://...) on the same problem         (context, not endorsement)
      - correction: the scout's note said X; the [abstract](https://...) says Y
      - flag: first posted Mar 2025 (v8)                                       (shown as a warning chip)
   ```
   Put a one-paragraph `checked:` summary in the report's front matter, and add same-window work from outside
   the server to [`beyond.md`](beyond.md). Check first-posted dates: OSF treats a new version as a new posting.
3. If the window's stats or method changed, put front matter at the top of the report:
   ```
   ---
   ranking: editorial
   stats: No public download ranking exists ...
   method: All 310 PsyArXiv preprints from Oct 18–24 ...
   ---
   ```
4. Validate: `python3 build_html.py --check` (unmatched lines, numbering, duplicate URLs, short tabs,
   `sources.json` problems; add `--strict` to fail on warnings) and `python3 build_html.py --check-links`
   (sites that block scripts — SSRN, PhilArchive, ChemRxiv, publishers — are reported as "blocked", not broken).
5. Build and archive:
   `python3 build_html.py --daterange "October 18 – October 24, 2026" --archive 2026-10-24`
   (also `--src`, `--out`, `--sources`, `--compiled`, `--json papers.json`).

## Cadence

Weekly, Saturdays ~9am CT, covering the trailing 7 days (cron `beyond-arxiv-weekly-digest`).

## Planned improvements

1. **Economics: rank with LogEc** — pull from RePEc and rank by real downloads, restoring a measured list.
2. **Altmetric research key** — attention scores for every pick.
3. **Keep the corroboration pass weekly** — done for the first edition; repeat it each week.
4. **Filter by first-posted date** — so revisions of old preprints don't count as new.
5. **Fill first-edition gaps** — ChemRxiv #17's authors, SSRN retry, 35 unmeasured SocArXiv papers.
6. **Politics** — a seventh tab from APSA Preprints, or fold it into Sociology.
7. **Retrospective at 3–6 months** — re-score picks with citations and publish how they aged.
