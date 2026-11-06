#!/usr/bin/env python
"""Append ATM straddle snapshots for each name's earnings event to output/snapshots.csv.

Usage: python snapshot.py [--session am|pm] [--reporters-only] [TICKER ...]   (no tickers = all Nasdaq-100)
  --session         tag rows 'am' or 'pm' (default: by America/Chicago clock, am before config cutoff hour)
  --reporters-only  only names whose reaction day is today (reported last night AMC or pre-market today);
                    candidates come from output/results.json (yesterday's batch), so the morning run is quick.
Event = the most recent earnings if within the last 10 calendar days and its post-earnings expiry hasn't expired
(we keep tracking the same contract through the IV crush); otherwise the next earnings (Yahoo x Nasdaq resolved).
After the event, also re-prices the straddle at the strike held in the last pre-event snapshot ('held_*' columns)."""
import sys, os, csv, time, json, datetime as dt
import numpy as np
import pandas as pd
import yfinance as yf
from config import CFG
from core import (now_chi, get_earnings, reaction_day_future, pick_expiries, atm_straddle, earnings_only_move,
                  retry, reaction_idx, get_history, resolve_event, liquidity, _px)

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output")
CSV = os.path.join(OUT, "snapshots.csv")
FIELDS = ["snapshot_ts", "snapshot_date", "session", "ticker", "event_date", "timing", "date_status", "reaction_day",
          "phase", "cal_days_to_earnings", "tdays_to_reaction", "expiry", "spot", "strike", "call", "put", "straddle",
          "implied_move_pct", "iv_straddle", "iv_yf", "price_src", "spread_pct", "atm_oi", "atm_volume", "liq_grade",
          "pre_expiry", "pre_straddle", "pre_iv_straddle", "earnings_only_move_pct",
          "held_strike", "held_call", "held_put", "held_straddle"]


def migrate():
    """Rewrite the CSV with the current header if older columns are found (keeps all rows)."""
    if not os.path.exists(CSV):
        return
    with open(CSV) as f:
        hdr = next(csv.reader(f), [])
    if hdr == FIELDS:
        return
    df = pd.read_csv(CSV, dtype=str)
    if "session" not in df.columns:
        df["session"] = [("am" if dt.datetime.fromisoformat(t).hour < CFG["morning_session_cutoff_hour_ct"] else "pm")
                         for t in df["snapshot_ts"]]
    df.reindex(columns=FIELDS).to_csv(CSV, index=False)
    print(f"migrated {CSV} to new schema ({len(df)} rows)")


def last_pre_strike(sym, event_date):
    if not os.path.exists(CSV):
        return None
    df = pd.read_csv(CSV, dtype=str)
    d = df[(df["ticker"] == sym) & (df["event_date"] == event_date) & (df["phase"] == "pre")]
    return float(d.sort_values("snapshot_ts")["strike"].iloc[-1]) if len(d) else None


def held_quote(tk, expiry, K):
    ch = retry(lambda: tk.option_chain(expiry))
    c, p = ch.calls.set_index("strike"), ch.puts.set_index("strike")
    if K not in c.index or K not in p.index:
        return None
    cp, _, _ = _px(c.loc[K]); pp, _, _ = _px(p.loc[K])
    return None if cp is None or pp is None else (cp, pp)


def snap(sym, session):
    sym = sym.upper().replace(".", "-")
    tk = yf.Ticker(sym)
    now = now_chi(); today = now.date()
    nxt, past = get_earnings(tk)
    ev, status = None, ""
    if len(past):
        last = past.iloc[-1]
        if (today - last["date"]).days <= 10:
            ev = {"date": last["date"], "timing": last["timing"]}
            status = "Reported"
            if ev["timing"] == "UNK":   # infer from the actual gap now that it's happened
                try:
                    r = reaction_idx(get_history(tk), last["date"], "UNK")
                    if r: ev["timing"] = r[2]
                except Exception:
                    pass
    if ev is None:
        r = resolve_event(tk, nxt, sym)
        if not r.get("date"):
            raise RuntimeError("no earnings date")
        ev = {"date": r["date"], "timing": r["timing"] or "UNK"}
        status = r["status"]
    rd = reaction_day_future(ev["date"], ev["timing"])
    spot = float(tk.fast_info["lastPrice"])
    exps = retry(lambda: tk.options)
    if not exps:
        raise RuntimeError("no options")
    post_e, pre_e = pick_expiries(exps, rd)
    if post_e is None:
        raise RuntimeError("no post-earnings expiry")
    post = atm_straddle(tk, post_e, spot)
    liq = liquidity(post)
    pre = None
    if pre_e and rd > today:
        try:
            pre = atm_straddle(tk, pre_e, spot)
        except Exception:
            pre = None
    tdays = int(np.busday_count(today, rd)) if rd >= today else -int(np.busday_count(rd, today))
    phase = "pre" if (today < rd) else ("reaction" if today == rd else "post")
    held = {}
    if phase != "pre":
        K = last_pre_strike(sym, ev["date"].isoformat())
        if K is not None:
            q = held_quote(tk, post_e, K)
            if q:
                held = {"held_strike": K, "held_call": round(q[0], 4), "held_put": round(q[1], 4),
                        "held_straddle": round(q[0] + q[1], 4)}
    return {"snapshot_ts": now.isoformat(timespec="seconds"), "snapshot_date": today.isoformat(), "session": session,
            "ticker": sym, "event_date": ev["date"].isoformat(), "timing": ev["timing"], "date_status": status,
            "reaction_day": rd.isoformat(), "phase": phase,
            "cal_days_to_earnings": (ev["date"] - today).days, "tdays_to_reaction": tdays, "expiry": post_e,
            "spot": round(spot, 4), "strike": post["strike"], "call": post["call"], "put": post["put"],
            "straddle": post["straddle"], "implied_move_pct": post["implied_move_pct"],
            "iv_straddle": post["iv_straddle"], "iv_yf": post["iv_yf"], "price_src": post["price_src"],
            "spread_pct": post.get("spread_pct_of_straddle"), "atm_oi": liq["atm_oi"], "atm_volume": liq["atm_volume"],
            "liq_grade": liq["grade"],
            "pre_expiry": pre["expiry"] if pre else "", "pre_straddle": pre["straddle"] if pre else "",
            "pre_iv_straddle": pre["iv_straddle"] if pre else "",
            "earnings_only_move_pct": earnings_only_move(post, pre) if pre else "", **held}


def reporters_today():
    """Names whose earnings reaction is today, from the last batch results (fallback: None = all)."""
    p = os.path.join(OUT, "results.json")
    if not os.path.exists(p):
        return None
    today = now_chi().date()
    out = []
    for r in json.load(open(p))["results"]:
        nd, rd = r.get("next_earnings"), r.get("reaction_day")
        if rd == today.isoformat():
            out.append(r["ticker"])
        elif nd and dt.date.fromisoformat(nd) < today <= dt.date.fromisoformat(rd or nd):
            out.append(r["ticker"])
    return out


def run(symbols, session=None, delay=0.4):
    session = session or ("am" if now_chi().hour < CFG["morning_session_cutoff_hour_ct"] else "pm")
    os.makedirs(OUT, exist_ok=True)
    migrate()
    new = not os.path.exists(CSV)
    ok, fail = 0, []
    with open(CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for s in symbols:
            try:
                w.writerow(snap(s, session)); f.flush(); ok += 1
            except Exception as e:
                fail.append((s, str(e)[:120]))
            time.sleep(delay)
    print(f"snapshot[{session}]: {ok} ok, {len(fail)} failed -> {CSV}")
    for s, e in fail:
        print(f"  FAIL {s}: {e}")
    return ok, fail


if __name__ == "__main__":
    args = sys.argv[1:]
    session = None
    if "--session" in args:
        i = args.index("--session"); session = args[i + 1]; del args[i:i + 2]
    only = "--reporters-only" in args
    args = [a for a in args if not a.startswith("--")]
    if args:
        syms = args
    else:
        syms = None
        if only:
            syms = reporters_today()
            if syms is not None:
                print(f"reporters today: {syms}")
        if syms is None:
            from n100 import get_n100
            syms = [x["ticker"] for x in get_n100()]
    run(syms, session)
