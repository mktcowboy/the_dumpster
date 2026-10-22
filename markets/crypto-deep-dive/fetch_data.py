#!/usr/bin/env python3
"""Fetch and normalize the crypto market snapshot used by the deep-dive page."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
HISTORY = ROOT / "data" / "history"
OUT = ROOT / "data" / "snapshot.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; crypto-deep-dive/1.0)"}
USED_ENDPOINTS = []

ENDPOINTS = {
    "cg_global": "https://api.coingecko.com/api/v3/global",
    "cg_markets": "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=1&sparkline=true&price_change_percentage=1h%2C24h%2C7d%2C30d",
    "cg_categories": "https://api.coingecko.com/api/v3/coins/categories",
    "cg_btc_365": "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=365&interval=daily",
    "cg_eth_365": "https://api.coingecko.com/api/v3/coins/ethereum/market_chart?vs_currency=usd&days=365&interval=daily",
    "cg_sol_365": "https://api.coingecko.com/api/v3/coins/solana/market_chart?vs_currency=usd&days=365&interval=daily",
    "stablecoins": "https://stablecoins.llama.fi/stablecoins?includePrices=true",
    "stablecoin_history": "https://stablecoins.llama.fi/stablecoincharts/all",
    "llama_protocols": "https://api.llama.fi/protocols",
    "llama_chains": "https://api.llama.fi/v2/chains",
    "llama_dexs": "https://api.llama.fi/overview/dexs?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true",
    "llama_tvl_history": "https://api.llama.fi/v2/historicalChainTvl",
    "llama_hacks": "https://api.llama.fi/hacks",
    "llama_pools": "https://yields.llama.fi/pools",
    "fng": "https://api.alternative.me/fng/?limit=31",
    "hyperliquid": "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard",
    "hyperliquid_meta": "https://api.hyperliquid.xyz/info",
}

PROVIDERS = {
    "CoinGecko": ["cg_global", "cg_markets", "cg_categories", "cg_btc_365", "cg_eth_365", "cg_sol_365"],
    "DefiLlama": ["stablecoins", "stablecoin_history", "llama_protocols", "llama_chains", "llama_dexs", "llama_tvl_history", "llama_hacks", "llama_pools"],
    "Alternative.me": ["fng"],
    "Hyperliquid": ["hyperliquid", "hyperliquid_meta"],
}

TAGS = {
    "bitcoin": "BTC",
    "ethereum": "L1",
    "binancecoin": "L1",
    "ripple": "Payments",
    "solana": "L1",
    "tron": "L1",
    "figure-heloc": "RWA",
    "zcash": "Privacy",
    "hyperliquid": "Perp DEX",
    "dogecoin": "Meme",
    "monero": "Privacy",
    "whitebit": "CEX",
    "chainlink": "Oracle",
    "cardano": "L1",
    "leo-token": "CEX",
    "near": "L1",
    "rain": "DeFi",
    "stellar": "Payments",
    "bitcoin-cash": "Payments",
    "litecoin": "Payments",
    "uniswap": "DeFi",
    "avalanche-2": "L1",
    "canton-network": "L1",
    "sui": "L1",
    "the-open-network": "L1",
    "hedera-hashgraph": "L1",
    "tether-gold": "RWA",
    "bittensor": "AI",
    "shiba-inu": "Meme",
    "ethena": "DeFi",
    "crypto-com-chain": "CEX",
    "quant-network": "Infra",
    "bitway": "Bitcoin DeFi",
    "okb": "CEX",
    "aave": "DeFi",
    "hashnote-usyc": "RWA",
    "ondo-us-dollar-yield": "RWA",
    "pump-fun": "Meme",
    "ondo-finance": "RWA",
    "blackrock-usd-institutional-digital-liquidity-fund": "RWA",
    "worldcoin-wld": "AI",
    "polkadot": "L1",
    "pepe": "Meme",
    "aster-2": "Perp DEX",
    "mantle": "L2",
    "pax-gold": "RWA",
    "sky": "DeFi",
    "world-liberty-financial": "DeFi",
    "memecore": "Meme",
    "spiko-amundi-overnight-swap-fund-eur": "RWA",
    "morpho": "DeFi",
    "internet-computer": "L1",
    "htx-dao": "CEX",
    "bitget-token": "CEX",
    "arbitrum": "L2",
    "venice-token": "AI",
    "ethereum-classic": "L1",
    "just": "DeFi",
    "jupiter-exchange-solana": "DeFi",
    "gatechain-token": "CEX",
    "kaspa": "L1",
    "kucoin-shares": "CEX",
    "algorand": "L1",
    "polygon-ecosystem-token": "L2",
    "render-token": "AI",
    "cosmos": "L1",
    "pi-network": "L1",
    "filecoin": "DePIN",
    "lighter": "Perp DEX",
    "injective-protocol": "L1",
    "aerodrome-finance": "DeFi",
    "layerzero": "Infra",
    "nexo": "CEX",
    "superstate-short-duration-us-government-securities-fund-ustb": "RWA",
    "pearl-2": "AI",
    "aptos": "L1",
    "pancakeswap-token": "DeFi",
    "midnight-3": "Privacy",
    "blockstack": "L2",
    "xdce-crowd-sale": "RWA",
    "ether-fi": "DeFi",
    "dash": "Privacy",
    "vechain": "L1",
    "pyth-network": "Oracle",
    "tether": "Stablecoin",
    "usd-coin": "Stablecoin",
    "usds": "Stablecoin",
    "ethena-usde": "Stablecoin",
    "dai": "Stablecoin",
    "usd1-wlfi": "Stablecoin",
    "global-dollar": "Stablecoin",
    "paypal-usd": "Stablecoin",
    "ripple-usd": "Stablecoin",
    "usdd": "Stablecoin",
    "falcon-finance": "Stablecoin",
    "united-stables": "Stablecoin",
    "bfusd": "Stablecoin",
    "usdgo": "Stablecoin",
    "open-usd": "Stablecoin",
    "gho": "Stablecoin",
}

SECTOR_DEFS = [
    ("l1", "L1 / smart contract platforms", "Smart Contract Platform"),
    ("stablecoins", "Stablecoins", "Stablecoins"),
    ("rwa", "RWA / tokenized credit", "Real World Assets (RWA)"),
    ("defi", "DeFi", "Decentralized Finance (DeFi)"),
    ("privacy", "Privacy", "Privacy"),
    ("perps", "Perp DEX / derivatives", "Perpetuals"),
    ("ai", "AI", "Artificial Intelligence (AI)"),
    ("memes", "Memes", "Meme"),
    ("l2", "Layer 2", "Layer 2 (L2)"),
    ("cex", "Exchange tokens", "Centralized Exchange (CEX) Token"),
    ("yield", "Yield farming", "Yield Farming"),
    ("depin", "DePIN", "DePIN"),
]


def fetch(name, url, refresh=False, payload=None, sleep=1.0):
    RAW.mkdir(parents=True, exist_ok=True)
    USED_ENDPOINTS.append(name)
    path = RAW / f"{name}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    if "coingecko.com" in url:
        sleep = max(sleep, 20.0)
    last_error = None
    for attempt in range(1, 6):
        try:
            data = None if payload is None else json.dumps(payload).encode()
            req = urllib.request.Request(url, data=data, headers=UA)
            if payload is not None:
                req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = resp.read()
            parsed = json.loads(body)
            if isinstance(parsed, dict) and parsed.get("status", {}).get("error_code") == 429:
                raise urllib.error.HTTPError(url, 429, "rate limited", {}, None)
            path.write_bytes(body)
            time.sleep(sleep)
            return parsed
        except Exception as exc:
            last_error = exc
            wait = 45 * attempt if "coingecko" in url else 8 * attempt
            print(f"  {name}: {exc}; retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"Unable to fetch {name}: {last_error}")


def usd(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def pct_change(current, previous):
    if not previous:
        return None
    return (current / previous - 1) * 100


def round_floats(value, digits=6):
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, list):
        return [round_floats(item, digits) for item in value]
    if isinstance(value, dict):
        return {key: round_floats(item, digits) for key, item in value.items()}
    return value


def utc_label(stamp):
    return f"{stamp.strftime('%B')} {stamp.day}, {stamp.year} · {stamp.strftime('%H:%M')} UTC"


def date_label(day):
    return f"{day.strftime('%B')} {day.day}, {day.year}"


def cache_fetched_at(name, fallback):
    path = RAW / f"{name}.json"
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return fallback


def source_metadata(now):
    used = set(USED_ENDPOINTS)
    sources = []
    stamps = []
    for provider, endpoints in PROVIDERS.items():
        names = [name for name in endpoints if name in used]
        if not names:
            continue
        times = [cache_fetched_at(name, now) for name in names]
        oldest = min(times)
        stamps.append(oldest)
        sources.append({
            "provider": provider,
            "fetched_at": oldest.isoformat(),
            "endpoints": names,
            "age_hours": round((now - oldest).total_seconds() / 3600, 1),
        })
    data_as_of = min(stamps) if stamps else now
    return data_as_of, sources


def load_prior_history(history_dir, current_date):
    candidates = []
    for path in history_dir.glob("*.json"):
        try:
            day = datetime.strptime(path.stem, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day < current_date:
            candidates.append((day, path))
    for day, path in sorted(candidates, reverse=True):
        try:
            entry = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(entry, dict):
            return day, entry
    return None


def build_comparison(prior_day, prior_entry, metrics):
    prior_metrics = prior_entry.get("metrics")
    if not isinstance(prior_metrics, dict):
        prior_metrics = {}
    comparison = {}
    for key, current in metrics.items():
        prior = prior_metrics.get(key)
        numeric = isinstance(current, (int, float)) and not isinstance(current, bool)
        numeric = numeric and isinstance(prior, (int, float)) and not isinstance(prior, bool)
        comparison[key] = {
            "current": current,
            "prior": prior,
            "delta": current - prior if numeric else None,
            "pct": (current / prior - 1) * 100 if numeric and prior else None,
        }
    return {
        "prior_date": prior_day.isoformat(),
        "prior_label": date_label(prior_day),
        "metrics": comparison,
    }


def daily_series(points, value_key=None):
    rows = {}
    for point in points:
        stamp, value = point if isinstance(point, list) else (point["date"], point[value_key])
        stamp = float(stamp)
        if stamp > 10_000_000_000:
            stamp /= 1000
        day = datetime.fromtimestamp(int(stamp), timezone.utc).date().isoformat()
        rows[day] = usd(value)
    return [[day, value] for day, value in sorted(rows.items())]


def main():
    refresh = "--refresh" in sys.argv
    print("Loading source data")
    cg_global = fetch("cg_global", ENDPOINTS["cg_global"], refresh)
    cg_markets = fetch("cg_markets", ENDPOINTS["cg_markets"], refresh)
    cg_categories = fetch("cg_categories", ENDPOINTS["cg_categories"], refresh)
    cg_btc = fetch("cg_btc_365", ENDPOINTS["cg_btc_365"], refresh)
    cg_eth = fetch("cg_eth_365", ENDPOINTS["cg_eth_365"], refresh)
    cg_sol = fetch("cg_sol_365", ENDPOINTS["cg_sol_365"], refresh)
    stablecoins = fetch("stablecoins", ENDPOINTS["stablecoins"], refresh)
    stable_history = fetch("stablecoin_history", ENDPOINTS["stablecoin_history"], refresh)
    protocols = fetch("llama_protocols", ENDPOINTS["llama_protocols"], refresh)
    chains = fetch("llama_chains", ENDPOINTS["llama_chains"], refresh)
    dexs = fetch("llama_dexs", ENDPOINTS["llama_dexs"], refresh)
    tvl_history = fetch("llama_tvl_history", ENDPOINTS["llama_tvl_history"], refresh)
    hacks = fetch("llama_hacks", ENDPOINTS["llama_hacks"], refresh)
    pools = fetch("llama_pools", ENDPOINTS["llama_pools"], refresh)
    fng = fetch("fng", ENDPOINTS["fng"], refresh)
    hyperliquid = fetch("hyperliquid", ENDPOINTS["hyperliquid"], refresh)
    hl_meta = fetch("hyperliquid_meta", ENDPOINTS["hyperliquid_meta"], refresh, payload={"type": "metaAndAssetCtxs"})

    now = datetime.now(timezone.utc)
    now_label = utc_label(now)
    data_as_of, sources = source_metadata(now)
    data_as_of_label = utc_label(data_as_of)

    global_data = cg_global["data"]
    total_mcap = usd(global_data["total_market_cap"]["usd"])
    total_volume = usd(global_data["total_volume"]["usd"])

    stable_rows = []
    stable_chain_totals = {}
    stable_gecko_ids = set()
    for asset in stablecoins.get("peggedAssets", []):
        current = usd((asset.get("circulating") or {}).get("peggedUSD"))
        if current < 1_000_000:
            continue
        prev_day = usd((asset.get("circulatingPrevDay") or {}).get("peggedUSD"))
        prev_week = usd((asset.get("circulatingPrevWeek") or {}).get("peggedUSD"))
        prev_month = usd((asset.get("circulatingPrevMonth") or {}).get("peggedUSD"))
        chain_values = {}
        for chain_name, chain_data in (asset.get("chainCirculating") or {}).items():
            value = usd((chain_data.get("current") or {}).get("peggedUSD"))
            if value > 0:
                chain_values[chain_name] = value
                stable_chain_totals[chain_name] = stable_chain_totals.get(chain_name, 0) + value
        top_chains = sorted(chain_values.items(), key=lambda item: -item[1])[:3]
        gecko_id = asset.get("gecko_id") or ""
        if gecko_id:
            stable_gecko_ids.add(gecko_id)
        stable_rows.append({
            "name": asset.get("name"),
            "symbol": asset.get("symbol"),
            "gecko_id": gecko_id,
            "supply": current,
            "price": usd(asset.get("price") or 1),
            "peg_type": asset.get("pegType"),
            "mechanism": asset.get("pegMechanism"),
            "change_1d": pct_change(current, prev_day),
            "change_7d": pct_change(current, prev_week),
            "change_30d": pct_change(current, prev_month),
            "chains": len([value for value in chain_values.values() if value > 1_000_000]),
            "top_chains": [[name, value] for name, value in top_chains],
        })
    stable_rows.sort(key=lambda row: -row["supply"])

    stable_points = [
        [row["date"], (row.get("totalCirculatingUSD") or {}).get("peggedUSD")]
        for row in stable_history
    ]
    stable_series = daily_series(stable_points)[-366:]
    stable_now = stable_series[-1][1] if stable_series else sum(row["supply"] for row in stable_rows)
    stable_1d = stable_series[-2][1] if len(stable_series) > 1 else stable_now
    stable_7d = stable_series[-8][1] if len(stable_series) > 7 else stable_now
    stable_30d = stable_series[-31][1] if len(stable_series) > 30 else stable_now

    tvl_series = daily_series(tvl_history, "tvl")[-366:]
    tvl_now = tvl_series[-1][1] if tvl_series else 0
    tvl_30d = tvl_series[-31][1] if len(tvl_series) > 30 else tvl_now

    coin_lookup = {}
    for coin in cg_markets:
        coin_lookup[coin["id"]] = {
            "symbol": (coin.get("symbol") or "").upper(),
            "name": coin.get("name"),
            "market_cap": usd(coin.get("market_cap")),
            "change_24h": coin.get("price_change_percentage_24h_in_currency"),
            "change_7d": coin.get("price_change_percentage_7d_in_currency"),
            "change_30d": coin.get("price_change_percentage_30d_in_currency"),
        }

    coins = []
    for coin in cg_markets[:100]:
        spark = ((coin.get("sparkline_in_7d") or {}).get("price") or [])[::2]
        tag = TAGS.get(coin["id"])
        if not tag and coin["id"] in stable_gecko_ids:
            tag = "Stablecoin"
        coins.append({
            "rank": coin.get("market_cap_rank"),
            "id": coin["id"],
            "symbol": (coin.get("symbol") or "").upper(),
            "name": coin.get("name"),
            "image": coin.get("image"),
            "price": usd(coin.get("current_price")),
            "market_cap": usd(coin.get("market_cap")),
            "fdv": usd(coin.get("fully_diluted_valuation")),
            "volume": usd(coin.get("total_volume")),
            "supply": usd(coin.get("circulating_supply")),
            "max_supply": usd(coin.get("max_supply")) if coin.get("max_supply") else None,
            "ath": usd(coin.get("ath")),
            "ath_change": coin.get("ath_change_percentage"),
            "ath_date": coin.get("ath_date"),
            "change_1h": coin.get("price_change_percentage_1h_in_currency"),
            "change_24h": coin.get("price_change_percentage_24h_in_currency"),
            "change_7d": coin.get("price_change_percentage_7d_in_currency"),
            "change_30d": coin.get("price_change_percentage_30d_in_currency"),
            "spark": [round(usd(value), 8) for value in spark],
            "tag": tag or "Other",
        })

    category_lookup = {}
    for category in cg_categories:
        category_lookup[category["name"]] = {
            "name": category["name"],
            "market_cap": usd(category.get("market_cap")),
            "change_24h": category.get("market_cap_change_24h"),
            "volume_24h": usd(category.get("volume_24h")),
            "top_ids": category.get("top_3_coins_id") or [],
        }

    sectors = []
    for key, label, category_name in SECTOR_DEFS:
        category = category_lookup.get(category_name)
        if not category:
            continue
        leaders = []
        for coin_id in category["top_ids"][:3]:
            info = coin_lookup.get(coin_id)
            if info:
                leaders.append({
                    "id": coin_id,
                    "symbol": info["symbol"],
                    "name": info["name"],
                    "market_cap": info["market_cap"],
                    "change_24h": info["change_24h"],
                    "change_7d": info["change_7d"],
                    "change_30d": info["change_30d"],
                })
            else:
                leaders.append({"id": coin_id, "symbol": coin_id[:8].upper(), "name": coin_id.replace("-", " ").title()})
        sectors.append({
            "key": key,
            "label": label,
            "category": category_name,
            "market_cap": category["market_cap"],
            "change_24h": category["change_24h"],
            "volume_24h": category["volume_24h"],
            "leaders": leaders,
        })

    category_rank = sorted(
        [category for category in category_lookup.values() if category["market_cap"] > 0],
        key=lambda item: -item["market_cap"],
    )[:24]

    chain_rows = []
    for chain in sorted(chains, key=lambda item: -usd(item.get("tvl")))[:18]:
        chain_rows.append({
            "name": chain.get("name"),
            "tvl": usd(chain.get("tvl")),
            "symbol": chain.get("tokenSymbol"),
        })

    protocol_rows = []
    for protocol in protocols:
        if protocol.get("category") == "CEX":
            continue
        if usd(protocol.get("tvl")) <= 0:
            continue
        protocol_rows.append({
            "name": protocol.get("name"),
            "category": protocol.get("category"),
            "tvl": usd(protocol.get("tvl")),
            "change_1d": protocol.get("change_1d"),
            "change_7d": protocol.get("change_7d"),
            "chains": (protocol.get("chains") or [])[:3],
        })
    protocol_rows.sort(key=lambda row: -row["tvl"])
    protocol_rows = protocol_rows[:18]

    exchange_rows = []
    for protocol in protocols:
        if protocol.get("category") != "CEX":
            continue
        exchange_rows.append({
            "name": protocol.get("name"),
            "tvl": usd(protocol.get("tvl")),
            "change_1d": protocol.get("change_1d"),
            "change_7d": protocol.get("change_7d"),
            "chains": len(protocol.get("chains") or []),
        })
    exchange_rows.sort(key=lambda row: -row["tvl"])
    exchange_rows = exchange_rows[:12]

    dex_protocols = []
    for protocol in dexs.get("protocols", []):
        if protocol.get("category") != "Dexs":
            continue
        if usd(protocol.get("total24h")) <= 0:
            continue
        dex_protocols.append({
            "name": protocol.get("name"),
            "volume_24h": usd(protocol.get("total24h")),
            "volume_7d": usd(protocol.get("total7d")),
            "change_7d": protocol.get("change_7d"),
            "chains": (protocol.get("chains") or [])[:3],
        })
    dex_protocols.sort(key=lambda row: -row["volume_24h"])
    dex_protocols = dex_protocols[:14]

    candidates = []
    for pool in pools.get("data", []):
        tvl = usd(pool.get("tvlUsd"))
        apy = usd(pool.get("apy"))
        if tvl < 20_000_000 or apy <= 0.1 or apy > 60:
            continue
        if pool.get("outlier"):
            continue
        symbol = (pool.get("symbol") or "").upper()
        stable = bool(pool.get("stablecoin"))
        if not stable and not any(token in symbol for token in ("ETH", "BTC", "SOL", "BNB", "HYPE")):
            continue
        if stable and apy > 25:
            continue
        risk = 0
        if not stable:
            risk += 2
        if pool.get("ilRisk") == "yes":
            risk += 2
        if pool.get("chain") not in ("Ethereum", "Solana", "Base", "Arbitrum", "Hyperliquid L1", "BSC"):
            risk += 1
        if tvl < 50_000_000:
            risk += 1
        if apy > 15:
            risk += 2
        if apy > 30:
            risk += 1
        reward = usd(pool.get("apyReward"))
        base = usd(pool.get("apyBase"))
        if reward > base * 2 and reward > 1:
            risk += 1
        mean30 = usd(pool.get("apyMean30d"))
        if mean30 and abs(apy - mean30) / mean30 > 0.5:
            risk += 1
        candidates.append({
            "project": pool.get("project"),
            "pool": pool.get("pool"),
            "chain": pool.get("chain"),
            "symbol": pool.get("symbol"),
            "tvl": tvl,
            "apy": apy,
            "apy_base": base,
            "apy_reward": reward,
            "apy_mean_30d": mean30,
            "stablecoin": stable,
            "il_risk": pool.get("ilRisk"),
            "risk": "High" if risk >= 5 else "Medium" if risk >= 3 else "Low",
            "risk_score": risk,
        })
    candidates.sort(key=lambda row: (-row["tvl"], -row["apy"]))
    yield_pools = candidates[:30]

    hacks_rows = []
    cutoff = now - timedelta(days=365)
    for hack in hacks:
        stamp = datetime.fromtimestamp(int(hack["date"]), timezone.utc)
        if stamp < cutoff:
            continue
        hacks_rows.append({
            "date": stamp.date().isoformat(),
            "name": hack.get("name"),
            "amount": usd(hack.get("amount")) if hack.get("amount") else None,
            "classification": hack.get("classification"),
            "technique": hack.get("technique"),
            "chains": hack.get("chain") or [],
        })
    hacks_rows.sort(key=lambda row: row["date"], reverse=True)
    hacks_total = sum(row["amount"] or 0 for row in hacks_rows)
    hacks_count = len(hacks_rows)
    hacks_recent = hacks_rows[:10]
    hacks_largest = sorted(hacks_rows, key=lambda row: -(row["amount"] or 0))[:6]

    fng_rows = list(reversed(fng.get("data", [])))
    fng_history = [{"value": int(row["value"]), "label": row.get("value_classification"), "date": int(row["timestamp"])} for row in fng_rows]
    fng_latest = fng_history[-1] if fng_history else {"value": 50, "label": "Neutral"}

    hl_rows = hyperliquid.get("leaderboardRows", [])
    eligible = []
    for row in hl_rows:
        account = usd(row.get("accountValue"))
        if account < 10_000:
            continue
        windows = {window: values for window, values in row.get("windowPerformances", [])}
        month = windows.get("month") or {}
        week = windows.get("week") or {}
        day = windows.get("day") or {}
        all_time = windows.get("allTime") or {}
        month_pnl = usd(month.get("pnl"))
        month_volume = usd(month.get("vlm"))
        if month_volume <= 0:
            continue
        eligible.append({
            "address": row.get("ethAddress"),
            "account": account,
            "day_pnl": usd(day.get("pnl")),
            "day_roi": usd(day.get("roi")),
            "week_pnl": usd(week.get("pnl")),
            "week_roi": usd(week.get("roi")),
            "month_pnl": month_pnl,
            "month_roi": usd(month.get("roi")),
            "month_volume": month_volume,
            "all_time_pnl": usd(all_time.get("pnl")),
            "all_time_roi": usd(all_time.get("roi")),
        })
    hl_top_pnl = sorted([row for row in eligible if row["account"] >= 100_000], key=lambda row: -row["month_pnl"])[:12]
    hl_top_accounts = sorted(eligible, key=lambda row: -row["account"])[:12]
    active = [row for row in eligible if row["account"] >= 100_000 and row["month_volume"] >= 1_000_000]
    month_rois = sorted(row["month_roi"] for row in active if row["month_roi"] != 0)
    if month_rois:
        middle = len(month_rois) // 2
        median_roi = month_rois[middle] if len(month_rois) % 2 else (month_rois[middle - 1] + month_rois[middle]) / 2
    else:
        median_roi = 0
    positive_share = (sum(1 for row in active if row["month_pnl"] > 0) / len(active) * 100) if active else 0
    hl_stats = {
        "accounts": len(active),
        "positive_share": positive_share,
        "median_month_roi": median_roi,
        "total_account_value": sum(row["account"] for row in eligible),
    }

    hl_universe, hl_contexts = hl_meta
    hl_markets = []
    for asset, context in zip(hl_universe.get("universe", []), hl_contexts):
        if asset.get("isDelisted"):
            continue
        mark = usd(context.get("markPx"))
        open_interest = usd(context.get("openInterest"))
        hl_markets.append({
            "name": asset.get("name"),
            "volume_24h": usd(context.get("dayNtlVlm")),
            "open_interest": open_interest * mark,
            "funding": usd(context.get("funding")),
            "mark": mark,
        })
    hl_markets.sort(key=lambda row: -row["volume_24h"])
    hl_total_volume = sum(row["volume_24h"] for row in hl_markets)
    hl_total_oi = sum(row["open_interest"] for row in hl_markets)

    btc_series = daily_series(cg_btc.get("prices", []))[-366:]
    eth_series = daily_series(cg_eth.get("prices", []))[-366:]
    sol_series = daily_series(cg_sol.get("prices", []))[-366:]

    def series_change(series, days):
        if len(series) <= 1:
            return None
        lookback = min(days, len(series) - 1)
        return pct_change(series[-1][1], series[-lookback - 1][1])

    perf_lookup = {coin["id"]: coin for coin in coins}
    performance = []
    for coin_id, label, series in (("bitcoin", "BTC", btc_series), ("ethereum", "ETH", eth_series), ("solana", "SOL", sol_series)):
        coin = perf_lookup.get(coin_id, {})
        performance.append({
            "symbol": label,
            "change_24h": coin.get("change_24h"),
            "change_7d": coin.get("change_7d"),
            "change_30d": coin.get("change_30d"),
            "change_90d": series_change(series, 90),
            "change_365d": series_change(series, 365),
            "ath_change": coin.get("ath_change"),
            "market_cap": coin.get("market_cap"),
        })

    btc_map = dict((day, value) for day, value in btc_series)
    eth_map = dict((day, value) for day, value in eth_series)
    ratio_series = [[day, eth_map[day] / btc_map[day]] for day in sorted(btc_map.keys() & eth_map.keys()) if btc_map[day]]
    ratio_now = ratio_series[-1][1] if ratio_series else 0
    ratio_30d = pct_change(ratio_now, ratio_series[-31][1]) if len(ratio_series) > 30 else None
    ratio_percentile = (
        sum(1 for _, value in ratio_series if value <= ratio_now) / len(ratio_series) * 100
        if ratio_series else None
    )

    top10 = coins[:10]
    top10_share = sum(coin["market_cap"] for coin in top10) / total_mcap * 100 if total_mcap else 0
    stablecoin_share = stable_now / total_mcap * 100 if total_mcap else 0

    breadth = {}
    for window in ("change_24h", "change_7d", "change_30d"):
        values = [coin[window] for coin in coins if coin.get(window) is not None]
        breadth[window] = {
            "up": sum(1 for value in values if value > 0),
            "down": sum(1 for value in values if value < 0),
            "total": len(values),
        }

    snapshot = {
        "generated_at": now.isoformat(),
        "generated_label": data_as_of_label,
        "built_at": now.isoformat(),
        "built_label": now_label,
        "data_as_of": data_as_of.isoformat(),
        "data_as_of_label": data_as_of_label,
        "sources": sources,
        "source_timestamp": global_data.get("updated_at"),
        "global": {
            "total_mcap": total_mcap,
            "total_volume": total_volume,
            "mcap_change_24h": global_data.get("market_cap_change_percentage_24h_usd"),
            "volume_change_24h": global_data.get("volume_change_percentage_24h_usd"),
            "btc_dominance": global_data["market_cap_percentage"].get("btc"),
            "eth_dominance": global_data["market_cap_percentage"].get("eth"),
            "active_cryptos": global_data.get("active_cryptocurrencies"),
            "markets": global_data.get("markets"),
            "cg_fng": global_data.get("fear_and_greed_index"),
        },
        "fear_greed": {
            "value": int(fng_latest["value"]),
            "label": fng_latest["label"],
            "history": fng_history,
        },
        "stablecoins": {
            "total": stable_now,
            "change_1d": pct_change(stable_now, stable_1d),
            "change_7d": pct_change(stable_now, stable_7d),
            "change_30d": pct_change(stable_now, stable_30d),
            "share_of_market": stablecoin_share,
            "assets": stable_rows[:24],
            "chains": sorted(
                [{"name": name, "value": value} for name, value in stable_chain_totals.items()],
                key=lambda row: -row["value"],
            )[:10],
            "history": stable_series,
        },
        "defi": {
            "tvl": tvl_now,
            "change_30d": pct_change(tvl_now, tvl_30d),
            "history": tvl_series,
            "protocols": protocol_rows,
            "chains": chain_rows,
        },
        "dexs": {
            "volume_24h": usd(dexs.get("total24h")),
            "volume_7d": usd(dexs.get("total7d")),
            "volume_30d": usd(dexs.get("total30d")),
            "change_1d": dexs.get("change_1d"),
            "change_7d": dexs.get("change_7d"),
            "change_1m": dexs.get("change_1m"),
            "protocols": dex_protocols,
        },
        "exchanges": exchange_rows,
        "yields": yield_pools,
        "hacks": {
            "count": hacks_count,
            "total": hacks_total,
            "recent": hacks_recent,
            "largest": hacks_largest,
        },
        "hyperliquid": {
            "volume_24h": hl_total_volume,
            "open_interest": hl_total_oi,
            "markets": hl_markets[:14],
            "top_pnl": hl_top_pnl,
            "top_accounts": hl_top_accounts,
            "stats": hl_stats,
        },
        "coins": coins,
        "sectors": sectors,
        "categories": category_rank,
        "history": {
            "btc": btc_series,
            "eth": eth_series,
            "sol": sol_series,
            "tvl": tvl_series,
            "stablecoins": stable_series,
        },
        "breadth": breadth,
        "performance": performance,
        "concentration": {
            "top10_share": top10_share,
            "btc_share": sum(coin["market_cap"] for coin in coins if coin["id"] == "bitcoin") / total_mcap * 100 if total_mcap else 0,
        },
        "internals": {
            "eth_btc": ratio_now,
            "eth_btc_change_30d": ratio_30d,
            "eth_btc_percentile": ratio_percentile,
            "btc_drawdown": perf_lookup.get("bitcoin", {}).get("ath_change"),
            "eth_drawdown": perf_lookup.get("ethereum", {}).get("ath_change"),
        },
    }

    metrics = {
        "total_mcap": snapshot["global"]["total_mcap"],
        "total_volume": snapshot["global"]["total_volume"],
        "btc_dominance": snapshot["global"]["btc_dominance"],
        "eth_dominance": snapshot["global"]["eth_dominance"],
        "stablecoin_total": snapshot["stablecoins"]["total"],
        "defi_tvl": snapshot["defi"]["tvl"],
        "fear_greed": snapshot["fear_greed"]["value"],
        "top10_share": snapshot["concentration"]["top10_share"],
        "dex_volume_24h": snapshot["dexs"]["volume_24h"],
        "hl_volume_24h": snapshot["hyperliquid"]["volume_24h"],
        "hl_open_interest": snapshot["hyperliquid"]["open_interest"],
        "btc_price": perf_lookup.get("bitcoin", {}).get("price"),
        "eth_price": perf_lookup.get("ethereum", {}).get("price"),
        "sol_price": perf_lookup.get("solana", {}).get("price"),
        "breadth_24h_up": snapshot["breadth"]["change_24h"]["up"],
        "hacks_count": snapshot["hacks"]["count"],
    }

    current_date = data_as_of.date()
    prior = load_prior_history(HISTORY, current_date)
    snapshot["comparison"] = build_comparison(prior[0], prior[1], metrics) if prior else None

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(round_floats(snapshot), separators=(",", ":")))
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")

    HISTORY.mkdir(parents=True, exist_ok=True)
    history_path = HISTORY / f"{current_date.isoformat()}.json"
    history_entry = {
        "date": current_date.isoformat(),
        "generated_at": now.isoformat(),
        "data_as_of": data_as_of.isoformat(),
        "metrics": metrics,
    }
    history_path.write_text(json.dumps(round_floats(history_entry), separators=(",", ":")))
    print(f"Wrote {history_path} ({history_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
