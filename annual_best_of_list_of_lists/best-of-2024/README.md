# Best of 2024

Standalone HTML page with two tabs. Lists is the directory of published best-of-2024 lists: each entry has a topic, the outlet, and a checked link. Master list ranks every work those lists name, grouped by category. A work on more lists ranks higher. Each row shows a × mention count and links back to the lists that name it. Open `Best_of_2024.html` in a browser; the page is self-contained.

## Rebuild

From this folder:

```bash
python3 build_master.py MASTER.md
python3 build_html.py
```

`build_master.py` reads `items.json` (written by `extract_lists.py`) and writes `MASTER.md` and `master_rank.json`. Before ranking, it passes the items through `scripts/item_cleanup.py`, which repairs known extraction mistakes. Titles are merged by `scripts/title_match.py`, with reviewed overrides in `scripts/bestof_merges.json`. Run `python3 ../scripts/near_miss.py .` after a refresh to list close titles that did not merge. `build_html.py` reads `lists.csv` and `master_rank.json` and writes `Best_of_2024.html`. It inlines `hub_style.css`, `hub_logic.js`, and `master_logic.js` from `scripts/bestof_assets/`. The page shows no dates.

`candidates.tsv` is the candidate list used by `check_links.py`, which fetches each URL and writes `check.csv`.

`build_master.py` and `extract_lists.py` are thin wrappers. The shared logic for every year is in `scripts/bestof_master.py` and `scripts/bestof_extract.py`; this folder keeps its own `custom.py` site parsers, `manual.json`, and `build_html.py`.
