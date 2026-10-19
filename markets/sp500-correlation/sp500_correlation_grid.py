"""
S&P 500 pairwise correlation grid.

Fetches the current S&P 500 constituent list from Wikipedia,
downloads 1 year of daily adjusted closes from Yahoo Finance's
chart API, computes the correlation matrix of daily returns,
and plots a sector-ordered heatmap.

Usage:
    python sp500_correlation_grid.py

Outputs (in the script's directory):
    sp500_correlation_grid.png   the heatmap
    sp500_correlation.csv        the full correlation matrix
    sp500_closes_1y.csv          raw adjusted closes (for reuse)

Requires: requests, pandas, numpy, matplotlib
"""

import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
OUT_DIR = "."
PERIOD = "1y"
WORKERS = 12


def get_constituents():
    """Return (tickers, {ticker: GICS sector}) from Wikipedia."""
    api = "https://en.wikipedia.org/w/api.php"
    r = requests.get(
        api,
        params={"action": "parse", "page": "List_of_S&P 500_companies",
                "format": "json", "prop": "text"},
        headers=UA, timeout=60,
    ).json()
    table = pd.read_html(io.StringIO(r["parse"]["text"]["*"]), header=0)[0]
    table = table[["Symbol", "GICS Sector"]].dropna()
    tickers = table["Symbol"].str.replace(".", "-", regex=False).tolist()
    sectors = dict(zip(tickers, table["GICS Sector"]))
    return tickers, sectors


def fetch_close(ticker, tries=3):
    """1y daily adjusted closes for one ticker via Yahoo's chart API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    for attempt in range(tries):
        try:
            r = requests.get(url, params={"interval": "1d", "range": PERIOD},
                             headers=UA, timeout=30)
            if r.status_code == 429:
                time.sleep(5)
                continue
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            px = (res["indicators"].get("adjclose", [{}])[0].get("adjclose")
                  or q["close"])
            idx = (pd.to_datetime(res["timestamp"], unit="s", utc=True)
                     .tz_convert("America/Chicago").tz_localize(None).normalize())
            s = pd.Series(px, index=idx, name=ticker).dropna()
            return ticker, s if len(s) > 200 else None
        except Exception:
            time.sleep(1 + attempt)
    return ticker, None


def download_closes(tickers):
    closes = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_close, t): t for t in tickers}
        for i, f in enumerate(as_completed(futs), 1):
            t, s = f.result()
            if s is not None:
                closes[t] = s
            if i % 100 == 0:
                print(f"{i}/{len(tickers)} done, {len(closes)} ok")
    return pd.DataFrame(closes).sort_index()


def plot_grid(corr, sectors, path):
    tickers = list(corr.columns)
    order = sorted(set(sectors.get(t, "?") for t in tickers))
    order_idx = sorted(tickers, key=lambda t: (order.index(sectors.get(t, "?")), t))
    corr = corr.loc[order_idx, order_idx]
    n = len(order_idx)

    fig, ax = plt.subplots(figsize=(20, 18))
    im = ax.imshow(corr.values, cmap="RdYlGn", vmin=-0.25, vmax=1.0, aspect="auto")
    ax.set_title(f"S&P 500 pairwise correlation — daily returns, 1 year ({n} stocks)",
                 fontsize=16, pad=14)
    ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(im, ax=ax, shrink=0.85).set_label("correlation", fontsize=12)

    # sector block boundaries + labels
    bounds, cur, start = [], sectors.get(order_idx[0], "?"), 0
    for i, t in enumerate(order_idx):
        if sectors.get(t, "?") != cur:
            bounds.append((cur, start, i)); cur = sectors.get(t, "?"); start = i
    bounds.append((cur, start, n))
    for s, a, b in bounds:
        ax.axhline(a - 0.5, color="black", lw=1.2)
        ax.axvline(a - 0.5, color="black", lw=1.2)
        ax.text(-8, (a + b) / 2, s, ha="right", va="center", fontsize=9)
        ax.text((a + b) / 2, n + 6, s, ha="center", va="top", fontsize=9, rotation=90)
    ax.axhline(n - 0.5, color="black", lw=1.2)
    ax.axvline(n - 0.5, color="black", lw=1.2)

    off = np.triu_indices(n, k=1)
    fig.text(0.5, 0.01,
             f"mean pairwise correlation: {corr.values[off].mean():.3f}  •  "
             "source: adjusted daily closes, trailing 1y",
             ha="center", fontsize=10, color="#555")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    t0 = time.time()
    tickers, sectors = get_constituents()
    print(f"{len(tickers)} constituents")
    closes = download_closes(tickers)
    closes.to_csv(f"{OUT_DIR}/sp500_closes_1y.csv")
    print("closes:", closes.shape)

    rets = closes.pct_change().dropna(how="all")
    rets = rets.loc[:, rets.notna().sum() > 200]
    corr = rets.corr()
    corr.to_csv(f"{OUT_DIR}/sp500_correlation.csv")
    print(f"tickers with data: {len(corr)}, mean pairwise corr: "
          f"{corr.values[np.triu_indices(len(corr), 1)].mean():.4f}")

    plot_grid(corr, sectors, f"{OUT_DIR}/sp500_correlation_grid.png")
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
