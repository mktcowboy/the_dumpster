#!/usr/bin/env python
"""Append today's ATM straddle for the earnings event's post-earnings expiry to output/snapshots.csv.
Usage: python snapshot.py [TICKER ...]   (no args = all Nasdaq-100)
Event = the most recent earnings if within the last 10 calendar days and its post-earnings expiry hasn't expired
(so we keep tracking the same contract through the IV crush); otherwise the next earnings."""
import sys, os, csv, time, datetime as dt
import numpy as np
import yfinance as yf
from core import (now_chi, get_earnings, reaction_day_future, pick_expiries, atm_straddle, earnings_only_move,
                  retry, reaction_idx, get_history)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
CSV = os.path.join(OUT, "snapshots.csv")
FIELDS = ["snapshot_ts", "snapshot_date", "ticker", "event_date", "timing", "reaction_day", "phase",
          "cal_days_to_earnings", "tdays_to_reaction", "expiry", "spot", "strike", "call", "put", "straddle",
          "implied_move_pct", "iv_straddle", "iv_yf", "price_src", "pre_expiry", "pre_straddle", "pre_iv_straddle",
          "earnings_only_move_pct"]


def snap(sym):
    sym = sym.upper().replace(".", "-")
    tk = yf.Ticker(sym)
    now = now_chi(); today = now.date()
    nxt, past = get_earnings(tk)
    ev = None
    if len(past):
        last = past.iloc[-1]
        if (today - last["date"]).days <= 10:
            ev = {"date": last["date"], "timing": last["timing"]}
            if ev["timing"] == "UNK":   # infer from the actual gap now that it's happened
                try:
                    r = reaction_idx(get_history(tk), last["date"], "UNK")
                    if r: ev["timing"] = r[2]
                except Exception:
                    pass
    if ev is None:
        if not nxt:
            raise RuntimeError("no earnings date")
        ev = {"date": nxt["date"], "timing": nxt["timing"]}
    rd = reaction_day_future(ev["date"], ev["timing"])
    spot = float(tk.fast_info["lastPrice"])
    exps = retry(lambda: tk.options)
    if not exps:
        raise RuntimeError("no options")
    post_e, pre_e = pick_expiries(exps, rd)
    if post_e is None:
        raise RuntimeError("no post-earnings expiry")
    post = atm_straddle(tk, post_e, spot)
    pre = None
    if pre_e and rd > today:
        try:
            pre = atm_straddle(tk, pre_e, spot)
        except Exception:
            pre = None
    tdays = int(np.busday_count(today, rd)) if rd >= today else -int(np.busday_count(rd, today))
    phase = "pre" if (today < rd) else ("reaction" if today == rd else "post")
    return {"snapshot_ts": now.isoformat(timespec="seconds"), "snapshot_date": today.isoformat(), "ticker": sym,
            "event_date": ev["date"].isoformat(), "timing": ev["timing"], "reaction_day": rd.isoformat(), "phase": phase,
            "cal_days_to_earnings": (ev["date"] - today).days, "tdays_to_reaction": tdays, "expiry": post_e,
            "spot": round(spot, 4), "strike": post["strike"], "call": post["call"], "put": post["put"],
            "straddle": post["straddle"], "implied_move_pct": post["implied_move_pct"],
            "iv_straddle": post["iv_straddle"], "iv_yf": post["iv_yf"], "price_src": post["price_src"],
            "pre_expiry": pre["expiry"] if pre else "", "pre_straddle": pre["straddle"] if pre else "",
            "pre_iv_straddle": pre["iv_straddle"] if pre else "",
            "earnings_only_move_pct": earnings_only_move(post, pre) if pre else ""}


def run(symbols, delay=0.4):
    os.makedirs(OUT, exist_ok=True)
    new = not os.path.exists(CSV)
    ok, fail = 0, []
    with open(CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for s in symbols:
            try:
                w.writerow(snap(s)); f.flush(); ok += 1
            except Exception as e:
                fail.append((s, str(e)[:120]))
            time.sleep(delay)
    print(f"snapshot: {ok} ok, {len(fail)} failed -> {CSV}")
    for s, e in fail:
        print(f"  FAIL {s}: {e}")
    return ok, fail


if __name__ == "__main__":
    if len(sys.argv) > 1:
        syms = sys.argv[1:]
    else:
        from n100 import get_n100
        syms = [x["ticker"] for x in get_n100()]
    run(syms)
