[![Yes No GIF](https://media1.tenor.com/m/GQBgOkfrMZ8AAAAC/yes-no.gif)](https://tenor.com/view/yes-no-gif-23142380)

*Last updated: November 5, 2026*

# Project index

Reports, data snapshots, visualizations, and small tools, grouped by topic.
The [HTML catalog](index.html) links to 20 projects and 31 report pages.
Most reports open directly in a browser; the live options board requires its local server.

## Infrastructure

| Project | What it is |
| --- | --- |
| [Data center deals](biz-other/infrastructure/data-center-deals/data-center-deals-all.html) | Searchable database of 379 publicly announced data center deals, 2025 H1 through 2026 H2, with company profiles and source links |
| [Solar farm proforma](biz-other/infrastructure/solar-farm-proforma/solar-farm-proforma.html) | Interactive 30-year proforma for a hypothetical 1,000-acre solar farm near Wichita Falls, TX, plus a decision-first companion model |

## Markets

| Project | What it is |
| --- | --- |
| [Crypto deep dive](markets/crypto-deep-dive/data/raw/) | Raw CoinGecko, DefiLlama, Fear and Greed, and Hyperliquid caches covering prices, categories, stablecoins, TVL, pools, and protocols |
| [Options — max pain](markets/options/) | SPY × QQQ max-pain report, QQQ universe scanner, and reproducible snapshot pipeline |
| [QQQ max-pain board](markets/options/qqq-max-pain.html) | Ranked max-pain board for all loadable QQQ holdings |
| [Options — live board](markets/options-live/) | Max-pain dashboard with click-through ticker details and charts; requires the [local server](markets/options-live/README.md) |
| [Size & style ETFs](markets/size-style/styles.html) | Nine iShares S&P style-box ETFs charted together, with a 6M, 1Y, 3Y, and 5Y total-return table. Yahoo Finance through November 4, 2026 |
| [SPDR sector ETFs](markets/size-style/sectors.html) | Companion chart of the 11 Select Sector SPDRs, daily and dividend-adjusted, with period returns. Yahoo Finance through November 4, 2026 |

## Real estate

| Project | What it is |
| --- | --- |
| [Texas Triangle land](real-estate/texas-triangle/texas-triangle-land.html) | 16,048 parcels, 5+ acres, inside the Dallas–San Antonio–Houston triangle and its 50-mile ring |

## Research and reports

| Project | What it is |
| --- | --- |
| [Epigenetics deep dive](research/religion/epigenetics-deep-dive/epigenetics-deep-dive.html) | Long-form, journal-style review of epigenetics, with 72 cited papers and linked sources |
| [Tanakh atlas](research/religion/tanakh-atlas/) | Single-file interactive atlas of the Tanakh and the later Jewish library, with the full JPS 1917 text, themes, people, places, and essays |
| [Rent-seeking report](biz-other/rent-seeking-report/rent-seeking-report.html) | Economic rents, their history, and 50 ways to create rental income today |
| [Arby's deal deep dive](biz-other/arbys-deal-deep-dive/arby-s-deal-deep-dive.html) | Sourced account of the Arby's acquisition and turnaround, including Roark's 2011 purchase |
| [James Beard award graphs](James-Beard/) | Unofficial Obsidian-style graphs of public James Beard Foundation award results: restaurants and chefs, 1991–2025, and books, broadcast, and journalism, 1991–2024 |

## Reading

| Project | What it is |
| --- | --- |
| [Beyond arXiv digest](research/reading/beyond-arxiv-digest/beyond-arxiv-top-papers.html) | Top papers from six preprint servers beyond arXiv, one tab per server |

## Boy toys

| Project | What it is |
| --- | --- |
| [Car search tracker](boy-toy-pricer/Car-pricer.html) | For-sale AutoTempest listings and Bring a Trailer sold comps for cars, trucks, and SUVs, from the Audi RS6 and G63 to the SF90, Huracan STO, and RUF Porsches |
| [Aircraft for-sale tracker](boy-toy-pricer/airplane-pricer/output/report.html) | Cirrus SR22, Vision Jet, CubCrafters, and Piper PA-28-180/181 listings in one HTML report |
| [Watch for-sale tracker](boy-toy-pricer/watch-pricer/output/report.html) | Patek Philippe Nautilus 5711 and blue or green Aquanaut listings in one HTML report |

## Misc

| Project | What it is |
| --- | --- |
| [Spikeandred prompt guide](research/spikeandred-prompt-guide/) | Field guide to a visual style: 12 photographic prompts, a consistency system, and a campaign playbook |
| [Dumpster GIF](dumpster.gif) | A cheerful looping dumpster fire, ready to embed |

## Repository notes

- `scripts/` holds the privacy checker and local setup script.
- Run `sh scripts/setup_privacy.sh` in each fresh checkout to install privacy hooks and the anonymous repository commit identity.
- Run `python3 scripts/check_privacy.py` before committing, per [CONTRIBUTING.md](CONTRIBUTING.md).
- [`index.html`](index.html) is the GitHub Pages catalog of the HTML projects. Card thumbnails live in [`site-assets/thumbs/`](site-assets/thumbs/).
- Each project folder contains its source files and, where available, a README with build or refresh instructions.
