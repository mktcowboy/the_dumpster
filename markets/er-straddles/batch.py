#!/usr/bin/env python
"""Run the analyzer over all Nasdaq-100 names -> output/results.json (+ per-ticker CSV/PNG/JSON).
Usage: python batch.py [--no-snapshot] [--limit N] [TICKER ...]"""
import sys, os, json, time, traceback
from core import analyze, now_chi
from n100 import get_n100
import analyze as A

OUT = A.OUT


def main(argv):
    snap = "--no-snapshot" not in argv
    lim = None
    if "--limit" in argv:
        lim = int(argv[argv.index("--limit") + 1])
    syms = [a for a in argv if not a.startswith("--") and not a.isdigit()]
    names = {x["ticker"]: x["name"] for x in get_n100()}
    if not syms:
        syms = list(names)
    syms = syms[:lim] if lim else syms
    results, failures = [], []
    t0 = time.time()
    from earnings_cal import get_index
    meta = get_index(now_chi().date())[1]   # prefetch Nasdaq earnings calendar once
    print("nasdaq calendar:", meta, flush=True)
    for i, s in enumerate(syms, 1):
        res = None
        for attempt in range(2):
            try:
                res = analyze(s); break
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                time.sleep(3)
        if res is None:
            failures.append({"ticker": s, "error": err[:300]}); print(f"[{i}/{len(syms)}] {s} FAIL {err[:100]}")
            continue
        res["name"] = names.get(s, s)
        t = res["ticker"]
        try:
            import pandas as pd
            pd.DataFrame(res.get("history") or []).to_csv(f"{OUT}/{t}_history.csv", index=False)
            res["chart_png"] = A.chart(res, f"{OUT}/{t}_moves.png")
        except Exception as e:
            res["notes"].append(f"chart/csv failed: {e}")
        json.dump(res, open(f"{OUT}/{t}_summary.json", "w"), indent=1, default=str)
        results.append(res)
        st = res.get("stats", {})
        print(f"[{i}/{len(syms)}] {t} next={res.get('next_earnings')} {res.get('timing')} impl={res.get('implied_move_pct')} "
              f"eo={res.get('earnings_only_move_pct')} {res.get('date_status')} liq={(res.get('liquidity') or {}).get('grade')} net={(res.get('pnl_stats') or {}).get('net_avg_pct')} avg={st.get('avg_abs_move_pct')} hit={st.get('seller_hit_rate')}", flush=True)
        time.sleep(0.5)
    from collections import Counter
    from earnings_cal import get_index
    date_counts = dict(Counter(r.get("date_status", "Unconfirmed") for r in results))
    liq_counts = dict(Counter((r.get("liquidity") or {}).get("grade", "n/a") for r in results))
    print("date status:", date_counts, "| liquidity:", liq_counts)
    out = {"date_status_counts": date_counts, "liquidity_counts": liq_counts,
           "nasdaq_calendar": get_index(now_chi().date())[1], "generated": now_chi().isoformat(timespec="seconds"), "n_ok": len(results), "n_fail": len(failures),
           "failures": failures, "results": results}
    json.dump(out, open(f"{OUT}/results.json", "w"), indent=1, default=str)
    print(f"batch done in {time.time()-t0:.0f}s: {len(results)} ok, {len(failures)} failed -> {OUT}/results.json")
    if snap:
        import snapshot
        snapshot.run(syms)
    import crush
    ev = crush.compute()
    ev.to_csv(crush.OUTCSV, index=False)
    print(f"crush events: {len(ev)} -> {crush.OUTCSV}")


if __name__ == "__main__":
    main(sys.argv[1:])
