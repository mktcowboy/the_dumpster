# Options — max pain

A SPY × QQQ max-pain report and a reproducible data pipeline behind it.

| File | Purpose |
| --- | --- |
| `index.html` | Standalone report for the Oct 23, 2026 expiry, based on the Oct 19 close |
| `max_pain.py` | Fetches a live chain from Cboe, computes the metrics, and writes a JSON snapshot |
| `data/` | Dated snapshots produced by `max_pain.py` |
| `requirements.txt` | `requests` (the only dependency) |

The HTML report is a hand-authored narrative layer. The script produces the
underlying numbers; it does not rewrite the page.

## Generate a snapshot

From the repository root:

```sh
python3 markets/options/max_pain.py --tickers SPY QQQ --expiry 2026-10-23
```

The script prints a summary and writes
`markets/options/data/2026-10-23-spy-qqq-2026-10-20.json` (expiry, tickers,
quote date). Use `--out` to put it somewhere else.

```
Max-pain snapshot — as of 2026-10-20T13:49:37+00:00 · expiry 2026-10-23

Ticker      Spot   OI max  Vol max    Blend            1σ range   ATM IV  P/C OI     GEX/1%     Flip       Pin
SPY       765.71   770.00   767.00   770.00       755.06–776.36    15.3%    1.99    $-2.77B   774.64      High
QQQ       713.84   726.00   720.00   726.00       696.99–730.69    26.0%    1.57    $-1.79B   730.68  Moderate
```

Requires Python 3.9+ and `requests`:

```sh
python3 -m pip install -r markets/options/requirements.txt
```

## What the snapshot contains

Each snapshot has top-level metadata (`as_of`, `expiry`, `dte`, `settlement`,
`source`, `method`) and one object per ticker under `snapshots`:

- `spot`, `prev_close`, `change_pct`
- `chain`: every listed strike in the expiry, with call and put `oi`, `volume`,
  `iv`, `delta`, `gamma`, `bid`, `ask`, `mid`, and `last`. IVs are decimal
  fractions (`0.1534` is 15.34%)
- `metrics.max_pain`: OI, volume, and blended max pain, the 1% shelf, and a
  method-spread confidence score
- `metrics.payout`: modeled payout at spot, the minimum payout, and the pain
  slope per $1
- `metrics.walls`: largest call-OI and put-OI strikes
- `metrics.ratios`: put/call open interest and volume
- `metrics.volatility`: ATM strike, ATM IV, ATM straddle, 1σ move and range,
  and the 25-delta risk reversal
- `metrics.gamma`: modeled net GEX per 1% move and the gamma flip
- `metrics.top_strikes`: top 12 strikes by combined OI, with tags
- `metrics.totals`: call/put OI and volume, and the strike count

## Definitions

**Max pain.** For each listed strike, compute the intrinsic payout to option
holders if the underlying settles there:

```
calls: OI × max(0, settlement − strike) × 100
puts:  OI × max(0, strike − settlement) × 100
```

The strike with the smallest total is the max-pain level. The volume variant
uses session volume; the blend uses `OI + 0.5 × volume` on each side. The
script brute-forces every listed strike, so nothing is interpolated.

**Pain shelf.** Every strike within 1% of the minimum payout. It shows how
flat the bottom of the curve is; a wider shelf is a weaker pin.

**Pin confidence.** A heuristic, not a probability: High when the OI, volume,
and blend levels are within 0.5% of spot, Moderate within 1%, otherwise Low.

**1σ range.** `spot × ATM IV × √(DTE / 365)`, where ATM IV is the mean of the
nearest-strike call and put IVs.

**25-delta risk reversal.** 25-delta put IV minus 25-delta call IV, in
volatility points. Positive means puts are richer than calls.

**Net GEX.** Black-Scholes gamma at each hypothetical spot × OI × 100 × S² ×
0.01, with calls positive and puts negative. The gamma flip is the nearest
zero crossing within ±15% of spot.

## Data source and caveats

- The script uses Cboe's delayed-quote endpoint for the full chain, including
  OI, volume, IV, and Greeks. Yahoo Finance via yfinance is the source named in
  the hand-authored report; the endpoint was unreliable when this pipeline was
  built.
- Open interest is the exchange's latest published value. Intraday volume is
  partial, so a snapshot taken during the session will differ from a
  close-of-day snapshot.
- The sign convention assumes dealers are short calls and long puts. Actual
  positioning is unobservable.
- Max pain is descriptive, not a price target. PM settlement, closing-auction
  flow, and large unwinds can move the level.
