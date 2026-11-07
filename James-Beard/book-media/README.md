# James Beard Media Award Graph

Book, Broadcast Media, and Journalism awards — Obsidian-style force graph (standalone from Restaurant & Chef).

```bash
python3 -m http.server 8080
```

Rebuild from `raw/james-beard-awards.csv` (the build also repairs the source's garbled accents and apostrophes, e.g. `Bon AppÃ©tit`):

```bash
python3 scripts/build_data.py
```
