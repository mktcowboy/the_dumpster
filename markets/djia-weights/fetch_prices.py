#!/usr/bin/env python3
"""Fetch monthly closes, split ratios, and validation-day closes from Yahoo Finance."""
import copy
import json
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

START = "2003-12-01"
TICKERS = [
    "MMM", "AA", "AXP", "AIG", "T", "BAC", "BA", "CAT", "CVX", "CSCO", "KO", "C",
    "DD", "DOW", "DIS", "XOM", "GE", "GS", "HD", "HON", "HPQ", "INTC", "IBM", "IP",
    "JNJ", "JPM", "MCD", "MO", "MRK", "MSFT", "NKE", "NVDA", "PFE", "PG", "RTX", "CRM",
    "SHW", "TRV", "UNH", "VZ", "V", "WMT", "AAPL", "AMZN", "AMGN", "GOOGL",
    "KFT", "DWDP", "WBA", "GM", "^DJI",
]

ANCHORS = ["2008-03-31", "2019-12-31", "2026-06-29", "2026-10-20"]
MANUAL_PATH = DATA / "manual_prices.json"


def frame(ticker, interval, **kwargs):
    for attempt in range(4):
        try:
            df = yf.download(
                ticker, start=START, interval=interval, auto_adjust=False,
                progress=False, threads=False, **kwargs
            )
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df
        except Exception as exc:  # noqa: BLE001
            print(f"  {ticker} {interval} attempt {attempt + 1}: {type(exc).__name__}")
        time.sleep(1.5 + attempt)
    return None


def main():
    manual = json.loads(MANUAL_PATH.read_text()) if MANUAL_PATH.exists() else {"prices": {}, "splits": {}, "sources": {}}
    prices, splits, missing = {}, {}, []
    for i, ticker in enumerate(TICKERS, 1):
        clean = ticker.lstrip("^")
        print(f"[{i}/{len(TICKERS)}] {ticker}")
        if clean in manual["prices"]:
            prices[clean] = copy.deepcopy(manual["prices"][clean])
            splits[clean] = copy.deepcopy(manual["splits"].get(clean, {}))
            print("  manual series; Yahoo skipped")
            continue
        monthly = frame(ticker, "1mo")
        if monthly is None:
            missing.append(ticker)
            print("  no monthly data")
            continue
        close = monthly["Close"].dropna()
        prices[clean] = {
            "monthly": [[str(idx.date()), round(float(v), 4)] for idx, v in close.items()],
        }

        daily = frame(ticker, "1d")
        if daily is not None:
            lookup = {str(idx.date()): round(float(v), 4) for idx, v in daily["Close"].dropna().items()}
            prices[clean]["daily"] = {d: lookup[d] for d in ANCHORS if d in lookup}
            if ticker != "^DJI":
                prices[clean]["last"] = {"date": max(lookup), "close": lookup[max(lookup)]}

        if ticker != "^DJI":
            ratios = {}
            for attempt in range(3):
                try:
                    series = yf.Ticker(ticker).splits
                    ratios = {
                        str(idx.date()): float(v)
                        for idx, v in series.items()
                        if float(v) > 0
                    }
                    break
                except Exception as exc:  # noqa: BLE001
                    print(f"  splits attempt {attempt + 1}: {type(exc).__name__}")
                    time.sleep(1.5)
            splits[clean] = {k: v for k, v in ratios.items() if k >= "2004-01-01"}
        time.sleep(0.6)

    for clean, series in manual["prices"].items():
        prices.setdefault(clean, copy.deepcopy(series))
        splits.setdefault(clean, copy.deepcopy(manual["splits"].get(clean, {})))
    out = {
        "retrieved": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "start": START,
        "anchors": ANCHORS,
        "prices": prices,
        "splits": splits,
        "manual": manual.get("sources", {}),
    }
    (DATA / "prices.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"\nwrote {DATA / 'prices.json'}")
    print("missing:", ", ".join(missing) if missing else "none")
    for t in TICKERS:
        k = t.lstrip("^")
        if k in prices:
            print(f"  {k:6s} monthly={len(prices[k]['monthly']):3d} splits={len(splits.get(k, {}))}")


if __name__ == "__main__":
    main()
