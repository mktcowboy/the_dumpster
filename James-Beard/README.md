# James Beard Award Graphs

Unofficial Obsidian-style interactive graphs of public James Beard Foundation award results.

| Site | Path | Live (GitHub Pages) |
|------|------|---------------------|
| Landing | [`index.html`](./index.html) | `James-Beard/` |
| Restaurant & Chef | [`restaurant-chef/`](./restaurant-chef/) | `James-Beard/restaurant-chef/` |
| Book / Broadcast / Journalism | [`book-media/`](./book-media/) | `James-Beard/book-media/` |

Open locally with any static server from this folder (JSON is loaded via `fetch`):

```bash
python3 -m http.server 8080
```

Each subgraph is self-contained (`index.html` + `data/*.json`). Relative paths only — works under GitHub Pages subpaths.

**Attribution:** Award names/results are trademarks of the James Beard Foundation. Primary data via [cjwinchester/james-beard](https://github.com/cjwinchester/james-beard) from the official search-past-awards page.
