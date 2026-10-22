# Tanakh Atlas — Progress Log

Deliverable: one self-contained HTML file linking the Tanakh, Oral Torah, commentaries,
law codes, philosophy, mysticism, and prayer — with themes, people, places, ideas, and
explanatory essays on why the tradition is shaped the way it is.

## Log

### 2026-10-20 — Session start
- Inspected workspace. Found prior `ancient-books/` library with JPS 1917 Tanakh EPUB,
  Rodkinson Talmud EPUB, Pirke Avot EPUB. Reusing local public-domain sources where possible.
- Confirmed Sefaria API reachable (but its default English Tanakh is a CC-BY-NC 2023
  translation, so not using it for embedded text).
- Created project skeleton: data/, sources/, agents/, notes/.
- Next: acquire public-domain texts (Tanakh, Siddur, Guide, Kuzari, Rashi, Talmud, Legends),
  define data schema, fan out content agents.

### 2026-10-20 — Text pipeline working
- Parsed the complete JPS 1917 Tanakh from eBible.org USFM: **24 books, 929 chapters, 23,145 verses**.
  Output: `data/tanakh_text.json` (~6 MB). Clean, public domain, no OCR noise.
- Confirmed local `ancient-books` sources for Pirke Avot and Rodkinson Talmud; will use for excerpts.
- Wrote canonical registry: 42 works, 43 people, 25 places, 41 ideas. All agents write against these IDs.
- Next: parallel content agents + app shell.
