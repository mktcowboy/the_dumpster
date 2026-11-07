# James Beard Award Graph

Static, self-contained Obsidian-style interactive graph of **James Beard Foundation Restaurant & Chef Awards** — winners, nominees, and semifinalists — with profiles, backlinks, filters, and a simple state-count map.

Open `index.html` locally (needs a tiny static server because of `fetch` of JSON), or host on GitHub Pages.

```bash
# from this directory
python3 -m http.server 8080
# then visit http://localhost:8080
```

## Features

- Force-directed graph (D3) with node types: person, restaurant, city/place, state, category, year, region
- Edges: won / nominated / semifinalist, works-at, located-in, in-state, in-region, in-year
- Click a node → profile side panel with award timeline, connected notes (backlinks), source URLs
- Search, year range, winner/nominee/semifinalist filters, node-type toggles, region filter
- Hover neighbor highlighting; optional local graph (1–2 hops from focus)
- Dark theme; optional US state count cards

## Data coverage (v1)

| Field | Value |
|-------|--------|
| Scope | Restaurant & Chef Awards only |
| Years | 1991–2025 |
| Records | 9,178 (726 duplicate source rows merged) |
| Winners / nominees / semifinalists | 1,087 / 2,673 / 5,418 |
| Graph | ~8,000 nodes, built in the browser from `data/awards.json` (1.4 MB) |

**Sources (no invented fields):**

1. Public CSV derived from [jamesbeard.org search-past-awards](https://www.jamesbeard.org/awards/search-past-awards) via [cjwinchester/james-beard](https://github.com/cjwinchester/james-beard) (through 2024).
2. [2025 Restaurant & Chef winners story](https://www.jamesbeard.org/stories/the-2025-james-beard-award-winners) (winners only).

### Known gaps

- 2025 nominees / semifinalists not yet scraped
- 2026 cycle not published / not included
- Book, Broadcast Media, Journalism, Leadership awards deferred to a later phase
- Some older rows have blank restaurant or location when the source CSV lacked them
- The source CSV repeats some awards under different recipient IDs; identical rows are merged at build time
- The source CSV has garbled accents and apostrophes (e.g. `Bullyâ€™s`); the build repairs them (`clean_text` in `scripts/build_data.py`)
- The source spells many names several ways (`Charlie Trotter's` / `Charlie Trotters`, `Magnolia Grill` / `Magnolia Grlll`, `Rob` / `Robert Connoley`). The build merges them (`merge_name_variants`): 320 restaurant spellings within the same city and 37 person spellings (near matches only when credited at the same restaurant). Reviewed look-alikes that are different places or people are listed in `KEEP_APART`.
- America’s Classics and restaurant-only categories may list the restaurant as the “recipient” in source data; the build script reassigns those when the category is restaurant-centric

## Rebuild data

```bash
# refresh CSV (from this directory)
curl -sL -A "JamesBeardGraphBot/1.0" \
  "https://raw.githubusercontent.com/cjwinchester/james-beard/master/james-beard-awards.csv" \
  -o raw/james-beard-awards.csv
python3 scripts/build_data.py
```

The build writes only `data/awards.json`: one row per award, blank fields omitted, sources listed once in `meta.sources` (rows from the 2025 story carry `"src": 1`). The page derives graph nodes and edges from these rows.

## License / attribution

Award names and results are trademarks/property of the James Beard Foundation. This project is an unofficial fan/research visualization of publicly listed results. CSV upstream: cjwinchester/james-beard.
