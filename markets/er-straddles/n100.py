"""Nasdaq-100 constituents, cached to output/n100.json (source: Nasdaq.com API; fallback Wikipedia, then cache)."""
import json, os, io, re, datetime as dt
import requests
from core import now_chi

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "n100.json")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
      "Accept": "application/json,text/html"}


def _nasdaq():
    r = requests.get("https://api.nasdaq.com/api/quote/list-type/nasdaq100", headers=UA, timeout=20)
    r.raise_for_status()
    rows = r.json()["data"]["data"]["rows"]
    out = [{"ticker": x["symbol"].strip().upper().replace(".", "-"),
            "name": re.sub(r"\s+(Common Stock|Class [A-C].*|Ordinary Shares.*|American Depositary.*)$", "",
                           x["companyName"]).strip()} for x in rows]
    return out, "api.nasdaq.com nasdaq100 list"


def _wikipedia():
    import pandas as pd
    r = requests.get("https://en.wikipedia.org/wiki/Nasdaq-100", headers=UA, timeout=20)
    for t in pd.read_html(io.StringIO(r.text)):
        cols = [str(c) for c in t.columns]
        tc = next((c for c in cols if "Ticker" in c or "Symbol" in c), None)
        if tc and len(t) > 90:
            nc = next((c for c in cols if "Company" in c or "Security" in c), tc)
            return [{"ticker": str(a).upper().replace(".", "-"), "name": str(b)} for a, b in zip(t[tc], t[nc])], "Wikipedia"
    raise RuntimeError("no constituents table on Wikipedia")


def get_n100(refresh=False, max_age_days=7):
    if not refresh and os.path.exists(CACHE):
        c = json.load(open(CACHE))
        age = (now_chi() - dt.datetime.fromisoformat(c["fetched"])).days
        if age <= max_age_days:
            return c["tickers"]
    for f in (_nasdaq, _wikipedia):
        try:
            tick, src = f()
            if len(tick) >= 90:
                os.makedirs(os.path.dirname(CACHE), exist_ok=True)
                json.dump({"fetched": now_chi().isoformat(timespec="seconds"), "source": src, "tickers": tick},
                          open(CACHE, "w"), indent=1)
                return tick
        except Exception as e:
            print(f"constituents via {f.__name__} failed: {e}")
    if os.path.exists(CACHE):
        return json.load(open(CACHE))["tickers"]
    raise RuntimeError("could not get Nasdaq-100 list")


if __name__ == "__main__":
    t = get_n100(refresh=True)
    print(len(t), [x["ticker"] for x in t])
