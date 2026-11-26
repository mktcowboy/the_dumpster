#!/usr/bin/env python3
"""Build the standalone crypto deep-dive page from the cached snapshot."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "template.html"
SNAPSHOT = ROOT / "data" / "snapshot.json"
OUTPUT = ROOT / "index.html"


def usd(value, digits=2):
    if value is None:
        return "—"
    sign = "-" if value < 0 else ""
    value = abs(float(value))
    for size, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if value >= size:
            return f"{sign}${value / size:.{digits}f}{suffix}"
    return f"{sign}${value:,.0f}"


def price(value):
    if value is None:
        return "—"
    value = float(value)
    if abs(value) >= 1000:
        return f"${value:,.0f}"
    if abs(value) >= 1:
        return f"${value:,.2f}"
    return f"${value:,.4f}"


def pct(value, digits=2):
    if value is None:
        return "—"
    return f"{float(value):+.{digits}f}%"


def rate(value, digits=2):
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}%"


def pct_class(value):
    if value is None:
        return "flat"
    value = float(value)
    return "up" if value > 0 else "down" if value < 0 else "flat"


def ordinal(value):
    if value is None:
        return "—"
    number = int(round(float(value)))
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def long_date(value):
    if not value:
        return "—"
    day = datetime.strptime(value, "%Y-%m-%d")
    return f"{day:%b} {day.day}, {day.year}"


def month_year(iso_ts):
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return f"{dt:%B %Y}"
    except Exception:
        return "Current snapshot"


def protocol_tvl(protocols, *names):
    lowered = {n.lower() for n in names}
    for row in protocols:
        if (row.get("name") or "").lower() in lowered:
            return row.get("tvl")
    for row in protocols:
        rname = (row.get("name") or "").lower()
        if any(n in rname for n in lowered):
            return row.get("tvl")
    return None


def describe_regime(btc_dd, eth_dd, btc_dom, stable_share, breadth_30d, mayer):
    btc_dd = btc_dd if btc_dd is not None else 0.0
    eth_dd = eth_dd if eth_dd is not None else 0.0
    breadth_30d = breadth_30d if breadth_30d is not None else 50

    if btc_dd <= -20 and breadth_30d < 50:
        headline = "A defensive tape with a growing dollar layer"
        tape_type = "defensive, dollar-heavy tape with narrow leadership"
        summary_title = "Two markets"
    elif btc_dd <= -12:
        headline = "A selective consolidation with deep dollar reserves"
        tape_type = "selective consolidation where cash-flow and dollar rails outpace broad beta"
        summary_title = "Selective rotation"
    elif breadth_30d >= 55:
        headline = "A risk-on tape with broadening participation"
        tape_type = "broad risk-on tape with expanding participation"
        summary_title = "Broad expansion"
    else:
        headline = "A top-heavy market led by bitcoin and dollars"
        tape_type = "top-heavy tape led by major reserve assets and stablecoin rails"
        summary_title = "Narrow leadership"

    mayer_note = f" BTC trades at {mayer:.2f}× its 200-day average." if mayer else ""
    aside = (
        f"BTC is <b class=\"warn-t\">{pct(btc_dd, 1)}</b> from its all-time high and ETH is "
        f"<b class=\"warn-t\">{pct(eth_dd, 1)}</b>. Stablecoins are <b>{rate(stable_share)}</b> of total market cap, "
        f"with {breadth_30d}/100 top assets green over 30 days.{mayer_note} This is a {tape_type}."
    )
    return headline, summary_title, aside


def describe_stable_trend(change_30d):
    if change_30d is None:
        return "steady"
    if change_30d > 2.0:
        return f"expanding ({pct(change_30d)} over 30 days)"
    if change_30d < -2.0:
        return f"contracting ({pct(change_30d)} over 30 days)"
    return f"essentially flat ({pct(change_30d)} over 30 days)"


def build_tokens(snapshot):
    global_stats = snapshot.get("global") or {}
    stablecoins = snapshot.get("stablecoins") or {}
    defi = snapshot.get("defi") or {}
    dexs = snapshot.get("dexs") or {}
    fees = snapshot.get("fees") or {}
    perps = snapshot.get("perps") or {}
    hyperliquid = snapshot.get("hyperliquid") or {}
    stats = hyperliquid.get("stats") or {}
    hacks = snapshot.get("hacks") or {}
    internals = snapshot.get("internals") or {}
    breadth = snapshot.get("breadth") or {}
    concentration = snapshot.get("concentration") or {}
    fear_greed = snapshot.get("fear_greed") or {}
    staking = snapshot.get("staking") or {}

    coins_list = snapshot.get("coins") or []
    coins = {coin["symbol"]: coin for coin in coins_list}
    performance = {row["symbol"]: row for row in (snapshot.get("performance") or [])}
    stable_assets = {row["symbol"]: row for row in (stablecoins.get("assets") or [])}
    largest_hack = (hacks.get("largest") or [{"name": "—", "amount": None}])[0]
    history = (snapshot.get("history") or {}).get("btc") or []

    btc = coins.get("BTC") or {}
    eth = coins.get("ETH") or {}
    sol = coins.get("SOL") or {}
    btc_perf = performance.get("BTC") or {}
    eth_perf = performance.get("ETH") or {}
    sol_perf = performance.get("SOL") or {}
    usdt = stable_assets.get("USDT") or {"supply": 0}
    usdc = stable_assets.get("USDC") or {"supply": 0}
    stable_total = stablecoins.get("total") or 1
    stable_count = sum(1 for coin in coins_list if coin.get("tag") == "Stablecoin")
    rwa_count = sum(1 for coin in coins_list if coin.get("tag") == "RWA")

    split_map = {row["key"]: row for row in (stablecoins.get("split") or [])}
    yield_stable = split_map.get("yield_synthetic") or {"supply": None, "share": None, "change_30d": None}

    cg_fng = global_stats.get("cg_fng") or {}
    cg_fng_val = str(cg_fng.get("value")) if cg_fng.get("value") is not None else "—"
    cg_fng_lbl = str(cg_fng.get("sentiment") or "Unavailable")

    b24_up = (breadth.get("change_24h") or {}).get("up", 0)
    b24_tot = (breadth.get("change_24h") or {}).get("total", len(coins_list))
    b30_up = (breadth.get("change_30d") or {}).get("up", 0)

    regime_headline, summary_title, regime_aside = describe_regime(
        btc.get("ath_change"),
        eth.get("ath_change"),
        global_stats.get("btc_dominance"),
        stablecoins.get("share_of_market"),
        b30_up,
        internals.get("btc_mayer"),
    )

    non_stable_movers = [
        c for c in coins_list
        if c.get("tag") != "Stablecoin" and (c.get("market_cap") or 0) > 500_000_000 and c.get("change_30d") is not None
    ]
    top_movers = sorted(non_stable_movers, key=lambda c: -c["change_30d"])[:3]
    top_movers_text = ", ".join(
        f"{c['symbol']} ({pct(c['change_30d'], 0)} 30d)" for c in top_movers
    ) or "selected large-cap leaders"

    fees_30d = fees.get("total_30d") or 0
    rev_30d = fees.get("revenue_30d") or 0
    agg_take_rate = (rev_30d / fees_30d * 100) if fees_30d > 0 else None

    hl_funding = hyperliquid.get("oi_weighted_funding_ann")
    hl_pos_oi = hyperliquid.get("positive_oi_share")
    hl_perp_share = perps.get("hl_fee_share")

    alt_season = internals.get("alt_season_30d")
    alt_label = (
        "Altcoin season" if (alt_season is not None and alt_season >= 75)
        else "Bitcoin season" if (alt_season is not None and alt_season <= 25)
        else "Mixed rotation"
    )

    eth_protocols = [
        p for p in (defi.get("protocols") or [])
        if "Ethereum" in (p.get("chains") or []) and p.get("category") not in ("Bridge", "Cross Chain Bridge", "Chain")
    ][:3]
    if len(eth_protocols) >= 3:
        eth_top3_prose = (
            f"{eth_protocols[0]['name']} holds about <strong>{usd(eth_protocols[0]['tvl'])}</strong>, "
            f"{eth_protocols[1]['name']} about <strong>{usd(eth_protocols[1]['tvl'])}</strong>, "
            f"and {eth_protocols[2]['name']} about <strong>{usd(eth_protocols[2]['tvl'])}</strong>."
        )
    else:
        eth_top3_prose = f"Top DeFi protocols on Ethereum account for a large share of the <strong>{usd(defi.get('tvl'))}</strong> in tracked TVL."

    return {
        "__MONTH_YEAR__": month_year(snapshot.get("data_as_of") or snapshot.get("generated_at") or ""),
        "__ETH_TOP3_PROSE__": eth_top3_prose,
        "__GENERATED_LABEL__": snapshot.get("generated_label") or "—",
        "__SNAPSHOT_JSON__": "",
        "__REGIME_HEADLINE__": regime_headline,
        "__SUMMARY_TITLE__": summary_title,
        "__REGIME_ASIDE__": regime_aside,
        "__STABLE_TREND_PROSE__": describe_stable_trend(stablecoins.get("change_30d")),
        "__TOP_MOVERS_PROSE__": top_movers_text,
        "__TOTAL_MCAP__": usd(global_stats.get("total_mcap")),
        "__TOTAL_VOL__": usd(global_stats.get("total_volume")),
        "__MCAP_CHANGE__": pct(global_stats.get("mcap_change_24h")),
        "__MCAP_CLASS__": pct_class(global_stats.get("mcap_change_24h")),
        "__VOL_CHANGE__": pct(global_stats.get("volume_change_24h")),
        "__BTC_DOM__": rate(global_stats.get("btc_dominance")),
        "__ETH_DOM__": rate(global_stats.get("eth_dominance")),
        "__STABLE_TOTAL__": usd(stable_total),
        "__STABLE_SHARE__": rate(stablecoins.get("share_of_market")),
        "__STABLE_COUNT__": str(stable_count),
        "__RWA_COUNT__": str(rwa_count),
        "__STABLE_30D__": pct(stablecoins.get("change_30d")),
        "__STABLE_30D_CLASS__": pct_class(stablecoins.get("change_30d")),
        "__USDT_SUPPLY__": usd(usdt.get("supply")),
        "__USDT_SHARE__": rate((usdt.get("supply") or 0) / stable_total * 100),
        "__USDC_SUPPLY__": usd(usdc.get("supply")),
        "__USDC_SHARE__": rate((usdc.get("supply") or 0) / stable_total * 100),
        "__YIELD_STABLE_SUPPLY__": usd(yield_stable.get("supply")),
        "__YIELD_STABLE_SHARE__": rate(yield_stable.get("share"), 1),
        "__YIELD_STABLE_30D__": pct(yield_stable.get("change_30d")),
        "__DEFI_TVL__": usd(defi.get("tvl")),
        "__DEFI_30D__": pct(defi.get("change_30d")),
        "__DEFI_CLASS__": pct_class(defi.get("change_30d")),
        "__FNG__": str(fear_greed.get("value", "—")),
        "__FNG_LABEL__": str(fear_greed.get("label") or "—"),
        "__CG_FNG__": cg_fng_val,
        "__CG_FNG_LABEL__": cg_fng_lbl,
        "__BREADTH_UP__": str(b24_up),
        "__BREADTH_TOTAL__": str(b24_tot),
        "__BREADTH_24H_UP__": str(b24_up),
        "__BREADTH_30D_UP__": str(b30_up),
        "__TOP10_SHARE__": rate(concentration.get("top10_share")),
        "__DEX_24H__": usd(dexs.get("volume_24h")),
        "__DEX_7D__": usd(dexs.get("volume_7d")),
        "__DEX_CHG_1D__": pct(dexs.get("change_1d"), 1),
        "__DEX_CHG_7D__": pct(dexs.get("change_7d"), 1),
        "__FEES_24H__": usd(fees.get("total_24h")),
        "__FEES_30D__": usd(fees.get("total_30d")),
        "__REV_24H__": usd(fees.get("revenue_24h")),
        "__REV_30D__": usd(fees.get("revenue_30d")),
        "__TAKE_RATE__": rate(agg_take_rate, 1),
        "__HL_VOL__": usd(hyperliquid.get("volume_24h")),
        "__HL_OI__": usd(hyperliquid.get("open_interest")),
        "__HL_FUNDING_ANN__": pct(hl_funding, 2),
        "__HL_FUNDING_CLASS__": pct_class(hl_funding),
        "__HL_POS_OI__": rate(hl_pos_oi, 1),
        "__HL_PERP_SHARE__": rate(hl_perp_share, 1),
        "__HL_ACCOUNTS__": f"{stats.get('accounts', 0):,}",
        "__HL_POSITIVE__": rate(stats.get("positive_share"), 1),
        "__HL_MEDIAN__": pct((stats.get("median_month_roi") or 0) * 100),
        "__HL_MEDIAN_CLASS__": pct_class(stats.get("median_month_roi")),
        "__HL_ACCOUNT_VALUE__": usd(stats.get("total_account_value")),
        "__HACKS_COUNT__": f"{hacks.get('count', 0):,}",
        "__HACKS_TOTAL__": usd(hacks.get("total")),
        "__HACKS_LARGEST__": str(largest_hack.get("name") or "—"),
        "__HACKS_LARGEST_AMOUNT__": usd(largest_hack.get("amount"), 1),
        "__COIN_COUNT__": str(len(coins_list)),
        "__BTC_PRICE__": price(btc.get("price")),
        "__BTC_MCAP__": usd(btc.get("market_cap")),
        "__BTC_ATH_DOWN__": pct(btc.get("ath_change"), 1),
        "__BTC_ATH__": price(btc.get("ath")),
        "__BTC_24H__": pct(btc_perf.get("change_24h")),
        "__BTC_24H_CLASS__": pct_class(btc_perf.get("change_24h")),
        "__BTC_30D__": pct(btc_perf.get("change_30d")),
        "__BTC_30D_CLASS__": pct_class(btc_perf.get("change_30d")),
        "__BTC_1Y__": pct(btc_perf.get("change_365d")),
        "__BTC_1Y_CLASS__": pct_class(btc_perf.get("change_365d")),
        "__BTC_MAYER__": f"{internals['btc_mayer']:.2f}×" if internals.get("btc_mayer") else "—",
        "__BTC_SMA_200__": price(internals.get("btc_sma_200")),
        "__BTC_VOL_30D__": rate(internals.get("btc_vol_30d"), 1),
        "__ETH_VOL_30D__": rate(internals.get("eth_vol_30d"), 1),
        "__SOL_VOL_30D__": rate(internals.get("sol_vol_30d"), 1),
        "__ALT_SEASON__": rate(alt_season, 0),
        "__ALT_SEASON_LABEL__": alt_label,
        "__ALT_BEATING__": str(internals.get("alt_beating_btc", 0)),
        "__ALT_SAMPLE__": str(internals.get("alt_sample", 50)),
        "__ETH_PRICE__": price(eth.get("price")),
        "__ETH_MCAP__": usd(eth.get("market_cap")),
        "__ETH_ATH_DOWN__": pct(eth.get("ath_change"), 1),
        "__ETH_ATH__": price(eth.get("ath")),
        "__ETH_24H__": pct(eth_perf.get("change_24h")),
        "__ETH_24H_CLASS__": pct_class(eth_perf.get("change_24h")),
        "__ETH_30D__": pct(eth_perf.get("change_30d")),
        "__ETH_30D_CLASS__": pct_class(eth_perf.get("change_30d")),
        "__ETH_1Y__": pct(eth_perf.get("change_365d")),
        "__ETH_1Y_CLASS__": pct_class(eth_perf.get("change_365d")),
        "__ETH_BTC__": f"{internals['eth_btc']:.4f}" if internals.get("eth_btc") else "—",
        "__ETH_BTC_PCT__": ordinal(internals.get("eth_btc_percentile")),
        "__ETH_BTC_30D__": pct(internals.get("eth_btc_change_30d")),
        "__SOL_PRICE__": price(sol.get("price")),
        "__SOL_MCAP__": usd(sol.get("market_cap")),
        "__SOL_ATH_DOWN__": pct(sol.get("ath_change"), 1),
        "__SOL_30D__": pct(sol_perf.get("change_30d")),
        "__SOL_30D_CLASS__": pct_class(sol_perf.get("change_30d")),
        "__ETH_STAKING_APY__": rate(staking.get("eth_apy")),
        "__SOL_STAKING_APY__": rate(staking.get("sol_apy")),
        "__ETH_STAKING_SRC__": str(staking.get("eth_source") or "stETH"),
        "__SOL_STAKING_SRC__": str(staking.get("sol_source") or "staked SOL"),
        "__AAVE_TVL__": usd(protocol_tvl(defi.get("protocols") or [], "Aave V3", "Aave")),
        "__MORPHO_TVL__": usd(protocol_tvl(defi.get("protocols") or [], "Morpho Blue", "Morpho")),
        "__EIGEN_TVL__": usd(protocol_tvl(defi.get("protocols") or [], "EigenCloud", "EigenLayer")),
        "__HISTORY_START__": long_date(history[0][0]) if history else "—",
        "__HISTORY_END__": long_date(history[-1][0]) if history else "—",
    }


def main():
    snapshot = json.loads(SNAPSHOT.read_text())
    template = TEMPLATE.read_text()
    tokens = build_tokens(snapshot)

    payload = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False)
    tokens["__SNAPSHOT_JSON__"] = payload.replace("</", "<\\/")

    html = template
    for token, value in tokens.items():
        html = html.replace(token, value)

    leftovers = sorted(set(re.findall(r"__[A-Z0-9_]+__", html)))
    if leftovers:
        raise SystemExit("Unreplaced tokens: " + ", ".join(leftovers))
    if "__SNAPSHOT_JSON__" in html:
        raise SystemExit("Snapshot placeholder was not replaced")

    OUTPUT.write_text(html)
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
