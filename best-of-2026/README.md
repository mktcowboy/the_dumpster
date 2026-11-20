# Best of 2026

Standalone HTML directory of published best-of-2026 lists. Each entry has a topic, the outlet, and a checked link. Open `Best_of_2026.html` in a browser; the page is self-contained.

## Rebuild

From this folder:

```bash
python3 build_html.py
```

`build_html.py` reads `lists.csv` and writes `Best_of_2026.html`. It inlines `hub_style.css` and `hub_logic.js`, and stamps the header with the day you run it.

`candidates.tsv` is the candidate list used by `check_links.py`, which fetches each URL and writes `check.csv`.
