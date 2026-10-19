# factor-returns

Daily breakdown of US investing-factor ETF returns vs the SPY and QQQ benchmarks.

## What it does

- **`factor_daily.py`** — pulls adjusted closes from Yahoo Finance via `yfinance`
  and prints a chat-ready table: 1-day, 5-day, and ~1-month (21 trading day)
  total returns for nine factor ETFs, plus each factor's 1-day spread vs SPY
  and vs QQQ. Prints `DATA_ERROR` and exits 1 if Yahoo returns nothing; notes
  when the market was closed (no fresh session).
- **`factor_chart.py`** — sorted horizontal bar chart of the 1-day returns
  (green positive, red negative, gray benchmarks) written to `factor_chart.png`.
  Also prints a compact line of ETFdb ticker links. Override the output path
  with the `FACTOR_CHART_PATH` env var.

## Factors

| Ticker | Factor |
| ------ | ------ |
| VTV | Large-cap value |
| VUG | Growth |
| MTUM | Momentum |
| QUAL | Quality |
| USMV | Low volatility |
| IWM | Small cap |
| VBR | Small-cap value |
| VYM | High dividend yield |
| VIG | Dividend growth |

Benchmarks: SPY, QQQ. All returns are total returns from adjusted closes.

## Run it

```bash
pip install -r requirements.txt
python factor_daily.py
python factor_chart.py
```

## Schedule

Runs every trading day ~4:45pm CT via cron; the table and chart get delivered
to chat with one line of commentary.
