# Best of 2026

Standalone HTML page with two tabs. Lists is the directory of published best-of-2026 lists: each entry has a topic, the outlet, and a checked link. Master list ranks every work those lists name, grouped by category. A work on more lists ranks higher. Each row shows a × mention count and links back to the lists that name it. Open `Best_of_2026.html` in a browser; the page is self-contained.

## Rebuild

From this folder:

```bash
python3 build_master.py MASTER.md
python3 build_html.py
```

`build_master.py` reads `items.json` (written by `extract_lists.py`) and writes `MASTER.md` and `master_rank.json`. `build_html.py` reads `lists.csv` and `master_rank.json` and writes `Best_of_2026.html`. It inlines `hub_style.css`, `hub_logic.js`, and `master_logic.js`, and stamps the header with the day you run it.

`candidates.tsv` is the candidate list used by `check_links.py`, which fetches each URL and writes `check.csv`.
