#!/usr/bin/env python3
"""Compute max-pain snapshots for listed options.

Fetches full option chains from Cboe's delayed-quote endpoint, filters one
expiry (or the nearest listed expiry), and writes a reproducible JSON snapshot
with open-interest, volume, and blended max pain, the 1% shelf, walls, ATM
volatility, the 25-delta risk reversal, modeled GEX, and the gamma flip.

Use --universe qqq to load every current QQQ holding. An optional standalone
HTML board ranks the whole universe.

Usage:
    python3 markets/options/max_pain.py --tickers SPY QQQ --expiry 2026-10-23
    python3 markets/options/max_pain.py --universe qqq --expiry 2026-10-23 \
        --html-out markets/options/qqq-max-pain.html

By default the snapshot is written to markets/options/data/ with a filename
that includes the expiry and the quote date. Pass --out to override it.
Requires only requests.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean
from typing import Iterable, Optional

try:
    import requests
except ImportError:
    requests = None

CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{ticker}.json"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
QQQ_LIST_PAGE = "List of NASDAQ-100 companies"
QQQ_LIST_URL = "https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
_local = threading.local()
OCC_RE = re.compile(r"^(?P<root>[A-Z_]+)(?P<ymd>\d{6})(?P<kind>[CP])(?P<strike>\d{8})$")
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = SCRIPT_DIR / "data"


def _session() -> "requests.Session":
    session = getattr(_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        _local.session = session
    return session


class TickerUnavailable(RuntimeError):
    """Raised when a ticker has no usable chain for the requested expiry."""


class Throttle:
    """Process-wide rate limiter for Cboe requests."""

    def __init__(self, min_interval: float = 0.65):
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._next_at = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next_at - now)
            self._next_at = max(now, self._next_at) + self.min_interval
        if delay:
            time.sleep(delay)


@dataclass
class Leg:
    """One side of a strike."""

    oi: float = 0.0
    volume: float = 0.0
    iv: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    theo: Optional[float] = None

    @property
    def mid(self) -> Optional[float]:
        if self.bid is not None and self.ask is not None and self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        if self.theo is not None:
            return self.theo
        return self.last

    def to_dict(self) -> dict:
        out = {
            "oi": _number(self.oi),
            "volume": _number(self.volume),
            "iv": _round(self.iv, 6),
            "delta": _round(self.delta, 6),
            "gamma": _round(self.gamma, 8),
            "bid": _round(self.bid, 4),
            "ask": _round(self.ask, 4),
            "mid": _round(self.mid, 4),
            "last": _round(self.last, 4),
        }
        return {key: value for key, value in out.items() if value is not None}


@dataclass
class StrikeRow:
    strike: float
    call: Optional[Leg] = None
    put: Optional[Leg] = None

    def leg(self, side: str) -> Optional[Leg]:
        return self.call if side == "call" else self.put

    @property
    def call_oi(self) -> float:
        return self.call.oi if self.call else 0.0

    @property
    def put_oi(self) -> float:
        return self.put.oi if self.put else 0.0

    @property
    def total_oi(self) -> float:
        return self.call_oi + self.put_oi

    @property
    def total_volume(self) -> float:
        return (self.call.volume if self.call else 0.0) + (self.put.volume if self.put else 0.0)

    def to_dict(self) -> dict:
        out = {"strike": _number(self.strike)}
        if self.call and (self.call.oi or self.call.volume or self.call.iv is not None):
            out["call"] = self.call.to_dict()
        if self.put and (self.put.oi or self.put.volume or self.put.iv is not None):
            out["put"] = self.put.to_dict()
        return out


@dataclass
class Chain:
    ticker: str
    spot: float
    prev_close: Optional[float]
    as_of: str
    as_of_date: date
    expiry: date
    rows: list[StrikeRow]
    skipped_contracts: int = 0
    payload_timestamp: str = ""

    @property
    def dte(self) -> int:
        return max(0, (self.expiry - self.as_of_date).days)

    @property
    def t_years(self) -> float:
        return self.dte / 365 if self.dte > 0 else 1 / 365

    @property
    def change_pct(self) -> Optional[float]:
        if not self.prev_close:
            return None
        return (self.spot / self.prev_close - 1) * 100


def _round(value: Optional[float], digits: int) -> Optional[float]:
    return None if value is None else round(float(value), digits)


def _number(value: float):
    return int(value) if float(value).is_integer() else round(float(value), 4)


def _mean(values: Iterable[float]) -> float:
    return fmean(values)


def _money(value: Optional[float]) -> str:
    if value is None:
        return "—"
    absolute = abs(value)
    if absolute >= 1e9:
        return f"${value / 1e9:+.2f}B"
    if absolute >= 1e6:
        return f"${value / 1e6:+.1f}M"
    if absolute >= 1e3:
        return f"${value / 1e3:+.0f}K"
    return f"${value:+.0f}"


def parse_occ(symbol: str) -> Optional[tuple[date, str, float]]:
    """Parse an OCC option symbol into (expiry, call/put, strike)."""
    match = OCC_RE.match(symbol)
    if not match:
        return None
    ymd = match.group("ymd")
    try:
        expiry = date(2000 + int(ymd[:2]), int(ymd[2:4]), int(ymd[4:6]))
    except ValueError:
        return None
    return expiry, match.group("kind"), int(match.group("strike")) / 1000


def fetch_payload(ticker: str, timeout: float, throttle: Throttle, retries: int = 4) -> dict:
    if requests is None:
        raise SystemExit("requests is required: python3 -m pip install requests")

    url = CBOE_URL.format(ticker=ticker.upper())
    last_error = "unknown error"
    for attempt in range(retries):
        throttle.wait()
        try:
            response = _session().get(url, timeout=timeout)
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.5 * (attempt + 1))
            continue

        if response.status_code == 429:
            response.close()
            last_error = "rate limited"
            time.sleep(1.5 * (attempt + 1) ** 2)
            continue
        if response.status_code == 404:
            response.close()
            raise TickerUnavailable("no listed options")
        try:
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            response.close()
            last_error = str(exc)
            time.sleep(0.5 * (attempt + 1))
            continue

        if not isinstance(payload, dict) or "data" not in payload:
            response.close()
            last_error = "unexpected response"
            continue
        return payload

    raise TickerUnavailable(last_error)


def fetch_qqq_constituents(timeout: float) -> list[str]:
    if requests is None:
        raise SystemExit("requests is required: python3 -m pip install requests")
    params = {
        "action": "parse",
        "page": QQQ_LIST_PAGE,
        "format": "json",
        "prop": "wikitext",
    }
    try:
        response = requests.get(
            WIKIPEDIA_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout
        )
        response.raise_for_status()
        wikitext = response.json()["parse"]["wikitext"]["*"]
    except Exception as exc:
        raise SystemExit(f"could not fetch the QQQ holdings list: {exc}") from exc

    tickers = []
    for match in re.finditer(r"^\|\s*([A-Z][A-Z0-9.\-]*)\s*\|\|", wikitext, re.MULTILINE):
        ticker = match.group(1)
        if ticker not in tickers:
            tickers.append(ticker)
    if len(tickers) < 50:
        raise SystemExit("QQQ holdings list looked incomplete; refusing to continue")
    return tickers


def available_expiries(payload: dict) -> list[date]:
    expiries = set()
    for option in payload.get("data", {}).get("options", []):
        parsed = parse_occ(option.get("option", ""))
        if parsed:
            expiries.add(parsed[0])
    return sorted(expiries)


def resolve_expiry(expiries: list[date], requested: date, mode: str) -> Optional[date]:
    if requested in expiries:
        return requested
    if mode == "exact" or not expiries:
        return None
    later = [expiry for expiry in expiries if expiry >= requested]
    if later:
        return min(later)
    return max(expiries)


def _parse_timestamp(value: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def build_chain(payload: dict, ticker: str, expiry: date) -> Chain:
    data = payload.get("data", {})
    spot = float(data["current_price"])
    prev_close = data.get("prev_day_close")
    prev_close = float(prev_close) if prev_close is not None else None
    stamp = _parse_timestamp(payload.get("timestamp", ""))
    rows: dict[float, StrikeRow] = {}
    skipped = 0

    for option in data.get("options", []):
        parsed = parse_occ(option.get("option", ""))
        if not parsed:
            skipped += 1
            continue
        option_expiry, kind, strike = parsed
        if option_expiry != expiry:
            continue
        row = rows.setdefault(strike, StrikeRow(strike=strike))
        leg = Leg(
            oi=float(option.get("open_interest") or 0),
            volume=float(option.get("volume") or 0),
            iv=option.get("iv"),
            delta=option.get("delta"),
            gamma=option.get("gamma"),
            bid=option.get("bid"),
            ask=option.get("ask"),
            last=option.get("last_trade_price"),
            theo=option.get("theo"),
        )
        if kind == "C":
            row.call = leg
        else:
            row.put = leg

    if not rows:
        raise TickerUnavailable(f"no contracts for {expiry.isoformat()}")

    return Chain(
        ticker=ticker.upper(),
        spot=spot,
        prev_close=prev_close,
        as_of=stamp.isoformat(),
        as_of_date=stamp.date(),
        expiry=expiry,
        rows=sorted(rows.values(), key=lambda row: row.strike),
        skipped_contracts=skipped,
        payload_timestamp=payload.get("timestamp", ""),
    )


def load_chain(
    ticker: str,
    requested_expiry: date,
    expiry_mode: str,
    timeout: float,
    throttle: Throttle,
) -> tuple[Chain, date]:
    payload = fetch_payload(ticker, timeout, throttle)
    actual_expiry = resolve_expiry(available_expiries(payload), requested_expiry, expiry_mode)
    if actual_expiry is None:
        raise TickerUnavailable(f"no {requested_expiry.isoformat()} expiry")
    return build_chain(payload, ticker, actual_expiry), actual_expiry


def _units(row: StrikeRow, side: str, field_name: str) -> float:
    leg = row.leg(side)
    if leg is None:
        return 0.0
    if field_name == "oi":
        return leg.oi
    if field_name == "volume":
        return leg.volume
    if field_name == "blend":
        return leg.oi + 0.5 * leg.volume
    raise ValueError(f"unknown field: {field_name}")


def payout(chain: Chain, settlement: float, field_name: str = "oi") -> float:
    total = 0.0
    for row in chain.rows:
        call_units = _units(row, "call", field_name)
        put_units = _units(row, "put", field_name)
        if call_units:
            total += call_units * max(0.0, settlement - row.strike) * 100
        if put_units:
            total += put_units * max(0.0, row.strike - settlement) * 100
    return total


def max_pain(chain: Chain, field_name: str = "oi") -> dict:
    candidates = [
        row.strike
        for row in chain.rows
        if _units(row, "call", field_name) or _units(row, "put", field_name)
    ]
    if not candidates:
        raise TickerUnavailable(f"no {field_name} data for {chain.expiry.isoformat()}")

    curve = {strike: payout(chain, strike, field_name) for strike in candidates}
    strike = min(candidates, key=lambda level: (curve[level], abs(level - chain.spot)))
    minimum = curve[strike]
    shelf = sorted(level for level, value in curve.items() if value <= minimum * 1.01)
    return {
        "strike": strike,
        "minimum_payout": minimum,
        "shelf": shelf,
        "curve": curve,
    }


def walls(chain: Chain) -> tuple[dict, dict]:
    call = max(chain.rows, key=lambda row: (row.call_oi, -abs(row.strike - chain.spot)))
    put = max(chain.rows, key=lambda row: (row.put_oi, -abs(row.strike - chain.spot)))
    return (
        {"strike": call.strike, "oi": call.call_oi},
        {"strike": put.strike, "oi": put.put_oi},
    )


def ratios(chain: Chain) -> tuple[Optional[float], Optional[float]]:
    call_oi = sum(row.call_oi for row in chain.rows)
    put_oi = sum(row.put_oi for row in chain.rows)
    call_volume = sum(row.call.volume if row.call else 0 for row in chain.rows)
    put_volume = sum(row.put.volume if row.put else 0 for row in chain.rows)
    pc_oi = put_oi / call_oi if call_oi else None
    pc_volume = put_volume / call_volume if call_volume else None
    return pc_oi, pc_volume


def atm_metrics(chain: Chain) -> dict:
    nearest = min(chain.rows, key=lambda item: abs(item.strike - chain.spot))
    ordered = sorted(chain.rows, key=lambda item: abs(item.strike - chain.spot))
    chosen = nearest
    ivs = []
    for row in ordered:
        ivs = [leg.iv for leg in (row.call, row.put) if leg and leg.iv and leg.iv > 0]
        if ivs:
            chosen = row
            break
    atm_iv = _mean(ivs) if ivs else None
    nearest_mids = [leg.mid for leg in (nearest.call, nearest.put) if leg and leg.mid is not None]
    chosen_mids = [leg.mid for leg in (chosen.call, chosen.put) if leg and leg.mid is not None]
    mids = nearest_mids if len(nearest_mids) == 2 else chosen_mids
    sigma = chain.spot * atm_iv * math.sqrt(chain.t_years) if atm_iv else None
    return {
        "strike": chosen.strike,
        "iv": atm_iv,
        "straddle": sum(mids) if len(mids) == 2 else None,
        "one_sigma_move": sigma,
        "one_sigma_range": [chain.spot - sigma, chain.spot + sigma] if sigma else None,
    }


def risk_reversal(chain: Chain) -> dict:
    calls = [
        row
        for row in chain.rows
        if row.call and row.call.delta and row.call.iv and row.strike >= chain.spot
    ]
    puts = [
        row
        for row in chain.rows
        if row.put and row.put.delta and row.put.iv and row.strike <= chain.spot
    ]
    if not calls or not puts:
        return {"points": None, "call": None, "put": None}

    call = min(calls, key=lambda row: abs(row.call.delta - 0.25))
    put = min(puts, key=lambda row: abs(row.put.delta + 0.25))
    return {
        "points": (put.put.iv - call.call.iv) * 100,
        "call": {
            "strike": call.strike,
            "delta": call.call.delta,
            "iv": call.call.iv,
        },
        "put": {
            "strike": put.strike,
            "delta": put.put.delta,
            "iv": put.put.iv,
        },
    }


def bs_gamma(spot: float, strike: float, t_years: float, iv: float) -> float:
    if spot <= 0 or strike <= 0 or iv <= 0 or t_years <= 0:
        return 0.0
    root = iv * math.sqrt(t_years)
    d1 = (math.log(spot / strike) + 0.5 * iv * iv * t_years) / root
    density = math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)
    return density / (spot * root)


def net_gex(chain: Chain, spot: float, fallback_iv: Optional[float]) -> float:
    total = 0.0
    for row in chain.rows:
        for leg, sign in ((row.call, 1), (row.put, -1)):
            if leg is None or not leg.oi:
                continue
            iv = leg.iv if leg.iv and leg.iv > 0 else fallback_iv
            if not iv:
                continue
            gamma = bs_gamma(spot, row.strike, chain.t_years, iv)
            total += sign * gamma * leg.oi * 100 * spot * spot * 0.01
    return total


def gamma_flip(chain: Chain, atm_iv: Optional[float]) -> Optional[float]:
    if not atm_iv:
        return None
    band = 0.15
    step = max(0.5, round(chain.spot * 0.002, 1))
    low = chain.spot * (1 - band)
    high = chain.spot * (1 + band)
    grid = []
    level = low
    while level <= high:
        grid.append(level)
        level += step

    values = [(level, net_gex(chain, level, atm_iv)) for level in grid]
    crossings = []
    for (left, left_value), (right, right_value) in zip(values, values[1:]):
        if left_value == 0:
            crossings.append(left)
        elif left_value * right_value < 0:
            crossings.append(left + (0 - left_value) * (right - left) / (right_value - left_value))
    if not crossings:
        return None
    return min(crossings, key=lambda level: abs(level - chain.spot))


def pin_confidence(levels: list[float], spot: float) -> tuple[str, float]:
    spread = max(levels) - min(levels)
    spread_pct = spread / spot * 100 if spot else 0.0
    if spread_pct <= 0.5:
        return "High", spread_pct
    if spread_pct <= 1.0:
        return "Moderate", spread_pct
    return "Low", spread_pct


def top_strikes(chain: Chain, oi_strike: float, call_wall: float, put_wall: float, limit: int = 12) -> list[dict]:
    ranked = sorted(chain.rows, key=lambda row: row.total_oi, reverse=True)[:limit]
    out = []
    for row in ranked:
        tags = []
        if row.strike == oi_strike:
            tags.append("max pain")
        if row.strike == call_wall:
            tags.append("call wall")
        if row.strike == put_wall:
            tags.append("put wall")
        if abs(row.strike - oi_strike) <= max(1.0, chain.spot * 0.01):
            tags.append("pin zone")
        if row.put_oi >= 20000:
            tags.append("put cluster")
        if row.call_oi >= 20000:
            tags.append("call cluster")
        out.append(
            {
                "strike": row.strike,
                "call_oi": _number(row.call_oi),
                "put_oi": _number(row.put_oi),
                "total_oi": _number(row.total_oi),
                "volume": _number(row.total_volume),
                "tags": tags,
            }
        )
    return out


def compute(chain: Chain) -> dict:
    oi = max_pain(chain, "oi")
    try:
        volume = max_pain(chain, "volume")
    except TickerUnavailable:
        volume = None
    blend = max_pain(chain, "blend")
    call_wall, put_wall = walls(chain)
    pc_oi, pc_volume = ratios(chain)
    atm = atm_metrics(chain)
    rr = risk_reversal(chain)
    current_gex = net_gex(chain, chain.spot, atm["iv"])
    if atm["iv"] is None and current_gex == 0:
        current_gex = None
    flip = gamma_flip(chain, atm["iv"])
    levels = [oi["strike"], blend["strike"]]
    if volume:
        levels.append(volume["strike"])
    confidence, spread_pct = pin_confidence(levels, chain.spot)
    slope_step = 0.5
    slope = (
        payout(chain, chain.spot + slope_step, "oi")
        - payout(chain, chain.spot - slope_step, "oi")
    ) / (2 * slope_step)
    distance_pct = (oi["strike"] / chain.spot - 1) * 100 if chain.spot else None

    return {
        "max_pain": {
            "oi": oi["strike"],
            "oi_minimum_payout": oi["minimum_payout"],
            "volume": volume["strike"] if volume else None,
            "blend": blend["strike"],
            "shelf_1pct": oi["shelf"],
            "shelf_width": len(oi["shelf"]),
            "distance_pct": distance_pct,
            "method_spread_pct": spread_pct,
            "pin_confidence": confidence,
        },
        "payout": {
            "at_spot": payout(chain, chain.spot, "oi"),
            "slope_per_dollar": slope,
            "minimum": oi["minimum_payout"],
        },
        "walls": {"call": call_wall, "put": put_wall},
        "ratios": {"pc_oi": pc_oi, "pc_volume": pc_volume},
        "volatility": {
            "atm_strike": atm["strike"],
            "atm_iv": atm["iv"],
            "atm_straddle": atm["straddle"],
            "one_sigma_move": atm["one_sigma_move"],
            "one_sigma_range": atm["one_sigma_range"],
            "risk_reversal_25d_points": rr["points"],
            "risk_reversal_legs": rr,
        },
        "gamma": {
            "net_gex_per_1pct": current_gex,
            "flip": flip,
            "fallback_iv": atm["iv"],
        },
        "top_strikes": top_strikes(chain, oi["strike"], call_wall["strike"], put_wall["strike"]),
        "totals": {
            "call_oi": sum(row.call_oi for row in chain.rows),
            "put_oi": sum(row.put_oi for row in chain.rows),
            "call_volume": sum(row.call.volume if row.call else 0 for row in chain.rows),
            "put_volume": sum(row.put.volume if row.put else 0 for row in chain.rows),
            "strikes": len(chain.rows),
        },
    }


def snapshot(chain: Chain, requested_expiry: date, include_chain: bool) -> dict:
    metrics = compute(chain)
    out = {
        "ticker": chain.ticker,
        "spot": chain.spot,
        "prev_close": chain.prev_close,
        "change_pct": chain.change_pct,
        "as_of": chain.as_of,
        "quote_timestamp": chain.payload_timestamp,
        "expiry": chain.expiry.isoformat(),
        "requested_expiry": requested_expiry.isoformat(),
        "expiry_drift_days": (chain.expiry - requested_expiry).days,
        "dte": chain.dte,
        "metrics": metrics,
    }
    if include_chain:
        out["chain"] = [row.to_dict() for row in chain.rows]
    return out


def _sort_key(snap: dict) -> tuple:
    distance = snap["metrics"]["max_pain"].get("distance_pct")
    return (abs(distance) if distance is not None else float("inf"), snap["ticker"])


def summarize(
    snapshots: list[dict],
    requested_expiry: date,
    as_of: str,
    limit: Optional[int] = None,
    show_expiry: bool = False,
) -> str:
    ordered = sorted(snapshots, key=_sort_key)
    shown = ordered[:limit] if limit else ordered
    header = (
        f"{'Ticker':<7} {'Spot':>8} {'OI max':>8} {'Away':>7} "
        f"{'Vol max':>8} {'Blend':>8} {'Shelf':>9}"
    )
    if show_expiry:
        header += f" {'Exp':>11} {'DTE':>4}"
    header += f" {'Pin':>8}"
    lines = [
        f"Max-pain snapshot — as of {as_of} · requested expiry {requested_expiry.isoformat()}",
        "",
        header,
    ]
    for snap in shown:
        metrics = snap["metrics"]
        pain = metrics["max_pain"]
        distance = pain.get("distance_pct")
        away = f"{distance:+.2f}%" if distance is not None else "—"
        shelf = pain["shelf_1pct"]
        shelf_text = f"{shelf[0]:g}" if len(shelf) == 1 else f"{shelf[0]:g}–{shelf[-1]:g}"
        volume = pain["volume"]
        volume_text = f"{volume:.2f}" if volume is not None else "—"
        row = (
            f"{snap['ticker']:<7} {snap['spot']:>8.2f} {pain['oi']:>8.2f} {away:>7} "
            f"{volume_text:>8} {pain['blend']:>8.2f} {shelf_text:>9}"
        )
        if show_expiry:
            expiry = snap["expiry"][5:].replace("-", "/")
            drift = snap.get("expiry_drift_days", 0)
            marker = "" if drift == 0 else f"+{drift}d" if drift > 0 else f"{drift}d"
            row += f" {expiry + marker:>13} {snap['dte']:>4}"
        row += f" {pain['pin_confidence']:>8}"
        lines.append(row)
    if limit and len(ordered) > limit:
        lines.append(f"... {len(ordered) - limit} more in the JSON snapshot")
    return "\n".join(lines)


def _cell(value, text: str, sort_value=None, css: str = "") -> str:
    attr = "" if sort_value is None else f' data-v="{sort_value}"'
    klass = f' class="{css}"' if css else ""
    return f"<td{klass}{attr}>{html.escape(text)}</td>"


def render_html(
    snapshots: list[dict],
    requested_expiry: date,
    as_of: str,
    out_path: Path,
    universe: Optional[dict],
) -> None:
    ordered = sorted(snapshots, key=_sort_key)
    rows = []
    for snap in ordered:
        metrics = snap["metrics"]
        pain = metrics["max_pain"]
        vol = metrics["volatility"]
        gamma = metrics["gamma"]
        distance = pain.get("distance_pct")
        away = "—" if distance is None else f"{distance:+.2f}%"
        away_class = "up" if distance is not None and distance > 0 else "down" if distance is not None else ""
        shelf = pain["shelf_1pct"]
        shelf_text = f"{shelf[0]:g}" if len(shelf) == 1 else f"{shelf[0]:g}–{shelf[-1]:g}"
        sigma = vol["one_sigma_range"]
        sigma_text = "—" if not sigma else f"{sigma[0]:.2f}–{sigma[1]:.2f}"
        iv_text = "—" if vol["atm_iv"] is None else f"{vol['atm_iv'] * 100:.1f}%"
        gex = gamma["net_gex_per_1pct"]
        gex_text = _money(gex)
        flip = "—" if gamma["flip"] is None else f"{gamma['flip']:.2f}"
        drift = snap.get("expiry_drift_days", 0)
        exp_text = snap["expiry"][5:].replace("-", "/") + ("" if drift == 0 else f" +{drift}d")
        pin = pain["pin_confidence"]
        pin_class = pin.lower()
        rows.append(
            "<tr>"
            + _cell(snap["ticker"], snap["ticker"], snap["ticker"], "ticker")
            + _cell(snap["spot"], f"{snap['spot']:.2f}", round(snap["spot"], 4))
            + _cell(pain["oi"], f"{pain['oi']:g}", pain["oi"], "pin")
            + _cell(distance, away, distance if distance is not None else -999, away_class)
            + _cell(
                pain["volume"],
                "—" if pain["volume"] is None else f"{pain['volume']:g}",
                pain["volume"] if pain["volume"] is not None else -999,
            )
            + _cell(pain["blend"], f"{pain['blend']:g}", pain["blend"])
            + _cell(len(shelf), shelf_text, len(shelf))
            + _cell(snap["expiry"], exp_text, snap["expiry"] + f"|{snap['dte']:04d}")
            + _cell(snap["dte"], str(snap["dte"]), snap["dte"])
            + _cell(pin, pin, {"High": 0, "Moderate": 1, "Low": 2}.get(pin, 3), f"badge {pin_class}")
            + _cell(metrics["ratios"]["pc_oi"], "—" if metrics["ratios"]["pc_oi"] is None else f"{metrics['ratios']['pc_oi']:.2f}", metrics["ratios"]["pc_oi"])
            + _cell(vol["atm_iv"], iv_text, vol["atm_iv"])
            + _cell(sigma, sigma_text, sigma[1] if sigma else None)
            + _cell(gex, gex_text, gex)
            + _cell(gamma["flip"], flip, gamma["flip"])
            + "</tr>"
        )

    loaded = len(snapshots)
    exact = sum(1 for snap in snapshots if snap.get("expiry_drift_days", 0) == 0)
    universe_label = ""
    if universe:
        universe_label = (
            f'<p class="note">Universe: QQQ holdings via <a href="{QQQ_LIST_URL}">Wikipedia</a> · '
            f"{universe['loaded']} loaded · {len(universe['skipped'])} skipped · "
            f"{exact} on the requested expiry.</p>"
        )

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QQQ max-pain board — {requested_expiry.isoformat()}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #070b12;
  --panel: #0d1623;
  --panel-2: #111d2d;
  --line: rgba(158, 181, 211, .16);
  --text: #eef3fa;
  --muted: #93a4bb;
  --dim: #64758c;
  --pin: #ffca62;
  --up: #47dfa1;
  --down: #ff7d89;
  --mono: "SFMono-Regular", "Cascadia Code", Consolas, monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: radial-gradient(900px 520px at 12% -8%, rgba(59, 216, 182, .10), transparent 62%),
              radial-gradient(900px 520px at 92% 0%, rgba(134, 165, 255, .10), transparent 62%),
              var(--bg);
  color: var(--text);
  font-family: var(--sans);
  font-variant-numeric: tabular-nums;
}}
.wrap {{ max-width: 1500px; margin: 0 auto; padding: 34px 26px 60px; }}
header {{ display: flex; flex-wrap: wrap; gap: 18px; justify-content: space-between; align-items: end; margin-bottom: 22px; }}
h1 {{ margin: 0; font-size: clamp(28px, 4vw, 46px); letter-spacing: -.03em; }}
h1 em {{ color: var(--pin); font-style: normal; }}
.kicker {{ color: var(--dim); font-family: var(--mono); font-size: 10px; letter-spacing: .16em; text-transform: uppercase; }}
.sub {{ color: var(--muted); font-size: 13px; max-width: 760px; line-height: 1.6; margin: 8px 0 0; }}
.note {{ color: var(--muted); font-size: 12px; margin: 4px 0 18px; }}
.note a {{ color: var(--pin); }}
.tools {{ display: flex; gap: 10px; align-items: center; margin: 0 0 14px; }}
input[type=search] {{
  width: min(340px, 100%);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 10px;
  color: var(--text);
  padding: 10px 13px;
  font: inherit;
  outline: none;
}}
input[type=search]:focus {{ border-color: rgba(255, 202, 98, .55); }}
.table-wrap {{ overflow: auto; border: 1px solid var(--line); border-radius: 16px; background: rgba(13, 22, 35, .82); }}
table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
th, td {{ padding: 10px 11px; border-bottom: 1px solid var(--line); text-align: right; white-space: nowrap; }}
th {{ position: sticky; top: 0; z-index: 1; background: var(--panel-2); color: var(--muted); font-size: 10px; letter-spacing: .1em; text-transform: uppercase; cursor: pointer; user-select: none; }}
th:first-child, td:first-child {{ text-align: left; }}
tbody tr:hover {{ background: rgba(255, 202, 98, .035); }}
td {{ font-family: var(--mono); font-size: 12px; }}
td.ticker {{ font-family: var(--sans); font-weight: 700; font-size: 13px; letter-spacing: .01em; }}
td.pin {{ color: var(--pin); font-weight: 700; }}
td.up {{ color: var(--up); }}
td.down {{ color: var(--down); }}
.badge {{ font-family: var(--sans); font-size: 10px; letter-spacing: .05em; text-transform: uppercase; }}
.badge.high {{ color: var(--up); }}
.badge.moderate {{ color: var(--pin); }}
.badge.low {{ color: var(--down); }}
.footer {{ color: var(--dim); font-size: 11px; line-height: 1.7; margin-top: 16px; }}
@media (max-width: 700px) {{
  .wrap {{ padding: 22px 14px 40px; }}
  th, td {{ padding: 9px 8px; }}
}}
</style>
</head>
<body>
<main class="wrap">
<header>
  <div>
    <div class="kicker">QQQ max-pain board</div>
    <h1>Where the pin sits, <em>across the Nasdaq-100.</em></h1>
    <p class="sub">Open-interest max pain for every loadable QQQ holding, with the volume and blended
    variants, the 1% shelf, the implied range, and modeled dealer gamma. Ranked by distance from spot.</p>
  </div>
  <div class="kicker">As of {html.escape(as_of)}<br>Requested expiry {requested_expiry.isoformat()}</div>
</header>
{universe_label}
<div class="tools">
  <input id="search" type="search" placeholder="Filter tickers…" autocomplete="off" spellcheck="false">
  <span class="note" style="margin:0">{loaded} tickers</span>
</div>
<div class="table-wrap">
<table id="board">
<thead><tr>
<th>Ticker</th><th>Spot</th><th>OI max</th><th>Away</th><th>Vol max</th><th>Blend</th><th>Shelf</th>
<th>Exp</th><th>DTE</th><th>Pin</th><th>P/C OI</th><th>ATM IV</th><th>1σ range</th><th>GEX / 1%</th><th>Flip</th>
</tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</div>
<p class="footer">Data: Cboe delayed quotes. Open interest is the latest published value; intraday volume is partial.
Max pain is descriptive, not a forecast. Not investment advice.</p>
</main>
<script>
const table = document.getElementById('board');
const headers = [...table.querySelectorAll('th')];
headers.forEach((th, index) => {{
  th.addEventListener('click', () => {{
    const tbody = table.querySelector('tbody');
    const rows = [...tbody.querySelectorAll('tr')];
    const ascending = th.dataset.order !== 'asc';
    headers.forEach(other => delete other.dataset.order);
    th.dataset.order = ascending ? 'asc' : 'desc';
    rows.sort((a, b) => {{
      const left = a.children[index];
      const right = b.children[index];
      const lv = left.dataset.v !== undefined ? Number(left.dataset.v) : left.textContent;
      const rv = right.dataset.v !== undefined ? Number(right.dataset.v) : right.textContent;
      if (typeof lv === 'number' && typeof rv === 'number') return ascending ? lv - rv : rv - lv;
      return ascending ? String(lv).localeCompare(String(rv)) : String(rv).localeCompare(String(lv));
    }});
    rows.forEach(row => tbody.appendChild(row));
  }});
}});
document.getElementById('search').addEventListener('input', event => {{
  const query = event.target.value.trim().toUpperCase();
  for (const row of table.querySelectorAll('tbody tr')) {{
    row.style.display = row.children[0].textContent.includes(query) ? '' : 'none';
  }}
}});
</script>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(document, encoding="utf-8")


def default_expiry(today: date) -> date:
    """Next Friday on or after today."""
    return today + timedelta(days=(4 - today.weekday()) % 7)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date {value!r}; use YYYY-MM-DD") from exc


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--tickers", nargs="+", help="option roots (default: SPY QQQ)")
    parser.add_argument("--universe", choices=["qqq"], help="load every QQQ holding")
    parser.add_argument("--expiry", type=parse_date, help="requested expiry (default: next Friday)")
    parser.add_argument(
        "--expiry-mode",
        choices=["auto", "exact", "nearest"],
        default="auto",
        help="exact skips missing expiries; nearest uses the next listed expiry; auto is exact for tickers, nearest for a universe",
    )
    parser.add_argument("--workers", type=int, default=4, help="parallel Cboe requests (default: 4)")
    parser.add_argument(
        "--chains",
        choices=["auto", "full", "none"],
        default="auto",
        help="include per-strike chains in the JSON (auto: full for tickers, none for a universe)",
    )
    parser.add_argument("--summary-limit", type=int, help="rows to print; default all for tickers, 25 for a universe")
    parser.add_argument("--html-out", type=Path, help="write a standalone HTML board")
    parser.add_argument("--out", type=Path, help="output JSON path")
    parser.add_argument("--timeout", type=float, default=45.0, help="request timeout in seconds")
    parser.add_argument("--quiet", action="store_true", help="do not print the summary table")
    args = parser.parse_args(argv)

    requested_expiry = args.expiry or default_expiry(date.today())
    universe = None
    if args.universe:
        tickers = fetch_qqq_constituents(args.timeout)
        expiry_mode = "nearest" if args.expiry_mode == "auto" else args.expiry_mode
        include_chain = args.chains == "full"
        universe = {
            "name": args.universe,
            "source": QQQ_LIST_URL,
            "requested": len(tickers),
            "loaded": 0,
            "skipped": [],
        }
    else:
        tickers = args.tickers or ["SPY", "QQQ"]
        expiry_mode = "exact" if args.expiry_mode == "auto" else args.expiry_mode
        include_chain = args.chains != "none"
    if args.chains == "none":
        include_chain = False

    def load_batch(
        batch: list[str], throttle: Throttle, workers: int
    ) -> tuple[dict[str, Chain], list[dict]]:
        loaded: dict[str, Chain] = {}
        failed: list[dict] = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {
                pool.submit(
                    load_chain, ticker, requested_expiry, expiry_mode, args.timeout, throttle
                ): ticker
                for ticker in batch
            }
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    chain, _ = future.result()
                except Exception as exc:
                    failed.append({"ticker": ticker, "reason": str(exc)})
                else:
                    loaded[ticker] = chain
        return loaded, failed

    chains, skipped = load_batch(tickers, Throttle(), args.workers)
    rate_limited = [item["ticker"] for item in skipped if "rate" in item["reason"].lower()]
    if rate_limited:
        time.sleep(3)
        retry_chains, retry_skipped = load_batch(
            rate_limited, Throttle(1.0), max(1, min(2, args.workers))
        )
        chains.update(retry_chains)
        skipped = [
            item for item in skipped if item["ticker"] not in retry_chains
        ] + retry_skipped

    if not chains:
        raise SystemExit("no tickers loaded")

    snapshots = [
        snapshot(chain, requested_expiry, include_chain)
        for _, chain in sorted(chains.items())
    ]
    as_of = max(chain.as_of for chain in chains.values())
    if universe:
        universe["loaded"] = len(snapshots)
        universe["skipped"] = sorted(skipped, key=lambda item: item["ticker"])

    result = {
        "schema_version": 2,
        "kind": "options_max_pain_snapshot",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "name": "Cboe delayed quotes",
            "url": CBOE_URL.format(ticker="{ticker}"),
            "delay": "vendor-delayed intraday quotes",
            "note": "Open interest is the exchange's latest published value; intraday volume is partial.",
        },
        "as_of": as_of,
        "requested_expiry": requested_expiry.isoformat(),
        "expiry_mode": expiry_mode,
        "settlement": "PM close",
        "universe": universe,
        "tickers": [snap["ticker"] for snap in snapshots],
        "snapshots": snapshots,
        "method": {
            "max_pain": "For every listed strike, sum intrinsic payout at that settlement: calls OI × max(0, S−K) + puts OI × max(0, K−S), times 100. Minimum wins.",
            "blend": "Open interest + 0.5 × session volume, per side.",
            "shelf": "Strikes whose total payout is within 1% of the minimum.",
            "one_sigma": "Spot × ATM IV × sqrt(DTE / 365). ATM IV is the mean of the nearest-strike call and put IVs.",
            "risk_reversal": "25-delta put IV minus 25-delta call IV, in volatility points.",
            "gex": "Black-Scholes gamma at each hypothetical spot × OI × 100 × S² × 0.01; calls positive, puts negative.",
            "gamma_flip": "Nearest modeled zero crossing of net GEX within ±15% of spot.",
            "pin_confidence": "High if the OI, volume, and blend max pains are within 0.5% of spot; Moderate within 1%; otherwise Low.",
        },
    }

    out_path = args.out
    if out_path is None:
        stamp = datetime.fromisoformat(as_of).date().isoformat()
        if universe:
            out_path = DEFAULT_OUT_DIR / f"{requested_expiry.isoformat()}-qqq-holdings-{stamp}.json"
        else:
            names = "-".join(ticker.lower() for ticker in tickers)
            out_path = DEFAULT_OUT_DIR / f"{requested_expiry.isoformat()}-{names}-{stamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if args.html_out:
        render_html(snapshots, requested_expiry, as_of, args.html_out, universe)
        if not args.quiet:
            print(f"Wrote {args.html_out}")

    if not args.quiet:
        limit = args.summary_limit
        if limit is None:
            limit = 25 if universe else None
        print(summarize(snapshots, requested_expiry, as_of, limit=limit, show_expiry=bool(universe)))
        if skipped:
            print(f"\nSkipped {len(skipped)}: " + ", ".join(item["ticker"] for item in skipped))
        print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
