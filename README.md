[![Yes No GIF](https://media1.tenor.com/m/GQBgOkfrMZ8AAAAC/yes-no.gif)](https://tenor.com/view/yes-no-gif-23142380)

# Project index

Reports, data snapshots, visualizations, and small tools, grouped by topic.
Most projects are self-contained HTML pages that open directly in a browser.

## Infrastructure

| Project | What it is |
| --- | --- |
| [Data center deals](infrastructure/data-center-deals/) | Searchable database of 379 publicly announced data center deals, 2025 H1 through 2026 H2, with company profiles and source links |
| [Solar farm proforma](infrastructure/solar-farm-proforma/) | Interactive 30-year proforma for a hypothetical 1,000-acre solar farm near Wichita Falls, TX, plus a decision-first companion model |

## Markets

| Project | What it is |
| --- | --- |
| [Factor returns](markets/factor-returns/) | Daily 1-day, 5-day, and 1-month returns for nine factor ETFs versus SPY and QQQ |
| [S&P 500 correlation](markets/sp500-correlation/) | One-year pairwise correlation grid and pair-trade screen across S&P 500 constituents |
| [S&P 500 tracker](markets/sp500-tracker/) | Constituent changes from 2007–2026, removed-stock performance, and ticker comparisons |
| [Options — max pain](markets/options/) | SPY × QQQ max-pain report, QQQ universe scanner, and reproducible snapshot pipeline |
| [QQQ max-pain board](markets/options/qqq-max-pain.html) | Ranked max-pain board for all loadable QQQ holdings |
| [Options — live board](markets/options-live/) | Self-refreshing max-pain dashboard with click-through ticker details and charts |

## Real estate

| Project | What it is |
| --- | --- |
| [Colorado land](real-estate/colorado/) | 999 for-sale land listings, 10+ acres, captured October 2026 |
| [Texas Triangle land](real-estate/texas-triangle/) | 16,048 parcels, 5+ acres, inside the Dallas–San Antonio–Houston triangle and its 50-mile ring |
| [Utah land](real-estate/utah/) | 1,184 for-sale land listings, 10+ acres, captured October 2026 |
| [Combined land listings](land-listings-combined/) | 18,231 Colorado, Texas, and Utah listings merged into one common-schema table |

## Research and reports

| Project | What it is |
| --- | --- |
| [Epigenetics deep dive](epigenetics-deep-dive/) | Long-form, journal-style review of epigenetics, with 72 cited papers and linked sources |
| [Oklahoma storage](oklahoma-storage/) | Statewide self-storage market report: 865 directory records, ownership profiles, and pricing observations |
| [Landfill methane & RNG](landfill-methane-rng/) | How landfill gas is captured and converted to renewable natural gas, plus Oklahoma projects |
| [Rent-seeking report](rent-seeking-report/) | Economic rents, their history, and 50 ways to create rental income today |
| [Microgreens business data](other_biz/microgreens-business-data/) | Research dossier for a rack-based microgreens operation in the OKC area, with unit economics |

## Reading

| Project | What it is |
| --- | --- |
| [Beyond arXiv digest](reading/beyond-arxiv-digest/) | Top papers from six preprint servers beyond arXiv, one tab per server |
| [Books](reading/books/) | Reading list |

## Misc

| Project | What it is |
| --- | --- |
| [Spikeandred prompt guide](misc/spikeandred-prompt-guide/) | Field guide to a visual style: 12 photographic prompts, a consistency system, and a campaign playbook |
| [Dumpster GIF](misc/dumpster-gif/) | A cheerful looping dumpster fire, ready to embed |

## Repository notes

- `drops/` holds agent file drops; `scripts/` holds the privacy checker.
- Run `python3 scripts/check_privacy.py` before committing, per [AGENTS.md](AGENTS.md).
- Each project folder contains its source files and, where available, a README with build or refresh instructions.
