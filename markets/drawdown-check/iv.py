#!/usr/bin/env python3
"""Implied-volatility metrics from a live option chain, plus vol-index history helpers.

Computes 30-day constant-maturity ATM IV, 30-day 25-delta put IV, 30-day
25-delta call IV, and 25-delta put-minus-call skew. Deltas are calculated
with Black-Scholes from each contract's implied volatility. Two expiries
that bracket 30 calendar days are interpolated in total variance.

Live chain source (preferred): CBOE delayed-quotes JSON, which also publishes
an iv30 field (ATM-ish 30-day IV, percent) used as a cross-check.
Fallback: yfinance option chains (IV only; deltas still from Black-Scholes).

Historical proxies (free): CBOE / Yahoo VIX (SPY), VXN (QQQ), RVX (IWM),
and single-stock equity VIX indexes VXAPL, VXAZN, VXGOG, VXGS, VXIBM.
There is no free VXNVDA history series.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
CBOE_OPTIONS = "https://cdn.cboe.com/api/global/delayed_quotes/options/{ticker}.json"
CBOE_VOL_CSV = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{index}_History.csv"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_CHART_QS = "period1=0&period2={end}&interval=1d&events=div,split&includeAdjustedClose=true"

TARGET_DAYS = 30
TARGET_PUT_DELTA = -0.25
TARGET_CALL_DELTA = 0.25
YEAR_DAYS = 365.0

# Official CBOE vol indexes we have verified as downloadable CSVs.
VOL_INDEXES = {
    "VIX": "S&P 500 30-day IV (VIX)",
    "VXN": "Nasdaq-100 30-day IV (VXN)",
    "RVX": "Russell 2000 30-day IV (RVX)",
    "VXAPL": "CBOE Equity VIX on Apple",
    "VXAZN": "CBOE Equity VIX on Amazon",
    "VXGOG": "CBOE Equity VIX on Google",
    "VXGS": "CBOE Equity VIX on Goldman Sachs",
    "VXIBM": "CBOE Equity VIX on IBM",
}

TICKER_TO_VOLINDEX = {
    "SPY": "VIX",
    "SPX": "VIX",
    "^SPX": "VIX",
    "^GSPC": "VIX",
    "IVV": "VIX",
    "VOO": "VIX",
    "QQQ": "VXN",
    "QQQM": "VXN",
    "NDX": "VXN",
    "^NDX": "VXN",
    "IWM": "RVX",
    "RUT": "RVX",
    "^RUT": "RVX",
    "AAPL": "VXAPL",
    "AMZN": "VXAZN",
    "GOOG": "VXGOG",
    "GOOGL": "VXGOG",
    "GS": "VXGS",
    "IBM": "VXIBM",
}

OCC_RE = re.compile(r"^([A-Z0-9]+)(\d{6})([CP])(\d{8})$")

DEFAULT_SNAPSHOT = Path("/workspace/drawdown/data/iv_snapshots.csv")
SNAPSHOT_FIELDS = [
    "date",
    "asof_et",
    "ticker",
    "source",
    "spot",
    "atm_iv_30d",
    "put25_iv_30d",
    "call25_iv_30d",
    "skew_25d",
    "cboe_iv30",
    "near_expiry",
    "far_expiry",
    "r",
    "q",
]


@dataclass
class Contract:
    symbol: str
    expiry: date
    kind: str  # call | put
    strike: float
    bid: float
    ask: float
    iv: float  # decimal (0.55 = 55%)
    delta_vendor: float | None = None
    volume: float = 0.0
    open_interest: float = 0.0
    last: float = 0.0


@dataclass
class ExpirySlice:
    expiry: date
    t_years: float
    atm_iv: float | None
    put25_iv: float | None
    call25_iv: float | None
    atm_iv_vendor: float | None = None
    put25_iv_vendor: float | None = None
    call25_iv_vendor: float | None = None
    n_calls: int = 0
    n_puts: int = 0


@dataclass
class IVMetrics:
    ticker: str
    asof: datetime
    source: str
    spot: float
    r: float
    q: float
    atm_iv_30d: float | None
    put25_iv_30d: float | None
    call25_iv_30d: float | None
    skew_25d: float | None
    cboe_iv30: float | None
    near_expiry: date | None
    far_expiry: date | None
    slices: list[ExpirySlice] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _http_json(url: str, timeout: int = 40) -> dict:
    req = Request(url, headers={"User-Agent": BROWSER_UA, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_text(url: str, timeout: int = 40) -> str:
    req = Request(url, headers={"User-Agent": BROWSER_UA, "Accept": "text/csv,application/json,*/*"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def year_fraction(expiry: date, asof: datetime) -> float:
    end = datetime.combine(expiry, time(16, 0), tzinfo=ET)
    if asof.tzinfo is None:
        asof = asof.replace(tzinfo=ET)
    asof = asof.astimezone(ET)
    seconds = (end - asof).total_seconds()
    return max(seconds, 0.0) / (YEAR_DAYS * 24 * 3600)


def session_close(asof: datetime | None = None) -> datetime:
    """Last 16:00 ET snapshot time (use previous weekday if now is after the weekend)."""
    now = asof or datetime.now(ET)
    if now.tzinfo is None:
        now = now.replace(tzinfo=ET)
    now = now.astimezone(ET)
    close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    if now < close:
        close = close - timedelta(days=1)
    while close.weekday() >= 5:
        close -= timedelta(days=1)
    return close


def bs_delta(spot: float, strike: float, t: float, r: float, q: float, sigma: float, kind: str) -> float | None:
    if spot <= 0 or strike <= 0 or t <= 1e-8 or sigma <= 1e-8:
        return None
    d1 = (math.log(spot / strike) + (r - q + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    disc_q = math.exp(-q * t)
    if kind == "call":
        return disc_q * norm_cdf(d1)
    return disc_q * (norm_cdf(d1) - 1.0)


def parse_occ(symbol: str) -> tuple[str, date, str, float] | None:
    m = OCC_RE.match(symbol.replace(" ", ""))
    if not m:
        return None
    root, yymmdd, cp, strike_raw = m.groups()
    expiry = datetime.strptime(yymmdd, "%y%m%d").date()
    kind = "call" if cp == "C" else "put"
    return root, expiry, kind, int(strike_raw) / 1000.0


def _usable(c: Contract) -> bool:
    if c.iv is None or c.iv <= 0.01 or c.iv > 5.0:
        return False
    # Prefer a two-sided market; allow last-only if mid cannot be formed.
    if c.bid > 0 and c.ask > 0 and c.ask >= c.bid:
        return True
    return c.last > 0


def interpolate_y(xs: list[float], ys: list[float], x0: float) -> float | None:
    """Linear interpolate y at x0; clamp to endpoints if x0 is slightly outside."""
    if not xs or len(xs) != len(ys):
        return None
    paired = sorted(zip(xs, ys), key=lambda p: p[0])
    xs, ys = [p[0] for p in paired], [p[1] for p in paired]
    if x0 < xs[0] or x0 > xs[-1]:
        # Allow a modest overshoot (0.03 in delta or similar units)
        span = xs[-1] - xs[0]
        pad = max(0.03, 0.15 * span) if span else 0.03
        if x0 < xs[0] - pad or x0 > xs[-1] + pad:
            return None
        return ys[0] if x0 < xs[0] else ys[-1]
    for i in range(1, len(xs)):
        if xs[i] >= x0:
            if xs[i] == xs[i - 1]:
                return ys[i]
            w = (x0 - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] * (1 - w) + ys[i] * w
    return ys[-1]


def iv_at_delta(contracts: list[Contract], t: float, spot: float, r: float, q: float, target: float, use_vendor: bool) -> float | None:
    xs, ys = [], []
    for c in contracts:
        if not _usable(c):
            continue
        if use_vendor:
            dlt = c.delta_vendor
        else:
            dlt = bs_delta(spot, c.strike, t, r, q, c.iv, c.kind)
        if dlt is None:
            continue
        xs.append(dlt)
        ys.append(c.iv)
    return interpolate_y(xs, ys, target)


def iv_at_strike(contracts: list[Contract], k0: float) -> float | None:
    xs, ys = [], []
    for c in contracts:
        if not _usable(c):
            continue
        xs.append(c.strike)
        ys.append(c.iv)
    return interpolate_y(xs, ys, k0)


def slice_expiry(
    expiry: date,
    contracts: list[Contract],
    spot: float,
    r: float,
    q: float,
    asof: datetime,
) -> ExpirySlice | None:
    t = year_fraction(expiry, asof)
    if t <= 3 / YEAR_DAYS:  # skip 0–2 DTE; IV/delta are unstable
        return None
    calls = [c for c in contracts if c.kind == "call"]
    puts = [c for c in contracts if c.kind == "put"]
    fwd = spot * math.exp((r - q) * t)
    atm = iv_at_strike(calls + puts, fwd)
    if atm is None:
        atm = iv_at_strike(calls + puts, spot)
    # 50-delta average as a supplement if strike ATM is missing
    if atm is None:
        c50 = iv_at_delta(calls, t, spot, r, q, 0.50, False)
        p50 = iv_at_delta(puts, t, spot, r, q, -0.50, False)
        if c50 is not None and p50 is not None:
            atm = 0.5 * (c50 + p50)
        else:
            atm = c50 if c50 is not None else p50
    return ExpirySlice(
        expiry=expiry,
        t_years=t,
        atm_iv=atm,
        put25_iv=iv_at_delta(puts, t, spot, r, q, TARGET_PUT_DELTA, False),
        call25_iv=iv_at_delta(calls, t, spot, r, q, TARGET_CALL_DELTA, False),
        atm_iv_vendor=iv_at_strike(calls + puts, fwd) if any(c.delta_vendor is not None for c in contracts) else None,
        put25_iv_vendor=iv_at_delta(puts, t, spot, r, q, TARGET_PUT_DELTA, True),
        call25_iv_vendor=iv_at_delta(calls, t, spot, r, q, TARGET_CALL_DELTA, True),
        n_calls=sum(1 for c in calls if _usable(c)),
        n_puts=sum(1 for c in puts if _usable(c)),
    )


def interpolate_maturity(slices: list[ExpirySlice], attr: str, target_t: float) -> tuple[float | None, ExpirySlice | None, ExpirySlice | None]:
    usable = [s for s in slices if getattr(s, attr) is not None]
    if not usable:
        return None, None, None
    exact = min(usable, key=lambda s: abs(s.t_years - target_t))
    if abs(exact.t_years - target_t) * YEAR_DAYS < 0.6:
        return getattr(exact, attr), exact, exact
    below = [s for s in usable if s.t_years <= target_t]
    above = [s for s in usable if s.t_years >= target_t]
    if not below or not above:
        # No bracket: do not extrapolate a long way; use nearest if within ~7 days
        if abs(exact.t_years - target_t) * YEAR_DAYS <= 7:
            return getattr(exact, attr), exact, exact
        return None, None, None
    s1 = max(below, key=lambda s: s.t_years)
    s2 = min(above, key=lambda s: s.t_years)
    if s1.expiry == s2.expiry:
        return getattr(s1, attr), s1, s2
    w1 = getattr(s1, attr)
    w2 = getattr(s2, attr)
    # Total-variance interpolation: IV^2 * T
    var = w1 * w1 * s1.t_years * (s2.t_years - target_t) / (s2.t_years - s1.t_years) + w2 * w2 * s2.t_years * (
        target_t - s1.t_years
    ) / (s2.t_years - s1.t_years)
    if var <= 0:
        return None, s1, s2
    return math.sqrt(var / target_t), s1, s2


def fetch_cboe_chain(ticker: str) -> tuple[float, float | None, list[Contract], datetime, dict]:
    payload = _http_json(CBOE_OPTIONS.format(ticker=ticker.upper()))
    data = payload.get("data") or {}
    close = data.get("close") or data.get("current_price")
    prev = data.get("prev_day_close")
    # After the bell, official close is the right spot for EOD IV.
    spot = float(close or data.get("current_price") or 0)
    cboe_iv30 = data.get("iv30")
    if cboe_iv30 is not None:
        cboe_iv30 = float(cboe_iv30) / 100.0  # published in percent
    ts = payload.get("timestamp")
    asof = session_close()
    last_trade = data.get("last_trade_time")
    if last_trade:
        try:
            asof = datetime.fromisoformat(last_trade).replace(tzinfo=ET)
        except ValueError:
            pass
    root = ticker.upper()
    contracts: list[Contract] = []
    for raw in data.get("options") or []:
        parsed = parse_occ(str(raw.get("option") or ""))
        if not parsed:
            continue
        occ_root, expiry, kind, strike = parsed
        if not occ_root.startswith(root) or occ_root != root:
            # Skip mini / non-standard roots (e.g. B1VDA)
            continue
        iv = raw.get("iv")
        try:
            iv = float(iv) if iv is not None else None
        except (TypeError, ValueError):
            iv = None
        if iv is None:
            continue
        delta = raw.get("delta")
        try:
            delta = float(delta) if delta is not None else None
        except (TypeError, ValueError):
            delta = None
        contracts.append(
            Contract(
                symbol=str(raw.get("option")),
                expiry=expiry,
                kind=kind,
                strike=strike,
                bid=float(raw.get("bid") or 0),
                ask=float(raw.get("ask") or 0),
                iv=iv,
                delta_vendor=delta,
                volume=float(raw.get("volume") or 0),
                open_interest=float(raw.get("open_interest") or 0),
                last=float(raw.get("last_trade_price") or 0),
            )
        )
    meta = {
        "close": float(close) if close else None,
        "current_price": data.get("current_price"),
        "prev_day_close": float(prev) if prev else None,
        "cboe_timestamp": ts,
        "last_trade_time": last_trade,
    }
    return spot, cboe_iv30, contracts, asof, meta


def fetch_yfinance_chain(ticker: str) -> tuple[float, None, list[Contract], datetime, dict]:
    import yfinance as yf

    inst = yf.Ticker(ticker)
    hist = inst.history(period="5d")
    if hist is None or hist.empty:
        raise RuntimeError(f"yfinance has no price history for {ticker}")
    spot = float(hist["Close"].iloc[-1])
    asof = session_close()
    contracts: list[Contract] = []
    expiries = list(inst.options or [])
    for exp_s in expiries:
        expiry = datetime.strptime(exp_s, "%Y-%m-%d").date()
        if year_fraction(expiry, asof) <= 0:
            continue
        try:
            chain = inst.option_chain(exp_s)
        except Exception:
            continue
        for kind, frame in (("call", chain.calls), ("put", chain.puts)):
            if frame is None or frame.empty:
                continue
            for _, row in frame.iterrows():
                try:
                    iv = float(row.get("impliedVolatility") or 0)
                    strike = float(row.get("strike"))
                except (TypeError, ValueError):
                    continue
                contracts.append(
                    Contract(
                        symbol=str(row.get("contractSymbol") or ""),
                        expiry=expiry,
                        kind=kind,
                        strike=strike,
                        bid=float(row.get("bid") or 0),
                        ask=float(row.get("ask") or 0),
                        iv=iv,
                        volume=float(row.get("volume") or 0) if row.get("volume") == row.get("volume") else 0,
                        open_interest=float(row.get("openInterest") or 0) if row.get("openInterest") == row.get("openInterest") else 0,
                        last=float(row.get("lastPrice") or 0) if row.get("lastPrice") == row.get("lastPrice") else 0,
                    )
                )
    return spot, None, contracts, asof, {"source": "yfinance"}


def fetch_rate() -> float:
    """13-week T-bill (^IRX) as a decimal risk-free rate; fall back to 4%."""
    try:
        import yfinance as yf

        hist = yf.Ticker("^IRX").history(period="10d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1]) / 100.0
    except Exception:
        pass
    try:
        end = int(datetime.now(ET).timestamp())
        url = YAHOO_CHART.format(symbol="%5EIRX") + "?" + YAHOO_CHART_QS.format(end=end)
        payload = _http_json(url)
        result = (payload.get("chart") or {}).get("result") or []
        closes = (((result[0].get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
        for v in reversed(closes):
            if v is not None:
                return float(v) / 100.0
    except Exception:
        pass
    return 0.04


def fetch_dividend_yield(ticker: str, spot: float) -> float:
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
        trailing = info.get("trailingAnnualDividendRate")
        if trailing:
            return max(float(trailing), 0.0) / spot
        yld = info.get("dividendYield")
        if yld is not None:
            yld = float(yld)
            return yld / 100.0 if yld > 0.2 else yld
    except Exception:
        pass
    return 0.0


def compute_metrics(
    ticker: str,
    spot: float,
    contracts: list[Contract],
    asof: datetime,
    source: str,
    r: float,
    q: float,
    cboe_iv30: float | None = None,
    notes: list[str] | None = None,
) -> IVMetrics:
    by_exp: dict[date, list[Contract]] = {}
    for c in contracts:
        by_exp.setdefault(c.expiry, []).append(c)
    slices: list[ExpirySlice] = []
    for expiry, group in sorted(by_exp.items()):
        sl = slice_expiry(expiry, group, spot, r, q, asof)
        if sl is not None:
            slices.append(sl)
    target_t = TARGET_DAYS / YEAR_DAYS
    atm, n1, n2 = interpolate_maturity(slices, "atm_iv", target_t)
    put25, p1, p2 = interpolate_maturity(slices, "put25_iv", target_t)
    call25, c1, c2 = interpolate_maturity(slices, "call25_iv", target_t)
    near = far = None
    for pair in ((n1, n2), (p1, p2), (c1, c2)):
        if pair[0] is not None:
            near, far = pair[0].expiry, pair[1].expiry
            break
    skew = None
    if put25 is not None and call25 is not None:
        skew = put25 - call25
    return IVMetrics(
        ticker=ticker.upper(),
        asof=asof,
        source=source,
        spot=spot,
        r=r,
        q=q,
        atm_iv_30d=atm,
        put25_iv_30d=put25,
        call25_iv_30d=call25,
        skew_25d=skew,
        cboe_iv30=cboe_iv30,
        near_expiry=near,
        far_expiry=far,
        slices=slices,
        notes=notes or [],
    )


def analyze_ticker(ticker: str) -> IVMetrics:
    ticker = ticker.upper()
    notes: list[str] = []
    r = fetch_rate()
    source = "cboe"
    try:
        spot, cboe_iv30, contracts, asof, meta = fetch_cboe_chain(ticker)
        if not contracts:
            raise RuntimeError("CBOE returned no standard-root contracts")
        notes.append(f"CBOE chain timestamp {meta.get('cboe_timestamp')}")
        if meta.get("current_price") and meta.get("close") and abs(float(meta["current_price"]) - float(meta["close"])) / float(meta["close"]) > 0.02:
            notes.append(
                f"Using regular-session close {float(meta['close']):.2f} "
                f"(feed current_price {float(meta['current_price']):.2f} ignored as off-session)"
            )
    except Exception as exc:
        notes.append(f"CBOE chain failed ({exc}); falling back to yfinance")
        spot, cboe_iv30, contracts, asof, meta = fetch_yfinance_chain(ticker)
        source = "yfinance"
    q = fetch_dividend_yield(ticker, spot)
    return compute_metrics(ticker, spot, contracts, asof, source, r, q, cboe_iv30, notes)


def fetch_volindex_history(index: str) -> list[tuple[date, float]]:
    index = index.upper()
    if index not in VOL_INDEXES:
        raise RuntimeError(f"Unsupported vol index {index}; allowed: {', '.join(VOL_INDEXES)}")
    text = _http_text(CBOE_VOL_CSV.format(index=index))
    rows = list(csv.DictReader(text.splitlines()))
    out: list[tuple[date, float]] = []
    for row in rows:
        raw_d = (row.get("DATE") or row.get("Date") or "").strip()
        raw_c = (row.get("CLOSE") or row.get("Close") or "").strip()
        if not raw_d or not raw_c:
            continue
        try:
            dt = datetime.strptime(raw_d, "%m/%d/%Y").date()
            px = float(raw_c)
        except ValueError:
            continue
        out.append((dt, px))
    return out


def volindex_for_ticker(ticker: str) -> str | None:
    return TICKER_TO_VOLINDEX.get(ticker.upper())


def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x * 100:.2f}%"


def format_report(m: IVMetrics) -> str:
    asof = m.asof.astimezone(ET).strftime("%Y-%m-%d %H:%M ET")
    lines = [
        f"{m.ticker} implied volatility  (as of {asof}, source={m.source})",
        f"  Spot:              {m.spot:.2f}",
        f"  30-day ATM IV:     {_fmt_pct(m.atm_iv_30d)}",
        f"  30-day 25Δ put IV: {_fmt_pct(m.put25_iv_30d)}",
        f"  30-day 25Δ call IV: {_fmt_pct(m.call25_iv_30d)}",
        f"  25Δ put−call skew: {_fmt_pct(m.skew_25d)}",
    ]
    if m.cboe_iv30 is not None:
        lines.append(f"  CBOE iv30 (ref):   {_fmt_pct(m.cboe_iv30)}")
    if m.near_expiry:
        if m.far_expiry and m.far_expiry != m.near_expiry:
            lines.append(f"  Expiries used:     {m.near_expiry.isoformat()} and {m.far_expiry.isoformat()}")
        else:
            lines.append(f"  Expiry used:       {m.near_expiry.isoformat()}")
    lines.append(f"  Rates:             r={m.r * 100:.3f}%, q={m.q * 100:.3f}%")
    proxy = volindex_for_ticker(m.ticker)
    if proxy:
        lines.append(f"  History proxy:     {proxy} ({VOL_INDEXES[proxy]})")
    else:
        lines.append("  History proxy:     none (no free official vol index for this ticker)")
    for n in m.notes:
        lines.append(f"  Note:              {n}")
    return "\n".join(lines)


def append_snapshot(metrics: Iterable[IVMetrics], path: Path = DEFAULT_SNAPSHOT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.exists()
    with path.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=SNAPSHOT_FIELDS)
        if not existing:
            writer.writeheader()
        for m in metrics:
            writer.writerow(
                {
                    "date": m.asof.astimezone(ET).date().isoformat(),
                    "asof_et": m.asof.astimezone(ET).strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "ticker": m.ticker,
                    "source": m.source,
                    "spot": f"{m.spot:.4f}",
                    "atm_iv_30d": f"{m.atm_iv_30d:.6f}" if m.atm_iv_30d is not None else "",
                    "put25_iv_30d": f"{m.put25_iv_30d:.6f}" if m.put25_iv_30d is not None else "",
                    "call25_iv_30d": f"{m.call25_iv_30d:.6f}" if m.call25_iv_30d is not None else "",
                    "skew_25d": f"{m.skew_25d:.6f}" if m.skew_25d is not None else "",
                    "cboe_iv30": f"{m.cboe_iv30:.6f}" if m.cboe_iv30 is not None else "",
                    "near_expiry": m.near_expiry.isoformat() if m.near_expiry else "",
                    "far_expiry": m.far_expiry.isoformat() if m.far_expiry else "",
                    "r": f"{m.r:.6f}",
                    "q": f"{m.q:.6f}",
                }
            )
    return path


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="30-day constant-maturity implied volatility from a live option chain")
    p.add_argument("tickers", nargs="+", help="One or more tickers, space- or comma-separated")
    p.add_argument("--snapshot", action="store_true", help=f"Append a row to {DEFAULT_SNAPSHOT}")
    p.add_argument("--snapshot-path", type=Path, default=DEFAULT_SNAPSHOT)
    p.add_argument("--history", action="store_true", help="Also print the official vol-index proxy history, if one exists")
    return p.parse_args(list(argv) if argv is not None else None)


def _expand(raw: list[str]) -> list[str]:
    out, seen = [], set()
    for item in raw:
        for part in item.split(","):
            t = part.strip().upper()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
    return out


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    tickers = _expand(args.tickers)
    results: list[IVMetrics] = []
    blocks: list[str] = []
    code = 0
    for ticker in tickers:
        try:
            m = analyze_ticker(ticker)
            results.append(m)
            text = format_report(m)
            if args.history:
                proxy = volindex_for_ticker(ticker)
                if proxy:
                    hist = fetch_volindex_history(proxy)
                    last = hist[-1] if hist else None
                    first = hist[0] if hist else None
                    text += (
                        f"\n  {proxy} history:     {len(hist)} sessions"
                        + (f" from {first[0].isoformat()} to {last[0].isoformat()}, last {last[1]:.2f}" if last else "")
                    )
            blocks.append(text)
        except Exception as exc:
            code = 1
            blocks.append(f"{ticker}\n  Error: {exc}")
    if args.snapshot and results:
        path = append_snapshot(results, args.snapshot_path)
        blocks.append(f"Snapshot appended to {path}")
    print("\n\n".join(blocks))
    return code


if __name__ == "__main__":
    sys.exit(main())
