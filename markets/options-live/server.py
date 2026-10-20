#!/usr/bin/env python3
"""Serve a live max-pain dashboard for the QQQ universe.

The server refreshes the universe on a background thread only during U.S.
market hours (weekdays 09:00-16:15 ET, excluding NYSE holidays) and while a
browser has viewed the board in the last 15 minutes. It serves the cached
snapshot to the browser and exposes on-demand detail endpoints for individual
tickers. Detail payloads also include daily OHLC history from Yahoo Finance
(with a Nasdaq fallback).
The original markets/options pipeline remains static and reproducible; this
folder is the live copy.

Usage:
    python3 markets/options-live/server.py
    python3 markets/options-live/server.py --interval 600 --port 8080
    python3 markets/options-live/server.py --tickers AAPL MSFT NVDA

Requires requests.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import max_pain

DATA_DIR = SCRIPT_DIR / "data"
LATEST_PATH = DATA_DIR / "latest.json"
QQQ_MEMBERS_PATH = DATA_DIR / "qqq_members.json"
INDEX_PATH = SCRIPT_DIR / "index.html"
SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
DETAIL_TTL = 300.0
IDLE_SECONDS = 900.0
REFRESH_DEDUPE_SECONDS = 120.0
ET = ZoneInfo("America/New_York")
MARKET_OPEN_TIME = dtime(9, 0)
MARKET_CLOSE_TIME = dtime(16, 15)
EARLY_CLOSE_TIME = dtime(13, 15)
MARKET_HOLIDAYS = {
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
    date(2027, 1, 1),
    date(2027, 1, 18),
    date(2027, 2, 15),
    date(2027, 3, 26),
    date(2027, 5, 31),
    date(2027, 6, 18),
    date(2027, 7, 5),
    date(2027, 9, 6),
    date(2027, 11, 25),
    date(2027, 12, 24),
}
MARKET_EARLY_CLOSES = {
    date(2026, 11, 27),
    date(2026, 12, 24),
    date(2027, 11, 26),
}
HISTORY_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
NASDAQ_HISTORY_URL = "https://api.nasdaq.com/api/quote/{ticker}/historical"
HISTORY_RANGE = "6mo"
HISTORY_DAYS = 190
HISTORY_TTL = 900.0
HISTORY_ERROR_TTL = 60.0
HISTORY_TIMEOUT = 10.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def market_open(now: datetime | None = None) -> bool:
    if now is None:
        now = datetime.now(ET)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=ET)
    else:
        now = now.astimezone(ET)
    if now.weekday() >= 5 or now.date() in MARKET_HOLIDAYS:
        return False
    close = EARLY_CLOSE_TIME if now.date() in MARKET_EARLY_CLOSES else MARKET_CLOSE_TIME
    minute = now.hour * 60 + now.minute
    return (
        MARKET_OPEN_TIME.hour * 60 + MARKET_OPEN_TIME.minute
        <= minute
        <= close.hour * 60 + close.minute
    )


class State:
    def __init__(self, args: argparse.Namespace) -> None:
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.snapshot: dict | None = None
        self.members: set[str] = set()
        self.extras: set[str] = set()
        self.fixed_tickers: list[str] | None = args.tickers
        self.interval = args.interval
        self.timeout = args.timeout
        self.workers = args.workers
        self.expiry = args.expiry
        self.requested_expiry: str | None = None
        self.throttle = max_pain.Throttle()
        self.refreshing = False
        self.last_success: str | None = None
        self.last_attempt: str | None = None
        self.next_refresh: str | None = None
        self.last_error: str | None = None
        self.last_viewed = 0.0
        self.last_refresh_at = 0.0
        self.detail_cache: dict[str, tuple[float, dict]] = {}
        self.history_cache: dict[tuple[str, str], tuple[float, dict]] = {}
        self.verbose = not args.quiet


def _history_number(value) -> float | None:
    text = str(value or "").replace("$", "").replace(",", "").strip()
    if not text or text.upper() == "N/A":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _yahoo_history(symbol: str, timeout: float) -> dict:
    ticker = symbol.replace(".", "-")
    params = {
        "range": HISTORY_RANGE,
        "interval": "1d",
        "includePrePost": "false",
        "events": "div,split",
    }
    response = max_pain.requests.get(
        HISTORY_URL.format(ticker=ticker),
        params=params,
        headers={"User-Agent": max_pain.USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        raise ValueError("no chart data")
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    candles = []
    for index, stamp in enumerate(timestamps):
        if index >= min(len(opens), len(highs), len(lows), len(closes)):
            break
        open_price = opens[index]
        high_price = highs[index]
        low_price = lows[index]
        close_price = closes[index]
        if None in (open_price, high_price, low_price, close_price):
            continue
        candles.append(
            {
                "t": datetime.fromtimestamp(stamp, timezone.utc).date().isoformat(),
                "o": round(float(open_price), 4),
                "h": round(float(high_price), 4),
                "l": round(float(low_price), 4),
                "c": round(float(close_price), 4),
                "v": int(volumes[index] or 0) if index < len(volumes) else 0,
            }
        )
    if not candles:
        raise ValueError("empty history")
    return {
        "symbol": symbol,
        "range": HISTORY_RANGE,
        "source": "yahoo",
        "candles": candles,
    }


def _nasdaq_history(symbol: str, timeout: float) -> dict:
    query = {
        "fromdate": (date.today() - timedelta(days=HISTORY_DAYS)).isoformat(),
        "todate": date.today().isoformat(),
        "limit": "200",
    }
    rows: list[dict] = []
    for assetclass in ("stocks", "etf"):
        params = {**query, "assetclass": assetclass}
        try:
            response = max_pain.requests.get(
                NASDAQ_HISTORY_URL.format(ticker=symbol),
                params=params,
                headers={
                    "User-Agent": max_pain.USER_AGENT,
                    "Accept": "application/json, text/plain, */*",
                },
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            rows = (((payload.get("data") or {}).get("tradesTable") or {}).get("rows") or [])
        except Exception:
            if assetclass == "etf":
                raise
            continue
        if rows:
            break
    if not rows:
        raise ValueError("empty history")
    candles = []
    for row in reversed(rows):
        raw_date = str(row.get("date") or "").strip()
        try:
            candle_date = datetime.strptime(raw_date, "%m/%d/%Y").date().isoformat()
        except ValueError:
            continue
        open_price = _history_number(row.get("open"))
        high_price = _history_number(row.get("high"))
        low_price = _history_number(row.get("low"))
        close_price = _history_number(row.get("close"))
        if None in (open_price, high_price, low_price, close_price):
            continue
        volume = _history_number(row.get("volume")) or 0
        candles.append(
            {
                "t": candle_date,
                "o": round(open_price, 4),
                "h": round(high_price, 4),
                "l": round(low_price, 4),
                "c": round(close_price, 4),
                "v": int(volume),
            }
        )
    if not candles:
        raise ValueError("empty history")
    candles.sort(key=lambda candle: candle["t"])
    return {
        "symbol": symbol,
        "range": HISTORY_RANGE,
        "source": "nasdaq",
        "candles": candles,
    }


def fetch_history(state: State, symbol: str) -> dict:
    key = (symbol, HISTORY_RANGE)
    now = time.monotonic()
    with state.lock:
        cached = state.history_cache.get(key)
    if cached:
        ttl = HISTORY_ERROR_TTL if cached[1].get("error") else HISTORY_TTL
        if now - cached[0] < ttl:
            return cached[1]
    timeout = min(state.timeout, HISTORY_TIMEOUT)
    errors = []
    for name, provider in (("yahoo", _yahoo_history), ("nasdaq", _nasdaq_history)):
        try:
            history = provider(symbol, timeout)
            with state.lock:
                state.history_cache[key] = (now, history)
            return history
        except Exception as exc:
            message = (str(exc).splitlines() or ["unknown error"])[0][:140]
            errors.append(f"{name}: {message}")
    result = {
        "symbol": symbol,
        "range": HISTORY_RANGE,
        "candles": [],
        "error": " / ".join(errors),
    }
    with state.lock:
        state.history_cache[key] = (now, result)
    return result


def load_qqq_members(state: State) -> list[str]:
    today = datetime.now(ET).date().isoformat()
    cached: list[str] = []
    try:
        payload = json.loads(QQQ_MEMBERS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = None
    if isinstance(payload, dict):
        raw = payload.get("tickers")
        if isinstance(raw, list):
            cached = [ticker for ticker in raw if isinstance(ticker, str) and ticker]
        if payload.get("date") == today and len(cached) >= 50:
            return cached
    try:
        tickers = max_pain.fetch_qqq_constituents(state.timeout)
    except (SystemExit, Exception) as exc:
        if len(cached) >= 50:
            return cached
        raise RuntimeError(str(exc)) from exc
    try:
        _atomic_write(
            QQQ_MEMBERS_PATH,
            {
                "date": today,
                "source": max_pain.QQQ_LIST_URL,
                "tickers": tickers,
            },
        )
    except OSError:
        pass
    return tickers


def load_seed() -> dict | None:
    if not DATA_DIR.exists():
        return None
    files = sorted(DATA_DIR.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if payload.get("kind") == "options_max_pain_snapshot" and payload.get("snapshots"):
            return payload
    return None


def load_batch(
    state: State,
    tickers: list[str],
    requested_expiry: date,
    throttle: max_pain.Throttle,
    workers: int,
) -> tuple[dict[str, max_pain.Chain], list[dict]]:
    loaded: dict[str, max_pain.Chain] = {}
    failed: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(
                max_pain.load_chain,
                ticker,
                requested_expiry,
                "nearest",
                state.timeout,
                throttle,
            ): ticker
            for ticker in tickers
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


def _carry_forward(
    previous: dict | None,
    requested: date,
    snapshots: list[dict],
    expected: set[str],
) -> int:
    if not previous or previous.get("requested_expiry") != requested.isoformat():
        return 0
    fresh = {item["ticker"] for item in snapshots}
    carried = 0
    for old in previous.get("snapshots", []):
        if old["ticker"] in fresh or old["ticker"] not in expected:
            continue
        item = dict(old)
        item["stale"] = True
        snapshots.append(item)
        carried += 1
    return carried


def do_refresh(state: State) -> dict:
    requested = state.expiry or max_pain.default_expiry(date.today())
    with state.lock:
        previous = copy.deepcopy(state.snapshot) if state.snapshot else None
        extras = sorted(state.extras)
        fixed = list(state.fixed_tickers) if state.fixed_tickers else None

    if fixed:
        tickers = fixed
        universe = None
    else:
        tickers = load_qqq_members(state)
        universe = {
            "name": "qqq",
            "source": max_pain.QQQ_LIST_URL,
            "requested": len(tickers),
            "loaded": 0,
            "carried": 0,
            "skipped": [],
            "extras": extras,
        }

    all_tickers = sorted(set(tickers) | set(extras))
    chains, skipped = load_batch(state, all_tickers, requested, state.throttle, state.workers)
    rate_limited = [item["ticker"] for item in skipped if "rate" in item["reason"].lower()]
    if rate_limited:
        time.sleep(2)
        retry_chains, retry_skipped = load_batch(
            state,
            rate_limited,
            requested,
            max_pain.Throttle(1.0),
            max(1, min(2, state.workers)),
        )
        chains.update(retry_chains)
        skipped = [item for item in skipped if item["ticker"] not in retry_chains] + retry_skipped

    if not chains:
        raise RuntimeError("no tickers loaded")

    snapshots = [max_pain.snapshot(chain, requested, False) for chain in chains.values()]
    carried = 0
    if universe is not None:
        carried = _carry_forward(
            previous, requested, snapshots, set(tickers) | set(extras)
        )
    snapshots.sort(key=max_pain._sort_key)

    if universe:
        fresh = {item["ticker"] for item in snapshots if not item.get("stale")}
        stale = {item["ticker"] for item in snapshots if item.get("stale")}
        universe["loaded"] = sum(1 for ticker in tickers if ticker in fresh)
        universe["carried"] = sum(1 for ticker in tickers if ticker in stale)
        universe["skipped"] = sorted(skipped, key=lambda item: item["ticker"])
        universe["extras"] = extras

    as_of = max((item["as_of"] for item in snapshots), default=_now_iso())
    result = {
        "schema_version": 2,
        "kind": "options_max_pain_snapshot",
        "generated_at": _now_iso(),
        "source": {
            "name": "Cboe delayed quotes",
            "url": max_pain.CBOE_URL.format(ticker="{ticker}"),
            "delay": "vendor-delayed intraday quotes",
            "note": "Open interest is the exchange's latest published value; intraday volume is partial.",
        },
        "as_of": as_of,
        "requested_expiry": requested.isoformat(),
        "expiry_mode": "nearest",
        "settlement": "PM close",
        "universe": universe,
        "extras": extras,
        "tickers": [item["ticker"] for item in snapshots],
        "snapshots": snapshots,
        "method": {
            "max_pain": "For every listed strike, sum intrinsic payout at that settlement: calls OI x max(0, S-K) + puts OI x max(0, K-S), times 100. Minimum wins.",
            "shelf": "Strikes whose total payout is within 1% of the minimum.",
            "one_sigma": "Spot x ATM IV x sqrt(DTE / 365).",
            "risk_reversal": "25-delta put IV minus 25-delta call IV, in volatility points.",
            "gex": "Black-Scholes gamma at each hypothetical spot x OI x 100 x S^2 x 0.01; calls positive, puts negative.",
        },
    }

    with state.lock:
        state.snapshot = result
        state.members = set(tickers)
        state.last_success = _now_iso()
        state.last_error = None
        state.detail_cache.clear()
    _atomic_write(LATEST_PATH, result)
    return result


def refresh(state: State) -> None:
    with state.lock:
        if state.refreshing:
            return
        state.refreshing = True
        state.last_attempt = _now_iso()
    try:
        do_refresh(state)
    except Exception as exc:
        with state.lock:
            state.last_error = str(exc)
    finally:
        with state.lock:
            state.refreshing = False
            state.last_refresh_at = time.time()
            state.next_refresh = datetime.fromtimestamp(
                state.last_refresh_at + state.interval, timezone.utc
            ).isoformat()


def refresh_loop(state: State) -> None:
    while not state.stop.is_set():
        now = time.time()
        watched = now - state.last_viewed < IDLE_SECONDS
        with state.lock:
            just_refreshed = now - state.last_refresh_at < min(REFRESH_DEDUPE_SECONDS, state.interval)
        if state.snapshot is None or (market_open() and watched and not just_refreshed):
            refresh(state)
        elif not just_refreshed:
            with state.lock:
                state.next_refresh = None
        state.stop.wait(state.interval)


def trigger_refresh(state: State) -> bool:
    with state.lock:
        if state.refreshing:
            return False
    threading.Thread(target=refresh, args=(state,), daemon=True).start()
    return True


def _find_snapshot(state: State, symbol: str) -> dict | None:
    with state.lock:
        snapshot = state.snapshot
    if not snapshot:
        return None
    for item in snapshot.get("snapshots", []):
        if item["ticker"] == symbol:
            return item
    return None


def _load_chain_bundle(
    state: State, symbol: str, target: date, requested: date, mode: str
) -> tuple[max_pain.Chain, date, list[max_pain.Chain]]:
    raw = max_pain.fetch_payload(symbol, state.timeout, state.throttle)
    expiries = max_pain.available_expiries(raw)
    actual = max_pain.resolve_expiry(expiries, target, mode)
    primary = None
    if actual is not None:
        try:
            primary = max_pain.build_chain(raw, symbol, actual)
        except max_pain.TickerUnavailable:
            primary = None
    if primary is None:
        actual = max_pain.resolve_expiry(expiries, requested, "nearest")
        if actual is None:
            raise max_pain.TickerUnavailable(f"no listed expiry for {symbol}")
        primary = max_pain.build_chain(raw, symbol, actual)

    chains = []
    for expiry in expiries:
        if expiry == actual:
            chains.append(primary)
            continue
        try:
            chains.append(max_pain.build_chain(raw, symbol, expiry))
        except max_pain.TickerUnavailable:
            continue
    return primary, actual, chains


def _chain_payload(state: State, symbol: str) -> dict:
    now = time.monotonic()
    with state.lock:
        cached = state.detail_cache.get(symbol)
        requested_text = state.requested_expiry
    if cached and now - cached[0] < DETAIL_TTL:
        return cached[1]
    if requested_text:
        requested = date.fromisoformat(requested_text)
    else:
        requested = state.expiry or max_pain.default_expiry(date.today())
    row = _find_snapshot(state, symbol)
    target = date.fromisoformat(row["expiry"]) if row else requested
    mode = "exact" if row else "nearest"
    chain, actual, chains = _load_chain_bundle(
        state, symbol, target, requested, mode
    )
    snap = max_pain.snapshot(chain, requested, False)
    expiry_series = []
    for item in chains:
        rows = [
            [row.strike, row.call_oi, row.put_oi]
            for row in item.rows
            if row.call_oi or row.put_oi
        ]
        if not rows and item.expiry != actual:
            continue
        expiry_series.append(
            {
                "expiry": item.expiry.isoformat(),
                "dte": item.dte,
                "primary": item.expiry == actual,
                "rows": rows,
            }
        )
    payload = {
        "ok": True,
        "symbol": chain.ticker,
        "spot": chain.spot,
        "expiry": chain.expiry.isoformat(),
        "requested_expiry": requested.isoformat(),
        "actual_expiry": actual.isoformat(),
        "dte": chain.dte,
        "as_of": chain.as_of,
        "chain": [item.to_dict() for item in chain.rows],
        "expiry_series": expiry_series,
        "metrics": snap["metrics"],
        "snapshot": snap,
        "history": fetch_history(state, symbol),
    }
    with state.lock:
        state.detail_cache[symbol] = (now, payload)
    return payload


class Handler(BaseHTTPRequestHandler):
    state: State
    server_version = "MaxPainLive/1.0"

    def log_message(self, fmt: str, *args) -> None:
        if self.state.verbose:
            super().log_message(fmt, *args)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        try:
            body = path.read_bytes()
        except OSError:
            self._send_json({"ok": False, "error": "not found"}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _snapshot_payload(self) -> dict:
        with self.state.lock:
            return {
                "ok": self.state.snapshot is not None,
                "refreshing": self.state.refreshing,
                "last_error": self.state.last_error,
                "last_success": self.state.last_success,
                "last_attempt": self.state.last_attempt,
                "next_refresh": self.state.next_refresh,
                "interval": self.state.interval,
                "market_open": market_open(),
                "requested_expiry": self.state.requested_expiry,
                "extras": sorted(self.state.extras),
                "snapshot": copy.deepcopy(self.state.snapshot),
            }

    def _ticker_payload(self, symbol: str) -> tuple[dict, int]:
        if not SYMBOL_RE.match(symbol):
            return {"ok": False, "error": "invalid ticker"}, 400
        row = _find_snapshot(self.state, symbol)
        if row and not row.get("stale"):
            return {"ok": True, "snapshot": row, "cached": True}, 200
        try:
            payload = _chain_payload(self.state, symbol)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}, 404
        item = payload["snapshot"]
        with self.state.lock:
            if symbol not in self.state.members:
                self.state.extras.add(symbol)
            snapshot = self.state.snapshot
            if snapshot:
                items = [item for item in snapshot.get("snapshots", []) if item["ticker"] != symbol]
                items.append(item)
                items.sort(key=max_pain._sort_key)
                snapshot["snapshots"] = items
                snapshot["generated_at"] = _now_iso()
                if item["as_of"] > snapshot.get("as_of", ""):
                    snapshot["as_of"] = item["as_of"]
                snapshot["extras"] = sorted(self.state.extras)
                universe = snapshot.get("universe")
                if universe is not None:
                    universe["extras"] = sorted(self.state.extras)
                _atomic_write(LATEST_PATH, snapshot)
            else:
                self.state.snapshot = {
                    "schema_version": 2,
                    "kind": "options_max_pain_snapshot",
                    "generated_at": _now_iso(),
                    "as_of": item["as_of"],
                    "requested_expiry": item["requested_expiry"],
                    "expiry_mode": "nearest",
                    "universe": None,
                    "extras": sorted(self.state.extras),
                    "tickers": [symbol],
                    "snapshots": [item],
                }
        return {"ok": True, "snapshot": item, "cached": False}, 200

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send_file(INDEX_PATH, "text/html; charset=utf-8")
            return
        if parsed.path == "/api/snapshot":
            now = time.time()
            was_idle = now - self.state.last_viewed >= IDLE_SECONDS
            self.state.last_viewed = now
            if was_idle and market_open():
                trigger_refresh(self.state)
            self._send_json(self._snapshot_payload())
            return
        if parsed.path == "/api/ticker":
            params = parse_qs(parsed.query)
            symbol = (params.get("symbol") or [""])[0].strip().upper()
            payload, status = self._ticker_payload(symbol)
            self._send_json(payload, status)
            return
        if parsed.path == "/api/chain":
            params = parse_qs(parsed.query)
            symbol = (params.get("symbol") or [""])[0].strip().upper()
            if not SYMBOL_RE.match(symbol):
                self._send_json({"ok": False, "error": "invalid ticker"}, 400)
                return
            try:
                self._send_json(_chain_payload(self.state, symbol))
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, 404)
            return
        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        self._send_json({"ok": False, "error": "not found"}, 404)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/refresh":
            self._send_json({"ok": False, "error": "not found"}, 404)
            return
        started = trigger_refresh(self.state)
        self._send_json({"ok": True, "started": started}, 202 if started else 200)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="port (default: 8000)")
    parser.add_argument("--interval", type=int, default=900, help="seconds between universe refreshes while watched (default: 900)")
    parser.add_argument("--expiry", type=max_pain.parse_date, help="requested expiry (default: next Friday)")
    parser.add_argument("--workers", type=int, default=4, help="parallel Cboe requests (default: 4)")
    parser.add_argument("--timeout", type=float, default=45.0, help="request timeout in seconds")
    parser.add_argument("--tickers", nargs="+", help="limit the board to these tickers instead of the QQQ universe")
    parser.add_argument("--quiet", action="store_true", help="suppress request logs")
    args = parser.parse_args(argv)

    if max_pain.requests is None:
        raise SystemExit("requests is required: python3 -m pip install -r requirements.txt")
    if args.interval < 60:
        parser.error("--interval must be at least 60 seconds")

    state = State(args)
    state.snapshot = load_seed()
    if state.snapshot:
        state.members = {item["ticker"] for item in state.snapshot.get("snapshots", [])}
        state.extras = (
            set(state.snapshot.get("extras") or [])
            | set((state.snapshot.get("universe") or {}).get("extras") or [])
        ) - state.members
        state.last_success = state.snapshot.get("generated_at")
        state.requested_expiry = (
            args.expiry.isoformat() if args.expiry else state.snapshot.get("requested_expiry")
        )
    if args.tickers:
        keep = {ticker.upper() for ticker in args.tickers}
        state.members = keep
        if state.snapshot:
            state.snapshot["snapshots"] = [
                item for item in state.snapshot.get("snapshots", []) if item["ticker"] in keep
            ]
            state.snapshot["tickers"] = [item["ticker"] for item in state.snapshot["snapshots"]]
            state.snapshot["universe"] = None

    Handler.state = state
    threading.Thread(target=refresh_loop, args=(state,), daemon=True).start()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    print(f"Live max-pain board: http://{args.host}:{args.port}")
    print(f"Refreshing every {args.interval}s during market hours while a viewer is active. Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        state.stop.set()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
