# Solar Farm Proforma — Wichita Falls, TX

Interactive 30-year financial proforma for a hypothetical 1,000-acre greenfield
utility-scale solar farm near Wichita Falls, Texas (ERCOT/Oncor), built
October 12, 2026.

- `solar-farm-proforma.html` — self-contained page: explainer on solar farm
  economics plus an after-tax proforma with editable assumptions (sliders),
  a return profile under three tax views, a line-by-line 30-year statement
  (every revenue, cost, debt and tax line), an assumption audit, and a CSV
  download of the full statement.
- `solar-farm-proforma-v2.html` — a decision-first companion model. It reduces
  the interactive inputs to the main investment drivers, uses a transparent
  net-ITC proxy and simple level debt, and adds a PPA-price × EPC-cost stress
  table. It deliberately excludes income taxes and detailed debt/tax mechanics;
  use V1 for those audit-level views.

Base case (revised Oct 12, 2026 after an assumption audit):
- 149 MWdc single-axis tracking (~115 MWac)
- $174.5M project cost ($1.17/Wdc incl. interconnection and 3% development/IDC)
- $14.3M year-1 revenue (275 GWh after 3% curtailment, $52/MWh PPA, 2%/yr escalator)
- After tax, sponsor using the tax losses: 3.6% unlevered / 1.7% levered IRR;
  standalone project (NOLs carried forward): 2.7% / 0.3%; pre-tax: 3.4% / 0.9%
- Debt sculpted to 1.30x DSCR (~$67M); 100% bonus depreciation worth ~$31M of
  year-1 tax if the sponsor can use it

What the audit changed: added federal income tax, 100% bonus depreciation and
MACRS, NOL rules, ITC on eligible basis only, school-district property tax
(not covered by a county Ch. 312 PILOT), a depreciating appraisal value,
curtailment, development costs, sculpted debt with fees and a reserve,
decommissioning, and the Texas franchise tax. Flagged but unchanged: the PPA
escalator (flat PPA = deal never pays back), 25-year PPA term (15 years also
fails), and the $52/MWh price.

Key sources embedded on the page: Wood Mackenzie/SEIA (Q2 2026 capex via
pv magazine), LevelTen PPA index, NREL, Berkeley Lab, Global Solar Atlas,
Texas Comptroller (Ch. 312, franchise tax), law-firm OBBBA summaries
(bonus depreciation, MACRS), EIA (ERCOT curtailment), SEIA (ITC/PTC).

Open questions flagged on the page: ERCOT-specific $/kW interconnection
benchmark, the site's actual school district and appraisal schedule, solar
MACRS class life after OBBBA, loss usability for the actual investor, and
energy-community status.
