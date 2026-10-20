#!/usr/bin/env python3
"""Compute a max-pain snapshot for listed ETF options.

Fetches the full option chain from Cboe's delayed-quote endpoint, filters one
expiry, and writes a reproducible JSON snapshot with:

  * open-interest, volume, and blended max pain
  * the 1% pain shelf
  * call and put walls plus the largest strikes by combined OI
  * ATM implied volatility, ATM straddle, and the 1-sigma implied range
  * the 25-delta risk reversal
  * modeled net gamma exposure (GEX) and the gamma flip
  * put/call ratios, payout at spot, and the pain slope at spot

Usage:
    python3 markets/options/max_pain.py --tickers SPY QQQ --expiry 2026-10-23

By default the snapshot is written to markets/options/data/ with a filename
that includes the expiry and the quote date. Pass --out to override it.
Requires only requests.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean
from typing import Iterable, Optional

CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{ticker}.json"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
OCC_RE = re.compile(r"^(?P<root>[A-Z_]+)(?P<ymd>\d{6})(?P<kind>[CP])(?P<strike>\d{8})$")
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = SCRIPT_DIR / "data"


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
        return {k: v for k, v in out.items() if v is not None}


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


def fetch_payload(ticker: str, timeout: float) -> dict:
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise SystemExit("requests is required: python3 -m pip install requests") from exc

    url = CBOE_URL.format(ticker=ticker.upper())
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise SystemExit(f"could not fetch {ticker} from Cboe: {exc}") from exc

    if not isinstance(payload, dict) or "data" not in payload:
        raise SystemExit(f"unexpected Cboe response for {ticker}")
    return payload


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
        raise SystemExit(f"{ticker}: no contracts found for {expiry.isoformat()}")

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
        raise SystemExit(f"{chain.ticker}: no {field_name} data for {chain.expiry.isoformat()}")

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
    row = min(chain.rows, key=lambda item: abs(item.strike - chain.spot))
    ivs = [leg.iv for leg in (row.call, row.put) if leg and leg.iv and leg.iv > 0]
    mids = [leg.mid for leg in (row.call, row.put) if leg and leg.mid is not None]
    atm_iv = _mean(ivs) if ivs else None
    sigma = chain.spot * atm_iv * math.sqrt(chain.t_years) if atm_iv else None
    return {
        "strike": row.strike,
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
    volume = max_pain(chain, "volume")
    blend = max_pain(chain, "blend")
    call_wall, put_wall = walls(chain)
    pc_oi, pc_volume = ratios(chain)
    atm = atm_metrics(chain)
    rr = risk_reversal(chain)
    current_gex = net_gex(chain, chain.spot, atm["iv"])
    flip = gamma_flip(chain, atm["iv"])
    confidence, spread_pct = pin_confidence(
        [oi["strike"], volume["strike"], blend["strike"]], chain.spot
    )
    slope_step = 0.5
    slope = (
        payout(chain, chain.spot + slope_step, "oi")
        - payout(chain, chain.spot - slope_step, "oi")
    ) / (2 * slope_step)

    return {
        "max_pain": {
            "oi": oi["strike"],
            "oi_minimum_payout": oi["minimum_payout"],
            "volume": volume["strike"],
            "blend": blend["strike"],
            "shelf_1pct": oi["shelf"],
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


def snapshot(chain: Chain) -> dict:
    metrics = compute(chain)
    return {
        "ticker": chain.ticker,
        "spot": chain.spot,
        "prev_close": chain.prev_close,
        "change_pct": chain.change_pct,
        "as_of": chain.as_of,
        "quote_timestamp": chain.payload_timestamp,
        "expiry": chain.expiry.isoformat(),
        "dte": chain.dte,
        "chain": [row.to_dict() for row in chain.rows],
        "metrics": metrics,
    }


def summarize(snapshots: list[dict], expiry: date, as_of: str) -> str:
    lines = [
        f"Max-pain snapshot — as of {as_of} · expiry {expiry.isoformat()}",
        "",
        f"{'Ticker':<7}{'Spot':>9}{'OI max':>9}{'Vol max':>9}{'Blend':>9}"
        f"{'1σ range':>20}{'ATM IV':>9}{'P/C OI':>8}{'GEX/1%':>11}{'Flip':>9}{'Pin':>10}",
    ]
    for snap in snapshots:
        metrics = snap["metrics"]
        pain = metrics["max_pain"]
        vol = metrics["volatility"]
        gamma = metrics["gamma"]
        sigma = vol["one_sigma_range"]
        sigma_text = f"{sigma[0]:.2f}–{sigma[1]:.2f}" if sigma else "—"
        iv_text = f"{vol['atm_iv'] * 100:.1f}%" if vol["atm_iv"] else "—"
        gex_text = f"${gamma['net_gex_per_1pct'] / 1e9:+.2f}B" if gamma["net_gex_per_1pct"] else "—"
        flip_text = f"{gamma['flip']:.2f}" if gamma["flip"] else "—"
        pc_text = f"{metrics['ratios']['pc_oi']:.2f}" if metrics["ratios"]["pc_oi"] else "—"
        lines.append(
            f"{snap['ticker']:<7}{snap['spot']:>9.2f}{pain['oi']:>9.2f}{pain['volume']:>9.2f}"
            f"{pain['blend']:>9.2f}{sigma_text:>20}{iv_text:>9}{pc_text:>8}{gex_text:>11}"
            f"{flip_text:>9}{pain['pin_confidence']:>10}"
        )
    return "\n".join(lines)


def default_expiry(today: date) -> date:
    """Next Friday on or after today."""
    return today + timedelta(days=(4 - today.weekday()) % 7)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date {value!r}; use YYYY-MM-DD") from exc


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tickers", nargs="+", default=["SPY", "QQQ"], help="option roots (default: SPY QQQ)")
    parser.add_argument("--expiry", type=parse_date, help="expiry date (default: next Friday)")
    parser.add_argument("--out", type=Path, help="output JSON path")
    parser.add_argument("--timeout", type=float, default=60.0, help="request timeout in seconds")
    parser.add_argument("--quiet", action="store_true", help="do not print the summary table")
    args = parser.parse_args(argv)

    expiry = args.expiry or default_expiry(date.today())
    chains = []
    for ticker in args.tickers:
        chains.append(build_chain(fetch_payload(ticker, args.timeout), ticker, expiry))

    snapshots = [snapshot(chain) for chain in chains]
    as_of = max(chain.as_of for chain in chains)
    result = {
        "schema_version": 1,
        "kind": "options_max_pain_snapshot",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "name": "Cboe delayed quotes",
            "url": CBOE_URL.format(ticker="{ticker}"),
            "delay": "vendor-delayed intraday quotes",
            "note": "Open interest is the exchange's latest published value; intraday volume is partial.",
        },
        "as_of": as_of,
        "expiry": expiry.isoformat(),
        "dte": chains[0].dte if chains else None,
        "settlement": "PM close",
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
        names = "-".join(snap["ticker"].lower() for snap in snapshots)
        out_path = DEFAULT_OUT_DIR / f"{expiry.isoformat()}-{names}-{stamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if not args.quiet:
        print(summarize(snapshots, expiry, as_of))
        print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
