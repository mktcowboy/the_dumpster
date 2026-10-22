#!/usr/bin/env python3
"""Build the standalone crypto deep-dive page from the cached snapshot."""
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
    value = abs(value)
    for size, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if value >= size:
            return f"{sign}${value / size:.{digits}f}{suffix}"
    return f"{sign}${value:,.0f}"


def price(value):
    if value is None:
        return "—"
    if abs(value) >= 1000:
        return f"${value:,.0f}"
    if abs(value) >= 1:
        return f"${value:,.2f}"
    return f"${value:,.4f}"


def pct(value, digits=2):
    if value is None:
        return "—"
    return f"{value:+.{digits}f}%"


def pct_class(value):
    if value is None:
        return "flat"
    return "up" if value > 0 else "down" if value < 0 else "flat"


def ordinal(value):
    number = int(round(value))
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def long_date(value):
    day = datetime.strptime(value, "%Y-%m-%d")
    return f"{day:%b} {day.day}, {day.year}"


def protocol_tvl(protocols, name):
    match = next((row for row in protocols if row["name"] == name), None)
    return match["tvl"] if match else None


def pool_apy(pools, symbol):
    match = next((row for row in pools if row["symbol"] == symbol), None)
    return match["apy"] if match else None


def build_tokens(snapshot):
    global_stats = snapshot["global"]
    stablecoins = snapshot["stablecoins"]
    defi = snapshot["defi"]
    dexs = snapshot["dexs"]
    hyperliquid = snapshot["hyperliquid"]
    stats = hyperliquid["stats"]
    hacks = snapshot["hacks"]
    internals = snapshot["internals"]
    breadth = snapshot["breadth"]
    concentration = snapshot["concentration"]
    fear_greed = snapshot["fear_greed"]
    coins = {coin["symbol"]: coin for coin in snapshot["coins"]}
    performance = {row["symbol"]: row for row in snapshot["performance"]}
    stable_assets = {row["symbol"]: row for row in stablecoins["assets"]}
    largest_hack = hacks["largest"][0]
    history = snapshot["history"]["btc"]

    btc = coins["BTC"]
    eth = coins["ETH"]
    sol = coins["SOL"]
    btc_perf = performance["BTC"]
    eth_perf = performance["ETH"]
    sol_perf = performance["SOL"]
    usdt = stable_assets["USDT"]
    usdc = stable_assets["USDC"]
    stable_total = stablecoins["total"]
    stable_count = sum(1 for coin in snapshot["coins"] if coin["tag"] == "Stablecoin")

    return {
        "__GENERATED_LABEL__": snapshot["generated_label"],
        "__SNAPSHOT_JSON__": "",
        "__TOTAL_MCAP__": usd(global_stats["total_mcap"]),
        "__TOTAL_VOL__": usd(global_stats["total_volume"]),
        "__MCAP_CHANGE__": pct(global_stats["mcap_change_24h"]),
        "__MCAP_CLASS__": pct_class(global_stats["mcap_change_24h"]),
        "__VOL_CHANGE__": pct(global_stats["volume_change_24h"]),
        "__BTC_DOM__": f"{global_stats['btc_dominance']:.2f}%",
        "__ETH_DOM__": f"{global_stats['eth_dominance']:.2f}%",
        "__STABLE_TOTAL__": usd(stable_total),
        "__STABLE_SHARE__": f"{stablecoins['share_of_market']:.2f}%",
        "__STABLE_COUNT__": str(stable_count),
        "__STABLE_30D__": pct(stablecoins["change_30d"]),
        "__STABLE_30D_CLASS__": pct_class(stablecoins["change_30d"]),
        "__USDT_SUPPLY__": usd(usdt["supply"]),
        "__USDT_SHARE__": f"{usdt['supply'] / stable_total * 100:.2f}%",
        "__USDC_SUPPLY__": usd(usdc["supply"]),
        "__USDC_SHARE__": f"{usdc['supply'] / stable_total * 100:.2f}%",
        "__DEFI_TVL__": usd(defi["tvl"]),
        "__DEFI_30D__": pct(defi["change_30d"]),
        "__DEFI_CLASS__": pct_class(defi["change_30d"]),
        "__FNG__": str(fear_greed["value"]),
        "__FNG_LABEL__": fear_greed["label"],
        "__CG_FNG__": str(global_stats["cg_fng"]["value"]),
        "__CG_FNG_LABEL__": global_stats["cg_fng"]["sentiment"],
        "__BREADTH_UP__": str(breadth["change_24h"]["up"]),
        "__BREADTH_TOTAL__": str(breadth["change_24h"]["total"]),
        "__BREADTH_24H_UP__": str(breadth["change_24h"]["up"]),
        "__BREADTH_30D_UP__": str(breadth["change_30d"]["up"]),
        "__TOP10_SHARE__": f"{concentration['top10_share']:.2f}%",
        "__DEX_24H__": usd(dexs["volume_24h"]),
        "__DEX_7D__": usd(dexs["volume_7d"]),
        "__DEX_CHG_1D__": pct(dexs["change_1d"], 1),
        "__DEX_CHG_7D__": pct(dexs["change_7d"], 1),
        "__HL_VOL__": usd(hyperliquid["volume_24h"]),
        "__HL_OI__": usd(hyperliquid["open_interest"]),
        "__HL_ACCOUNTS__": f"{stats['accounts']:,}",
        "__HL_POSITIVE__": f"{stats['positive_share']:.1f}%",
        "__HL_MEDIAN__": pct(stats["median_month_roi"] * 100),
        "__HL_MEDIAN_CLASS__": pct_class(stats["median_month_roi"]),
        "__HL_ACCOUNT_VALUE__": usd(stats["total_account_value"]),
        "__HACKS_COUNT__": f"{hacks['count']:,}",
        "__HACKS_TOTAL__": usd(hacks["total"]),
        "__HACKS_LARGEST__": largest_hack["name"],
        "__HACKS_LARGEST_AMOUNT__": usd(largest_hack["amount"], 1),
        "__COIN_COUNT__": str(len(snapshot["coins"])),
        "__BTC_PRICE__": price(btc["price"]),
        "__BTC_MCAP__": usd(btc["market_cap"]),
        "__BTC_ATH_DOWN__": pct(btc["ath_change"], 1),
        "__BTC_24H__": pct(btc_perf["change_24h"]),
        "__BTC_24H_CLASS__": pct_class(btc_perf["change_24h"]),
        "__BTC_30D__": pct(btc_perf["change_30d"]),
        "__BTC_30D_CLASS__": pct_class(btc_perf["change_30d"]),
        "__BTC_1Y__": pct(btc_perf["change_365d"]),
        "__BTC_1Y_CLASS__": pct_class(btc_perf["change_365d"]),
        "__ETH_PRICE__": price(eth["price"]),
        "__ETH_MCAP__": usd(eth["market_cap"]),
        "__ETH_ATH_DOWN__": pct(eth["ath_change"], 1),
        "__ETH_24H__": pct(eth_perf["change_24h"]),
        "__ETH_24H_CLASS__": pct_class(eth_perf["change_24h"]),
        "__ETH_30D__": pct(eth_perf["change_30d"]),
        "__ETH_30D_CLASS__": pct_class(eth_perf["change_30d"]),
        "__ETH_1Y__": pct(eth_perf["change_365d"]),
        "__ETH_1Y_CLASS__": pct_class(eth_perf["change_365d"]),
        "__ETH_BTC__": f"{internals['eth_btc']:.4f}",
        "__ETH_BTC_PCT__": ordinal(internals["eth_btc_percentile"]),
        "__ETH_BTC_30D__": pct(internals["eth_btc_change_30d"]),
        "__SOL_PRICE__": price(sol["price"]),
        "__SOL_MCAP__": usd(sol["market_cap"]),
        "__SOL_ATH_DOWN__": pct(sol["ath_change"], 1),
        "__SOL_30D__": pct(sol_perf["change_30d"]),
        "__SOL_30D_CLASS__": pct_class(sol_perf["change_30d"]),
        "__ETH_STAKING_APY__": f"{pool_apy(snapshot['yields'], 'STETH'):.2f}%",
        "__SOL_STAKING_APY__": f"{pool_apy(snapshot['yields'], 'BNSOL'):.2f}%",
        "__AAVE_TVL__": usd(protocol_tvl(defi["protocols"], "Aave V3")),
        "__MORPHO_TVL__": usd(protocol_tvl(defi["protocols"], "Morpho Blue")),
        "__EIGEN_TVL__": usd(protocol_tvl(defi["protocols"], "EigenCloud")),
        "__HISTORY_START__": long_date(history[0][0]),
        "__HISTORY_END__": long_date(history[-1][0]),
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
