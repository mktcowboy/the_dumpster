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
    u = t.tz_convert("UTC")
    if u.hour == 20 and u.minute == 0:   # Yahoo's "after close" stamp (16:00 EDT) shown as 15:00 EST after DST ends
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
            "put_oi": int(p.loc[K].get("openInterest") or 0) if pd.notna(p.loc[K].get("openInterest")) else 0,
            "call_vol": int(c.loc[K].get("volume")) if pd.notna(c.loc[K].get("volume")) else 0,
            "put_vol": int(p.loc[K].get("volume")) if pd.notna(p.loc[K].get("volume")) else 0}


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


# ---------------------------------------------------------------- liquidity
def liquidity(post: dict, cfg=None) -> dict:
    from config import CFG
    cfg = cfg or CFG
    oi = (post.get("call_oi") or 0) + (post.get("put_oi") or 0)
    vol = (post.get("call_vol") or 0) + (post.get("put_vol") or 0)
    sp = post.get("spread_pct_of_straddle")
    grade = "F"
    if sp is not None and post.get("price_src") == "mid":
        for g in ("A", "B", "C"):
            t = cfg["liquidity_grades"][g]
            if oi >= t["min_oi"] and vol >= t["min_volume"] and sp <= t["max_spread_pct"]:
                grade = g
                break
    return {"atm_oi": oi, "atm_volume": vol, "spread_pct_of_mid": sp, "grade": grade}


# ---------------------------------------------------------------- earnings event resolution (Yahoo x Nasdaq)
def resolve_event(tk: yf.Ticker, nxt: dict | None, symbol: str) -> dict:
    from earnings_cal import lookup, reconcile
    today = now_chi().date()
    y_est = None
    try:
        y_est = tk.info.get("isEarningsDateEstimate")
    except Exception:
        pass
    try:
        hit, meta = lookup(symbol, today)
    except Exception as e:
        hit, meta = None, {"error": str(e)}
    r = reconcile(nxt["date"] if nxt else None, nxt["timing"] if nxt else "UNK", y_est, hit)
    r["nasdaq_meta"] = meta
    return r


# ---------------------------------------------------------------- cost-aware P&L model
def ex_earnings_vol(h: pd.DataFrame, moves: pd.DataFrame, lookback=63) -> float | None:
    """Annualized realized vol of the last `lookback` closes, excluding earnings reaction days."""
    r = np.log(h["Close"]).diff().dropna()
    if moves is not None and len(moves):
        excl = set(pd.to_datetime(moves["reaction_date"]))
        r = r[~r.index.isin(excl)]
    r = r.tail(lookback)
    return float(r.std() * math.sqrt(252)) if len(r) > 20 else None


def residual_model(post: dict, pre: dict | None, react_day: dt.date, hist_vol: float | None) -> dict | None:
    """Term-structure model (documented on the site):
      sigma_ex  = ATM IV of the expiry before earnings (fallback: 63d realized vol ex-earnings days)
      E^2       = sigma_post^2*T_post - sigma_ex^2*(T_post - 1d)        (earnings-day variance)
      T_rem     = trading days from reaction-day close to post expiry
      entry     = ATM straddle at the close before the event with variance E^2 + sigma_ex^2*T_rem (+ 1 day of time)
      exit(m)   = BS straddle at reaction-day close: spot*(1+m), strike = old spot, T_rem, sigma_ex  (residual time value)
    All in % of spot, r=0."""
    s1, T1 = post.get("iv_straddle"), post.get("T_years")
    if not s1 or not T1:
        return None
    if pre and pre.get("iv_straddle"):
        s_ex, src = pre["iv_straddle"], "pre-earnings expiry ATM IV"
    elif hist_vol:
        s_ex, src = hist_vol, "63d realized vol ex-earnings (proxy: no pre-earnings expiry)"
    else:
        return None
    exp = dt.date.fromisoformat(post["expiry"])
    t_rem = max(int(np.busday_count(react_day, exp)), 0) / 252
    E2 = s1 * s1 * T1 - s_ex * s_ex * max(T1 - 1 / 252, 0)
    flag = None
    if E2 <= 0:
        E2, flag = 0.0, "term structure shows no earnings premium (E=0)"
    T_e = t_rem + 1 / 252
    sig_e = math.sqrt((E2 + s_ex * s_ex * t_rem) / T_e)
    entry = 100 * bs_straddle(1.0, 1.0, T_e, sig_e, r=0.0)
    return {"sigma_ex": round(s_ex, 4), "sigma_ex_src": src, "E_std_pct": round(100 * math.sqrt(E2), 3),
            "t_rem_days": int(round(t_rem * 252)), "entry_premium_pct": round(entry, 3), "flag": flag}


def exit_value_pct(m: float, model: dict) -> float:
    return 100 * bs_straddle(1.0 + m, 1.0, model["t_rem_days"] / 252, model["sigma_ex"], r=0.0)


def costs_pct(post: dict, spot: float, cfg=None) -> dict:
    from config import CFG
    cfg = cfg or CFG
    spread = post.get("spread")
    est = False
    if spread is None or post.get("price_src") != "mid":
        spread = post["straddle"] * cfg["default_spread_pct_of_mid_if_unknown"] / 100
        est = True
    half = spread / 2
    entry = cfg["entry_slippage_frac_of_half_spread"] * half / spot * 100
    exit_ = cfg["exit_slippage_frac_of_half_spread"] * half * cfg["exit_spread_multiplier"] / spot * 100
    comm = 4 * cfg["commission_per_contract"] / (100 * spot) * 100   # 2 legs x (open+close), per 1 straddle = 100 sh
    return {"entry_slip_pct": round(entry, 4), "exit_slip_pct": round(exit_, 4), "commission_pct": round(comm, 4),
            "total_cost_pct": round(entry + exit_ + comm, 4), "spread_estimated": est, "spread_used": round(spread, 4)}


def cost_pnl(moves: pd.DataFrame, model: dict | None, costs: dict | None) -> tuple[list, dict]:
    if moves is None or moves.empty or not model or not costs:
        return [], {}
    prem = model["entry_premium_pct"]
    per = []
    for _, x in moves.iterrows():
        m = x["move_close_pct"] / 100
        ex = exit_value_pct(m, model)
        g = prem - ex
        per.append({"earnings_date": x["earnings_date"], "move_pct": x["move_close_pct"], "exit_value_pct": round(ex, 3),
                    "gross_pct": round(g, 3), "net_pct": round(g - costs["total_cost_pct"], 3)})
    net = np.array([p["net_pct"] for p in per]); gross = np.array([p["gross_pct"] for p in per])
    k = max(1, math.ceil(len(net) * 0.25))
    st = {"entry_premium_pct": prem, "cost_pct": costs["total_cost_pct"],
          "gross_avg_pct": round(gross.mean(), 3), "net_avg_pct": round(net.mean(), 3),
          "net_avg_pct_of_premium": round(100 * net.mean() / prem, 1) if prem else None,
          "gross_hit_rate": round(100 * (gross > 0).mean(), 1), "net_hit_rate": round(100 * (net > 0).mean(), 1),
          "net_worst_pct": round(net.min(), 3), "net_tail25_pct": round(np.sort(net)[:k].mean(), 3),
          "net_avg_win_pct": round(net[net > 0].mean(), 3) if (net > 0).any() else None,
          "net_avg_loss_pct": round(net[net <= 0].mean(), 3) if (net <= 0).any() else None}
    return per, st


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
    ev = resolve_event(tk, nxt, symbol)
    res["date_check"] = {k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in ev.items()}
    res["date_status"] = ev["status"]
    if ev["status"] == "Mismatch":
        res["notes"].append(f"Earnings date/timing mismatch ({ev['detail']}); using {ev['date']} {ev['timing']} "
                            f"({ev['timing_src']}), expiry chosen to cover both candidates.")
    if ev.get("date"):
        d, timing = ev["date"], ev["timing"] or "UNK"
        res["next_earnings"] = d.isoformat()
        res["timing"] = timing
        res["timing_src"] = ev.get("timing_src")
        res["days_to_earnings"] = (d - now_chi().date()).days
        rd = reaction_day_future(d, timing)
        if ev.get("alt_date"):
            rd = max(rd, reaction_day_future(ev["alt_date"], ev.get("alt_timing") or "UNK"))
        res["reaction_day"] = rd.isoformat()
        if timing == "UNK":
            res["notes"].append("Next earnings timing unknown in all sources -> assumed AMC (reaction next trading day) "
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
                res["liquidity"] = liquidity(post)
                if res["days_event_to_expiry"] > 5:
                    res["notes"].append(f"Post-earnings expiry is {res['days_event_to_expiry']} trading days after the "
                                        "reaction day; straddle includes material non-earnings time value.")
                pre = None
                if pre_e:
                    try:
                        pre = atm_straddle(tk, pre_e, spot)
                        res["pre"] = pre
                        res["earnings_only_move_pct"] = earnings_only_move(post, pre)
                    except Exception as e:
                        res["notes"].append(f"Pre-earnings expiry {pre_e} unusable: {e}")
                if post["price_src"] != "mid":
                    res["notes"].append(f"Straddle priced from last trade ({post['price_src']}), not bid/ask mid.")
                hv = ex_earnings_vol(hist, moves)
                res["hist_vol_ex_earnings"] = None if hv is None else round(hv, 4)
                model = residual_model(post, pre, rd, hv)
                res["model"] = model
                if model:
                    res["costs"] = costs_pct(post, spot)
                    if res["costs"]["spread_estimated"]:
                        res["notes"].append("Bid/ask spread unavailable; costs use default spread % from config.")
                    if model.get("flag"):
                        res["notes"].append("Model: " + model["flag"])
                    per, st = cost_pnl(moves, model, res["costs"])
                    res["pnl_per_quarter"], res["pnl_stats"] = per, st
            else:
                res["notes"].append("No listed expiry after the earnings reaction day yet.")
    else:
        res["notes"].append("No upcoming earnings date found.")
    res["stats"] = seller_stats(moves, res.get("implied_move_pct"))
    eo = res.get("earnings_only_move_pct")
    if eo and not moves.empty:
        res["stats_earnings_only"] = seller_stats(moves, eo)
    return res
