#!/usr/bin/env python3
"""Refresh Yahoo Finance price history embedded in styles.html and sectors.html."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
import re
import sys
import time
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

HERE = Path(__file__).resolve().parent
STYLES_HTML = HERE / "styles.html"
SECTORS_HTML = HERE / "sectors.html"
README_MD = HERE / "README.md"

STYLE_TICKERS = ["IVE", "IVV", "IVW", "IJJ", "IJH", "IJK", "IJS", "IJR", "IJT"]
SECTOR_TICKERS = [
    "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE", "XLC",
]

# Rolling calendar windows with margin for 2Y OHLC charts and 5Y total-return tables.
SHORT_WINDOW_DAYS = 790   # ~26 months (> 2Y button)
LONG_WINDOW_DAYS = 2010   # ~5.5 years (> 5Y table)

MIN_SHORT_BARS = 450
MIN_LONG_BARS = 1200


def _extract_ticker_frame(raw: pd.DataFrame, ticker: str, single: bool) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    if single:
        df = raw.copy()
        if isinstance(df.columns, pd.MultiIndex):
            if ticker in df.columns.get_level_values(0):
                df = df[ticker]
            elif ticker in df.columns.get_level_values(-1):
                df = df.xs(ticker, axis=1, level=-1)
    else:
        if not isinstance(raw.columns, pd.MultiIndex):
            return pd.DataFrame()
        if ticker in raw.columns.get_level_values(0):
            df = raw[ticker].copy()
        elif ticker in raw.columns.get_level_values(-1):
            df = raw.xs(ticker, axis=1, level=-1).copy()
        else:
            return pd.DataFrame()
    return df


def _clean_frame(df: pd.DataFrame, today: dt.date) -> pd.DataFrame:
    required = ["Open", "High", "Low", "Close"]
    if df.empty or any(col not in df.columns for col in required):
        return pd.DataFrame()
    out = df[required].copy()
    for col in required:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=required)
    out = out[(out[required] > 0).all(axis=1)]
    if out.empty:
        return pd.DataFrame()
    idx = pd.to_datetime(out.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    out.index = idx.strftime("%Y-%m-%d")
    today_str = today.isoformat()
    out = out[out.index <= today_str]
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def download_tickers(
    tickers: list[str],
    start: dt.date,
    today: dt.date,
    attempts: int = 3,
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    remaining = list(tickers)

    for attempt in range(1, attempts + 1):
        if not remaining:
            break
        try:
            raw = yf.download(
                remaining if len(remaining) > 1 else remaining[0],
                start=start.isoformat(),
                interval="1d",
                auto_adjust=True,
                actions=False,
                progress=False,
                group_by="ticker",
                threads=True,
            )
            single = len(remaining) == 1
            for ticker in list(remaining):
                cleaned = _clean_frame(_extract_ticker_frame(raw, ticker, single), today)
                if not cleaned.empty:
                    frames[ticker] = cleaned
                    remaining.remove(ticker)
        except Exception as exc:
            print(f"Batch download attempt {attempt} failed: {exc}", file=sys.stderr)

        if remaining and attempt < attempts:
            delay = 2 ** attempt
            print(
                f"Retrying {len(remaining)} ticker(s) ({', '.join(remaining)}) in {delay}s...",
                file=sys.stderr,
            )
            time.sleep(delay)

    # Final single-ticker fallback for any stubborn symbol.
    for ticker in list(remaining):
        try:
            hist = yf.Ticker(ticker).history(
                start=start.isoformat(), interval="1d", auto_adjust=True, actions=False
            )
            cleaned = _clean_frame(hist, today)
            if not cleaned.empty:
                frames[ticker] = cleaned
                remaining.remove(ticker)
        except Exception as exc:
            print(f"Fallback fetch failed for {ticker}: {exc}", file=sys.stderr)

    if remaining:
        raise RuntimeError(f"Failed to fetch Yahoo Finance data for: {', '.join(remaining)}")
    return frames


def build_ohlc_series(
    frames: dict[str, pd.DataFrame],
    tickers: list[str],
    cutoff: str,
    min_bars: int,
) -> tuple[dict[str, list[list]], str]:
    common: set[str] | None = None
    for ticker in tickers:
        dates = {d for d in frames[ticker].index if d >= cutoff}
        common = dates if common is None else (common & dates)
    assert common is not None
    ordered_dates = sorted(common)
    if len(ordered_dates) < min_bars:
        raise RuntimeError(
            f"Too few common OHLC bars ({len(ordered_dates)} < {min_bars}) for {tickers}"
        )

    data: dict[str, list[list]] = {}
    for ticker in tickers:
        sub = frames[ticker].loc[ordered_dates]
        rows = []
        for date_str, row in sub.iterrows():
            vals = [round(float(row[c]), 2) for c in ("Open", "High", "Low", "Close")]
            if not all(math.isfinite(v) and v > 0 for v in vals):
                raise RuntimeError(f"Invalid OHLC value for {ticker} on {date_str}: {vals}")
            rows.append([date_str, *vals])
        data[ticker] = rows
    return data, ordered_dates[-1]


def build_close_series(
    frames: dict[str, pd.DataFrame],
    tickers: list[str],
    min_bars: int,
) -> tuple[dict[str, list[list]], str]:
    common: set[str] | None = None
    for ticker in tickers:
        dates = set(frames[ticker].index)
        common = dates if common is None else (common & dates)
    assert common is not None
    ordered_dates = sorted(common)
    if len(ordered_dates) < min_bars:
        raise RuntimeError(
            f"Too few common long-term bars ({len(ordered_dates)} < {min_bars}) for {tickers}"
        )

    data: dict[str, list[list]] = {}
    for ticker in tickers:
        sub = frames[ticker].loc[ordered_dates]
        rows = []
        for date_str, close in sub["Close"].items():
            val = round(float(close), 4)
            if not (math.isfinite(val) and val > 0):
                raise RuntimeError(f"Invalid close value for {ticker} on {date_str}: {val}")
            rows.append([date_str, val])
        data[ticker] = rows
    return data, ordered_dates[-1]


def existing_last_date(html_text: str, var_name: str = "D") -> str | None:
    match = re.search(rf"^const {var_name}=(\{{.*?\}});", html_text, flags=re.MULTILINE)
    if not match:
        return None
    payload = json.loads(match.group(1))
    first_series = next(iter(payload.values()), [])
    return first_series[-1][0] if first_series else None


def replace_const_json(html_text: str, var_name: str, data: dict) -> str:
    pattern = re.compile(rf"^const {var_name}=\{{.*?\}};", flags=re.MULTILINE)
    replacement = f"const {var_name}={json.dumps(data, separators=(', ', ': '))};"
    updated, count = pattern.subn(lambda _: replacement, html_text, count=1)
    if count != 1:
        raise RuntimeError(f"Expected exactly 1 'const {var_name}=...' declaration, found {count}")
    return updated


def format_human_date(iso_date: str) -> str:
    parsed = dt.date.fromisoformat(iso_date)
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def update_readme(last_iso_date: str, dry_run: bool) -> None:
    if not README_MD.exists():
        return
    text = README_MD.read_text(encoding="utf-8")
    human = format_human_date(last_iso_date)
    updated, count = re.subn(
        r"through [A-Z][a-z]+ \d{1,2}, \d{4}\.",
        f"through {human}.",
        text,
        count=1,
    )
    if count == 1 and updated != text and not dry_run:
        README_MD.write_text(updated, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and validate data without modifying files.",
    )
    parser.add_argument(
        "--allow-older",
        action="store_true",
        help="Allow writing data even if the latest bar is older than the existing HTML.",
    )
    args = parser.parse_args()

    today = dt.datetime.now(ZoneInfo("America/New_York")).date()
    short_start = today - dt.timedelta(days=SHORT_WINDOW_DAYS)
    long_start = today - dt.timedelta(days=LONG_WINDOW_DAYS)
    short_cutoff = short_start.isoformat()

    print(f"Fetching {len(STYLE_TICKERS)} style ETFs from {long_start}...", file=sys.stderr)
    style_frames = download_tickers(STYLE_TICKERS, start=long_start, today=today)
    style_d, style_last = build_ohlc_series(style_frames, STYLE_TICKERS, short_cutoff, MIN_SHORT_BARS)
    style_ld, style_ld_last = build_close_series(style_frames, STYLE_TICKERS, MIN_LONG_BARS)

    print(f"Fetching {len(SECTOR_TICKERS)} sector ETFs from {short_start}...", file=sys.stderr)
    sector_frames = download_tickers(SECTOR_TICKERS, start=short_start, today=today)
    sector_d, sector_last = build_ohlc_series(sector_frames, SECTOR_TICKERS, short_cutoff, MIN_SHORT_BARS)

    styles_text = STYLES_HTML.read_text(encoding="utf-8")
    sectors_text = SECTORS_HTML.read_text(encoding="utf-8")

    prev_styles = existing_last_date(styles_text, "D")
    prev_sectors = existing_last_date(sectors_text, "D")

    if not args.allow_older:
        if prev_styles and style_last < prev_styles:
            raise RuntimeError(f"Style data regressed: {style_last} < {prev_styles}")
        if prev_sectors and sector_last < prev_sectors:
            raise RuntimeError(f"Sector data regressed: {sector_last} < {prev_sectors}")

    new_styles = replace_const_json(styles_text, "D", style_d)
    new_styles = replace_const_json(new_styles, "LD", style_ld)
    new_sectors = replace_const_json(sectors_text, "D", sector_d)

    print(
        f"styles.html:  {prev_styles} -> {style_last} "
        f"(D: {len(style_d['IVV'])} bars, LD: {len(style_ld['IVV'])} bars, LD through {style_ld_last})"
    )
    print(
        f"sectors.html: {prev_sectors} -> {sector_last} "
        f"(D: {len(sector_d['XLK'])} bars)"
    )

    if args.dry_run:
        print("Dry run complete; no files written.")
        return 0

    STYLES_HTML.write_text(new_styles, encoding="utf-8")
    SECTORS_HTML.write_text(new_sectors, encoding="utf-8")
    update_readme(min(style_last, sector_last), dry_run=False)
    print("Updated styles.html, sectors.html, and README.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
