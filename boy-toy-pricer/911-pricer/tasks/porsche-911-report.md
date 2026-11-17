# Porsche 911 report

Goal: `911s/report.html`, every 911, one tab per generation, with chip rows for phase, trim, body, gearbox, drive, and options. Self-contained in `911s/`; `../scanner` (the main tracker) is untouched and in use elsewhere.

- [x] Generation tabs (992, 991, 997, 996, 993, 964, G-body & 930, early) in `porsche_911.py`
- [x] AutoTempest year windows; Bring a Trailer generation pages, last 3 years
- [x] `classify()` puts each car in one generation and tags it; overlap years go to the right tab
- [x] Chip rows; chips filter the BaT overlay; tags feed the market model
- [x] Moved out of `../scanner` into `911s/` (2026-11-16); scanner restored to its pre-session state
- [x] Tests: `test_911` (6) pass; scanner tests (15) pass
- [x] First full scrape, 2026-11-16 22:17 to 2026-11-17 ~01:55 UTC, no warnings. Asking/BaT: 992 3,221/688, 991 1,332/973, 997 754/1,115, 996 464/1,199, 993 149/595, 964 87/349, G-body 255/1,265, early 73/312. Most of the time went to BaT mileage page lookups, now cached.
- [x] Browser check of the 992 tab: all cars tagged, chips filter the tables and BaT overlay, model R² 0.97
- [x] Browser check of all 8 tabs: no console errors, every car tagged, a market model on each tab (R² 0.97 for the 992 down to 0.37 for early cars, where condition dominates)
- [x] Trim names: 964 "Carrera" becomes Carrera 2, 993 "Carrera 2" becomes Carrera, untrimmed G-body becomes SC (1978-83) or Carrera (1984-89)
- [ ] Optional: schedule a weekly 911 refresh

Decisions:
- 991 GT3 Touring is undercounted (4): CarGurus titles them "GT3 Coupe" and nothing states Touring.
- No Autotrader (it needs a visible Chrome window; the user wants no popups). In 2024, Autotrader had 554 911s and AutoTempest 581.
- Tags are computed at load time (report build and the server's refresh payload), not saved in CSVs.
- Gearbox is unknown for about 60% of AutoTempest cars, because descriptions are cut off.
- `--no-msrp`: CarGurus answered 3 of 4 test page loads with "Verification Required", and the lookups would have added hours to each run.
- A GT3 whose description says "GT3 Touring" is tagged GT3 Touring.
- Server on port 8911, so it does not collide with the main tracker's 8765.

Lessons:
- **2026-11-16 — No popup windows.** The user wants scrapes to run in the background. Autotrader only works in a visible Chrome window, and disguising headless Chrome to get past its bot protection is off-limits. **Rule:** use only AutoTempest (headless) and Bring a Trailer (HTTP); ask before any Autotrader run.
- **2026-11-16 — Keep the 911 project separate.** The main tracker is in use elsewhere. **Rule:** all 911 code, data, and docs live in `911s/`; don't edit `../scanner` for 911 work.
