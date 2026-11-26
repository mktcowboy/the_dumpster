# Size and style

Self-contained ETF price-history pages. Open either file in a browser; no server is required. Prices are Yahoo Finance daily bars, auto-adjusted for splits and dividends, through November 25, 2026.

| File | Purpose |
| --- | --- |
| `styles.html` | Nine iShares S&P style-box ETFs (large, mid, and small; value, core, and growth), charted together, with a style-box heatmap and a 6M, 1Y, 3Y, and 5Y total-return table. Small value and large growth are highlighted, the comparison in Meb Faber's post. |
| `sectors.html` | Companion chart for the 11 Select Sector SPDRs, with a period-return table. |
| `refresh.py` | Fetches updated Yahoo Finance daily bars via `yfinance` and updates `styles.html`, `sectors.html`, and this file. |

## Keeping data updated

A scheduled GitHub Actions workflow (`.github/workflows/markets-daily-refresh.yml`) runs `refresh.py` on weekdays at 5:10 PM Eastern after US market close and commits any new bars back to the repository so GitHub Pages stays current. It can also be triggered manually via **Actions -> Refresh daily market reports -> Run workflow**, or run locally:

```bash
python3 -m pip install -r markets/size-style/requirements.txt
python3 markets/size-style/refresh.py
```
