"""Core earnings-straddle engine (seller's perspective). Data: yfinance (free, delayed, best-effort)."""
from __future__ import annotations
import math, time, datetime as dt
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import yfinance as yf

NY = ZoneInfo("America/New_York")
CHI = ZoneInfo("America/Chicago")
N_HIST = 12            # past earnings to analyze
RATE = 0.04            # risk-free rate for IV inversion


def now_chi() -> dt.datetime:
    return dt.datetime.now(CHI)


def retry(fn, tries=3, delay=2.0):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa
            last = e
            time.sleep(delay * (i + 1))
    raise last


# ---------------------------------------------------------------- earnings dates
def classify_timing(ts: pd.Timestamp) -> str:
    """BMO / AMC / UNK from the earnings timestamp (NY time)."""
    t = ts.tz_convert(NY) if ts.tzinfo else ts.tz_localize(NY)
    mins = t.hour * 60 + t.minute
    if mins == 0:
        return "UNK"
    if mins < 9 * 60 + 30:
        return "BMO"
    if mins >= 16 * 60:
        return "AMC"
    return "UNK"   # intraday stamps (e.g. 15:00) are usually placeholders / unconfirmed


def get_earnings(tk: yf.Ticker, limit=N_HIST + 8):
    ed = retry(lambda: tk.get_earnings_dates(limit=limit))
    if ed is None or len(ed) == 0:
        raise RuntimeError("no earnings dates from yfinance")
    ed = ed[~ed.index.duplicated()].sort_index()
    rows = []
    for ts, r in ed.iterrows():
        rows.append({"ts": ts, "date": ts.tz_convert(NY).date(), "timing": classify_timing(ts),
                     "eps_est": r.get("EPS Estimate"), "eps_act": r.get("Reported EPS"),
                     "surprise": r.get("Surprise(%)")})
    df = pd.DataFrame(rows)
    # Same-day duplicates (rare) -> keep first
    df = df.drop_duplicates("date")
    today = now_chi().date()
    # Today's event (even if already reported AMC) counts as "next": its reaction is still ahead/in progress.
    past = df[df["date"] < today]
    future = df[df["date"] >= today]
    nxt = future.iloc[0].to_dict() if len(future) else None
    # Fallback: calendar
    if nxt is None:
        try:
            cal = tk.calendar or {}
            d = (cal.get("Earnings Date") or [None])[0]
            if d and d >= today:
                nxt = {"date": d, "timing": "UNK", "ts": None}
        except Exception:
            pass
    return nxt, past.tail(N_HIST).reset_index(drop=True)


# ---------------------------------------------------------------- price history / realized moves
def get_history(tk: yf.Ticker) -> pd.DataFrame:
    h = retry(lambda: tk.history(period="5y", auto_adjust=False))
    if h is None or h.empty:
        raise RuntimeError("no price history")
    h.index = pd.DatetimeIndex([d.date() for d in h.index])
    return h[["Open", "High", "Low", "Close"]]


def reaction_idx(h: pd.DataFrame, d: dt.date, timing: str):
    """Return (pre_idx, react_idx, timing_used, inferred_flag)."""
    idx = h.index
    pos = idx.searchsorted(pd.Timestamp(d))      # first trading day >= d
    if pos >= len(idx):
        return None
    on_day = idx[pos].date() == d

    def bmo():
        p = pos  # reaction is earnings day (or next trading day if d was a holiday)
        return (p - 1, p) if p >= 1 else None

    def amc():
        p = pos + 1 if on_day else pos
        return (p - 1, p) if p >= 1 and p < len(idx) else None

    if timing == "BMO":
        r = bmo(); return (*r, "BMO", False) if r else None
    if timing == "AMC":
        r = amc(); return (*r, "AMC", False) if r else None
    # Unknown: infer from the larger overnight gap
    cands = []
    for lab, f in (("BMO", bmo), ("AMC", amc)):
        r = f()
        if r:
            g = abs(h["Open"].iloc[r[1]] / h["Close"].iloc[r[0]] - 1)
            cands.append((g, lab, r))
    if not cands:
        return None
    g, lab, r = max(cands)
    return (*r, lab, True)


def realized_moves(h: pd.DataFrame, past: pd.DataFrame) -> pd.DataFrame:
    out = []
    for _, e in past.iterrows():
        r = reaction_idx(h, e["date"], e["timing"])
        if not r:
            continue
        pi, ri, tused, inferred = r
        pc, ro, rc = h["Close"].iloc[pi], h["Open"].iloc[ri], h["Close"].iloc[ri]
        out.append({"earnings_date": e["date"].isoformat(), "timing": tused, "timing_inferred": inferred,
                    "pre_close_date": h.index[pi].date().isoformat(), "reaction_date": h.index[ri].date().isoformat(),
                    "pre_close": round(float(pc), 4), "react_open": round(float(ro), 4), "react_close": round(float(rc), 4),
                    "move_close_pct": round(100 * (rc / pc - 1), 3), "move_open_pct": round(100 * (ro / pc - 1), 3),
                    "abs_close_pct": round(abs(100 * (rc / pc - 1)), 3), "abs_open_pct": round(abs(100 * (ro / pc - 1)), 3),
                    "eps_surprise_pct": None if pd.isna(e.get("surprise")) else float(e.get("surprise"))})
    return pd.DataFrame(out)


def next_trading_day(d: dt.date) -> dt.date:
    d += dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def reaction_day_future(d: dt.date, timing: str) -> dt.date:
    # UNK -> assume AMC (conservative: picks the later expiry so the event is always covered)
    return d if timing == "BMO" else next_trading_day(d)


# ---------------------------------------------------------------- options
def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_straddle(S, K, T, sig, r=RATE):
    if T <= 0 or sig <= 0:
        return abs(S - K)
    d1 = (math.log(S / K) + (r + 0.5 * sig * sig) * T) / (sig * math.sqrt(T))
    d2 = d1 - sig * math.sqrt(T)
    c = S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    p = c - S + K * math.exp(-r * T)
    return c + p


def straddle_iv(price, S, K, T):
    """Invert BS straddle price for a single vol (bisection)."""
    if not (price and T > 0) or price <= bs_straddle(S, K, T, 1e-4):
        return None
    lo, hi = 1e-4, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if bs_straddle(S, K, T, mid) > price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def year_frac(expiry: dt.date, now: dt.datetime | None = None) -> float:
    """Trading-day year fraction to expiry close (counts the rest of today if market open)."""
    now = now or now_chi()
    nyt = now.astimezone(NY)
    days = np.busday_count(nyt.date() + dt.timedelta(days=1), expiry + dt.timedelta(days=1))
    if nyt.weekday() < 5 and nyt.hour * 60 + nyt.minute < 16 * 60:
        frac = max(0.0, (16 * 60 - max(9 * 60 + 30, nyt.hour * 60 + nyt.minute)) / 390)
        days += frac
    return float(days) / 252.0


def _px(row):
    b, a, l = row.get("bid"), row.get("ask"), row.get("lastPrice")
    if pd.notna(b) and pd.notna(a) and b > 0 and a > 0 and a >= b:
        return (b + a) / 2, "mid", float(a - b)
    if pd.notna(l) and l > 0:
        return float(l), "last", None
    return None, None, None


def atm_straddle(tk: yf.Ticker, expiry: str, spot: float) -> dict:
    ch = retry(lambda: tk.option_chain(expiry))
    c, p = ch.calls.set_index("strike"), ch.puts.set_index("strike")
    strikes = sorted(set(c.index) & set(p.index))
    if not strikes:
        raise RuntimeError(f"empty chain {expiry}")
    K = min(strikes, key=lambda k: abs(k - spot))
    cp, csrc, cspr = _px(c.loc[K])
    pp, psrc, pspr = _px(p.loc[K])
    if cp is None or pp is None:
        raise RuntimeError(f"no usable quotes at K={K} {expiry}")
    straddle = cp + pp
    # Adjust for strike != spot: straddle at K differs from ATM by ~|S-K| intrinsic asymmetry; we report raw.
    T = year_frac(dt.date.fromisoformat(expiry))
    iv = straddle_iv(straddle, spot, K, T) if T > 0 else None
    yiv = np.nanmean([c.loc[K].get("impliedVolatility"), p.loc[K].get("impliedVolatility")])
    spread = (cspr or 0) + (pspr or 0) if (cspr is not None and pspr is not None) else None
    return {"expiry": expiry, "strike": float(K), "call": round(cp, 4), "put": round(pp, 4),
            "price_src": csrc if csrc == psrc else f"{csrc}/{psrc}", "straddle": round(straddle, 4),
            "implied_move_pct": round(100 * straddle / spot, 3), "T_years": round(T, 5),
            "iv_straddle": None if iv is None else round(iv, 4),
            "iv_yf": None if np.isnan(yiv) else round(float(yiv), 4),
            "spread": None if spread is None else round(spread, 4),
            "spread_pct_of_straddle": None if not spread else round(100 * spread / straddle, 1),
            "call_oi": int(c.loc[K].get("openInterest") or 0) if pd.notna(c.loc[K].get("openInterest")) else 0,
            "put_oi": int(p.loc[K].get("openInterest") or 0) if pd.notna(p.loc[K].get("openInterest")) else 0}


def pick_expiries(expiries, react_day: dt.date):
    ex = [dt.date.fromisoformat(e) for e in expiries]
    post = next((e for e in ex if e >= react_day), None)
    today = now_chi().date()
    pre = [e for e in ex if e < react_day and e > today]
    pre = pre[-1] if pre else None
    return (post.isoformat() if post else None), (pre.isoformat() if pre else None)


def earnings_only_move(post: dict, pre: dict | None):
    """Back out the earnings-day move from the term structure:
    sigma_post^2*T_post = sigma_pre^2*(T_post - 1d) + E^2 ; expected |move| = E*sqrt(2/pi)."""
    if not pre or not post.get("iv_straddle") or not pre.get("iv_straddle"):
        return None
    s1, T1, s0 = post["iv_straddle"], post["T_years"], pre["iv_straddle"]
    var = s1 * s1 * T1 - s0 * s0 * max(T1 - 1 / 252, 0)
    if var <= 0:
        return None
    return round(100 * math.sqrt(var) * math.sqrt(2 / math.pi), 3)


# ---------------------------------------------------------------- seller stats
def seller_stats(moves: pd.DataFrame, implied: float | None, col="abs_close_pct") -> dict:
    if moves is None or moves.empty:
        return {}
    a = moves[col].astype(float)
    s = {"n_quarters": int(len(a)), "avg_abs_move_pct": round(a.mean(), 3), "median_abs_move_pct": round(a.median(), 3),
         "max_abs_move_pct": round(a.max(), 3), "avg_abs_open_move_pct": round(moves["abs_open_pct"].mean(), 3)}
    if implied:
        pnl = implied - a
        s.update({"implied_over_avg": round(implied / a.mean(), 3) if a.mean() else None,
                  "implied_over_median": round(implied / a.median(), 3) if a.median() else None,
                  "pct_exceeded_implied": round(100 * (a > implied).mean(), 1),
                  "seller_hit_rate": round(100 * (a < implied).mean(), 1),
                  "avg_pnl_pct_spot": round(pnl.mean(), 3), "total_pnl_pct_spot": round(pnl.sum(), 3),
                  "worst_pnl_pct_spot": round(pnl.min(), 3),
                  "avg_pnl_pct_premium": round(100 * pnl.mean() / implied, 1)})
    return s


# ---------------------------------------------------------------- top-level
def analyze(symbol: str) -> dict:
    symbol = symbol.upper().replace(".", "-")
    tk = yf.Ticker(symbol)
    res = {"ticker": symbol, "as_of": now_chi().isoformat(timespec="seconds"), "notes": [], "error": None}
    nxt, past = get_earnings(tk)
    hist = get_history(tk)
    spot = None
    try:
        spot = float(tk.fast_info["lastPrice"])
    except Exception:
        pass
    if not spot or math.isnan(spot):
        spot = float(hist["Close"].iloc[-1])
    res["spot"] = round(spot, 4)
    moves = realized_moves(hist, past)
    if not moves.empty and moves["timing_inferred"].any():
        res["notes"].append(f"{int(moves['timing_inferred'].sum())} past quarter(s) had unknown BMO/AMC timing; "
                            "reaction day inferred from the larger overnight gap.")
    res["history"] = moves.to_dict("records")
    if nxt:
        d = nxt["date"]
        res["next_earnings"] = d.isoformat()
        res["timing"] = nxt["timing"]
        res["days_to_earnings"] = (d - now_chi().date()).days
        rd = reaction_day_future(d, nxt["timing"])
        res["reaction_day"] = rd.isoformat()
        if nxt["timing"] == "UNK":
            res["notes"].append("Next earnings timing unknown/unconfirmed -> assumed AMC (reaction next trading day) "
                                "for expiry selection.")
        expiries = retry(lambda: tk.options)
        if not expiries:
            res["notes"].append("No listed options in yfinance.")
        else:
            post_e, pre_e = pick_expiries(expiries, rd)
            if post_e:
                post = atm_straddle(tk, post_e, spot)
                res["post"] = post
                res["implied_move_pct"] = post["implied_move_pct"]
                res["days_event_to_expiry"] = int(np.busday_count(rd, dt.date.fromisoformat(post_e)))
                if res["days_event_to_expiry"] > 5:
                    res["notes"].append(f"Post-earnings expiry is {res['days_event_to_expiry']} trading days after the "
                                        "reaction day; straddle includes material non-earnings time value.")
                if pre_e:
                    try:
                        pre = atm_straddle(tk, pre_e, spot)
                        res["pre"] = pre
                        res["earnings_only_move_pct"] = earnings_only_move(post, pre)
                    except Exception as e:
                        res["notes"].append(f"Pre-earnings expiry {pre_e} unusable: {e}")
                if post["price_src"] != "mid":
                    res["notes"].append(f"Straddle priced from last trade ({post['price_src']}), not bid/ask mid.")
            else:
                res["notes"].append("No listed expiry after the earnings reaction day yet.")
    else:
        res["notes"].append("No upcoming earnings date found.")
    res["stats"] = seller_stats(moves, res.get("implied_move_pct"))
    eo = res.get("earnings_only_move_pct")
    if eo and not moves.empty:
        res["stats_earnings_only"] = seller_stats(moves, eo)
    return res
