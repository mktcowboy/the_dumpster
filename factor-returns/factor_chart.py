#!/usr/bin/env python3
"""Companion to factor_daily.py: sorted bar chart of 1D factor returns.

Uses the same tickers and methodology (yfinance adjusted closes) as
factor_daily.py. Writes a PNG chart and prints a compact line of
ETFdb ticker links.

Output:
  - factor_chart.png in the chart directory (overwritten each run)
  - stdout: CHART_PATH line + ETFdb ticker/url pairs, one compact block

Set FACTOR_CHART_PATH to override the output location.
"""
import os
import sys
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yfinance as yf

FACTORS = {
    "VTV": "Value",
    "VUG": "Growth",
    "MTUM": "Momentum",
    "QUAL": "Quality",
    "USMV": "Low Vol",
    "IWM": "Small Cap",
    "VBR": "SC Value",
    "VYM": "Div Yield",
    "VIG": "Div Growth",
}
BENCHMARKS = ["SPY", "QQQ"]
TICKERS = BENCHMARKS + list(FACTORS)

CHART_PATH = os.environ.get("FACTOR_CHART_PATH", "factor_chart.png")
ETFDB = "https://etfdb.com/etf/{t}/"


def main():
    df = yf.download(TICKERS, period="3mo", interval="1d",
                     auto_adjust=True, progress=False, threads=True)
    if df is None or df.empty:
        print("DATA_ERROR: no data returned from Yahoo Finance", file=sys.stderr)
        sys.exit(1)
    closes = df["Close"].dropna(how="all").dropna(axis=1, how="all")
    if closes.empty or len(closes) < 2:
        print("DATA_ERROR: insufficient data", file=sys.stderr)
        sys.exit(1)

    last = closes.index[-1].date()

    def ret(t, n):
        s = closes[t].dropna()
        if len(s) <= n:
            return None
        return (s.iloc[-1] / s.iloc[-1 - n] - 1) * 100

    day = {}
    for t in TICKERS:
        r = ret(t, 1)
        if r is not None:
            day[t] = r
    if not day:
        print("DATA_ERROR: no 1D returns", file=sys.stderr)
        sys.exit(1)

    # Sorted descending: best performer on top.
    ordered = sorted(day.items(), key=lambda kv: kv[1], reverse=True)
    tickers = [t for t, _ in ordered]
    values = [v for _, v in ordered]
    labels = [f"{t} ({FACTORS.get(t, 'bench')})" for t in tickers]
    colors = []
    for t in tickers:
        if t in BENCHMARKS:
            colors.append("#6b7280")          # gray for benchmarks
        elif day[t] >= 0:
            colors.append("#16a34a")          # green positive
        else:
            colors.append("#dc2626")          # red negative

    fig, ax = plt.subplots(figsize=(8, 5.2))
    y = range(len(tickers))
    bars = ax.barh(y, values, color=colors, edgecolor="none", height=0.62)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.axvline(0, color="#111827", linewidth=0.8)
    ax.set_xlabel("1-day total return (%)", fontsize=10)
    ax.set_title(f"Factor 1D returns — session of {last:%a %b %d, %Y}", fontsize=11, pad=10)
    for bar, v in zip(bars, values):
        ax.text(v + (0.02 if v >= 0 else -0.02), bar.get_y() + bar.get_height() / 2,
                f"{v:+.2f}%", va="center",
                ha="left" if v >= 0 else "right", fontsize=8.5, color="#111827")
    pad = max(abs(min(values)), abs(max(values))) * 0.28 + 0.05
    ax.set_xlim(min(values) - pad, max(values) + pad)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)

    print(f"CHART_PATH: {CHART_PATH}")
    print("ETFdb: " + "  ".join(f"{t} {ETFDB.format(t=t)}" for t in TICKERS))


if __name__ == "__main__":
    main()
