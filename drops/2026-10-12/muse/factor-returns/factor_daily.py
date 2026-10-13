#!/usr/bin/env python3
"""Daily investing factor returns vs SPY and QQQ.

Fetches daily adjusted closes via yfinance and prints a chat-ready table:
1-day, 5-day, and 1-month total returns for standard US factor ETFs,
plus each factor's spread vs SPY and vs QQQ.
"""
import sys
from datetime import date
import yfinance as yf
import pandas as pd

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

def main():
    df = yf.download(TICKERS, period="3mo", interval="1d",
                     auto_adjust=True, progress=False, threads=True)
    if df is None or df.empty:
        print("DATA_ERROR: no data returned from Yahoo Finance")
        sys.exit(1)
    closes = df["Close"].dropna(how="all")
    closes = closes.dropna(axis=1, how="all")
    if closes.empty or len(closes) < 2:
        print("DATA_ERROR: insufficient data")
        sys.exit(1)

    last = closes.index[-1].date()
    today = date.today()
    # If the latest bar isn't today's session, the market was closed today.
    fresh = (last == today)

    def ret(t, n):
        s = closes[t].dropna()
        if len(s) <= n:
            return None
        return (s.iloc[-1] / s.iloc[-1 - n] - 1) * 100

    rows = {}
    for t in TICKERS:
        rows[t] = {"1D": ret(t, 1), "5D": ret(t, 5), "1M": ret(t, 21)}

    spy_1d, qqq_1d = rows["SPY"]["1D"], rows["QQQ"]["1D"]
    spy_5d, qqq_5d = rows["SPY"]["5D"], rows["QQQ"]["5D"]

    lines = []
    lines.append(f"FACTOR BREAKDOWN — session of {last:%a %b %d, %Y}")
    if not fresh:
        lines.append("(no new data today — market closed; showing last session)")
    lines.append("")
    lines.append(f"{'Ticker':<6}{'Factor':<10}{'1D %':>7}{'5D %':>7}{'1M %':>7}{'vsSPY 1D':>9}{'vsQQQ 1D':>9}")
    for b in BENCHMARKS:
        r = rows[b]
        lines.append(f"{b:<6}{'bench':<10}{r['1D']:>6.2f}%{r['5D']:>6.2f}%{r['1M']:>6.2f}%")
    lines.append("-" * 62)
    for t, name in FACTORS.items():
        r = rows[t]
        vs_spy = (r["1D"] - spy_1d) if r["1D"] is not None and spy_1d is not None else None
        vs_qqq = (r["1D"] - qqq_1d) if r["1D"] is not None and qqq_1d is not None else None
        lines.append(
            f"{t:<6}{name:<10}{r['1D']:>6.2f}%{r['5D']:>6.2f}%{r['1M']:>6.2f}%"
            f"{vs_spy:>+8.2f}pp{vs_qqq:>+8.2f}pp"
        )
    lines.append("")
    # Winners / losers on the day
    day = {t: rows[t]["1D"] for t in FACTORS if rows[t]["1D"] is not None}
    if day:
        best, worst = max(day, key=day.get), min(day, key=day.get)
        lines.append(f"Best factor: {best} ({FACTORS[best]}) {day[best]:+.2f}% | "
                     f"Worst: {worst} ({FACTORS[worst]}) {day[worst]:+.2f}%")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
