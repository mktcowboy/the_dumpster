# Wine Spectator Top 100, 1988–2026

[wine-spectator-top-100.html](wine-spectator-top-100.html) is an unofficial report on every Wine Spectator Top 100 list: 39 lists and 3,900 wines, pulled November 26, 2026.

## What's in the report

The page is styled as a cellar book: parchment paper, an engraved vineyard masthead, serif type, label-framed wines, and a "cellar" dark mode.

| Tab | Contents |
| --- | --- |
| The 2026 List | Summary figures, the Wine of the Year, the Top 10 with story links, wines by country, score against price, the best wines at $30 and $50, and all 100 wines set as a wine list you can arrange by rank, country, color, price, or score |
| The Cellar | All 3,900 wines in one ledger. Filter by year, color, country, US state, score, price, and open drinking window, then export the filtered rows to CSV |
| Wines of the Year | Every No. 1 wine, 1988–2026, on a timeline |
| Vintage Trends | Country share, color mix, average score, median and mean price, 95-point wines, and age at listing, by year, plus an all-time country table |
| The Estates | Wineries and individual wines that appear on the most lists, with each appearance linked to its review |
| Provenance | Source links, links to all 39 lists, editorial pages and the 140 Top 10 story links, data caveats, and taster initials |

Each wine links to its Wine Spectator review, its Top 10 story (2013 on), searches on Wine-Searcher, Vivino, and CellarTracker, its label image where one exists, and its year's list.

## Data

- [data/top100.csv](data/top100.csv) and [data/top100.json](data/top100.json) hold all 3,900 records: year, rank, winery, wine, vintage, score, price, bottle size, color, type, country, US state, region, taster initials, issue date, drinking window, case production, and links.
- Tasting-note text is Wine Spectator's writing and isn't copied here. The build reads each note only to pull the drinking window and case counts; the review link leads to the full note.

## Rebuilding

```bash
python3 fetch.py
```

```bash
python3 build.py
```

`fetch.py` downloads the list site's JavaScript bundle and data chunks, where each year's list is stored as a `JSON.parse('…')` module. It also pulls the editorial site's year pages for the Top 10 story links. Raw files go to `.cache/`, which git ignores. `build.py` normalizes the records and writes the HTML, CSV, and JSON. The page layout lives in `template.html`.

## Caveats

- **1998:** the source repeats ranks 1–40 and has no ranks 51–100. Those ranks are shown as published, marked †, and left out of the No. 1 counts.
- **1997:** Fonseca and Taylor Fladgate, both 1994 Vintage Port, tie at No. 1.
- **US states:** older years put the state in the country field. The build moves it to a separate state field and sets the country to United States.
- **Prices:** release prices at review time, not adjusted for inflation.
- **Retail links:** searches, not checked matches.

Not affiliated with Wine Spectator.
