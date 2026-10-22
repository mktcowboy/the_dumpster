# Oklahoma for-sale sources, 2026-10-22

Review for the statewide tracker in `real-estate/oklahoma`. The September 2026 distressed review is `source-review-2026-09-15.md`. This note covers the extra question: which for-sale feeds can be read by automation, statewide, without ignoring robots.txt or terms.

## Method

- Ordinary GET and HEAD. Default client. No spoofed user agent, no login, no challenge bypass, no bulk download of a disallowed path.
- A site that answers with a captcha, Akamai 403, or Cloudflare challenge is recorded as manual. The body behind the challenge was not fetched.
- Official APIs are wired only behind an environment variable. With no key they are skipped.
- No owner, defendant, or attorney names were copied into this note or into the tracker.

## Sale-price disclosure

Oklahoma is not a pure non-disclosure state. 68 O.S. § 3201 imposes a documentary stamp tax of $0.75 per $500 of consideration, exclusive of liens or encumbrances remaining on the property. When a deed carries stamps, the stamp amount implies a consideration range. Many transfers are exempt (68 O.S. § 3202) and show no stamps. There is no free statewide feed of arm's-length sold prices.

This tracker does not convert stamps into a price. A sold comp is stored only when a source field states an amount (ATTOM sale snapshot `saleAmt`, or Mashvisor `last_sale_price` on the listing record). Assessed value and assessor total value are labeled as assessments. The September review's Canadian County parcel layer has no sale-price field, which matches that limit.

## What the sync actually used

Run at 2026-10-22T19:46Z with no API keys. 115 listings.

| Source | Access | This run |
|---|---|---|
| Sheriff JSON: Canadian, Grady, Lincoln, Logan, Caddo, Seminole | Working. `/dmxConnect/api/SheriffSales/Read.php` is the path the county pages call. Terms on the shared template allow copying for personal, non-commercial use. Defendant and attorney fields are dropped. | 21, 9, 6, 0, 3, 9. Logan returned an empty upcoming list. |
| Payne County sheriff HTML | Working. `https://www.paynecountyok.gov/sheriff-sale` (singular). `paynecounty.org` and the plural path are not this table. robots.txt is `Allow: /`. The copyright page on the redesigned site returned 404. The table has date, case, appraisal, starting bid, and address. No party names. | 10 upcoming |
| McClain County sheriff HTML | Manual on this date. `https://mcclaincountysheriff.com/sheriff-sales/` returned HTTP 202 with a SiteGround captcha. The September review had read the page. The parser is still tested against a saved fixture and refuses a captcha body. | Error, 0 stored |
| VRM | Working, now statewide. `vrmproperties.com` robots.txt still allows the listing path and disallows account paths. September terms on vrmco.com had no automated-access ban; not re-quoted here. | 57 Oklahoma REO |
| Canadian County assessor | Working as enrichment only. FeatureServer `ParcelDataService_2_view` layer 3, capabilities Query and Extract, about 84,817 parcels. Fields requested: situs, city, ZIP, total assessed, total value, land value, building value, parcel size, property class. Owner and mailing fields are not requested. | 8 matches |
| RentCast, Mashvisor, ATTOM | Needs a key. Adapters are in `sources/` and covered by tests. | Skipped |

## Portals left manual

Checked the same day unless noted. None of these are fetched by sync.

| Source | What was observed | Decision |
|---|---|---|
| Realtor.com | robots.txt legal notice: scraping is unauthorized without written permission from Move Sales, Inc. | Manual. Not used. |
| Zillow | Terms of use govern access. robots.txt disallows `/` for a default crawler. | Manual |
| Redfin | `User-agent: *` disallows `/stingray/`, the search API. | Manual |
| Crexi | Terms bar scraping and robots. The partner Listing API sends listings into Crexi; it is not a public search. robots.txt itself returned a challenge. | Manual |
| LoopNet | robots.txt returned Akamai 403. CoStar terms forbid scraping. | Manual |
| CityFeet, LandWatch, Land.com, LandAndFarm, Lands of America | robots.txt returned Akamai 403. | Manual |
| CommercialSearch | robots.txt returned a challenge. | Manual |
| HUD Home Store | robots.txt is `Disallow: /`. | Manual |
| Freddie Mac HomeSteps | robots.txt allows listing HTML and disallows `/search/`. September 2026 terms allowed a personal download and forbade republishing. Terms page was not re-fetched. | Manual, because this repository is public |
| Fannie Mae HomePath | No usable robots.txt (the app shell). Left off since September. | Manual |
| Auction.com | robots.txt is an Imperva challenge. | Manual |
| Bid4Assets | Akamai 403, including the Oklahoma County sheriff storefront. | Manual |
| Xome | Terms bar data mining and robots. | Manual |
| OSCN | Turnstile challenge, including robots.txt, as of September 2026. Not re-opened. | Manual |
| OKCountyRecords | Official API needs a key. Terms were Cloudflare 403 in September. Results are legal descriptions, not street addresses. | Not wired as listings |
| Oklahoma County assessor | `TaxParcelsPublics_view` did not resolve in an ArcGIS search. A similarly named FeatureServer used winter and summer tax fields and a continental extent (wrong jurisdiction). | Not used |
| Commissioners of the Land Office | Public GIS auction layer is agricultural leases, not land for sale. | Not mixed into the for-sale list |

## What this leaves out

There is no keyless automated feed here for ordinary MLS residential inventory, for office, retail, industrial, or mixed-use, or for farm and ranch listings. RentCast, if a key is set, can add residential, multifamily, and land, and still does not cover office, retail, or industrial, and does not provide cap rate. Mashvisor can add city residential pages and, only when the listing record includes them, a cap rate, occupancy, or last sale price. Cap rate is never estimated from a market assumption.

The 115-row snapshot is therefore sheriff and REO only. Commercial and land counts are zero because those sources blocked or forbid automated access, not because the page hides rows.
