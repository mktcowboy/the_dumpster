# S&P 500 Correlation Grid + Pair Trade Finder

Built Sep 27, 2026. Pairwise correlation of daily returns across S&P 500
constituents, trailing 1 year (Sep 2025 – Sep 2026), plus a pair-trade screen.

## What's here

| File | Description |
|---|---|
| `sp500_correlation_grid.py` | Standalone script: fetches constituents from Wikipedia, downloads 1y of adjusted closes from Yahoo Finance, computes the correlation matrix, plots the heatmap. `python sp500_correlation_grid.py` — also regenerates the PNG and CSVs below in ~1 minute. |
| `pair_trade_finder.ipynb` | Jupyter notebook version of the pair-trade workflow (runs in Cursor). Screens pairs with correlation ≥ 0.80, z-scores the log-price spread, ranks candidates, charts the top 3. |
| `pair_candidates.csv` | 127 pairs with corr ≥ 0.80, spread z-score, 1-month leg returns, mean-reversion half-life, trade direction. |

Generated locally by the script (not stored here — rerun to refresh): `sp500_correlation_grid.png`
(the heatmap), `sp500_correlation.csv` (full 501×501 matrix), `sp500_closes_1y.csv`
(raw adjusted closes).

## Headline findings (from the Sep 27, 2026 run)

- Mean pairwise correlation: **0.12** — the index moves on a handful of names, not a common tide.
- Tightest sectors: Utilities (0.50) and Energy (0.46) trade as blocs; Tech (0.19) and Communication Services (0.16) are the loosest.
- Energy is the true diversifier: average correlation to the rest of the market ≈ 0.00.
- Tightest genuine pairs: UNP/NSC rails (0.94), CPT/MAA apartments (0.92), DHI/PHM homebuilders (0.91). Dual share classes (GOOGL/GOOG etc.) excluded from the screen.
- Strongest pair-trade signal: ADP/PAYX, z +4.03 (PAYX −19.9% vs ADP −6.8% over 1m, half-life ~33d).
- No real inverse correlation exists inside the index: the most negative sector pair is −0.07, and the single most market-negative stock (CF Industries) is only −0.18 vs the market.

## Caveats

- Constituent list and prices are a snapshot — rerun the script/notebook for fresh data.
- A wide z-score is only a trade if the relationship is intact; check for earnings, guidance, or M&A on either leg before sizing.
