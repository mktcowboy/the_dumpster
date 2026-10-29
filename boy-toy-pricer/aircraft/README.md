# Aircraft listing tracker

This folder tracks used airplanes and writes **one self-contained HTML file** with a tab for each search:

- **Cirrus SR22** — SR22, SR22T, SR22 TN, G1 through G7 / G7+, GTS, and turbo. SR20 listings are collected on this tab and stay hidden until **Include SR20** is checked.
- **Cirrus Vision Jet** — SF50, including G1, G2, G2+, G3, G3+, and Arrivee when a listing states them.
- **CubCrafters** — Carbon Cub SS, EX, EX-2, EX-3, FX, FX-2, FX-3, Top Cub (CC18-180), XCub, NXCub, Sport Cub S2, and any other CubCrafters airplane a listing names. Piper Super Cubs and other makers' cubs are excluded, including Piper ads on CubCrafters' own inventory page.
- **Piper PA-28-180/181** — Cherokee 180 (including lettered 180C/180D and Cherokee Challenger), Cherokee Archer, Archer II, Archer III, Archer DX, Archer LX, and a Pilot 100i when the listing states PA-28-181. Any spelling of Cherokee 180, Archer, PA-28-180, PA-28-181, PA28-180, or PA28-181. Warrior, Arrow, Dakota, Cruiser, Cherokee 140/150/160/235/236, and a 140 with a 180 hp conversion are excluded.
- **README** — this document, rendered into the report when the HTML file is built.

Each airplane tab uses the same layout: filters, sorting, badges, thumbnails, per-site prices, a **Data as of** line (America/Chicago), and click-through. The usage column is **Hours** (total time), not mileage. The identifier column is the **N-number**. Clicking a row, title, thumbnail, or chart point opens the lowest-priced listing. Each price in the Source column opens that site's own listing.

This folder is the aircraft tracker. It listens on port 8766 so it can run beside another local tool on port 8765.

In this repository the project lives at:

`boy-toy-pricer/aircraft`

The report file is:

`<repo>/boy-toy-pricer/aircraft/output/report.html`

The same page is served at `http://127.0.0.1:8766` when the local server is running.

## Folder layout

| Path | What it does |
| --- | --- |
| `listings.py` | Field list and text parsing. Decides family (SR22, SR20, SF50, CubCrafters) from the title, make, and model. Does not invent a generation, engine time, or gear type. |
| `scrape_sources.py` | One scraper per site. Cirrus and ASO are JSON. The other sites are HTML loaded in a browser. |
| `fetch.py` | Opens Chromium, then Google Chrome if Chromium is missing. If the browser is blocked and a plain HTTP GET still returns the page, that response is used for HTML. JSON tries the browser's request client, then HTTP. |
| `merge_listings.py` | One row per airplane. N-number first, serial number if there is no N-number. The row price is the lowest USD ask. Every site keeps its own price and link. |
| `saved_store.py` | Reads and writes `saved/<slug>/`. Freshness window, America/Chicago timestamps, atomic CSV writes. |
| `refresh_searches.py` | Refreshes one or all searches and rebuilds the report when the snapshot changes. |
| `generate_report.py` | Builds `output/report.html` from the saved CSVs and from this README. |
| `report_template.html` | The page shell (styles and tab behavior). Not opened directly. |
| `search_server.py` | Local server on port **8766**. Serves the report, refreshes a stale tab in the background, and runs UPDATE. |
| `run_sr22_weekly.sh` | Entry point for GitHub Actions, the UPDATE button, and the Mac launchd job. Uses `.venv/bin/python` when that virtualenv exists. |
| `requirements.txt` | Python packages. Right now that is Playwright. |
| `test_listings.py`, `test_saved.py` | Parser, merge, report, and snapshot tests. No network. |
| `saved/freshness.json` | `fresh_days` (default 2). |
| `saved/sr22/`, `saved/sf50/`, `saved/cubcrafters/`, `saved/pa28-180-181/` | One snapshot per tab. See below. |
| `output/report.html` | The file you open or share. |
| `output/update.log` | Log from the UPDATE button. Not committed. |
| `output/launchd.log` | Log from the Mac schedule, if you install the plist below. Not committed. |
| `.venv/` | Optional virtualenv created in the first-run steps. Not committed. |

Inside each `saved/<slug>/` folder:

- `cirrus.csv` on the SR22 and Vision Jet snapshots, or `cubcrafters.csv` on the CubCrafters snapshot, plus `aso.csv`, `globalair.csv`, `aircraftdealer.csv`, and `barnstormers.csv` when that source returned rows.
- `controller.csv`, `tradeaplane.csv`, `aircraftcom.csv`, `aerotrader.csv`, and `ebay.csv` appear only after that source succeeds. A blocked run does not create an empty file.
- `merged.csv` is one row per airplane.
- `meta.json` has `scraped_at` and any warnings.

## Prerequisites

- macOS with Google Chrome installed ([google.com/chrome](https://www.google.com/chrome/)). The scraper tries Playwright's Chromium first and Chrome second.
- Python 3.11 or 3.12. Check with `python3 --version`. The weekly GitHub Action uses 3.12. Install from [python.org](https://www.python.org/downloads/) or with `brew install python@3.12` if `python3` is missing.
- Network access the first time Playwright downloads Chromium, and whenever a refresh hits the listing sites.

## First run

From the repository root:

```bash
cd boy-toy-pricer/aircraft
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
python3 -m unittest test_listings.py test_saved.py
python3 generate_report.py
```

`generate_report.py` rewrites `output/report.html` from the saved snapshots and from this README. A clone already contains a snapshot, so this does not scrape.

Open the report with no server:

`<repo>/boy-toy-pricer/aircraft/output/report.html`

Or start the server (leave this Terminal open):

```bash
cd boy-toy-pricer/aircraft
source .venv/bin/activate
python3 search_server.py
```

Then open `http://127.0.0.1:8766`. Port 8765 is the car tracker. This server uses 8766 so both can run.

Later commands in this README assume the virtualenv is active (`source .venv/bin/activate`) and the current directory is the folder above.

## Refresh

A normal refresh skips a search whose `merged.csv` is still inside the freshness window (default **2 days**).

```bash
python3 refresh_searches.py
```

Force every search, including fresh ones:

```bash
python3 refresh_searches.py --force
```

The same forced refresh, which is what UPDATE and the schedule run:

```bash
./run_sr22_weekly.sh --force
```

One tab only. The slug is `sr22`, `sf50`, `cubcrafters`, or `pa28-180-181`:

```bash
python3 refresh_searches.py --slug cubcrafters
python3 refresh_searches.py --slug pa28-180-181
python3 refresh_searches.py --slug sf50
python3 refresh_searches.py --slug sr22 --force
```

Rebuild the HTML without scraping. Do this after editing this README if you did not just refresh:

```bash
python3 generate_report.py
```

A refresh that actually scrapes rebuilds the report, including the README tab. A refresh that skips because the snapshot is fresh leaves `output/report.html` as it was.

Change the window for one run with `--fresh-days 3`, or for every run by editing `saved/freshness.json` (`{"fresh_days": 2}`) or by setting `SR22_FRESH_DAYS`.

## Tests

```bash
python3 -m unittest test_listings.py test_saved.py
```

These do not open a browser and do not hit the listing sites.

## Snapshots, freshness, and UPDATE

Each search is fresh while `meta.json` `scraped_at` is at most `fresh_days` old and `merged.csv` exists. The **Data as of** line is that timestamp in America/Chicago. The page header uses the oldest tab.

Opening the HTML file by itself shows the saved rows. Nothing is scraped.

When `search_server.py` is running and a tab is older than the window, that tab refreshes in the background and the table updates in place. The first view is not blocked. If the refresh fails, the saved rows stay and a warning appears on the tab.

The **UPDATE** button is shown only when the page was loaded from the local server. It runs `run_sr22_weekly.sh --force` (every search, even fresh ones) and then reloads. Progress is written to `output/update.log`.

A source that fails keeps its previous CSV. The report still shows those rows, and `meta.json` records the warning. If a source already has at least 5 saved rows and a later scrape returns nothing, that empty result is treated as a failure so a broken parser cannot wipe the last good file.

New and price-drop marks compare this `merged.csv` with the previous one. The first snapshot has nothing marked new.

## Weekly GitHub Actions

`.github/workflows/aircraft-pricer-weekly.yml` runs `boy-toy-pricer/aircraft/run_sr22_weekly.sh` with working directory `boy-toy-pricer/aircraft` on Mondays at 7:00 AM America/Chicago. GitHub's clock is UTC, so the file schedules both 12:00 and 13:00 UTC and continues only when the Chicago hour is 07. That keeps the same local hour across daylight-saving changes.

Scheduled workflows run from the default branch (`main`) only. After this branch is merged, you can also run it by hand: GitHub → Actions → **Refresh aircraft for-sale report** → **Run workflow**. The job commits `boy-toy-pricer/aircraft/output/report.html` and `boy-toy-pricer/aircraft/saved` when they change. It runs `python3 scripts/check_privacy.py` before that commit. It needs the `contents: write` permission already set in the workflow file. No repository secret is required.

A Monday run still skips a search whose snapshot is inside the freshness window. The Mac launchd job below is the same script on your computer. You do not need both, but they do not conflict: a fresh snapshot is left alone.

## Mac launchd job

This runs the weekly script every Monday at 7:00 on the Mac's own clock. Set the Mac time zone to America/Chicago if you want that to match the GitHub schedule. Use a LaunchAgent (your user), not a LaunchDaemon, so Playwright can see the browsers you installed.

Save this as `~/Library/LaunchAgents/com.example.aircraft-scan.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.example.aircraft-scan</string>
  <key>WorkingDirectory</key>
  <string><repo>/boy-toy-pricer/aircraft</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string><repo>/boy-toy-pricer/aircraft/run_sr22_weekly.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key>
    <integer>1</integer>
    <key>Hour</key>
    <integer>7</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string><repo>/boy-toy-pricer/aircraft/output/launchd.log</string>
  <key>StandardErrorPath</key>
  <string><repo>/boy-toy-pricer/aircraft/output/launchd.log</string>
</dict>
</plist>
```

`Weekday` 1 is Monday. Replace `<repo>` with the absolute path of your clone. Save the plist with a text editor to `~/Library/LaunchAgents/com.example.aircraft-scan.plist`, then load it:

```bash
mkdir -p ~/Library/LaunchAgents
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.aircraft-scan.plist
```

Check it:

```bash
launchctl print gui/$(id -u)/com.example.aircraft-scan
```

Run it once without waiting for Monday:

```bash
launchctl kickstart -p gui/$(id -u)/com.example.aircraft-scan
```

Unload it with:

```bash
launchctl bootout gui/$(id -u)/com.example.aircraft-scan
```

If `which python3` is not on the PATH in the plist, either rely on `.venv/bin/python` (the shell script picks that up when `.venv` exists) or put that python's directory first in the PATH string. Chrome and the Playwright browsers must be installed for the same user that owns the LaunchAgent.

## Add a new airplane tab

Use the CubCrafters search as the pattern. A new family string (for example `pc12`) becomes a slug, a `saved/<slug>/` folder, and a tab. Do not guess specs the listing does not state.

1. **Recognize the airplane** in `listings.py`. `apply_listing` sets `family` from the title, model, and description. Add a detector that matches the make and model names you care about and rejects lookalikes (the CubCrafters path rejects Piper Super Cub, J-3, and American Legend). Put the stated marketing name in `model` and the stated subtype in `variant`. Leave generation, engine, and gear blank unless the text states them.
2. **Teach each source** in `scrape_sources.py`.
   - Cirrus models: add ids to `CIRRUS_MODELS` only if Cirrus's own feed has that model.
   - Another factory inventory page: add a scraper and call it from `sources_for` the way `scrape_cubcrafters` is called for the `cubcrafters` family.
   - ASO: add model ids to `ASO_MODELS`, or text queries like `ASO_CUB_QUERIES`, and keep the row only when `family` matches.
   - GlobalAir: add a manufacturer URL to `GLOBALAIR_PAGES`.
   - AircraftDealer: add a category URL to `DEALER_CATEGORIES` and, if needed, search phrases.
   - Barnstormers: add search URLs and extend `_title_matches_families` so other makers are dropped.
   - Blocked sites: add a URL list to `BLOCKED_BY_FAMILY`. They are still attempted.
3. **Register the search** in `refresh_searches.py`:

```python
{"slug": "pc12", "title": "Pilatus PC-12", "families": ("pc12",)},
```

`generate_report.py` reads `SEARCHES`, so the new tab is included on the next build. The README tab stays last.

4. **New source file name.** If you add a source key that is not already in `saved_store.py` `SOURCE_FILES` (the existing keys are `cirrus`, `cubcrafters`, `aso`, `globalair`, `aircraftdealer`, `barnstormers`, `controller`, `tradeaplane`, `aircraftcom`, `aerotrader`, `ebay`, `merged`), add a CSV name there. Add a label in `generate_report.py` `SITE_LABELS` so the Source column shows a readable name.
5. **Optional filter chips** in `report_template.html` `SPEC_TERMS`. A chip with `display: true` is a filter only. It appears on a tab only when at least one listing matches. Put related names in one `group` so selecting several of them means "any of these".
6. **Tests** in `test_listings.py` (a kept row, a rejected lookalike, and a parser fixture) and `test_saved.py` (a snapshot for the new slug does not write `saved/sr22/`).
7. **Scrape and rebuild:**

```bash
python3 -m unittest test_listings.py test_saved.py
python3 refresh_searches.py --slug pc12
python3 generate_report.py
```

8. Add the new tab to the "This snapshot" section of this README and rebuild the HTML so the README tab matches.

## Data sources

These returned listings on the 2026-10-28 scrape, plus the PA-28-180/181 scrape on 2026-10-29.

| Source | SR22 raw | Vision Jet raw | CubCrafters raw | PA-28-180/181 raw | How it is read |
| --- | ---: | ---: | ---: | ---: | --- |
| Cirrus approved pre-owned | 297 | 31 |  |  | `cirrusaircraft.com` aircraft-listings JSON |
| CubCrafters inventory |  |  | 17 |  | `cubcrafters.com/c/inventory/`. Sold ads and Piper ads dropped |
| ASO | 308 | 20 | 11 | 8 | `aso.com` marketplace JSON. Cirrus uses model ids. CubCrafters and PA-28 use text queries, then a title/model filter. Every result page is read |
| GlobalAir | 265 | 13 | 14 | 9 | Manufacturer page in the browser, followed until there is no next page. PA-28 uses the Piper page and keeps only 180/181 titles |
| AircraftDealer.com | 138 | 7 | 5 | 9 | Category pages in the browser, then the detail page when N-number or total time is missing. PA-28 uses the Archer and Cherokee 180 categories plus text search. This is not Aerotrader |
| Barnstormers | 8 | 0 | 11 | 15 | Advanced search. Parts, ferry, and service ads are dropped. The Vision Jet search had no whole-airplane ads |

Merged counts in that snapshot:

- SR22 tab, data as of 2026-10-28 10:49 CDT: **414** airplanes (327 SR22-family, 87 SR20). **395** have an N-number. **260** are on more than one site. Asks run up to about $1.7 million.
- Vision Jet tab, data as of 2026-10-28 16:46 CDT: **39** SF50s. Generations the listings stated: 3 G1, 13 G2, 22 G2+, 5 Arrivee, 3 Premium, and 1 with no generation written down. No listing stated G3 or G3+. **38** have an N-number. **17** are on more than one site. Asks run to about $2.75 million. One listing stated engine cycles. Landings and a Cirrus Jet Support date were not stated.
- CubCrafters tab, data as of 2026-10-28 18:17 CDT: **45** rows after N-number dedupe. **32** have an N-number. A 2016 Carbon Cub SS at $249,000 and a 2021 Carbon Cub EX-2 at $140,000 are each posted on AircraftDealer and Barnstormers with no registration, so each pair stays as two rows. Lines named in the ads: 28 Carbon Cub (11 SS, 7 FX-3, 5 EX-2, 3 EX-3, 1 EX, 1 FX-2), 7 NXCub, 6 XCub, 3 Sport Cub (2 of them S2), 1 Top Cub. Asks run from about $134,500 to $495,000.
- Piper PA-28-180/181 tab, data as of 2026-10-29 13:01 CDT: **32** airplanes. **22** have an N-number. **8** are on more than one site. Stated models: 11 PA-28-180, 9 Cherokee 180, 2 Cherokee 180D, 1 Cherokee 180C, 1 Cherokee 180 Challenger, 5 PA-28-181 (2 Pilot 100i, plus Archer II, Archer III, and Archer LX), 2 Archer, 1 Archer II, and 1 Archer III. Warriors, Arrows, Dakotas, Cruisers, and a Cherokee 140 with a 180 hp conversion were excluded. Asks run from about $49,900 to $539,900. Sixteen rows state an engine-time figure such as SMOH.

These five sites blocked automated access. They are still attempted on every refresh. A failure does not erase a previous file, and no rows were invented for them:

| Site | What happened |
| --- | --- |
| Controller.com | Cloudflare challenge ("Just a moment...") |
| Trade-A-Plane | The request was blocked before any search results |
| Aircraft.com | Cloudflare challenge |
| Aerotrader | The request was blocked before any listings. AircraftDealer.com is a different site and is scraped |
| eBay Motors | Robot block |

### Known gaps

A cell stays blank when the listing does not state the value. Nothing is estimated. A 2004 SR22 is not labeled G2 unless the listing says G2. "Less than 100 TT" is not stored as 100. A type code such as CCX-2300 is not renamed to XCub or NXCub unless the listing says which one. Bushwheels are not relabeled as tundra tires.

Often blank because the page does not say: engine time-to-TBO, propeller time, interior and exterior colors, airport identifier, days on market, and a dollar amount for a price drop. GlobalAir and Barnstormers cards are used as published, so engine time on those rows is blank unless the card states it. ASO's result feed states total time, registration, serial, price, seller, and the published date, and does not state engine time or CAPS. "Call for price" is blank. A non-USD ask is kept in that currency and is not converted. Two different N-numbers are never merged. An airplane with no N-number and no serial stays its own row, so the same ad on two sites can appear twice.

Market value, BaT, and MSRP columns are on the page so the layout matches the car report. There is no sold-auction feed and no stated MSRP for these airplanes, so those cells are empty.

## Share the report

`output/report.html` is one file. The listings, the four tabs, and this README are inside it. Airplanes, filters, sorting, and the price chart work with the file open from disk and no local server. The server is only for background refresh and the UPDATE button.

Send that file, or commit it and have the other person open the same path in their clone. Fonts and the chart library load from the network (Google Fonts and jsDelivr). With no network the tables still show; the chart does not.

The README tab is a copy of this file at the moment `generate_report.py` or a scraping refresh last ran. Edit `README.md`, then run `python3 generate_report.py`, or the tab and the markdown file will differ.

## Troubleshooting

**A source shows a warning and no new rows.** Controller, Trade-A-Plane, Aircraft.com, Aerotrader, and eBay usually fail. The tab warning and `saved/<slug>/meta.json` name the reason. Rows from the last good CSV for that source stay. The other sources still update. You do not need to do anything for a blocked site.

**A refresh returned no listings.** If that source already had a real snapshot, the empty result is rejected and the old CSV stays. If this is the first run and the source has no file, `meta.json` says there are no saved listings. Read the warning. Do not delete `saved/<slug>/` to "start clean" unless you mean to lose the last good snapshot.

**The page looks old.** Check **Data as of** on the tab. If it is inside the freshness window, `python3 refresh_searches.py` will skip it. Use `--force` or the UPDATE button (server must be running: `python3 search_server.py`, then `http://127.0.0.1:8766`). Opening the HTML file never scrapes.

**UPDATE does nothing or says the server is not running.** The button only works on `http://127.0.0.1:8766`, not on a `file://` URL. Start `python3 search_server.py` from this folder with the virtualenv active, and leave it running.

**Chrome or Chromium was not found.** From this folder, with the virtualenv active:

```bash
python3 -m playwright install chromium
```

Install Google Chrome as well. The next refresh tries Chromium, then Chrome. If both fail, the message is `could not launch a browser`. The tests do not need a browser.

**`python3 -m venv .venv` fails, or `python3` is the wrong version.** `python3 --version` should be 3.11 or newer. Use the python.org installer or `brew install python@3.12` if venv reports that ensurepip is missing. The weekly script uses `.venv/bin/python` when `.venv` is in this folder, which is what the first-run steps create. Recreate it with `python3 -m venv .venv` if the folder was moved.

**The README tab is missing or stale.** Run `python3 generate_report.py`. A skipped refresh does not rebuild the HTML.
