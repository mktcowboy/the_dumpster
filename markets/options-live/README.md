# Options — live max-pain board

A live copy of the `markets/options/` scanner. The original folder remains a
static, reproducible snapshot workflow. This copy serves a browser dashboard
that refreshes itself, and every row opens a detail panel.

## Run it

```sh
python3 -m pip install -r markets/options-live/requirements.txt
python3 markets/options-live/server.py
```

Open <http://127.0.0.1:8000>.

The first universe refresh takes about 75 seconds. The bundled
`data/latest.json` seed is served immediately while that refresh runs. With the
default settings the refresh starts when a browser opens the board during market
hours; outside those hours the seed is served as-is.

```sh
# Refresh every 5 minutes on a different port
python3 markets/options-live/server.py --interval 300 --port 8080

# Limit the board to a few tickers (fast startup)
python3 markets/options-live/server.py --tickers AAPL MSFT NVDA

# Bind beyond localhost (only on a trusted network)
python3 markets/options-live/server.py --host 0.0.0.0
```

| Flag | Default | Purpose |
| --- | --- | --- |
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8000` | HTTP port |
| `--interval` | `900` | Seconds between universe refreshes while watched (minimum 60) |
| `--expiry` | next Friday | Requested expiry |
| `--workers` | `4` | Parallel Cboe requests |
| `--timeout` | `45` | Per-request timeout in seconds |
| `--tickers` | QQQ universe | Limit the board to specific tickers |
| `--quiet` | off | Suppress request logs |

## How it refreshes

The server runs one background refresh loop, using a small worker pool for Cboe
requests. It fetches every current QQQ holding
from the [Wikipedia Nasdaq-100 list](https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies),
loads Cboe's delayed option chains, computes the metrics, and replaces the
in-memory snapshot plus `data/latest.json`.

- **Market hours only:** Cboe refreshes run on weekdays from 09:00 to 16:15 ET,
  including the pre-open and post-close windows. NYSE holidays are skipped, and
  early-close days stop at 13:15 ET. The calendar in `server.py` covers
  2026-2027; update `MARKET_HOLIDAYS` and `MARKET_EARLY_CLOSES` annually.
- **Idle pause:** the server stops refreshing when no browser has requested
  `/api/snapshot` for 15 minutes. Opening the board again during market hours
  triggers a refresh immediately. The page still polls every 10 seconds, but
  that only hits the local server.
- **Auto refresh:** the page polls `/api/snapshot` every 10 seconds and
  re-renders when the server has a newer snapshot. The server refresh cadence is
  set by `--interval` (15 minutes by default).
- **Manual refresh:** the **Refresh now** button triggers a background refresh
  at any time. If one is already running, the request is ignored.
- **Daily holdings cache:** the Nasdaq-100 list is written to
  `data/qqq_members.json` once per day and reused for the rest of the day. If
  Wikipedia is unavailable, the last cached list is used when it has at least
  50 tickers.
- **Carry-forward:** if a ticker fails during a refresh (usually a 429), the
  previous row is kept and marked with an amber dot instead of disappearing.
- **Connection reuse:** each worker thread keeps one `requests.Session`, so a
  refresh reuses Cboe connections instead of opening a new one per ticker.
- **Ad-hoc tickers:** type any symbol into the filter box and press Enter. The
  server fetches it on demand, adds it to the board, and keeps it in future
  refreshes.

The main table includes a **Vol/OI** column: today's option volume divided by
current open interest. It is a quick read on how much of the existing
positioning is trading today. Treat it as a screen, not a signal.

Cboe requests are throttled and retried. The dashboard is read-only; it places
no trades and needs no API key.

## Click a row

Each row opens a detail drawer with:

- Max pain by OI, volume, and blend, plus the 1% shelf and distance from spot
- Modeled payout at spot, the minimum, and the slope per $1
- Call and put walls
- P/C open interest and volume
- ATM strike, IV, straddle, 1σ range, and the 25-delta risk reversal
- Net GEX per 1% and the gamma flip
- Total open interest, volume, and strike count
- Call/put volume, total volume, and volume-to-OI ratios
- The top 12 strikes by combined OI, with tags

The **Chart & chain** tab fetches the primary chain and the open-interest
series for every listed expiry on demand, then adds:

- A **price and open interest chart**: daily OHLC candles (1M, 3M, or 6M) with
  current call and put open interest by strike on the same price axis. Expiry
  chips overlay up to three expirations at once (the primary expiry starts
  selected); call bars extend right, put bars left, and each expiry keeps its
  color across ranges. Spot and the primary expiry's max pain are marked.
  History comes from Yahoo Finance with a Nasdaq fallback.
- A modeled payout curve by settlement. The payout and full chain table always
  use the primary expiry, even when additional OI overlays are selected.
- The top 12 strikes by today's volume, including each strike's Vol/OI.
- The complete strike-by-strike chain table. Max pain and the two OI walls are
  highlighted.

OHLC history is cached for 15 minutes per ticker. If both providers are
unavailable, the chart falls back to the OI profile around spot and shows the
error above it.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Dashboard |
| `GET /api/snapshot` | Cached universe snapshot, refresh status, and market-open flag |
| `GET /api/ticker?symbol=AAPL` | Load or return one ticker |
| `GET /api/chain?symbol=AAPL` | Primary chain, all-expiry OI series (`expiry_series`), metrics, payout inputs, and 6 months of daily OHLC |
| `POST /api/refresh` | Start a background refresh |

## Files

| File | Purpose |
| --- | --- |
| `server.py` | HTTP server, background refresher, and detail API |
| `index.html` | Dashboard, table, drawer, price/OI chart, and payoff chart |
| `max_pain.py` | Copy of the static scanner used by the server |
| `data/latest.json` | Seed and last successful snapshot |
| `data/qqq_members.json` | Daily cache of the Nasdaq-100 holdings list |
| `requirements.txt` | `requests` |

## Caveats

- Quotes are vendor-delayed. Open interest is the exchange's latest published
  value; intraday volume is partial.
- Daily OHLC comes from Yahoo Finance's public chart endpoint, with Nasdaq's
  historical endpoint as a fallback. It is cached for 15 minutes and only
  requested when a detail panel opens; the rest of the dashboard does not depend
  on it.
- The price chart uses the underlying's daily OHLC. OI bars are the current
  snapshot by strike for the selected expiries; the delayed feed does not
  provide historical OI. The `/api/chain` response builds OI series for every
  listed expiry from a single Cboe payload, so the payload is larger than the
  primary chain alone.
- A full refresh makes 101 Cboe requests. The default 15-minute interval,
  market-hours/idle gating, and 0.65-second throttle are deliberate; lowering
  them will hit rate limits.
- The requested weekly is not listed for every holding. Those rows use the next
  listed monthly and show a drift marker such as `+28d`.
- Ad-hoc tickers are stored in `data/latest.json` and reloaded on restart.
  Delete that file to start from an empty board.
