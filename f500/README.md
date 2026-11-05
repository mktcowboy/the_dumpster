# Fortune 500 · 2026 Atlas

`f500_explorer.html` is a single-file interactive explorer of the **2026 Fortune 500**. It has an overview dashboard, a sortable/filterable table, an HQ map (clusters, bubbles and a state choropleth), an industry treemap/sunburst, a sourced relationship network, a Public vs Private ownership tab and a full profile for every company. Deep links use the URL hash, e.g. `#/company/16-nvidia` or `#/network/7`.

All data is real and comes from public sources (missing values show as `n/a`):

| Source | Used for |
|---|---|
| fortune.com/ranking/fortune500/2026 (+ company pages) | rank, revenue, profit, assets, market value, employees, sector/industry, HQ, CEO, website, ticker, description, rank history |
| SEC EDGAR (submissions + XBRL company facts + 10-K text) | revenue/net income/assets history, SIC, incorporation, customer-concentration edges |
| Wikidata SPARQL | founding year (fallback), founders, chair, logo, Wikipedia link, ownership/subsidiary/spin-off/board edges |
| US Census 2024 Gazetteer | HQ city coordinates |
| us-atlas | state boundaries |
| Wikipedia (infobox type, lead) | ownership-type evidence for non-traded companies |

## Rebuild
```
python3 01_fetch_fortune.py      # Fortune list + 500 company pages
python3 02_fetch_sec.py          # SEC submissions + company facts
python3 03_fetch_wikidata.py && python3 03b_wikidata_fallback.py
python3 04_scan_10k.py           # 10-K customer mentions
# Census gazetteer files: 2024_Gaz_place_national.zip and 2024_Gaz_cousubs_national.zip into data/
python3 08_fetch_ownership.py                                 # Wikidata P31 / P1454 / P749
python3 09_fetch_ownership_sec_wiki.py && python3 09b_fetch_wiki_intros.py  # SEC exchanges + delisting forms, Wikipedia infobox type + lead
python3 05_build_data.py         # -> data/companies.json, data/edges.json, data/stats.json
python3 05b_classify_ownership.py  # ownership type + evidence (run after 05)
python3 06_build_html.py         # -> f500_explorer.html
python3 07_verify.py             # headless Chromium check + screenshots
```
