#!/usr/bin/env python
"""IV-crush events from our own snapshots (output/snapshots.csv) -> output/crush_events.csv.
For each (ticker, event): last 'pre' snapshot (before the announcement) vs first snapshot on/after the reaction day
(prefer the 'am' session of the reaction day). Same expiry required.
  straddle_crush_pct = ATM straddle (re-centered) after / before - 1
  iv_crush_pct       = ATM IV after / before - 1 ; iv_drop_pts = (before - after) * 100
  held_pnl_pct_prem  = seller P&L on the strike held before the event, % of premium collected (needs held_* columns)"""
import os
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(ROOT, "output", "snapshots.csv")
OUTCSV = os.path.join(ROOT, "output", "crush_events.csv")


def compute(snaps: pd.DataFrame | None = None) -> pd.DataFrame:
    if snaps is None:
        if not os.path.exists(CSV):
            return pd.DataFrame()
        snaps = pd.read_csv(CSV)
    if snaps is None or snaps.empty or "phase" not in snaps:
        return pd.DataFrame()
    s = snaps.copy()
    if "session" not in s:
        s["session"] = "pm"
    s = s.sort_values("snapshot_ts")
    rows = []
    for (t, ev), g in s.groupby(["ticker", "event_date"]):
        pre = g[g["phase"] == "pre"]
        post = g[g["phase"].isin(["reaction", "post"])]
        if pre.empty or post.empty:
            continue
        b = pre.iloc[-1]
        post = post[post["expiry"] == b["expiry"]]
        if post.empty:
            continue
        a = post.iloc[0]
        r = {"ticker": t, "event_date": ev, "timing": b.get("timing"), "expiry": b["expiry"],
             "before_ts": b["snapshot_ts"], "after_ts": a["snapshot_ts"], "after_session": a.get("session"),
             "spot_before": b["spot"], "spot_after": a["spot"],
             "move_pct": round(100 * (a["spot"] / b["spot"] - 1), 3),
             "straddle_before": b["straddle"], "straddle_after": a["straddle"],
             "straddle_crush_pct": round(100 * (a["straddle"] / b["straddle"] - 1), 2),
             "iv_before": b["iv_straddle"], "iv_after": a["iv_straddle"],
             "iv_crush_pct": round(100 * (a["iv_straddle"] / b["iv_straddle"] - 1), 2) if pd.notna(a["iv_straddle"]) and b["iv_straddle"] else None,
             "iv_drop_pts": round(100 * (b["iv_straddle"] - a["iv_straddle"]), 2) if pd.notna(a["iv_straddle"]) else None,
             "implied_move_before": b["implied_move_pct"]}
        hs = a.get("held_straddle")
        if pd.notna(hs) if hs is not None else False:
            r.update({"held_strike": a["held_strike"], "held_straddle_after": hs,
                      "held_pnl_pct_prem": round(100 * (b["straddle"] - hs) / b["straddle"], 1)})
        rows.append(r)
    return pd.DataFrame(rows)


def summary(ev: pd.DataFrame) -> dict:
    """ticker -> dict(n, avg straddle crush, avg iv crush)."""
    out = {}
    if ev is None or ev.empty:
        return out
    for t, g in ev.groupby("ticker"):
        out[t] = {"n_events": int(len(g)), "avg_straddle_crush_pct": round(g["straddle_crush_pct"].mean(), 2),
                  "avg_iv_crush_pct": round(g["iv_crush_pct"].dropna().mean(), 2) if g["iv_crush_pct"].notna().any() else None}
    return out


if __name__ == "__main__":
    ev = compute()
    ev.to_csv(OUTCSV, index=False)
    print(f"{len(ev)} crush events -> {OUTCSV}")
    if len(ev):
        print(ev.to_string(index=False))
