# Oklahoma Storage Market Report

Open **`oklahoma-storage-market-report.html`** for the complete interactive report. The single HTML embeds its research data, styling, scripts, company profiles and map library. No server or installation is needed. External source pages and map tiles need internet access.

## Contents

- Statewide overview with Census demand context, geographic distribution and evidence limits.
- 865 baseline directory records across 127 distinct city-field labels, including county labels; not an exhaustive verified facility census.
- Company and brand profiles that aggregate aliases and reviewed shared operator domains. Public REITs, public operating companies, disclosed PE platforms, institutional private capital and unresolved ownership are distinguished.
- Expandable profiles with all assigned locations, original brand labels, ownership evidence, rental observations, offering links and map navigation.
- 22 facility-level price observations, plus 10 operator-published regional average observations. These are selective public-source samples, not statewide rent estimates.
- 5 published broker offerings covering 6 properties; 9 additional unverified marketplace leads; 1 separate announced closed sale.
- Sources, collection limitations, duplicate/address review flags and JSON exports.

Research reviewed October 19, 2026. Observation dates do not imply that a page or search index was updated on that date. No broker availability confirmations or property-level operating statements were obtained.

## Reading the classifications

Brand and operator affiliations do not prove real-estate ownership. Storelocal profiles represent a shared brand network. U-Haul records may include affiliate relationships. REIT-branded properties can be third-party managed. A missing PE sponsor is recorded as unknown, not as proof of independent ownership.

Counts represent source records, including unresolved rebrands and duplicate candidates. The report does not estimate statewide square footage, revenue, occupancy or market valuation from those counts. Pricing separates parking, storage, promotions and unstated billing periods. Closed sales and unverified marketplace leads are excluded from published-offering totals.

## Files and rebuilding

- `oklahoma-storage-market-report.html` — final, portable report.
- `oklahoma-storage-directory.html` — original directory/map, with a link to the report.
- `oklahoma-storage-master.json` — baseline records.
- `report/research.json` — curated sources, ownership notes, rates, demographics and offerings.
- `report/build_report.py` — standard-library aggregation and HTML build.
- `report/report.template.html` — report layout and interactions.
- `report/report-data.json` — generated research and company/location relationships.

From the repository root:

```sh
python3 oklahoma-storage/report/build_report.py
python3 scripts/check_privacy.py
```

The build performs no network calls. Update the research inputs and source dates before rebuilding; rerunning the build does not refresh external prices or listings. The bundled Leaflet assets are reused from the directory with their existing license headers.

## Baseline quality

The raw directory contains 208 OKC-group records, 184 Tulsa-group records and 473 elsewhere. These are source-defined groupings, not official Census metros. There are 124 approximate coordinate flags and 5 records without coordinates. Fields missing: 5 addresses, 61 phones, 192 websites and 619 ZIP codes. Populated address fields sometimes lack a full street address.

Three public-facing name/address fields across two baseline entries were neutralized because they matched repository-blocked identity tokens. Those entries remain in the dataset, with street-name omission explicit. The privacy checker and hooks remain unchanged.

The prior directory’s place-search methodology is inherited rather than independently reproduced; original per-record collection citations and timestamps were unavailable. Its earlier claim of 150+ cities was not supported by the data and has been corrected.
