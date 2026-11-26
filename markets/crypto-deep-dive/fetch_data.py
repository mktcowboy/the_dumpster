#!/usr/bin/env python3
"""Fetch and normalize the crypto market snapshot used by the deep-dive page."""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
HISTORY = ROOT / "data" / "history"
OUT = ROOT / "data" / "snapshot.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; crypto-deep-dive/2.0)"}

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
    "llama_fees": "https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true",
    "llama_revenue": "https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue",
    "llama_tvl_history": "https://api.llama.fi/v2/historicalChainTvl",
    "llama_hacks": "https://api.llama.fi/hacks",
    "llama_pools": "https://yields.llama.fi/pools",
    "fng": "https://api.alternative.me/fng/?limit=31",
    "hyperliquid": "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard",
    "hyperliquid_meta": "https://api.hyperliquid.xyz/info",
    "yahoo_qqq": "https://query1.finance.yahoo.com/v8/finance/chart/QQQ?range=1y&interval=1d",
    "yahoo_gld": "https://query1.finance.yahoo.com/v8/finance/chart/GLD?range=1y&interval=1d",
    "yahoo_dxy": "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?range=1y&interval=1d",
    "yahoo_tnx": "https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?range=1y&interval=1d",
}

OPTIONAL_ENDPOINTS = {"yahoo_qqq", "yahoo_gld", "yahoo_dxy", "yahoo_tnx"}

PROVIDERS = {
    "CoinGecko": ["cg_global", "cg_markets", "cg_categories", "cg_btc_365", "cg_eth_365", "cg_sol_365"],
    "DefiLlama": [
        "stablecoins",
        "stablecoin_history",
        "llama_protocols",
        "llama_chains",
        "llama_dexs",
        "llama_fees",
        "llama_revenue",
        "llama_tvl_history",
        "llama_hacks",
        "llama_pools",
    ],
    "Alternative.me": ["fng"],
    "Hyperliquid": ["hyperliquid", "hyperliquid_meta"],
    "Yahoo Finance": ["yahoo_qqq", "yahoo_gld", "yahoo_dxy", "yahoo_tnx"],
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
    "optimism": "L2",
    "lido-dao": "DeFi",
    "maker": "DeFi",
    "curve-dao-token": "DeFi",
    "pendle": "DeFi",
    "raydium": "DeFi",
    "bonk": "Meme",
    "floki": "Meme",
    "official-trump": "Meme",
    "fartcoin": "Meme",
    "virtual-protocol": "AI",
    "fetch-ai": "AI",
    "artificial-superintelligence-alliance": "AI",
    "helium": "DePIN",
    "arweave": "DePIN",
    "sei-network": "L1",
    "celestia": "Infra",
    "eigenlayer": "Infra",
    "story-2": "L1",
    "berachain-bera": "L1",
    "monad": "L1",
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
    "first-digital-usd": "Stablecoin",
    "true-usd": "Stablecoin",
    "paxos-standard": "Stablecoin",
    "frax": "Stablecoin",
    "usual-usd": "Stablecoin",
}

CATEGORY_TO_TAG = {
    "Stablecoins": "Stablecoin",
    "Real World Assets (RWA)": "RWA",
    "Privacy": "Privacy",
    "Perpetuals": "Perp DEX",
    "Artificial Intelligence (AI)": "AI",
    "Meme": "Meme",
    "Layer 2 (L2)": "L2",
    "Centralized Exchange (CEX) Token": "CEX",
    "DePIN": "DePIN",
    "Oracle": "Oracle",
    "Decentralized Finance (DeFi)": "DeFi",
    "Yield Farming": "DeFi",
    "Smart Contract Platform": "L1",
}

LLAMA_CAT_TO_TAG = {
    "Lending": "DeFi",
    "Dexs": "DeFi",
    "Yield": "DeFi",
    "Yield Aggregator": "DeFi",
    "Liquid Staking": "DeFi",
    "Liquid Restaking": "DeFi",
    "CDP": "DeFi",
    "Restaking": "Infra",
    "Bridge": "Infra",
    "Cross Chain Bridge": "Infra",
    "Derivatives": "Perp DEX",
    "RWA": "RWA",
    "RWA Lending": "RWA",
    "CEX": "CEX",
    "Oracle": "Oracle",
    "Privacy": "Privacy",
    "Chain": "L1",
    "Rollup": "L2",
}

# Explicit DefiLlama parent/slug -> CoinGecko ID map for revenue/FDV joins
PROTOCOL_GECKO_MAP = {
    "parent#hyperliquid": "hyperliquid",
    "hyperliquid-perps": "hyperliquid",
    "hyperliquid-spot": "hyperliquid",
    "parent#uniswap": "uniswap",
    "parent#aave": "aave",
    "parent#pump": "pump-fun",
    "pump.fun": "pump-fun",
    "pumpswap": "pump-fun",
    "parent#morpho": "morpho",
    "morpho-blue": "morpho",
    "lido": "lido-dao",
    "parent#jupiter": "jupiter-exchange-solana",
    "parent#aerodrome": "aerodrome-finance",
    "parent#pancakeswap": "pancakeswap-token",
    "parent#sky": "sky",
    "parent#ethena": "ethena",
    "parent#ether.fi": "ether-fi",
    "parent#lighter": "lighter",
    "lighter-perps": "lighter",
    "parent#aster": "aster-2",
    "aster-perps": "aster-2",
    "parent#raydium": "raydium",
    "parent#pendle": "pendle",
    "parent#gmx": "gmx",
    "parent#dydx": "dydx-chain",
    "parent#curve-finance": "curve-dao-token",
    "parent#compound-finance": "compound-governance-token",
    "parent#jito": "jito-governance-token",
    "ethereum": "ethereum",
    "solana": "solana",
    "tron": "tron",
    "bsc": "binancecoin",
    "arbitrum": "arbitrum",
    "avalanche": "avalanche-2",
    "base": None,
    "bitcoin": "bitcoin",
    "sui": "sui",
    "near": "near",
    "ton": "the-open-network",
    "aptos": "aptos",
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

YIELD_STABLE_SYMBOLS = {
    "USDE", "SUSDE", "USDS", "SUSDS", "USDY", "USYC", "USDF", "BFUSD",
    "BUIDL", "USTB", "USD0", "USD0++", "SDAI", "OUSG", "USR", "USDX",
    "USDM", "STUSD", "EUSD", "USDN", "YUSD", "DEUSD",
}

MACRO_BENCHMARKS = [
    ("yahoo_qqq", "QQQ", "QQQ", "Nasdaq 100", False),
    ("yahoo_gld", "GLD", "GLD", "Gold (SPDR)", False),
    ("yahoo_dxy", "DX-Y.NYB", "DXY", "US Dollar Index", False),
    ("yahoo_tnx", "^TNX", "US10Y", "US 10Y Yield", True),
]


def fetch(name: str, url: str, refresh: bool = False, payload: dict | None = None, sleep: float = 0.4, optional: bool = False):
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{name}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())

    cg_key = os.environ.get("COINGECKO_DEMO_API_KEY", "").strip()
    is_cg = "coingecko.com" in url
    if is_cg:
        sleep = 2.0 if cg_key else max(sleep, 12.0)

    headers = dict(UA)
    if is_cg and cg_key:
        headers["x-cg-demo-api-key"] = cg_key

    last_error = None
    attempts = 3 if optional else 5
    for attempt in range(1, attempts + 1):
        try:
            data = None if payload is None else json.dumps(payload).encode()
            req = urllib.request.Request(url, data=data, headers=headers)
            if payload is not None:
                req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = resp.read()
            parsed = json.loads(body)
            if isinstance(parsed, dict) and isinstance(parsed.get("status"), dict) and parsed["status"].get("error_code") == 429:
                raise urllib.error.HTTPError(url, 429, "rate limited", {}, None)
            path.write_bytes(body)
            if sleep > 0:
                time.sleep(sleep)
            return parsed
        except Exception as exc:
            last_error = exc
            wait = (30 * attempt if is_cg else 5 * attempt)
            if attempt < attempts:
                print(f"  {name}: {exc}; retrying in {wait}s", file=sys.stderr)
                time.sleep(wait)

    if path.exists():
        print(f"  {name}: refresh failed ({last_error}); falling back to cached file", file=sys.stderr)
        return json.loads(path.read_text())
    if optional:
        print(f"  {name}: optional fetch failed ({last_error}); skipping", file=sys.stderr)
        return None
    raise RuntimeError(f"Unable to fetch {name}: {last_error}")


def usd(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def pct_change(current, previous):
    if not previous:
        return None
    return (current / previous - 1) * 100


def sig_round(value: float, digits: int = 4) -> float:
    if value == 0 or not math.isfinite(value):
        return 0.0
    return float(f"{value:.{digits}g}")


def downsample_spark(values: list, target: int = 32) -> list[float]:
    if not values:
        return []
    n = len(values)
    if n <= target:
        return [sig_round(usd(v), 4) for v in values]
    step = (n - 1) / (target - 1)
    return [sig_round(usd(values[round(i * step)]), 4) for i in range(target)]


def round_floats(value, digits: int = 6):
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, digits)
    if isinstance(value, list):
        return [round_floats(item, digits) for item in value]
    if isinstance(value, dict):
        return {key: round_floats(item, digits) for key, item in value.items()}
    return value


def utc_label(stamp: datetime) -> str:
    return f"{stamp.strftime('%B')} {stamp.day}, {stamp.year} · {stamp.strftime('%H:%M')} UTC"


def date_label(day) -> str:
    return f"{day.strftime('%B')} {day.day}, {day.year}"


def cache_fetched_at(name: str, fallback: datetime) -> datetime:
    path = RAW / f"{name}.json"
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return fallback


def source_metadata(now: datetime, used_endpoints: set[str]):
    sources = []
    stamps = []
    for provider, endpoints in PROVIDERS.items():
        names = [name for name in endpoints if name in used_endpoints]
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


def load_history_entries(history_dir: Path) -> list[tuple]:
    entries = []
    if not history_dir.exists():
        return entries
    for path in sorted(history_dir.glob("*.json")):
        try:
            day = datetime.strptime(path.stem, "%Y-%m-%d").date()
            entry = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(entry, dict) and isinstance(entry.get("metrics"), dict):
            entries.append((day, entry))
    return entries


def load_prior_history(entries: list[tuple], current_date):
    for day, entry in reversed(entries):
        if day < current_date:
            return day, entry
    return None


def build_comparison(prior_day, prior_entry, metrics):
    prior_metrics = prior_entry.get("metrics") or {}
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


def yahoo_daily_series(raw: dict | None) -> list[list]:
    if not raw or not isinstance(raw, dict):
        return []
    try:
        result = raw["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        closes = result["indicators"]["quote"][0].get("close") or []
    except (KeyError, IndexError, TypeError):
        return []
    rows = {}
    for ts, close in zip(timestamps, closes):
        if ts is None or close is None:
            continue
        day = datetime.fromtimestamp(int(ts), timezone.utc).date().isoformat()
        rows[day] = float(close)
    return [[day, val] for day, val in sorted(rows.items())]


def realized_vol(series: list[list], days: int) -> float | None:
    if len(series) < max(days, 10) + 1:
        return None
    tail = [val for _, val in series[-(days + 1):] if val and val > 0]
    if len(tail) < 10:
        return None
    rets = [math.log(tail[i] / tail[i - 1]) for i in range(1, len(tail))]
    if len(rets) < 2:
        return None
    return statistics.stdev(rets) * math.sqrt(365) * 100


def max_drawdown_1y(series: list[list]) -> float | None:
    vals = [val for _, val in series if val and val > 0]
    if len(vals) < 2:
        return None
    peak = vals[0]
    worst = 0.0
    for v in vals:
        if v > peak:
            peak = v
        dd = (v / peak - 1) * 100
        if dd < worst:
            worst = dd
    return worst


def pearson_corr(xs: list[float], ys: list[float]) -> float | None:
    n = min(len(xs), len(ys))
    if n < 15:
        return None
    xs, ys = xs[-n:], ys[-n:]
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def aligned_return_corr(crypto_map: dict[str, float], macro_series: list[list], days: int = 90, diff_mode: bool = False) -> float | None:
    """Align US market close on date D (16:00 ET) with CoinGecko's D+1 00:00 UTC close."""
    macro_map = {day: val for day, val in macro_series if val is not None}
    macro_days = sorted(macro_map.keys())
    xs, ys = [], []
    for i in range(1, len(macro_days)):
        d0, d1 = macro_days[i - 1], macro_days[i]
        c_day0 = (datetime.fromisoformat(d0) + timedelta(days=1)).date().isoformat()
        c_day1 = (datetime.fromisoformat(d1) + timedelta(days=1)).date().isoformat()
        c0, c1 = crypto_map.get(c_day0), crypto_map.get(c_day1)
        m0, m1 = macro_map[d0], macro_map[d1]
        if not c0 or not c1 or (not diff_mode and (not m0 or not m1)):
            continue
        xs.append(math.log(c1 / c0))
        ys.append((m1 - m0) if diff_mode else math.log(m1 / m0))
    return pearson_corr(xs[-days:], ys[-days:])


def fetch_all(refresh: bool) -> tuple[dict, set[str]]:
    results = {}
    used = set()

    cg_names = PROVIDERS["CoinGecko"]
    other_names = [name for name in ENDPOINTS if name not in cg_names]

    def run_coingecko():
        out = {}
        for name in cg_names:
            out[name] = fetch(name, ENDPOINTS[name], refresh=refresh)
        return out

    def run_one(name):
        payload = {"type": "metaAndAssetCtxs"} if name == "hyperliquid_meta" else None
        opt = name in OPTIONAL_ENDPOINTS
        return name, fetch(name, ENDPOINTS[name], refresh=refresh, payload=payload, sleep=0.25, optional=opt)

    with ThreadPoolExecutor(max_workers=6) as pool:
        cg_future = pool.submit(run_coingecko)
        other_futures = [pool.submit(run_one, name) for name in other_names]
        for fut in as_completed(other_futures):
            name, data = fut.result()
            if data is not None:
                results[name] = data
                used.add(name)
        cg_data = cg_future.result()
        for name, data in cg_data.items():
            if data is not None:
                results[name] = data
                used.add(name)

    return results, used


def find_staking_benchmark(pools_data: list[dict], preferred_symbols: tuple[str, ...], preferred_projects: tuple[str, ...]) -> tuple[float | None, str]:
    best = None
    for pool in pools_data:
        sym = (pool.get("symbol") or "").upper()
        proj = (pool.get("project") or "").lower()
        tvl = usd(pool.get("tvlUsd"))
        apy = usd(pool.get("apy"))
        if tvl < 5_000_000 or apy <= 0 or apy > 25 or pool.get("outlier"):
            continue
        if sym in preferred_symbols:
            score = (1 if proj in preferred_projects else 0, -preferred_symbols.index(sym), tvl)
            if best is None or score > best[0]:
                best = (score, apy, f"{pool.get('project')} {pool.get('symbol')}")
    if best:
        return best[1], best[2]
    return None, "—"


def main():
    refresh = "--refresh" in sys.argv
    print("Loading source data" + (" (refreshing live APIs)" if refresh else " (using local cache where available)"))
    raw, used_endpoints = fetch_all(refresh)

    cg_global = raw["cg_global"]
    cg_markets = raw["cg_markets"]
    cg_categories = raw["cg_categories"]
    cg_btc = raw["cg_btc_365"]
    cg_eth = raw["cg_eth_365"]
    cg_sol = raw["cg_sol_365"]
    stablecoins = raw["stablecoins"]
    stable_history = raw["stablecoin_history"]
    protocols = raw["llama_protocols"]
    chains = raw["llama_chains"]
    dexs = raw["llama_dexs"]
    fees_raw = raw["llama_fees"]
    revenue_raw = raw["llama_revenue"]
    tvl_history = raw["llama_tvl_history"]
    hacks = raw["llama_hacks"]
    pools = raw["llama_pools"]
    fng = raw["fng"]
    hyperliquid = raw["hyperliquid"]
    hl_meta = raw["hyperliquid_meta"]

    now = datetime.now(timezone.utc)
    now_label = utc_label(now)
    data_as_of, sources = source_metadata(now, used_endpoints)
    data_as_of_label = utc_label(data_as_of)

    global_data = cg_global["data"]
    total_mcap = usd(global_data["total_market_cap"]["usd"])
    total_volume = usd(global_data["total_volume"]["usd"])

    # --- Stablecoins + payment vs yield-bearing split ---
    stable_rows = []
    stable_chain_totals = {}
    stable_gecko_ids = set()
    split_buckets = {
        "fiat_payment": {"label": "Fiat-backed payment", "supply": 0.0, "prev_month": 0.0, "count": 0},
        "yield_synthetic": {"label": "Yield-bearing / synthetic / RWA", "supply": 0.0, "prev_month": 0.0, "count": 0},
        "crypto_other": {"label": "Crypto-backed / other", "supply": 0.0, "prev_month": 0.0, "count": 0},
    }

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
        sym_upper = (asset.get("symbol") or "").upper()
        mech = (asset.get("pegMechanism") or "").lower()
        name_lower = (asset.get("name") or "").lower()
        if sym_upper in YIELD_STABLE_SYMBOLS or "yield" in name_lower or "treasury" in name_lower or "synthetic" in mech or "algorithmic" in mech and sym_upper in ("USDE", "USDS"):
            bucket_key = "yield_synthetic"
        elif "fiat" in mech:
            bucket_key = "fiat_payment"
        else:
            bucket_key = "crypto_other"
        split_buckets[bucket_key]["supply"] += current
        split_buckets[bucket_key]["prev_month"] += prev_month if prev_month > 0 else current
        split_buckets[bucket_key]["count"] += 1

        stable_rows.append({
            "id": str(asset.get("id") or ""),
            "name": asset.get("name"),
            "symbol": asset.get("symbol"),
            "gecko_id": gecko_id,
            "supply": current,
            "price": usd(asset.get("price") or 1),
            "peg_type": asset.get("pegType"),
            "mechanism": asset.get("pegMechanism"),
            "bucket": bucket_key,
            "change_1d": pct_change(current, prev_day),
            "change_7d": pct_change(current, prev_week),
            "change_30d": pct_change(current, prev_month),
            "chains": len([value for value in chain_values.values() if value > 1_000_000]),
            "top_chains": [[name, value] for name, value in top_chains],
        })
    stable_rows.sort(key=lambda row: -row["supply"])

    split_total = sum(b["supply"] for b in split_buckets.values()) or 1.0
    stable_split = []
    for key in ("fiat_payment", "yield_synthetic", "crypto_other"):
        b = split_buckets[key]
        stable_split.append({
            "key": key,
            "label": b["label"],
            "supply": b["supply"],
            "share": b["supply"] / split_total * 100,
            "change_30d": pct_change(b["supply"], b["prev_month"]),
            "count": b["count"],
        })

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

    # --- Build auto-tag fallbacks from CoinGecko categories & DefiLlama protocols ---
    auto_tags = {}
    for category in cg_categories:
        mapped = CATEGORY_TO_TAG.get(category.get("name"))
        if not mapped:
            continue
        for cid in (category.get("top_3_coins_id") or []):
            auto_tags.setdefault(cid, mapped)

    llama_gecko_to_cat = {}
    llama_id_to_gecko = {}
    llama_slug_to_gecko = {}
    llama_parent_to_gecko = {}
    for p in protocols:
        gid = p.get("gecko_id")
        if not gid:
            continue
        cat = p.get("category")
        if cat in LLAMA_CAT_TO_TAG:
            llama_gecko_to_cat.setdefault(gid, LLAMA_CAT_TO_TAG[cat])
        if p.get("id"):
            llama_id_to_gecko[str(p["id"])] = gid
        if p.get("slug"):
            llama_slug_to_gecko[p["slug"]] = gid
        if p.get("parentProtocol"):
            llama_parent_to_gecko.setdefault(p["parentProtocol"], gid)

    coin_lookup = {}
    coin_by_symbol = {}
    for coin in cg_markets:
        sym = (coin.get("symbol") or "").upper()
        mc = usd(coin.get("market_cap"))
        fdv = usd(coin.get("fully_diluted_valuation"))
        info = {
            "id": coin["id"],
            "symbol": sym,
            "name": coin.get("name"),
            "price": usd(coin.get("current_price")),
            "market_cap": mc,
            "fdv": fdv,
            "change_24h": coin.get("price_change_percentage_24h_in_currency"),
            "change_7d": coin.get("price_change_percentage_7d_in_currency"),
            "change_30d": coin.get("price_change_percentage_30d_in_currency"),
        }
        coin_lookup[coin["id"]] = info
        if sym and (sym not in coin_by_symbol or mc > coin_by_symbol[sym]["market_cap"]):
            coin_by_symbol[sym] = info

    coins = []
    for coin in cg_markets[:100]:
        spark_raw = (coin.get("sparkline_in_7d") or {}).get("price") or []
        cid = coin["id"]
        tag = TAGS.get(cid)
        if not tag and cid in stable_gecko_ids:
            tag = "Stablecoin"
        if not tag:
            tag = auto_tags.get(cid) or llama_gecko_to_cat.get(cid)
        if not tag:
            nm = (coin.get("name") or "").lower()
            if "usd" in nm or "eur" in nm and abs(usd(coin.get("current_price")) - 1) < 0.25:
                tag = "Stablecoin"
            elif "gold" in nm or "treasury" in nm or "fund" in nm:
                tag = "RWA"
            else:
                tag = "Other"

        mc = usd(coin.get("market_cap"))
        fdv = usd(coin.get("fully_diluted_valuation"))
        supply = usd(coin.get("circulating_supply"))
        max_supply = usd(coin.get("max_supply")) if coin.get("max_supply") else None
        if max_supply and max_supply > 0:
            circ_pct = min(100.0, (supply / max_supply) * 100)
        elif fdv and fdv > 0 and mc > 0:
            circ_pct = min(100.0, (mc / fdv) * 100)
        else:
            circ_pct = None

        coins.append({
            "rank": coin.get("market_cap_rank"),
            "id": cid,
            "symbol": (coin.get("symbol") or "").upper(),
            "name": coin.get("name"),
            "price": usd(coin.get("current_price")),
            "market_cap": mc,
            "fdv": fdv,
            "volume": usd(coin.get("total_volume")),
            "circ_pct": round(circ_pct, 1) if circ_pct is not None else None,
            "ath": usd(coin.get("ath")),
            "ath_change": coin.get("ath_change_percentage"),
            "change_24h": coin.get("price_change_percentage_24h_in_currency"),
            "change_7d": coin.get("price_change_percentage_7d_in_currency"),
            "change_30d": coin.get("price_change_percentage_30d_in_currency"),
            "spark": downsample_spark(spark_raw, target=32),
            "tag": tag,
        })

    category_lookup = {}
    for category in cg_categories:
        category_lookup[category["name"]] = {
            "id": category.get("id") or "",
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
            "id": category["id"],
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

    chain_rows = [
        {
            "name": chain.get("name"),
            "tvl": usd(chain.get("tvl")),
            "symbol": chain.get("tokenSymbol"),
        }
        for chain in sorted(chains, key=lambda item: -usd(item.get("tvl")))[:18]
    ]

    protocol_rows = []
    for protocol in protocols:
        if protocol.get("category") == "CEX":
            continue
        if usd(protocol.get("tvl")) <= 0:
            continue
        protocol_rows.append({
            "name": protocol.get("name"),
            "slug": protocol.get("slug") or "",
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
            "slug": protocol.get("slug") or "",
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
            "slug": protocol.get("slug") or "",
            "volume_24h": usd(protocol.get("total24h")),
            "volume_7d": usd(protocol.get("total7d")),
            "change_7d": protocol.get("change_7d"),
            "chains": (protocol.get("chains") or [])[:3],
        })
    dex_protocols.sort(key=lambda row: -row["volume_24h"])
    dex_protocols = dex_protocols[:14]

    # --- Protocol Fees, Revenue & Valuation (P/F, P/S) + Perp DEX Fee Share ---
    rev_by_key = {}
    for p in revenue_raw.get("protocols", []):
        k = str(p.get("defillamaId") or p.get("slug") or p.get("name"))
        rev_by_key[k] = p

    fee_agg = {}
    perp_venues = []
    for p in fees_raw.get("protocols", []):
        f24 = usd(p.get("total24h"))
        f7 = usd(p.get("total7d"))
        f30 = usd(p.get("total30d"))
        if f30 <= 0 and f24 <= 0:
            continue
        rk = str(p.get("defillamaId") or p.get("slug") or p.get("name"))
        r = rev_by_key.get(rk, {})
        r24 = usd(r.get("total24h"))
        r30 = usd(r.get("total30d"))

        if p.get("category") == "Derivatives" and f30 > 100_000:
            ch = p.get("chains") or []
            perp_venues.append({
                "name": p.get("displayName") or p.get("name"),
                "slug": (p.get("parentProtocol") or "").replace("parent#", "") or p.get("slug") or "",
                "fees_24h": f24,
                "fees_30d": f30,
                "rev_30d": r30,
                "change_7d": p.get("change_7dover7d"),
                "chains": ch[:3],
                "off_chain": ch == ["Off Chain"],
            })

        parent = p.get("parentProtocol") or ""
        slug = p.get("slug") or ""
        agg_key = parent or slug or (p.get("name") or "")
        llama_slug = parent.replace("parent#", "") if parent else slug
        gid = (
            PROTOCOL_GECKO_MAP.get(parent)
            if parent in PROTOCOL_GECKO_MAP
            else PROTOCOL_GECKO_MAP.get(slug)
            if slug in PROTOCOL_GECKO_MAP
            else llama_id_to_gecko.get(str(p.get("defillamaId")))
            or llama_slug_to_gecko.get(slug)
            or llama_parent_to_gecko.get(parent)
        )
        display = (
            parent.replace("parent#", "").replace("-", " ").title()
            if parent
            else (p.get("displayName") or p.get("name"))
        )
        # Clean up well-known parent display names
        display_fixes = {
            "Pump": "Pump.fun / PumpSwap",
            "Ether.Fi": "ether.fi",
            "Circle": "Circle (USDC)",
            "Dydx": "dYdX",
            "Gmx": "GMX",
            "Raydium": "Raydium",
            "Hyperliquid": "Hyperliquid",
            "Uniswap": "Uniswap",
            "Aave": "Aave",
            "Morpho": "Morpho",
            "Jupiter": "Jupiter",
            "Aerodrome": "Aerodrome",
            "Pancakeswap": "PancakeSwap",
            "Polymarket": "Polymarket",
        }
        display = display_fixes.get(display, display)

        entry = fee_agg.setdefault(agg_key, {
            "name": display,
            "slug": llama_slug,
            "category": p.get("category") or "—",
            "fees_24h": 0.0,
            "fees_7d": 0.0,
            "fees_30d": 0.0,
            "rev_24h": 0.0,
            "rev_30d": 0.0,
            "gecko_id": gid,
        })
        entry["fees_24h"] += f24
        entry["fees_7d"] += f7
        entry["fees_30d"] += f30
        entry["rev_24h"] += r24
        entry["rev_30d"] += r30
        if gid and not entry["gecko_id"]:
            entry["gecko_id"] = gid

    top_fee_protocols = []
    valuation_rows = []
    for entry in sorted(fee_agg.values(), key=lambda x: -x["fees_30d"]):
        ann_fees = entry["fees_30d"] * 12
        ann_rev = entry["rev_30d"] * 12
        take_rate = (entry["rev_30d"] / entry["fees_30d"] * 100) if entry["fees_30d"] > 0 else None
        cg = coin_lookup.get(entry["gecko_id"]) if entry["gecko_id"] else None
        fdv = (cg["fdv"] or cg["market_cap"]) if cg else None
        pf = (fdv / ann_fees) if (fdv and ann_fees > 1_000_000) else None
        ps = (fdv / ann_rev) if (fdv and ann_rev > 1_000_000) else None

        row = {
            "name": entry["name"],
            "slug": entry.get("slug") or "",
            "gecko_id": entry.get("gecko_id") or "",
            "category": entry["category"],
            "symbol": cg["symbol"] if cg else None,
            "fees_24h": entry["fees_24h"],
            "fees_30d": entry["fees_30d"],
            "rev_30d": entry["rev_30d"],
            "ann_fees": ann_fees,
            "ann_rev": ann_rev,
            "take_rate": take_rate,
            "fdv": fdv,
            "pf": pf,
            "ps": ps,
        }
        if len(top_fee_protocols) < 16:
            top_fee_protocols.append(row)
        if cg and fdv and entry["fees_30d"] >= 1_000_000 and entry["category"] != "Stablecoin Issuer" and cg["symbol"] not in ("BTC",):
            if len(valuation_rows) < 16:
                valuation_rows.append(row)

    perp_venues.sort(key=lambda x: -x["fees_30d"])
    perp_onchain = [v for v in perp_venues if not v["off_chain"]]
    perp_total_30d = sum(v["fees_30d"] for v in perp_onchain) or 1.0
    for v in perp_onchain:
        v["share_30d"] = v["fees_30d"] / perp_total_30d * 100
    perp_top = perp_onchain[:10]
    hl_perp_share = next((v["share_30d"] for v in perp_top if "hyperliquid" in v["name"].lower()), None)

    # --- Yield Pools + Benchmark Staking ---
    pools_data = pools.get("data", [])
    eth_stake_apy, eth_stake_src = find_staking_benchmark(pools_data, ("STETH", "WSTETH", "CBETH", "RETH"), ("lido", "coinbase-wrapped-staked-eth", "rocket-pool"))
    sol_stake_apy, sol_stake_src = find_staking_benchmark(pools_data, ("BNSOL", "JITOSOL", "MSOL", "JUPSOL"), ("binance-staked-sol", "jito-liquid-staking", "marinade-liquid-staking", "jupiter-staked-sol"))

    candidates = []
    for pool in pools_data:
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
        reasons = []
        if not stable:
            risk += 2
            reasons.append("Volatile asset (+2)")
        if pool.get("ilRisk") == "yes":
            risk += 2
            reasons.append("Impermanent loss (+2)")
        if pool.get("chain") not in ("Ethereum", "Solana", "Base", "Arbitrum", "Hyperliquid L1", "BSC"):
            risk += 1
            reasons.append("Non-major chain (+1)")
        if tvl < 50_000_000:
            risk += 1
            reasons.append("TVL < $50M (+1)")
        if apy > 15:
            risk += 2
            reasons.append("APY > 15% (+2)")
        if apy > 30:
            risk += 1
            reasons.append("APY > 30% (+1)")
        reward = usd(pool.get("apyReward"))
        base = usd(pool.get("apyBase"))
        if reward > base * 2 and reward > 1:
            risk += 1
            reasons.append("Reward > 2× base (+1)")
        mean30 = usd(pool.get("apyMean30d"))
        if mean30 and abs(apy - mean30) / mean30 > 0.5:
            risk += 1
            reasons.append("APY deviates >50% from 30d avg (+1)")
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
            "risk_reasons": reasons or ["Blue-chip stable/low-IL profile (0)"],
        })
    candidates.sort(key=lambda row: (-row["tvl"], -row["apy"]))
    yield_pools = candidates[:40]

    # --- Hacks ---
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
            "source": hack.get("source") or "",
        })
    hacks_rows.sort(key=lambda row: row["date"], reverse=True)
    hacks_total = sum(row["amount"] or 0 for row in hacks_rows)
    hacks_count = len(hacks_rows)
    hacks_recent = hacks_rows[:10]
    hacks_largest = sorted(hacks_rows, key=lambda row: -(row["amount"] or 0))[:6]

    # --- Fear & Greed ---
    fng_rows = list(reversed(fng.get("data", [])))
    fng_history = [{"value": int(row["value"]), "label": row.get("value_classification"), "date": int(row["timestamp"])} for row in fng_rows]
    fng_latest = fng_history[-1] if fng_history else {"value": 50, "label": "Neutral"}

    # --- Hyperliquid Leaderboard + OI-Weighted Funding & OI/MCap ---
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
        name = asset.get("name") or ""
        mark = usd(context.get("markPx"))
        oi_usd = usd(context.get("openInterest")) * mark
        funding_hr = usd(context.get("funding"))
        funding_ann = funding_hr * 24 * 365 * 100
        sym_clean = name.lstrip("k") if name.startswith("k") and len(name) > 2 else name
        cg_match = coin_by_symbol.get(name.upper()) or coin_by_symbol.get(sym_clean.upper())
        oi_mcap_pct = (oi_usd / cg_match["market_cap"] * 100) if (cg_match and cg_match["market_cap"] > 0) else None
        hl_markets.append({
            "name": name,
            "volume_24h": usd(context.get("dayNtlVlm")),
            "open_interest": oi_usd,
            "funding": funding_hr,
            "funding_ann": funding_ann,
            "oi_mcap_pct": oi_mcap_pct,
            "mark": mark,
        })
    hl_markets.sort(key=lambda row: -row["volume_24h"])
    hl_total_volume = sum(row["volume_24h"] for row in hl_markets)
    hl_total_oi = sum(row["open_interest"] for row in hl_markets)
    oi_weighted_funding = (
        sum(row["open_interest"] * row["funding_ann"] for row in hl_markets) / hl_total_oi
        if hl_total_oi > 0 else 0.0
    )
    positive_oi_share = (
        sum(row["open_interest"] for row in hl_markets if row["funding"] > 0) / hl_total_oi * 100
        if hl_total_oi > 0 else 50.0
    )

    # --- Price Series, Cycle Metrics, Volatility, Altcoin Season & Macro Correlations ---
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
            "vol_30d": realized_vol(series, 30),
            "max_dd_1y": max_drawdown_1y(series),
            "market_cap": coin.get("market_cap"),
        })

    btc_map = {day: value for day, value in btc_series}
    eth_map = {day: value for day, value in eth_series}
    sol_map = {day: value for day, value in sol_series}

    ratio_series = [[day, eth_map[day] / btc_map[day]] for day in sorted(btc_map.keys() & eth_map.keys()) if btc_map[day]]
    ratio_now = ratio_series[-1][1] if ratio_series else 0
    ratio_30d = pct_change(ratio_now, ratio_series[-31][1]) if len(ratio_series) > 30 else None
    ratio_percentile = (
        sum(1 for _, value in ratio_series if value <= ratio_now) / len(ratio_series) * 100
        if ratio_series else None
    )

    sol_btc_series = [[day, sol_map[day] / btc_map[day]] for day in sorted(btc_map.keys() & sol_map.keys()) if btc_map[day]]
    sol_btc_now = sol_btc_series[-1][1] if sol_btc_series else 0
    sol_btc_30d = pct_change(sol_btc_now, sol_btc_series[-31][1]) if len(sol_btc_series) > 30 else None

    btc_200 = [val for _, val in btc_series[-200:] if val > 0]
    btc_sma_200 = (sum(btc_200) / len(btc_200)) if len(btc_200) >= 150 else None
    btc_spot = perf_lookup.get("bitcoin", {}).get("price") or (btc_series[-1][1] if btc_series else 0)
    btc_mayer = (btc_spot / btc_sma_200) if (btc_sma_200 and btc_spot) else None

    btc_30d_ret = perf_lookup.get("bitcoin", {}).get("change_30d")
    alt_candidates = [
        c for c in coins
        if c["id"] != "bitcoin" and c["tag"] != "Stablecoin" and c.get("change_30d") is not None
    ][:50]
    if alt_candidates and btc_30d_ret is not None:
        alt_beating = sum(1 for c in alt_candidates if c["change_30d"] > btc_30d_ret)
        alt_season_30d = alt_beating / len(alt_candidates) * 100
    else:
        alt_beating = 0
        alt_season_30d = None

    # Macro benchmarks & 90d rolling correlations
    macro_rows = []
    for key, yahoo_sym, sym, label, diff_mode in MACRO_BENCHMARKS:
        series = yahoo_daily_series(raw.get(key))
        if len(series) < 25:
            continue
        last_val = series[-1][1]
        c30 = (last_val - series[-min(22, len(series) - 1) - 1][1]) if diff_mode else series_change(series, 21)
        c90 = (last_val - series[-min(64, len(series) - 1) - 1][1]) if diff_mode else series_change(series, 63)
        c1y = (last_val - series[0][1]) if diff_mode else pct_change(last_val, series[0][1])
        macro_rows.append({
            "symbol": sym,
            "yahoo_symbol": yahoo_sym,
            "label": label,
            "last": last_val,
            "is_rate": diff_mode,
            "change_30d": c30,
            "change_90d": c90,
            "change_1y": c1y,
            "corr_btc_90d": aligned_return_corr(btc_map, series, days=90, diff_mode=diff_mode),
            "corr_eth_90d": aligned_return_corr(eth_map, series, days=90, diff_mode=diff_mode),
        })

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

    cg_fng = global_data.get("fear_and_greed_index")
    if not isinstance(cg_fng, dict):
        cg_fng = None

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
            "cg_fng": cg_fng,
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
            "split": stable_split,
            "assets": stable_rows[:24],
            "chains": sorted(
                [{"name": name, "value": value} for name, value in stable_chain_totals.items()],
                key=lambda row: -row["value"],
            )[:10],
        },
        "defi": {
            "tvl": tvl_now,
            "change_30d": pct_change(tvl_now, tvl_30d),
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
        "fees": {
            "total_24h": usd(fees_raw.get("total24h")),
            "total_30d": usd(fees_raw.get("total30d")),
            "revenue_24h": usd(revenue_raw.get("total24h")),
            "revenue_30d": usd(revenue_raw.get("total30d")),
            "protocols": top_fee_protocols,
            "valuation": valuation_rows,
        },
        "perps": {
            "onchain_fees_30d": perp_total_30d,
            "hl_fee_share": hl_perp_share,
            "venues": perp_top,
        },
        "exchanges": exchange_rows,
        "staking": {
            "eth_apy": eth_stake_apy,
            "eth_source": eth_stake_src,
            "sol_apy": sol_stake_apy,
            "sol_source": sol_stake_src,
        },
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
            "oi_weighted_funding_ann": oi_weighted_funding,
            "positive_oi_share": positive_oi_share,
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
        "macro": macro_rows,
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
            "sol_btc": sol_btc_now,
            "sol_btc_change_30d": sol_btc_30d,
            "btc_drawdown": perf_lookup.get("bitcoin", {}).get("ath_change"),
            "eth_drawdown": perf_lookup.get("ethereum", {}).get("ath_change"),
            "btc_mayer": btc_mayer,
            "btc_sma_200": btc_sma_200,
            "btc_vol_30d": realized_vol(btc_series, 30),
            "btc_vol_90d": realized_vol(btc_series, 90),
            "eth_vol_30d": realized_vol(eth_series, 30),
            "sol_vol_30d": realized_vol(sol_series, 30),
            "alt_season_30d": alt_season_30d,
            "alt_beating_btc": alt_beating,
            "alt_sample": len(alt_candidates),
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
        "fees_24h": snapshot["fees"]["total_24h"],
        "revenue_24h": snapshot["fees"]["revenue_24h"],
        "hl_volume_24h": snapshot["hyperliquid"]["volume_24h"],
        "hl_open_interest": snapshot["hyperliquid"]["open_interest"],
        "hl_funding_ann": snapshot["hyperliquid"]["oi_weighted_funding_ann"],
        "btc_price": perf_lookup.get("bitcoin", {}).get("price"),
        "eth_price": perf_lookup.get("ethereum", {}).get("price"),
        "sol_price": perf_lookup.get("solana", {}).get("price"),
        "breadth_24h_up": snapshot["breadth"]["change_24h"]["up"],
        "hacks_count": snapshot["hacks"]["count"],
    }

    HISTORY.mkdir(parents=True, exist_ok=True)
    current_date = data_as_of.date()
    history_entries = load_history_entries(HISTORY)
    prior = load_prior_history(history_entries, current_date)
    snapshot["comparison"] = build_comparison(prior[0], prior[1], metrics) if prior else None

    history_path = HISTORY / f"{current_date.isoformat()}.json"
    history_entry = {
        "date": current_date.isoformat(),
        "generated_at": now.isoformat(),
        "data_as_of": data_as_of.isoformat(),
        "metrics": metrics,
    }
    history_path.write_text(json.dumps(round_floats(history_entry), separators=(",", ":")))
    print(f"Wrote {history_path} ({history_path.stat().st_size / 1024:.1f} KB)")

    # Reload full history including today for multi-snapshot trend series
    all_history = load_history_entries(HISTORY)[-60:]
    snapshot["history_snapshots"] = [
        {
            "date": day.isoformat(),
            "total_mcap": e["metrics"].get("total_mcap"),
            "btc_price": e["metrics"].get("btc_price"),
            "btc_dominance": e["metrics"].get("btc_dominance"),
            "stablecoin_total": e["metrics"].get("stablecoin_total"),
            "defi_tvl": e["metrics"].get("defi_tvl"),
            "fear_greed": e["metrics"].get("fear_greed"),
            "hl_open_interest": e["metrics"].get("hl_open_interest"),
        }
        for day, e in all_history
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(round_floats(snapshot), separators=(",", ":")))
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
