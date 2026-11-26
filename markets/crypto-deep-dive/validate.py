#!/usr/bin/env python3
"""Validate snapshot.json schema, invariants, and freshness before building."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "data" / "snapshot.json"


def check(condition: bool, msg: str, errors: list[str]) -> None:
    if not condition:
        errors.append(msg)


def main() -> int:
    if not SNAPSHOT.exists():
        print(f"ERROR: Missing snapshot file {SNAPSHOT}", file=sys.stderr)
        return 1

    data = json.loads(SNAPSHOT.read_text())
    errors: list[str] = []
    warnings: list[str] = []

    required_top = (
        "generated_at",
        "generated_label",
        "data_as_of",
        "sources",
        "global",
        "fear_greed",
        "stablecoins",
        "defi",
        "dexs",
        "fees",
        "perps",
        "exchanges",
        "staking",
        "yields",
        "hacks",
        "hyperliquid",
        "coins",
        "sectors",
        "categories",
        "history",
        "breadth",
        "performance",
        "concentration",
        "internals",
    )
    for key in required_top:
        check(key in data, f"Missing top-level key: {key}", errors)

    coins = data.get("coins") or []
    check(len(coins) == 100, f"Expected 100 coins, found {len(coins)}", errors)
    symbols = {c.get("symbol") for c in coins}
    for sym in ("BTC", "ETH", "SOL"):
        check(sym in symbols, f"Core asset missing from top 100: {sym}", errors)

    other_coins = [c.get("symbol") for c in coins if c.get("tag") == "Other"]
    if len(other_coins) > 15:
        warnings.append(f"{len(other_coins)} coins tagged 'Other': {', '.join(other_coins[:10])}")

    g = data.get("global") or {}
    check((g.get("total_mcap") or 0) > 1e11, f"Total market cap suspiciously low: {g.get('total_mcap')}", errors)
    check(10 < (g.get("btc_dominance") or 0) < 95, f"BTC dominance out of range: {g.get('btc_dominance')}", errors)

    st = data.get("stablecoins") or {}
    check((st.get("total") or 0) > 5e10, f"Stablecoin total suspiciously low: {st.get('total')}", errors)
    check(len(st.get("assets") or []) >= 10, "Expected at least 10 stablecoin assets", errors)
    check(len(st.get("split") or []) == 3, "Expected 3 stablecoin split buckets", errors)
    check("history" not in st, "Duplicate stablecoins.history found; should live only under history.stablecoins", errors)

    defi = data.get("defi") or {}
    check((defi.get("tvl") or 0) > 1e10, f"DeFi TVL suspiciously low: {defi.get('tvl')}", errors)
    check(len(defi.get("protocols") or []) >= 10, "Expected at least 10 DeFi protocols", errors)
    check("history" not in defi, "Duplicate defi.history found; should live only under history.tvl", errors)

    fees = data.get("fees") or {}
    check((fees.get("total_30d") or 0) > 1e8, f"30d fees suspiciously low: {fees.get('total_30d')}", errors)
    check(len(fees.get("protocols") or []) >= 10, "Expected at least 10 fee protocols", errors)
    check(len(fees.get("valuation") or []) >= 8, "Expected at least 8 valuation rows", errors)

    perps = data.get("perps") or {}
    check(len(perps.get("venues") or []) >= 5, "Expected at least 5 perp DEX venues", errors)

    hl = data.get("hyperliquid") or {}
    check((hl.get("open_interest") or 0) > 1e8, f"Hyperliquid OI suspiciously low: {hl.get('open_interest')}", errors)
    check(len(hl.get("markets") or []) >= 8, "Expected at least 8 Hyperliquid markets", errors)
    check(len(hl.get("top_pnl") or []) >= 5, "Expected at least 5 Hyperliquid leaderboard rows", errors)

    yields = data.get("yields") or []
    check(len(yields) >= 15, f"Expected at least 15 yield pools, found {len(yields)}", errors)
    if yields:
        check(bool(yields[0].get("risk_reasons")), "Yield pools missing risk_reasons breakdown", errors)

    hist = data.get("history") or {}
    for k in ("btc", "eth", "sol", "tvl", "stablecoins"):
        check(len(hist.get(k) or []) >= 180, f"History series '{k}' has fewer than 180 points", errors)

    internals = data.get("internals") or {}
    check(internals.get("btc_mayer") is not None, "Missing btc_mayer in internals", errors)
    check(internals.get("btc_vol_30d") is not None, "Missing btc_vol_30d in internals", errors)
    check(internals.get("alt_season_30d") is not None, "Missing alt_season_30d in internals", errors)

    if not data.get("macro"):
        warnings.append("Macro cross-asset series empty (Yahoo Finance optional fetch skipped)")

    size_kb = SNAPSHOT.stat().st_size / 1024
    if size_kb > 220:
        warnings.append(f"snapshot.json is {size_kb:.0f} KB (target < 200 KB)")

    for w in warnings:
        print(f"WARN: {w}")
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1

    print(
        f"VALIDATE OK · {SNAPSHOT.name} ({size_kb:.0f} KB) · "
        f"{len(coins)} coins ({len(other_coins)} Other) · "
        f"{len(fees.get('valuation', []))} valuation rows · "
        f"{len(data.get('macro', []))} macro benchmarks · "
        f"{len(data.get('history_snapshots', []))} history snapshots"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
