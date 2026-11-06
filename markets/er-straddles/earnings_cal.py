"""Second earnings-date source: Nasdaq earnings calendar (api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD).
Per-date responses cached in output/cache/nasdaq_cal/ (refetched if older than 12h)."""
import os, json, time, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import requests
from config import CFG

ROOT = os.path.dirname(os.path.abspath(__file__))
CDIR = os.path.join(ROOT, "output", "cache", "nasdaq_cal")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
      "Accept": "application/json"}
TMAP = {"time-pre-market": "BMO", "time-after-hours": "AMC"}


def _fetch(d: dt.date, max_age_h=12):
    os.makedirs(CDIR, exist_ok=True)
    p = os.path.join(CDIR, f"{d.isoformat()}.json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < max_age_h * 3600:
        return json.load(open(p))
    rows = None
    for i in range(3):
        try:
            r = requests.get(f"https://api.nasdaq.com/api/calendar/earnings?date={d.isoformat()}", headers=UA, timeout=25)
            r.raise_for_status()
            rows = [{"symbol": x["symbol"].strip().upper().replace(".", "-"), "time": TMAP.get(x.get("time"), "UNK"),
                     "fiscal": x.get("fiscalQuarterEnding")} for x in ((r.json().get("data") or {}).get("rows") or [])]
            break
        except Exception:
            time.sleep(2 * (i + 1))
    if rows is None:
        return json.load(open(p)) if os.path.exists(p) else None   # stale cache better than nothing
    json.dump(rows, open(p, "w"))
    return rows


def weekdays(a: dt.date, b: dt.date):
    d = a
    while d <= b:
        if d.weekday() < 5:
            yield d
        d += dt.timedelta(days=1)


def build_index(start: dt.date, end: dt.date, workers=4):
    """symbol -> sorted list of (date, timing) found in Nasdaq calendar between start and end."""
    days = list(weekdays(start, end))
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(_fetch, days))
    idx, missing = {}, 0
    for d, rows in zip(days, res):
        if rows is None:
            missing += 1
            continue
        for x in rows:
            idx.setdefault(x["symbol"], []).append((d, x["time"]))
    return idx, {"days_queried": len(days), "days_failed": missing, "start": start.isoformat(), "end": end.isoformat()}


_INDEX = None


def get_index(today: dt.date):
    global _INDEX
    if _INDEX is None:
        _INDEX = build_index(today, today + dt.timedelta(days=CFG["nasdaq_calendar_horizon_days"]))
    return _INDEX


def lookup(symbol: str, today: dt.date):
    idx, meta = get_index(today)
    hits = [h for h in idx.get(symbol.upper(), []) if h[0] >= today]
    return (hits[0] if hits else None), meta


def reconcile(yahoo_date, yahoo_timing, yahoo_is_estimate, nasdaq_hit):
    """Return dict(status, date, timing, sources...). Status: Confirmed | Mismatch | Unconfirmed."""
    nd, nt = (nasdaq_hit or (None, None))
    out = {"yahoo_date": yahoo_date.isoformat() if yahoo_date else None, "yahoo_timing": yahoo_timing,
           "yahoo_is_estimate": yahoo_is_estimate, "nasdaq_date": nd.isoformat() if nd else None, "nasdaq_timing": nt}
    if yahoo_date and nd:
        if yahoo_date == nd:
            if yahoo_timing in ("BMO", "AMC") and nt in ("BMO", "AMC") and yahoo_timing != nt:
                out.update(status="Mismatch", detail=f"timing: Yahoo {yahoo_timing} vs Nasdaq {nt}", date=nd,
                           timing="AMC", timing_src="conservative (AMC) due to mismatch")
            else:
                t = yahoo_timing if yahoo_timing in ("BMO", "AMC") else nt
                src = "Yahoo+Nasdaq" if (yahoo_timing == nt and nt in ("BMO", "AMC")) else (
                    "Yahoo" if yahoo_timing in ("BMO", "AMC") else ("Nasdaq" if nt in ("BMO", "AMC") else "none"))
                out.update(status="Confirmed", detail="date agrees" + (" and timing agrees" if src == "Yahoo+Nasdaq" else ""),
                           date=nd, timing=t if t in ("BMO", "AMC") else "UNK", timing_src=src)
        else:
            # Prefer Yahoo when Yahoo flags its date as non-estimated; otherwise the earlier one? -> take Nasdaq.
            pick_y = yahoo_is_estimate is False
            d, t = (yahoo_date, yahoo_timing) if pick_y else (nd, nt)
            out.update(status="Mismatch", detail=f"date: Yahoo {yahoo_date} {yahoo_timing} vs Nasdaq {nd} {nt}",
                       date=d, timing=t, timing_src=("Yahoo (non-estimate flag)" if pick_y else "Nasdaq"),
                       alt_date=(nd if pick_y else yahoo_date), alt_timing=(nt if pick_y else yahoo_timing))
    elif yahoo_date:
        out.update(status="Unconfirmed", detail="Yahoo only" + (" (Yahoo marks it an estimate)" if yahoo_is_estimate else "")
                   + "; not found in Nasdaq calendar window", date=yahoo_date, timing=yahoo_timing, timing_src="Yahoo")
    elif nd:
        out.update(status="Unconfirmed", detail="Nasdaq only", date=nd, timing=nt, timing_src="Nasdaq")
    else:
        out.update(status="Unconfirmed", detail="no source", date=None, timing="UNK", timing_src="none")
    return out
