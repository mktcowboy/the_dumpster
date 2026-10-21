#!/usr/bin/env python
"""python analyze.py TICKER [TICKER...]  -> console report + output/<T>_history.csv, <T>_summary.json, <T>_moves.png"""
import sys, json, os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from tabulate import tabulate
from core import analyze

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def chart(res, path):
    h = pd.DataFrame(res.get("history") or [])
    if h.empty:
        return None
    fig, ax = plt.subplots(figsize=(10, 4.5))
    colors = ["#c0392b" if (res.get("implied_move_pct") and v > res["implied_move_pct"]) else "#2e86c1"
              for v in h["abs_close_pct"]]
    ax.bar(h["earnings_date"], h["abs_close_pct"], color=colors, label="Realized |close-to-close| move")
    ax.scatter(h["earnings_date"], h["abs_open_pct"], color="black", marker="_", s=200, label="|gap at open|", zorder=3)
    if res.get("implied_move_pct"):
        ax.axhline(res["implied_move_pct"], color="#e67e22", ls="--", lw=2,
                   label=f"Implied now {res['implied_move_pct']:.2f}% ({res['post']['expiry']})")
    if res.get("earnings_only_move_pct"):
        ax.axhline(res["earnings_only_move_pct"], color="#8e44ad", ls=":", lw=2,
                   label=f"Earnings-only implied {res['earnings_only_move_pct']:.2f}%")
    ax.set_title(f"{res['ticker']} earnings moves vs implied (seller wins on blue bars) | next: "
                 f"{res.get('next_earnings','?')} {res.get('timing','')}")
    ax.set_ylabel("% move"); ax.tick_params(axis="x", rotation=45); ax.legend(fontsize=8); fig.tight_layout()
    fig.savefig(path, dpi=110); plt.close(fig)
    return path


def report(res):
    t = res["ticker"]
    print("=" * 90)
    print(f"{t}  spot {res.get('spot')}   as of {res['as_of']} (America/Chicago)")
    print(f"Next earnings: {res.get('next_earnings')} {res.get('timing')}  (reaction day {res.get('reaction_day')}, "
          f"{res.get('days_to_earnings')} days away)")
    rows = []
    for k in ("post", "pre"):
        o = res.get(k)
        if o:
            rows.append([("POST-earnings" if k == "post" else "pre-earnings"), o["expiry"], o["strike"], o["call"], o["put"],
                         o["straddle"], f"{o['implied_move_pct']:.2f}%", o["iv_straddle"], o["price_src"],
                         o.get("spread_pct_of_straddle")])
    if rows:
        print(tabulate(rows, headers=["expiry", "date", "K", "call", "put", "straddle", "impl move", "IV", "px", "sprd%"]))
    if res.get("earnings_only_move_pct"):
        print(f"Earnings-only implied move (term-structure variance diff): {res['earnings_only_move_pct']:.2f}%")
    h = pd.DataFrame(res.get("history") or [])
    if not h.empty:
        im = res.get("implied_move_pct")
        tbl = h[["earnings_date", "timing", "reaction_date", "move_open_pct", "move_close_pct"]].copy()
        if im:
            tbl["seller P&L %spot"] = (im - h["abs_close_pct"]).round(2)
            tbl["win"] = (h["abs_close_pct"] < im).map({True: "W", False: "L"})
        tbl["timing"] = [f"{a}{'*' if b else ''}" for a, b in zip(h["timing"], h["timing_inferred"])]
        print(tabulate(tbl, headers="keys", showindex=False, floatfmt=".2f"))
    s = res.get("stats", {})
    if s:
        print(f"Avg |move| {s['avg_abs_move_pct']:.2f}%  median {s['median_abs_move_pct']:.2f}%  max {s['max_abs_move_pct']:.2f}%"
              f"  (n={s['n_quarters']})")
        if "seller_hit_rate" in s:
            print(f"Implied/avg {s['implied_over_avg']}x | realized > implied {s['pct_exceeded_implied']}% of quarters | "
                  f"seller hit rate {s['seller_hit_rate']}% | avg P&L {s['avg_pnl_pct_spot']:+.2f}% of spot "
                  f"({s['avg_pnl_pct_premium']:+.1f}% of premium), worst {s['worst_pnl_pct_spot']:+.2f}%")
    for n in res.get("notes", []):
        print("note:", n)
    print("(* = timing inferred. P&L ignores residual time value/bid-ask; uses TODAY's implied move for every past quarter.)")


def run(sym):
    res = analyze(sym)
    t = res["ticker"]
    os.makedirs(OUT, exist_ok=True)
    pd.DataFrame(res.get("history") or []).to_csv(f"{OUT}/{t}_history.csv", index=False)
    json.dump(res, open(f"{OUT}/{t}_summary.json", "w"), indent=1, default=str)
    res["chart_png"] = chart(res, f"{OUT}/{t}_moves.png")
    report(res)
    return res


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for s in sys.argv[1:]:
        try:
            run(s)
        except Exception as e:
            print(f"{s}: FAILED: {e}")
