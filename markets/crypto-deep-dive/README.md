# Crypto Deep Dive

A standalone, single-file map of the crypto industry as of October 21, 2026. Open `index.html` in any browser. Styles, scripts, and the data snapshot are embedded, so the page runs without a server and makes no live API calls.

## What is in the report

- **Executive summary and market state:** market cap, volume, dominance, breadth, sentiment, and a one-year indexed chart for BTC, ETH, SOL, stablecoin supply, and DeFi TVL.
- **Market map and top 100:** interactive treemap, sortable/searchable asset table, FDV-to-market-cap and volume-to-market-cap ratios, and 7-day sparklines.
- **Sectors and narratives:** category-level market caps, leaders, and a narrative scoreboard.
- **Market structure:** spot DEX volume, chains, DeFi protocols, and exchange reserves.
- **Bitcoin, Ethereum, and Solana:** price performance, drawdowns, staking yields, and value-accrual comparisons.
- **Stablecoins:** supply by chain, issuer table with peg deviations, taxonomy, regulation, and a due-diligence checklist.
- **Yield farming:** filterable pool table, risk heuristic, compound-interest calculator, and impermanent-loss calculator.
- **Wallets and traders:** entity-labeling workflow, watchlist builder with explorer links, Hyperliquid leaderboard, and a trader scorecard.
- **Valuation, regulation, security, playbooks, glossary, and method notes:** frameworks for evaluating tokens, jurisdictions, hacks, and repeatable processes.

## Snapshot

The embedded snapshot was generated on October 21, 2026 at 18:19 UTC from public APIs. Headline values:

| Metric | Value |
| --- | --- |
| Total crypto market cap | $2.85T |
| 24h spot volume | $83.70B |
| BTC dominance | 59.59% |
| Stablecoin supply | $303.53B |
| DeFi TVL | $92.85B |
| Fear & greed (alternative.me) | 63 · Greed |

The page is a snapshot, not a live terminal. Market caps can be wrong, categories overlap, yields can be subsidized, and leaderboards are selected samples. Nothing here is investment advice.

## Data sources

| Source | Used for |
| --- | --- |
| [CoinGecko](https://www.coingecko.com/en/api) | Top 100 assets, prices, market caps, FDVs, 7-day sparklines, categories, global market data, one-year history |
| [DefiLlama](https://defillama.com/) | Stablecoin supply and chains, DeFi TVL, chains, protocols, DEX volume, yields, hacks, exchange reserves |
| [alternative.me](https://alternative.me/crypto/fear-and-greed-index/) | Fear & Greed Index |
| [Hyperliquid](https://hyperliquid.xyz/) | Public leaderboard, perpetual volumes, open interest, funding, mark prices |

## Files and rebuilding

| File | Purpose |
| --- | --- |
| `index.html` | Generated standalone report; the only file needed to view it |
| `template.html` | Editable page shell with placeholders, styles, and application code |
| `fetch_data.py` | Fetches and caches public API data, then writes `data/snapshot.json` |
| `build.py` | Replaces template tokens with formatted values and embeds the snapshot |
| `data/snapshot.json` | Generated data payload embedded in `index.html` |
| `data/raw/` | Local API cache; ignored by git |

From the repository root:

```sh
python3 markets/crypto-deep-dive/fetch_data.py --refresh
python3 markets/crypto-deep-dive/build.py
```

Omit `--refresh` to rebuild from the existing cache in `data/raw/`. CoinGecko requests are rate-limited, so a full refresh can take several minutes.

## Validation and smoke test

From the repository root:

```sh
python3 markets/crypto-deep-dive/validate.py
python3 markets/crypto-deep-dive/build.py
python3 markets/crypto-deep-dive/test_smoke.py
```

The smoke test loads the generated `index.html` in a real browser and checks the responsive layout, tables, charts, sorting, filtering, search, calculator, watchlist, Hyperliquid toggle, theme switch, and chart tooltip. Playwright and Chrome are optional test dependencies; the script falls back to bundled Chromium and prints install instructions if either is missing.

## Limitations

- Hyperliquid statistics come from the public leaderboard filtered to accounts with at least $100k of account value and $1M of 30-day volume. This is a selected sample skewed toward large, active, surviving accounts.
- Stablecoin supply on DefiLlama can differ from CoinGecko because wrapped, bridged, and yield-bearing versions are counted differently.
- Category market caps overlap and should not be summed.
- Hack losses are nominal USD at the time of the incident and are not exhaustive.
- Regulatory and tax summaries are high-level and time-sensitive, not legal or tax advice.
