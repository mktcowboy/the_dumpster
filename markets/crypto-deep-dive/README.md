# Crypto Deep Dive

A standalone, single-file map of the crypto industry. Open [`index.html`](index.html) in any browser — styles, scripts, and the compressed data snapshot are embedded, so the page runs without a server and makes no live API calls from the client.

## What is in the report

- **Executive summary & market state:** total market cap, volume, BTC/ETH dominance, 24h & 30d breadth, Altcoin Season (30d), BTC Mayer Multiple (`Price / 200d SMA`), 30d realized volatility, Fear & Greed, multi-snapshot history deltas, a 30D/90D/1Y interactive chart (indexed or drawdown mode), and 90-day macro correlations (`QQQ`, `GLD`, `DXY`, `US10Y`).
- **Market map & top 100:** interactive top-60 treemap (toggle between sector colors and 24h/7d/30d return heatmap), sortable/searchable asset table with exclude-stablecoins toggle, CSV export, `FDV / MC`, `% unlocked` float bars, `Vol / MC`, and 7-day sparklines.
- **Sectors & narratives:** category-level market caps, leaders, narrative scoreboard, and non-stablecoin 7d momentum board.
- **Market structure:** protocol fees & revenue league table (aggregated by parent protocol), on-chain Perp DEX fee share, spot DEX volume, chain TVL, largest DeFi protocols, and CEX on-chain reserves.
- **Bitcoin, Ethereum, and Solana:** price performance, drawdowns, 30d realized vol, benchmark staking yields, and value-accrual comparisons.
- **Stablecoins:** payment vs. yield-bearing/synthetic/RWA dollar split, supply by chain, issuer table with peg deviations in bps, taxonomy, regulation, and a due-diligence checklist.
- **Yield farming:** sortable, chain-filterable pool table with risk-score breakdown tooltips, compound-interest calculator, and impermanent-loss calculator.
- **Wallets & traders:** entity-labeling workflow, browser-local watchlist builder with explorer/DeBank/Arkham links, Hyperliquid leaderboard, OI-weighted annualized funding & `OI / MCap` leverage heat, and a trader expectancy scorecard.
- **Valuation, regulation, security, playbooks, glossary, and method notes:** live cash-flow multiples (`FDV / Fees`, `FDV / Revenue`, take rate) matched to CoinGecko FDV, jurisdictions, DefiLlama trailing-12m hack ledger, and repeatable playbooks.

## Data sources

| Source | Used for |
| --- | --- |
| [CoinGecko](https://www.coingecko.com/en/api) | Top 100/250 assets, prices, market caps, FDVs, 7d sparklines, categories, global market data, 1y price history |
| [DefiLlama](https://defillama.com/) | Stablecoin supply & chains, DeFi TVL, chain & protocol TVL, spot DEX volume, protocol fees & revenue, perp DEX fee share, yield pools, hack database, exchange reserves |
| [alternative.me](https://alternative.me/crypto/fear-and-greed-index/) | Fear & Greed Index |
| [Hyperliquid](https://hyperliquid.xyz/) | Public leaderboard, perpetual volumes, open interest, hourly funding, mark prices |
| [Yahoo Finance](https://finance.yahoo.com/) | Daily closes for `QQQ`, `GLD`, `DX-Y.NYB`, and `^TNX` (optional; used for 90d macro correlations) |

## Files and rebuilding

| File | Purpose |
| --- | --- |
| `index.html` | Generated standalone report; the only file needed to view it |
| `template.html` | Editable page shell with dynamic tokens, styles, and application code |
| `fetch_data.py` | Concurrently fetches & caches public API data (stdlib Python only), computes analytics, and writes `data/snapshot.json` + `data/history/YYYY-MM-DD.json` |
| `validate.py` | Verifies snapshot schema, invariants, core assets, and payload size before building |
| `build.py` | Replaces template tokens with null-safe formatted values and embeds the snapshot |
| `test_smoke.py` | Optional Playwright browser smoke test across 390px, 768px, and 1440px viewports |
| `data/snapshot.json` | Generated compressed data payload embedded in `index.html` |
| `data/history/` | Daily metric snapshots used for delta cards and multi-snapshot trend history |
| `data/raw/` | Local API cache; excluded from version control via `.gitignore` |

No third-party Python packages are required to refresh and build. From the repository root:

```sh
python3 markets/crypto-deep-dive/fetch_data.py --refresh
python3 markets/crypto-deep-dive/validate.py
python3 markets/crypto-deep-dive/build.py
```

Omit `--refresh` to rebuild from the existing cache in `data/raw/`. Set `COINGECKO_DEMO_API_KEY` (optional) to speed up CoinGecko refreshes. This report is also wired into `.github/workflows/markets-daily-refresh.yml` for automated weekday refreshes.

## Smoke test (optional)

```sh
python3 markets/crypto-deep-dive/test_smoke.py
```

Playwright and Chrome/Chromium are optional test dependencies; the script prints install instructions if missing.

## Limitations

- Hyperliquid statistics come from the public leaderboard filtered to accounts with at least $100k of account value and $1M of 30-day volume — a selected sample skewed toward large, active survivors.
- Protocol P/F and P/S multiples annualize trailing 30-day fees and revenue (`× 12`) against CoinGecko FDV; treat them as run-rate snapshots, not forward guidance.
- Macro correlations align US market closes on date `D` (16:00 ET) with CoinGecko's `D+1 00:00 UTC` bar.
- Stablecoin supply on DefiLlama can differ from CoinGecko because wrapped, bridged, and yield-bearing versions are counted differently.
- Category market caps overlap and should not be summed.
- Hack losses are nominal USD at the time of the incident and are not exhaustive.
- Nothing here is investment, legal, or tax advice.
