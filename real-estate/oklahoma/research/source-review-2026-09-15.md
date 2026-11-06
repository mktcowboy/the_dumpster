# 5 — Skeptical review: verified sources and build order (OKC 50-mile deal-flow tracker)

Review date: 2026-09-15. I re-checked the decision-relevant claims in files 1–4 myself.

**Methods and limits**
- Read-only GET/HEAD via curl (default user agent, no spoofing), plus 4 WebSearches and 1 WebFetch.
- No logins, POSTs, API keys, or terms accepted. No challenges bypassed.
- No PDF/XLSX/CSV downloads. ArcGIS: `?f=json` metadata and `returnCountOnly` only.
- No name searches. No owner or defendant names recorded.
- About 82 requests in total, slightly over the ~70 target. No domain got more than 6.
- Items marked "not re-checked" rest on the original file's evidence.

Verdict key: **VERIFIED** = I reproduced the claim today. **CORRECTED** = the source is real but a claim was wrong. **UNVERIFIABLE** = I was blocked, or confirming would break the ground rules. **REJECT** = don't automate (a manual route may still exist; see §3).

---

## 1. Verdicts

| Source | Distress type | Counties in area | Verdict | Access path we'd actually use | Decision needed |
|---|---|---|---|---|---|
| **Sheriff-sale JSON feeds (shared Wappler/DMX template)**: ccsheriff.net, gradycosheriff.com, lincolncountysheriffok.gov, logancountyso.org, caddocountysheriff.com, seminolecosheriff.com | sheriff sale | Canadian, Grady, Lincoln, Logan (core); Caddo, Seminole (partial) | **CORRECTED, usable.** Endpoints return JSON with `address`, `city`, `zip`, `case`, `date`, `status`, `appraisal`. Row counts match file 2: 16/11/11/0/7/1, of which 10/11/8/0/6/1 are active and future-dated. Every row has an address and ZIP. robots.txt disallows `/dmxAppConnect/api`, `/dmxAppConnect/modules/*`, `/files`, `/admin` and login pages, but not `/dmxConnect/api/` (the path the page calls). Seminole has no robots.txt. **New finding: file 2 never read the terms.** The ccsheriff.net `copyright-accessibility` page says material may be copied "for your personal, non-commercial home use only". It has no automated-access ban and credits Lighthouse Web Designs as vendor (file 2 said "SheriffWebsites.com"; not confirmed). | 1 GET/day per county to `/dmxConnect/api/SheriffSales/Read.php`. Drop the `defendant` field. | Decide whether a private deal tracker fits "personal, non-commercial" use (§4 Q1) |
| **OKCountyRecords.com API (KellPro)** | pre-foreclosure (lis pendens), judgment, sheriff's deed | McClain, Logan, Pottawatomie, Lincoln, Kingfisher, Grady (core); Garvin, Seminole, Blaine (partial). **Not** Oklahoma, Cleveland, Canadian, Payne, Caddo. | **VERIFIED, terms unread.** Docs page: "Query up to 150 search results per day for free. Pay $0.01 for each search result beyond"; pages of up to 15; watermarked images $0.40. The county nav lists 65 counties matching the coverage above. robots.txt disallows only `/document*` and `/plat-maps-*`; `/api/` is allowed. `/terms` still returns a Cloudflare 403, so the terms are **UNVERIFIABLE** from here. | Official API, HTTP Basic key; daily `indexed_date` window per county × instrument type | **Free API key**; read the terms at signup |
| **OSCN dockets** (oscn.net) | foreclosure (CJ), probate, eviction | Oklahoma, Cleveland, Canadian, Logan, Payne (and possibly all 77) | **REJECT for automation.** Every path I tried returned HTTP 201 `<title>OSCN Turnstile</title>`: `/`, `Search.aspx`, `Results.aspx?...dcct=2&FiledDateL=...`, and **even `/robots.txt`**. File 1 said `Search.aspx` returned 200; that is no longer true. The `Disallow: /` robots claim and the `dcct`/`FiledDateL` parameter names are **UNVERIFIABLE** today because the gate hides them. | Manual lookups in the operator's browser to confirm a lead's case status | none (manual) |
| **ODCR web search + KellPro ODCR API** | foreclosure (CJ), probate, eviction | McClain, Pottawatomie, Lincoln, Kingfisher, Grady (core); Caddo, Garvin, Seminole, Blaine (partial) | **VERIFIED.** `/status` lists all nine; Oklahoma, Cleveland, Logan and Payne are absent, and "Canadian" appears only inside another court's address. Terms quote confirmed: "Accessing the data by any automated mechanism is not permitted, unless using the API." API: "$200 monthly fee, $5 every 1,000 transactions". Web: Advanced Tools $5/mo, images $25/mo (single court) or $55/mo. | Free web search by hand. The API only if paid. | **Paid $200/mo + usage**, or manual |
| **Oklahoma County Clerk**, okcc.online (and the Tyler portal) | pre-foreclosure (lis pendens), judgment, deed | Oklahoma | **VERIFIED block.** robots.txt is `User-agent: * / Disallow: /`. Tyler disclaimer not re-checked. | Weekly manual Document Type = LIS PENDENS search | **Manual weekly step**; optional data-extract request to the clerk |
| **Cleveland (Tyler) / Canadian (cogov) clerk portals** | lis pendens, deeds | Cleveland, Canadian | **UNVERIFIABLE.** Not re-fetched (budget); both sit behind click-through disclaimers per file 1. | Weekly manual search after the operator reads the disclaimers | **Manual weekly step** + read the disclaimers |
| **Bid4Assets, Oklahoma County Sheriff storefront** | sheriff sale | Oklahoma | **UNVERIFIABLE.** `robots.txt` and `/OKCSheriff` both return Akamai "Access Denied" 403, so the terms, the "Download Property List", and inventory remain unseen. A search result title confirms the storefront exists. KFOR headline: "Oklahoma County Sheriff's Office to resume online auction sales"; the article itself returned 403. The current sale cadence is unconfirmed ("specified Tuesdays" vs "every other Tuesday"). | a local browser: weekly look, plus any account alert or property-list download | **Manual weekly step**; decision in §4 Q3 |
| **McClain County Sheriff HTML list** | sheriff sale | McClain | **VERIFIED.** 9 `CASE #` blocks today. robots.txt disallows only `/wp-admin/`. Terms not reviewed. | 1 GET/week, regex the labeled blocks | none |
| **Payne County `/sheriff-sale` HTML** | sheriff sale | Payne (partial) | **VERIFIED.** 4 unique rows (each address appears twice in the HTML), formatted "street, City OK ZIP". robots.txt is `Allow: /`. | 1 GET/week, parse the table, dedupe | none |
| **Cleveland County Sheriff PDF** (`ccso-ok.us/DocumentCenter/View/24`) | sheriff sale | Cleveland | **UNVERIFIABLE (contents).** The page text is confirmed: sales on the 1st and 3rd Wednesday at 10:00, lists posted about 3 months at a time. robots.txt does not cover `/DocumentCenter`; it blocks `/RSS.aspx`, `/Search*`, `/map*`, and blocks Baidu/Yandex outright. HEAD returns 404 again. A GET would download a PDF, which the rules forbid, so the fields and address format are unknown. | GET the PDF plus text extraction, once the operator confirms the format | **Manual one-time step**: open the PDF and confirm it has street + city |
| **Pottawatomie County Sheriff PDF** | sheriff sale | Pottawatomie | **VERIFIED link, contents unverified.** `/DocumentCenter/View/196/September-2026-Sheriff-Sales`. Sales held at the County Administration Building since 2025-09-01. | Scrape the page for the current link, then parse the PDF | Manual one-time format check |
| **Oklahoma County Treasurer, County-Owned List** (`CountyOwnedList.asp`) | county-owned surplus | Oklahoma | **CORRECTED (file 4).** 196 data rows, but only **1 has a real street address**. 187 read "0 UNKNOWN <city>", 3 read "UNKNOWN", 5 are HOA "COMMON AREA" parcels. Suggested bids run $210–$17,840 (median $445, 90th percentile $630); initial bid is $0 or $265. No robots.txt. | 1 GET/week + parcel → assessor REST join | Scope decision (§4 Q8) |
| **Oklahoma County Treasurer, Active Resale** (`ResaleActiveList.asp`) | tax sale | Oklahoma | **CORRECTED (file 2).** Returns **HTTP 200**, not 404: "These are the accounts that are currently active in our 2026 Resale… The Oklahoma County Resale Is Complete. See You Next Year!" Seasonal. | Seasonal GET (spring to June) | none |
| **Cleveland County Treasurer resale** | tax sale | Cleveland | **VERIFIED.** "This sale takes place the second week in June online. We have partnered with GovEase." List published in May. | Annual May reminder / manual | Manual annual step |
| **OPA legal-notice search** (oklahomanotices.com → opa.eclipping.org) | newspaper notices (sheriff sale, probate, resale) | statewide, all 14 counties | **VERIFIED as manual-only.** The landing page says it is free and searchable "by newspaper, city, county or Zip Codes". The iframe form is `method="post"`, so automation would mean scripted POSTs. | Weekly manual keyword search (e.g., "sheriff's sale", Oklahoma County) | **Manual weekly step** |
| **VRM (VA + Mr. Cooper REO)**, vrmproperties.com | government/bank REO | area-wide | **CORRECTED count, usable.** **77** Oklahoma listings today (file 3 said 76), over 5 pages. By URL slug: **20 in core cities** (OKC 5, Choctaw 3, Yukon 2, Shawnee 2; Edmond, McLoud, Moore, El Reno, Kingfisher, Chandler, Norman, Midwest City 1 each), plus Pauls Valley, Prague and Seminole at the edge, and Konawa and Watonga outside. robots.txt disallows only `/Auth`, `/Error`, `/User`, `/Lead`. Terms (www.vrmco.com) contain no robot/scrape/automated-access clause. | 5 GETs/week, parse slugs and cards | none |
| **Freddie Mac HomeSteps** | GSE REO | area-wide | **VERIFIED.** "13 properties", 13 `RealEstateListing` JSON-LD blocks, 4 in area (OKC 73132, Mustang 73064, Norman 73026, Noble 73068). robots.txt doesn't cover `/listing/`. Terms: "may be downloaded for personal use, but no portion… may be published, sold, republished…". No robot clause found. | 1 GET/day, parse JSON-LD. Private use only. | none |
| **HUD Home Store** | FHA REO | area-wide | **VERIFIED as manual-only.** robots.txt is `User-agent: * / Disallow: /`. 14 Oklahoma listings; 5 within 50 mi by HUD's own coordinates (7.0, 7.4, 11.1, 41.3, 49.6 mi). **All 5 are in the "Exclusive" (owner-occupant) period** (file 3 showed "—" for two). | Weekly manual check | **Manual weekly step** |
| **Xome Auctions** | REO / foreclosure auctions | area-wide | **REJECT for automation (terms), wording corrected.** robots.txt allows `/auctions/ok`. Terms live at `xome.com/terms-of-use` (`/pages/terms-of-use` redirects there) and bar anyone who would "use data mining, robots, or similar data gathering and extraction tools". File 3's quote and its "§2" citation don't match the current text; the substance does. Inventory not re-counted. | Saved-search email alerts parsed from Gmail, or manual | Create an account + alerts |
| **ServiceLink Auction sitemap** | foreclosure / REO auctions | area-wide | **UNVERIFIABLE (terms).** robots.txt is `User-agent: *` with no Disallow, plus 2 sitemaps (confirmed). Terms not found (Angular app; search turned up nothing). Sitemap counts not re-checked. | Hold. Weekly sitemap diff only after the operator reads the terms. | Read the terms |
| **Auction.com** | foreclosure / REO auctions | likely area-wide | **REJECT for automation.** `robots.txt` itself returns an Imperva Incapsula challenge (`_Incapsula_Resource`, `incap_ses` cookies). | Account alerts, parsed from Gmail | Create an account + alerts |
| **Fannie Mae HomePath** | GSE REO | unknown | **REJECT for automation.** `/robots.txt` returns the JS app HTML (user-agent-sniffing script), so there is no real robots.txt. | Account alerts or MLS | Create an account + alerts |
| **Hubzu** | REO auctions | unknown | **VERIFIED robots `Allow: /`**; the JS-shell finding was not re-checked. Not worth a headless build. | Alerts / manual | optional account |
| **Oklahoma County Assessor, TaxParcelsPublics_view** (ArcGIS Online) | parcel enrichment | Oklahoma | **VERIFIED.** `Query,Extract`; maxRecordCount 2000; last edit 2026-09-15 09:17 UTC; count 337,026. Situs fields are `location`/`locationcity`; no situs ZIP. Mailing and sale fields are present. | REST query per lead (parcel or `location`) | Bulk vs on-demand decision (optional) |
| **Oklahoma County Assessor, View_OKPublicRecord** | parcel enrichment | Oklahoma | **VERIFIED.** `Query,Extract`; 8 tables (Account, Improvement, ImprovementDetail, LandAttributes, Owner, Sales, STR, ValueDetail). The Improvement table has `owner_occupied`, `condition`, `quality`, `year_built`, `year_remodeled`, `percent_complete`. | REST joins on `account_num` / `parcel_num` | none |
| **Canadian County, Parcel Data (External)** | parcel enrichment | Canadian | **VERIFIED.** `Query,Extract`; count 84,803; has `situs`, `situs_city`, `situs_zip`, mailing fields, `hs_ex_amount`. No year built or sale data. | REST query per lead | none |
| **Cleveland County Tax/Tax FeatureServer** | parcel geometry | Cleveland | **VERIFIED (metadata only).** The service `?f=json` and layer 1 `?f=json` both report `"capabilities": "Query,Create,Update,Delete,Uploads,Editing,Extract"`. Layers: Parcel Annotation, Parcel Area, Old Lines. No situs address and no values. I attempted **no** edit, applyEdits, add, update or delete request. | Read-only query for PIN/geometry; weak enrichment | Whether to tell the county (§4 Q10) |
| **OKC Abandoned Buildings PDF** | code violation / vacant | Oklahoma City | **VERIFIED stale.** HEAD: 200, `application/pdf`, 117,002 bytes, Last-Modified **2025-06-13**. The okc.gov robots.txt has no rule for `/files/assets/`. | Weekly HEAD; parse only when it changes | none |
| **OKC open data (data.okc.gov)** | none | Oklahoma City | **VERIFIED "no distress dataset."** The catalog API returns 82 items. The query "code enforcement" matches 0, and no title matches code, abandon, dilapidated, demolition, lien, violation, vacant, condemn, nuisance or permit. | none | none |
| **MLSOK via MLS Grid** | on-market fixers | all core counties | **VERIFIED process.** okcmar.org: "Only the Agent or Broker can request access to the data", email data@okcmar.org, delivered via MLS Grid. Price not public. | Licensed RESO API | **Broker sponsor + license fee (unknown)** |
| **RentCast API** | on-market listings (no remarks) | all | **Partly verified.** Overage tiers $0.20 / $0.06 / $0.03 / $0.015 per request and the 5,000 and 25,000 per-month tiers confirmed. Plan prices ($74/$199/$449) and the free 50/mo tier not captured. | Official API | Paid $74+/mo (unverified) |
| **PropStream** | pre-foreclosure, tax-delinquent, vacant (filters) | all | **VERIFIED price.** Essentials "$99/mo", "$81/mo" billed annually. No API (not re-checked). | Manual CSV export | **Paid $99/mo** + manual export |
| oktaxrolls.com, Garvin sheriff PDF, Kingfisher okcounties.org, Pickens/Dakil, OCURA, OKC PrimeGov agendas | various | various | **Not re-checked** (outside every top 5 or low stakes); original evidence stands | See §3 manual list | — |

---

## 2. Errors and contradictions found

- **File 4, ranked #2: the OK County county-owned list "with parcel # and address".** Wrong. Only 1 of 196 rows has a street address; 190 are "UNKNOWN" and 5 are HOA common areas. Every row needs a parcel → assessor join, and most are vacant slivers (median suggested bid $445). File 2's description ("190 of 196 no address") is correct. **The source drops from a top-5 build item to optional.**
- **File 2: `ResaleActiveList.asp` "returns 404".** Wrong. It returned HTTP 200 today with a "Resale Is Complete. See You Next Year!" page. File 4 is correct.
- **File 1: OSCN `Search.aspx` "returned 200".** It no longer does: `Search.aspx`, the homepage and **robots.txt** all return the Turnstile page (HTTP 201). The `Disallow: /` robots claim and the form field names can't be re-verified. The no-automation verdict stands either way.
- **File 1 vs. outside evidence on OSCN coverage.** File 1 infers that ODCR counties (McClain, Grady, Lincoln, Pottawatomie, Kingfisher) aren't on OSCN, and so `server.js` routes them wrong. A search-engine summary says OSCN serves "all 77 county District Courts". The Turnstile makes this unresolvable, and the point is moot: neither system is a free automated feed.
- **File 2: sheriff-template terms "not reviewed."** Now reviewed. The ccsheriff.net terms allow copying "for your personal, non-commercial home use only". That is a real compliance question for build item #1, not a blocker. The vendor credited is Lighthouse Web Designs, not the "SheriffWebsites.com" name file 2 used.
- **File 2: robots.txt summaries for the template sites are incomplete.** Canadian's robots.txt also disallows `/files` and several `/dmxAppConnect/modules/*` paths; Grady's lists `/admin` and several `.php` pages beyond `/Connections`. The key conclusion holds: `/dmxConnect/api/` is not disallowed anywhere.
- **File 3: VRM count and HUD listing periods.** VRM now shows 77 Oklahoma listings, not 76 (the in-area count of 20 core plus edge towns does check out). All 5 in-range HUD homes, including Sparks and Anadarko, are in the owner-occupant-only "Exclusive" period, so none is investor-biddable today.
- **File 3: Xome terms quote.** The quoted wording and "§2" don't appear in the current terms, which live at `/terms-of-use`. The current clause bans "data mining, robots, or similar data gathering and extraction tools", so the verdict is unchanged.
- **File 2 vs. File 4: October tax-lien certificate sale.** File 4 says it happens the first Monday in October; file 2 says a §3105 amendment eliminated it. Both rest on search snippets. **Unresolved.** Don't build a fall-sale reminder until a treasurer confirms.
- **File 2: Bid4Assets cadence "specified Tuesdays."** A search summary of the 2023 launch coverage says "every other Tuesday, 10 a.m. to noon". A KFOR headline says sales were set to *resume* after a pause. The current schedule is unverified either way.
- **Duplicates across files (merge in the tracker):**
  - OK County county-owned list: file 2 #5 = file 4 #2.
  - OPA notice search: file 1 leads = file 2 source.
  - oktaxrolls: files 2 and 4 (file 2 adds Pottawatomie).
  - Cleveland Treasurer GovEase: files 2 and 4.
  - Bid4Assets: file 2 (OK County sheriff) and file 3 (USMS storefront).
  - ServiceLink Auction is Hudson & Marshall's inventory (file 3).
  - Xome "Live Event/Marketing" lots overlap county sheriff sales; dedupe by address.
  - HUD, HomeSteps and HomePath homes also appear on the MLS (files 3 and 4).
- **In-area county coverage is consistent between files.** Kingfisher records are on OKCountyRecords and dockets on ODCR (file 1), while its sheriff list is on okcounties.org (file 2). Different offices, no conflict.

---

## 3. Recommended build order

Ranked by deal value in the area × reliability × compliance. Effort: S = hours, M = 1–2 days, L = more.

1. **Sheriff-sale JSON feeds (Canadian, Grady, Lincoln, Logan; Caddo and Seminole filtered to 50 mi).**
   - Adds confirmed, dated foreclosure auctions with appraisal and case number; 36 active future sales across the six feeds today.
   - Access: one GET/day per county.
   - Street + city + ZIP in every row.
   - Effort **S**. Build once the operator OKs the "personal, non-commercial use" clause (§4 Q1). Filter on `status` and `date`, and don't store `defendant`.
2. **VRM (VA + Mr. Cooper REO).**
   - Adds the largest verified, automation-permitted REO inventory: 20 core-city listings.
   - Access: 5 paginated GETs/week.
   - Street + city + ZIP in the URL slug and card.
   - Effort **S–M**.
3. **Oklahoma County Assessor REST (TaxParcelsPublic + View_OKPublicRecord).**
   - Adds the enrichment backbone for the biggest county: absentee test (situs vs mailing), `owner_occupied`, `condition`, `year_built`, last sale. It also resolves parcel numbers from treasurer lists and manual clerk finds.
   - Access: per-lead REST queries.
   - Situs street + city present; ZIP is often null, so geocode on street + city.
   - Effort **S–M**.
4. **OKCountyRecords API: lis pendens (+ journal entry, sheriff's deed), daily.**
   - Adds the earliest foreclosure signal (pre-foreclosure) for 6 core and 3 partial counties, with a 150-results/day free tier.
   - Access: official API with a free key.
   - **No situs address.** Results carry a legal description and party mailing addresses. Those counties have no verified parcel REST service, so plan to (a) match the case number against the sheriff JSON feeds when a sale posts, and (b) keep the rest as "needs manual address" leads.
   - Effort **M**.
5. **McClain HTML list + Payne HTML table.**
   - Adds sheriff sales in one core county and one partial county.
   - Access: plain GET weekly.
   - McClain: street + city, no ZIP (geocode with city + OK). Payne: street, city and ZIP.
   - Effort **S**.
6. **Freddie Mac HomeSteps.**
   - Adds GSE REO (4 in area) cheaply and reliably.
   - Access: 1 GET/day, JSON-LD parse. Private use only, no republishing.
   - Street + city + ZIP.
   - Effort **S**.
7. **Canadian County parcel REST.**
   - Adds homestead-exemption and absentee flags for the Canadian sheriff rows and any Yukon/Mustang/El Reno leads.
   - Access: per-lead REST query.
   - Situs + city + ZIP.
   - Effort **S**.
8. **Cleveland County sheriff PDF.**
   - Adds a high-volume core county (sales twice a month).
   - Access: GET at the fixed DocumentCenter ID, text extraction, change detection by hash.
   - Address format unknown until the operator opens it once.
   - Effort **M**.
9. **Pottawatomie and Garvin sheriff PDFs.**
   - Adds core Pottawatomie and partial Garvin.
   - Access: find the current PDF link on each page, then parse.
   - Address format unknown.
   - Effort **M** each.
10. **OKC Abandoned Buildings PDF watcher.**
    - Adds the only official OKC vacant/dilapidated signal, but it is 15 months stale.
    - Access: weekly HEAD; parse only when Last-Modified changes.
    - Street addresses, city = OKC.
    - Effort **S**.
11. *(Optional, only if the operator wants land plays)* **OK County county-owned list.**
    - Adds cheap vacant parcels.
    - Access: weekly GET plus a parcel → assessor join (build #3).
    - Almost no addresses on the list itself.
    - Effort **S**.

**Paid/licensed options (only with the operator's go-ahead):**
- MLSOK via MLS Grid: best on-market fixer feed; needs a broker sponsor.
- PropStream at $99/mo: manual CSV export with distress filters.
- ODCR API at $200/mo + usage: not recommended for these low-volume counties.

**Compliant manual steps (weekly unless noted):**
- **Oklahoma County sheriff sales on Bid4Assets:** look in your own browser, and check whether the storefront offers an email alert or a property-list download.
- **Oklahoma County Clerk (okcc.online):** Document Type = LIS PENDENS, last 7 days. robots.txt is `Disallow: /`.
- **Cleveland (Tyler) and Canadian (cogov) clerk portals:** lis pendens by type, after reading their disclaimers.
- **HUD Home Store:** watch for homes moving from Exclusive to Extended; bid openings are daily.
- **OPA legal-notice search:** keyword "sheriff's sale" for Oklahoma and Cleveland counties, as a backstop.
- **Saved-search email alerts** on Xome, Auction.com, HomePath and optionally Hubzu, LoopNet and Crexi. The tracker can parse them from Gmail as review-gated drafts.
- **Every two weeks:** skim OKC council agendas for dilapidated/unsecured declarations (PrimeGov robots.txt is `Disallow: /` per file 4).
- **Each May:** check the resale lists (OK County publication PDF, Cleveland GovEase, oktaxrolls county pages).
- **One-time:** open the Cleveland sheriff PDF and confirm it lists street + city.

---

## 4. Decisions only the operator can make

1. **Sheriff-site terms:** the template sites allow "personal, non-commercial home use". Options: treat the private tracker as personal use and build; email the sheriffs' offices for an OK first; or skip.
2. **OKCountyRecords API:** create a free key and read its terms (unreadable from here), or skip pre-foreclosure in the six smaller core counties?
3. **Oklahoma County sheriff sales (Bid4Assets blocks plain HTTP and the terms are unreadable):** manual weekly check, check the site yourself for a list download or alert, or skip?
4. **Terms stance:** follow the stricter of robots.txt and site terms (recommended; rules out Xome and HUD automation), or robots.txt only?
5. **Alert accounts:** which of Xome, Auction.com, HomePath, Hubzu, LoopNet and Crexi should you sign up for so their emails feed the tracker via Gmail?
6. **Paid data:** none, PropStream $99/mo (manual export), ODCR API $200/mo + $5 per 1,000, or an MLSOK license via a broker?
7. **Clerk records and data requests:** will you read the OK County, Cleveland and Canadian clerk disclaimers and run the weekly lis pendens checks? And should I draft emails or Open Records requests (clerks, the courts' administrative office, OKC code enforcement) for you to send?
8. **Scope:** include vacant county-owned lots, voluntary/estate/commercial auctions (Pickens, Dakil, CLO), evictions and probate, or strictly foreclosure/REO housing?
9. **Radius:** keep every row from the partial counties and cut at 50.0 geocoded miles, or skip counties below a coverage share?
10. **Cleveland County GIS:** its public Tax FeatureServer advertises Create/Update/Delete. Notify the county, or leave it?

---

## 5. Coverage gaps

- **Oklahoma County has no automatable foreclosure source at any stage.** Pre-foreclosure (okcc.online, `Disallow: /`), court filings (OSCN Turnstile) and sheriff sales (Bid4Assets 403) are all manual. It is the biggest county, so this is the most important gap.
- **Cleveland County:** lis pendens is manual behind a disclaimer. The sheriff PDF's contents are unverified. The parcel REST has no situs address or values, so there's no free enrichment or address join.
- **Canadian County pre-foreclosure** is manual (clerk disclaimer); its sheriff sales and parcels are covered.
- **Street addresses for pre-foreclosure leads** in McClain, Logan, Pottawatomie, Lincoln, Grady and Kingfisher: OKCountyRecords returns legal descriptions only, and none of these counties has a verified public parcel REST service (Logan and Pottawatomie actDataScout return 403; the others are JS or manual lookups). Until a case reaches the sheriff feed, those leads can't be geocoded.
- **Code violation / condemned / vacant:** no city in the area publishes open data. OKC's only list is a 2025 PDF; Norman, Edmond, Moore, Midwest City and Shawnee have nothing public.
- **Probate and eviction:** no compliant free automated feed (OSCN gated, ODCR API paid, the civil-court eviction data is aggregate only).
- **Tax delinquency before the resale:** no per-parcel automatable list (Oklahoma County `TaxLiens.asp` returned 500 per files 2 and 4; oktaxrolls search method unknown). Only annual resale lists.
- **On-market fixers (as-is or investor remarks):** nothing compliant without an MLS license or a paid vendor.
- **Kingfisher and Blaine sheriff sales:** Kingfisher shows no events; Blaine's site has a TLS certificate error (file 2). Low volume, not re-checked.
- **Payne and Caddo land records:** CAPTCHA and a JS app respectively (file 1). Manual only.
