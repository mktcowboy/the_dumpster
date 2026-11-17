# Porsche 911 tracker

The report is `report.html` in this folder: every Porsche 911 for sale, one tab per generation. This folder is self-contained. The main car tracker in `../scanner` is a separate project, and nothing here changes it.

| Tab | Model years scraped | Phase chips |
|---|---|---|
| 992 | 2020–2026, one AutoTempest URL per year | 992.1 / 992.2 |
| 991 | 2012–2020 in two-year windows | 991.1 / 991.2 |
| 997 | 2005–2013 | 997.1 / 997.2 |
| 996 | 1999–2005 | |
| 993 | 1994–1998 | |
| 964 | 1989–1994 | |
| G-body & 930 | 1974–1989 | |
| Early 911 | 1964–1973 | |

## Files

- `porsche_911.py`: the generation tabs (`GENERATIONS`), their search lines, and `classify()`
- `refresh_911.py`: scrapes each generation, keeps only that generation's cars, and rebuilds `report.html` after each one
- `generate_report_v2.py`: writes the HTML report, including the chip rows
- `search_server_v2.py`: serves the report at http://127.0.0.1:8911 and runs background refreshes
- `autotempest_scraper_v2.py`, `bat_sold_scraper.py`, `merge_listings_v2.py`, `saved_store_v2.py`: scraping, VIN merge, and saved files (copied from `../scanner`; `bat_sold_scraper.py` applies `--since-days`)
- `saved/<generation>/`: `autotempest.csv`, `bat.csv`, `merged.csv`, `meta.json`
- `data/`: the MSRP and BaT mileage caches (git-ignored)
- `test_911.py`: tests
- `tasks/porsche-911-report.md`: plan, decisions, and open items

## Sources

- **AutoTempest:** `make=porsche&model=911` with a model-year window. 2024 alone returned 581 listings in 40 seconds, so no window comes near the result cap. Headless, so no browser window opens.
- **Bring a Trailer:** the generation's model pages (for example `992-gt3`, `992-911-carrera-gts`, `930-turbo`), sales from the last three years. There is no early-911 page, so that tab reads the all-911 page and keeps titles from 1964–73.
- **Autotrader:** not used. It answers only a visible Chrome window, and these scrapes run with no windows.

Years shared by two generations (1989, 2005, 2012, 2013, 2020) are scraped by both tabs. `classify()` keeps each car in one tab, using the trim where the year alone doesn't decide it: a 2012 Carrera S coupe is a 991, a 2012 cabriolet a 997, a 2013 Turbo a 997, and a 2020 Turbo S a 991. Race cars, Cup cars, and other Porsche models are dropped.

## Chips

Each car is tagged from its title first and its description second:

- **Phase:** 997.1/.2, 991.1/.2, 992.1/.2
- **Trim:** Carrera through GT2 RS, plus the classic trims (911T/E/S, SC, Carrera 2, RS America...)
- **Body:** Coupe, Cabriolet, Targa
- **Gearbox:** Manual or PDK/Auto, only when stated or when the trim came with one gearbox. AutoTempest cuts descriptions short, so many cars have none.
- **Drive:** RWD or AWD, from the trim
- **Options:** Weissach, Lightweight, Clubsport, Paint to Sample, ceramic brakes, bucket seats, front lift, Sport Chrono, Burmester, special editions, Exclusive Series, CPO, PPF

Chips in one row are alternatives, and different rows must all match. They filter the chart, the Listings table, the By model year summary, and the Bring a Trailer overlay. A row with only one value is hidden.

Tags are worked out when the report is built, not stored in the CSVs, so a rule change needs only a rebuild:

```bash
../scanner/.venv/bin/python3 -c "import refresh_911 as r; r.write_report()"
```

The market-value model uses trim (against the tab's most common trim), cabriolet, manual, and options alongside model year and miles. Phase and drive are filters only, because the year and trim already decide them. When terms always occur together and the fit fails, it is retried without the last term.

## Running

Run from this folder with the scanner's virtualenv, which has Playwright:

```bash
../scanner/.venv/bin/python3 refresh_911.py              # refresh stale generations
../scanner/.venv/bin/python3 refresh_911.py --force      # scrape every generation again
../scanner/.venv/bin/python3 refresh_911.py --slug 992   # one generation
../scanner/.venv/bin/python3 search_server_v2.py         # http://127.0.0.1:8911
../scanner/.venv/bin/python3 -m unittest test_911
```

MSRP comes only from what a listing's text states (`--no-msrp`). CarGurus answers most listing-page lookups with a "Verification Required" page, so those lookups are skipped.
