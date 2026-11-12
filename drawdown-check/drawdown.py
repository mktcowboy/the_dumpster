#!/usr/bin/env python3
"""Report current and historical drawdown from all-time highs for one or more tickers."""

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

BG = "#131a2e"
LINE = "#6fa8f5"
FILL_ALPHA = 0.32
GRID = "#ffffff"
GRID_ALPHA = 0.09
TEXT = "#c8d0e0"
SPINE = "#3d4a66"
LEGEND_FACE = "#1a2340"

DEFAULT_OUT_DIR = Path("/workspace/drawdown/out")


@dataclass
class PriceHistory:
    ticker: str
    adj_close: pd.Series
    close: pd.Series | None
    source: str
    adj_label: str


@dataclass
class DrawdownStats:
    ticker: str
    source: str
    price_kind: str
    ath_value: float
    ath_date: date
    last_value: float
    last_date: date
    current_dd: float
    max_dd: float
    max_dd_peak_date: date
    max_dd_trough_date: date
    days_since_ath: int
    drawdown: pd.Series
    prices: pd.Series


def _to_date(value) -> date:
    if hasattr(value, "date") and callable(value.date):
        try:
            return value.date()
        except (ValueError, OSError):
            pass
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(None)
    return ts.date()


def _normalize_series(series: pd.Series, name: str) -> pd.Series:
    s = series.copy()
    s.index = pd.to_datetime(s.index)
    if getattr(s.index, "tz", None) is not None:
        s.index = s.index.tz_localize(None)
    s = pd.to_numeric(s, errors="coerce").dropna().sort_index()
    s = s[s > 0]
    s.name = name
    if s.index.duplicated().any():
        s = s[~s.index.duplicated(keep="last")]
    return s


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [
            str(col[0]) if isinstance(col, tuple) else str(col) for col in df.columns
        ]
    return df


def fetch_yfinance(ticker: str) -> PriceHistory:
    import yfinance as yf

    instrument = yf.Ticker(ticker)
    df = instrument.history(period="max", auto_adjust=False, actions=False)
    if df is None or df.empty:
        # Fallback download path used by some yfinance versions / tickers
        df = yf.download(
            ticker,
            period="max",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    if df is None or df.empty:
        raise RuntimeError(f"yfinance returned no rows for {ticker}")

    df = _flatten_columns(df)
    columns = {str(c).strip(): c for c in df.columns}
    lower = {c.lower().replace(" ", "_"): orig for c, orig in columns.items()}

    close_col = lower.get("close")
    adj_col = lower.get("adj_close") or lower.get("adjclose") or close_col
    if close_col is None and adj_col is None:
        raise RuntimeError(f"yfinance response for {ticker} has no close columns")

    adj = _normalize_series(df[adj_col], "adj_close")
    close = _normalize_series(df[close_col], "close") if close_col is not None else None
    if adj.empty:
        raise RuntimeError(f"yfinance adjusted-close series for {ticker} is empty")

    # If Adj Close is missing, Close may already be split-adjusted only
    if adj_col == close_col:
        adj_label = "close (yfinance; Adj Close not provided)"
    else:
        adj_label = "adjusted close (yfinance, total-return-ish)"

    return PriceHistory(
        ticker=ticker.upper(),
        adj_close=adj,
        close=close if close is not None and not close.empty else None,
        source="yfinance",
        adj_label=adj_label,
    )


def _stooq_symbols(ticker: str) -> list[str]:
    raw = ticker.strip().lower()
    symbols = []
    if "." in raw and not raw.endswith(".us"):
        # Already looks like a Stooq symbol (e.g. 7203.jp) or Yahoo-style (BRK-B)
        symbols.append(raw.replace("-", "."))
        symbols.append(raw)
    else:
        base = raw.replace("-", ".")
        if base.endswith(".us"):
            symbols.append(base)
        else:
            symbols.append(f"{base}.us")
            symbols.append(base)
    # Unique, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def fetch_stooq(ticker: str) -> PriceHistory:
    last_error: Exception | None = None
    for symbol in _stooq_symbols(ticker):
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
        req = Request(
            url,
            headers={"User-Agent": "drawdown-check/1.0 (research)"},
        )
        try:
            with urlopen(req, timeout=30) as resp:
                body = resp.read()
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
            continue

        text = body.decode("utf-8", errors="replace").strip()
        if not text or text.lower().startswith("<!") or "not found" in text.lower():
            last_error = RuntimeError(f"Stooq had no CSV for {symbol}")
            continue
        try:
            df = pd.read_csv(io.StringIO(text))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
        if df.empty or "Close" not in df.columns or "Date" not in df.columns:
            last_error = RuntimeError(f"Stooq CSV for {symbol} missing Date/Close")
            continue
        # Stooq returns "No data" as a one-column file in some cases
        if list(df.columns) == ["No data"] or (df.shape[1] == 1 and "No data" in str(df.iloc[0, 0])):
            last_error = RuntimeError(f"Stooq has no data for {symbol}")
            continue
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).set_index("Date")
        close = _normalize_series(df["Close"], "close")
        if close.empty:
            last_error = RuntimeError(f"Stooq close series for {symbol} is empty")
            continue
        return PriceHistory(
            ticker=ticker.upper(),
            adj_close=close,
            close=close,
            source="stooq",
            adj_label="close (Stooq; typically split-adjusted, not dividend-adjusted)",
        )

    raise RuntimeError(f"Stooq fallback failed for {ticker}: {last_error}")


def fetch_history(ticker: str) -> PriceHistory:
    errors: list[str] = []
    try:
        return fetch_yfinance(ticker)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"yfinance: {exc}")
    try:
        return fetch_stooq(ticker)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"stooq: {exc}")
    raise RuntimeError(f"Could not fetch price history for {ticker} ({'; '.join(errors)})")


def _slice(series: pd.Series, start: date | None, end: date | None) -> pd.Series:
    out = series
    if start is not None:
        out = out[out.index >= pd.Timestamp(start)]
    if end is not None:
        out = out[out.index <= pd.Timestamp(end) + pd.Timedelta(days=0)]
        # include the end date fully (timestamps at midnight already match)
        out = out[out.index.normalize() <= pd.Timestamp(end)]
    return out


def compute_drawdown(prices: pd.Series) -> pd.Series:
    running_peak = prices.cummax()
    return prices / running_peak - 1.0


def analyze(prices: pd.Series, ticker: str, source: str, price_kind: str) -> DrawdownStats:
    if prices.empty:
        raise RuntimeError(f"No price observations for {ticker}")
    dd = compute_drawdown(prices)
    ath_date = _to_date(prices.idxmax())
    ath_value = float(prices.max())
    last_date = _to_date(prices.index[-1])
    last_value = float(prices.iloc[-1])
    current_dd = float(dd.iloc[-1])
    trough_ts = dd.idxmin()
    max_dd = float(dd.loc[trough_ts])
    # Peak is the most recent all-time (running) high on or before the trough
    up_to_trough = prices.loc[:trough_ts]
    peak_ts = up_to_trough.idxmax()
    return DrawdownStats(
        ticker=ticker,
        source=source,
        price_kind=price_kind,
        ath_value=ath_value,
        ath_date=ath_date,
        last_value=last_value,
        last_date=last_date,
        current_dd=current_dd,
        max_dd=max_dd,
        max_dd_peak_date=_to_date(peak_ts),
        max_dd_trough_date=_to_date(trough_ts),
        days_since_ath=(last_date - ath_date).days,
        drawdown=dd,
        prices=prices,
    )


def _fmt_price(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.2f}"
    if abs(value) >= 1:
        return f"{value:,.2f}"
    return f"{value:.4f}"


def _fmt_pct(value: float) -> str:
    # Drawdowns are <= 0; show 0.00% at highs rather than -0.00%
    if abs(value) < 5e-5:
        return "0.00%"
    return f"{value * 100:.2f}%"


def format_report(primary: DrawdownStats, unadjusted: DrawdownStats | None, chart_path: Path | None) -> str:
    lines = [
        f"{primary.ticker}",
        f"  Price basis:     {primary.price_kind}",
        f"  Source:          {primary.source}",
        f"  ATH:             {_fmt_price(primary.ath_value)} on {primary.ath_date.isoformat()}",
        f"  Latest close:    {_fmt_price(primary.last_value)} on {primary.last_date.isoformat()}",
        f"  Current drawdown:{'':<1} {_fmt_pct(primary.current_dd)}",
        (
            "  Max drawdown:    "
            f"{_fmt_pct(primary.max_dd)}  "
            f"(peak {primary.max_dd_peak_date.isoformat()} → "
            f"trough {primary.max_dd_trough_date.isoformat()})"
        ),
        f"  Days since ATH:  {primary.days_since_ath}",
    ]
    if unadjusted is not None:
        lines.append(
            "  Unadjusted close:"
            f" current {_fmt_pct(unadjusted.current_dd)}, "
            f"ATH {_fmt_price(unadjusted.ath_value)} on {unadjusted.ath_date.isoformat()}, "
            f"max {_fmt_pct(unadjusted.max_dd)} "
            f"({unadjusted.max_dd_peak_date.isoformat()} → {unadjusted.max_dd_trough_date.isoformat()})"
        )
    if chart_path is not None:
        lines.append(f"  Chart:           {chart_path}")
    return "\n".join(lines)


def plot_drawdown(stats: DrawdownStats, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    dd_pct = stats.drawdown * 100.0
    dates = dd_pct.index.to_pydatetime()

    fig, ax = plt.subplots(figsize=(12.0, 5.6), dpi=160)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    ax.fill_between(dates, dd_pct.values, 0.0, color=LINE, alpha=FILL_ALPHA, linewidth=0, zorder=2)
    ax.plot(dates, dd_pct.values, color=LINE, linewidth=1.45, solid_capstyle="round", label=stats.ticker, zorder=3)
    ax.axhline(0.0, color=LINE, linewidth=0.7, alpha=0.55, zorder=1)

    ax.set_ylabel("Drawdown", color=TEXT, fontsize=11, labelpad=8)
    ax.set_xlabel("")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _pos: f"{v:.0f}%"))
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator(2))

    span_days = max((dd_pct.index[-1] - dd_pct.index[0]).days, 1)
    if span_days > 365 * 8:
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    elif span_days > 365 * 3:
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    elif span_days > 180:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    else:
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))

    ax.grid(True, which="major", axis="both", color=GRID, alpha=GRID_ALPHA, linewidth=0.6, zorder=0)
    ax.grid(True, which="minor", axis="y", color=GRID, alpha=GRID_ALPHA * 0.5, linewidth=0.4, zorder=0)
    ax.tick_params(colors=TEXT, labelsize=9, length=3, width=0.6)
    ax.tick_params(which="minor", length=0)
    for spine in ax.spines.values():
        spine.set_color(SPINE)
        spine.set_linewidth(0.6)

    ymin = min(float(dd_pct.min()) * 1.08, -1.0)
    ax.set_ylim(ymin, 0.0)  # 0% at the top
    ax.set_xlim(dates[0], dates[-1])
    ax.margins(x=0)

    legend = ax.legend(
        loc="lower left",
        frameon=True,
        facecolor=LEGEND_FACE,
        edgecolor=SPINE,
        labelcolor=TEXT,
        fontsize=10,
        borderpad=0.5,
        handlelength=1.6,
    )
    legend.get_frame().set_linewidth(0.6)
    legend.get_frame().set_alpha(0.95)

    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    return path


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Show how far a ticker is below its all-time high and plot a "
            "testfol.io-style drawdown chart."
        )
    )
    parser.add_argument(
        "tickers",
        nargs="+",
        help="One or more tickers (space- or comma-separated), e.g. QQQ NVDA or QQQ,SPY",
    )
    parser.add_argument(
        "--start",
        type=_parse_iso_date,
        default=None,
        help="History start (YYYY-MM-DD). ATH and drawdowns are computed from this date.",
    )
    parser.add_argument(
        "--end",
        type=_parse_iso_date,
        default=None,
        help="History end (YYYY-MM-DD). Defaults to the latest available session.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Directory for chart PNGs (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--no-chart",
        action="store_true",
        help="Skip writing chart PNGs; print stats only.",
    )
    parser.add_argument(
        "--iv",
        action="store_true",
        help="Also print 30-day ATM / 25-delta implied volatility from the live option chain.",
    )
    parser.add_argument(
        "--iv-snapshot",
        action="store_true",
        help="With --iv, append today's IV metrics to data/iv_snapshots.csv.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _parse_iso_date(text: str) -> date:
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {text!r}") from exc


def _expand_tickers(raw: list[str]) -> list[str]:
    tickers: list[str] = []
    seen: set[str] = set()
    for item in raw:
        for part in item.split(","):
            ticker = part.strip().upper()
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            tickers.append(ticker)
    return tickers


def process_ticker(
    ticker: str,
    start: date | None,
    end: date | None,
    out_dir: Path,
    no_chart: bool,
) -> tuple[str, int]:
    history = fetch_history(ticker)
    adj = _slice(history.adj_close, start, end)
    if adj.empty:
        window = []
        if start:
            window.append(f"start={start.isoformat()}")
        if end:
            window.append(f"end={end.isoformat()}")
        extra = f" in window ({', '.join(window)})" if window else ""
        raise RuntimeError(f"No {history.adj_label} data for {ticker}{extra}")

    primary = analyze(adj, history.ticker, history.source, history.adj_label)
    unadjusted = None
    if history.close is not None:
        raw = _slice(history.close, start, end)
        # Only show a second line when unadjusted actually differs from adjusted
        if not raw.empty:
            alt = analyze(raw, history.ticker, history.source, "unadjusted close")
            if history.source != "stooq" and history.close is not history.adj_close:
                unadjusted = alt

    chart_path = None
    if not no_chart:
        safe = "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in primary.ticker)
        chart_path = plot_drawdown(primary, out_dir / f"{safe}_drawdown.png")

    return format_report(primary, unadjusted, chart_path), 0


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    tickers = _expand_tickers(args.tickers)
    if not tickers:
        print("error: no tickers given", file=sys.stderr)
        return 2
    if args.start and args.end and args.start > args.end:
        print("error: --start cannot be after --end", file=sys.stderr)
        return 2

    exit_code = 0
    blocks: list[str] = []
    iv_rows = []
    for ticker in tickers:
        try:
            text, _ = process_ticker(ticker, args.start, args.end, args.out_dir, args.no_chart)
            if args.iv or args.iv_snapshot:
                from iv import analyze_ticker, format_report as format_iv, append_snapshot
                try:
                    ivm = analyze_ticker(ticker)
                    iv_rows.append(ivm)
                    text = text + "\n\n" + format_iv(ivm)
                except Exception as iv_exc:  # noqa: BLE001
                    text = text + f"\n\n{ticker} implied volatility\n  Error: {iv_exc}"
            blocks.append(text)
        except Exception as exc:  # noqa: BLE001
            exit_code = 1
            blocks.append(f"{ticker}\n  Error: {exc}")
    if args.iv_snapshot and iv_rows:
        from iv import append_snapshot
        path = append_snapshot(iv_rows)
        blocks.append(f"IV snapshot appended to {path}")
    print("\n\n".join(blocks))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
