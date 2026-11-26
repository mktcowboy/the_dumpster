"""Fetch futures term-structure data from Yahoo Finance (per-contract tickers) -> data.json.

For each market: probe every contract in its real listed-month cycle over a horizon,
keep contracts that return live data, and record last/chg/volume, prices ~1W and ~1M ago,
plus ~1Y of the front-month continuous series (ROOT=F).  No price is ever synthesised.
"""
import argparse, json, datetime as dt, sys, os, time
import pandas as pd, yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "data.json")
MIN_MARKETS = 30
MC = "FGHJKMNQUVXZ"
MN = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
ALL = MC
# (root, name, exchange suffix, listed month cycle, horizon in months, unit)
G = {
"Indices":[("ES","E-mini S&P 500","CME","HMUZ",15,"index pts"),("NQ","E-mini Nasdaq 100","CME","HMUZ",15,"index pts"),
           ("YM","E-mini Dow","CBT","HMUZ",15,"index pts"),("RTY","E-mini Russell 2000","CME","HMUZ",15,"index pts")],
"Energy":[("CL","Crude Oil WTI","NYM",ALL,36,"$/bbl"),("BZ","Brent Crude","NYM",ALL,36,"$/bbl"),("NG","Natural Gas","NYM",ALL,36,"$/MMBtu"),
          ("RB","RBOB Gasoline","NYM",ALL,24,"$/gal"),("HO","Heating Oil","NYM",ALL,24,"$/gal")],
"Metals":[("GC","Gold","CMX","GJMQVZ",30,"$/oz"),("SI","Silver","CMX","FHKNUZ",30,"$/oz"),("HG","Copper","CMX",ALL,24,"$/lb"),
          ("PL","Platinum","NYM","FJNV",18,"$/oz"),("PA","Palladium","NYM","HMUZ",18,"$/oz")],
"Grains":[("ZC","Corn","CBT","HKNUZ",30,"¢/bu"),("ZW","Chicago Wheat","CBT","HKNUZ",30,"¢/bu"),("KE","KC Wheat","CBT","HKNUZ",24,"¢/bu"),
          ("ZS","Soybeans","CBT","FHKNQUX",30,"¢/bu"),("ZM","Soybean Meal","CBT","FHKNQUVZ",24,"$/short ton"),
          ("ZL","Soybean Oil","CBT","FHKNQUVZ",24,"¢/lb"),("ZO","Oats","CBT","HKNUZ",18,"¢/bu"),("ZR","Rough Rice","CBT","FHKNUX",18,"$/cwt")],
"Meats":[("LE","Live Cattle","CME","GJMQVZ",18,"¢/lb"),("GF","Feeder Cattle","CME","FHJKQUVX",15,"¢/lb"),("HE","Lean Hogs","CME","GJKMNQVZ",18,"¢/lb")],
"Softs":[("KC","Coffee","NYB","HKNUZ",24,"¢/lb"),("SB","Sugar #11","NYB","HKNV",30,"¢/lb"),("CC","Cocoa","NYB","HKNUZ",24,"$/t"),
         ("CT","Cotton","NYB","HKNVZ",24,"¢/lb"),("OJ","Orange Juice","NYB","FHKNUX",18,"¢/lb")],
"Currencies":[("DX","US Dollar Index","NYB","HMUZ",15,"index"),("6E","Euro","CME","HMUZ",15,"$/EUR"),("6B","British Pound","CME","HMUZ",15,"$/GBP"),
              ("6J","Japanese Yen","CME","HMUZ",15,"$/JPY"),("6A","Australian Dollar","CME","HMUZ",15,"$/AUD"),
              ("6C","Canadian Dollar","CME","HMUZ",15,"$/CAD"),("6S","Swiss Franc","CME","HMUZ",15,"$/CHF")],
"Rates":[("ZB","30Y T-Bond","CBT","HMUZ",12,"pts"),("ZN","10Y T-Note","CBT","HMUZ",12,"pts"),
         ("ZF","5Y T-Note","CBT","HMUZ",12,"pts"),("ZT","2Y T-Note","CBT","HMUZ",12,"pts")],
}

SPOT_FALLBACK = {"DX": "DX-Y.NYB"}   # ICE US Dollar Index (spot)
HSRC = {}

def candidates(root, sfx, cycle, horizon, today):
    out = []
    y, m = today.year, today.month
    for k in range(horizon + 1):
        mm = (m - 1 + k) % 12 + 1; yy = y + (m - 1 + k) // 12
        code = MC[mm - 1]
        if code in cycle:
            out.append(dict(t=f"{root}{code}{yy%100:02d}.{sfx}", code=code, y=yy, m=mm, lab=f"{MN[mm-1]} {yy%100:02d}"))
    return out

def _clean_frame(f):
    if f is None or f.empty or "Close" not in f.columns:
        return None
    cols = ["Close", "Volume"] if "Volume" in f.columns else ["Close"]
    out = f[cols].dropna(subset=["Close"]).copy()
    if "Volume" not in out.columns:
        out["Volume"] = 0
    if not len(out):
        return None
    idx = pd.to_datetime(out.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    out.index = idx
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out

def dl(tickers, period, attempts=3):
    frames = {}
    for i in range(0, len(tickers), 80):
        chunk = tickers[i:i+80]
        d = None
        for attempt in range(1, attempts + 1):
            try:
                d = yf.download(chunk, period=period, interval="1d", auto_adjust=False, progress=False, group_by="ticker", threads=True)
                if d is not None and not d.empty:
                    break
            except Exception as exc:
                print(f"chunk {i//80 + 1} attempt {attempt} failed: {exc}", file=sys.stderr)
            if attempt < attempts:
                time.sleep(2 ** attempt)
        if d is None or d.empty:
            continue
        is_multi = isinstance(d.columns, pd.MultiIndex)
        lvl0 = set(d.columns.get_level_values(0)) if is_multi else set()
        for t in chunk:
            try:
                if is_multi:
                    if t not in lvl0:
                        continue
                    raw = d[t]
                else:
                    if len(chunk) != 1:
                        continue
                    raw = d
                f = _clean_frame(raw)
                if f is not None:
                    frames[t] = f
            except Exception:
                pass
    return frames

def main():
    parser = argparse.ArgumentParser(description="Fetch futures term-structure data into data.json.")
    parser.add_argument("--force", action="store_true", help="Write data.json even if market data is unchanged.")
    parser.add_argument("--allow-older", action="store_true", help="Allow writing data even if asof_bar regressed.")
    args = parser.parse_args()

    today = dt.date.today()
    cands = {}
    for g, l in G.items():
        for root, n, sfx, cyc, hz, u in l:
            cands[root] = candidates(root, sfx, cyc, hz, today)
    tick = [c["t"] for v in cands.values() for c in v]
    print("probing", len(tick), "contract tickers", file=sys.stderr)
    px = dl(tick, "3mo")
    if not px:
        raise RuntimeError("No contract quotes returned from Yahoo Finance.")
    cont = dl([r[0] + "=F" for l in G.values() for r in l], "14mo")
    # continuous series Yahoo lacks: fall back to the cash/spot index (labelled as such in the report)
    for root, alt in SPOT_FALLBACK.items():
        if root + "=F" not in cont:
            f = dl([alt], "14mo").get(alt)
            if f is not None: cont[root + "=F"] = f; HSRC[root] = alt
    last_day = max(f.index[-1] for f in px.values())
    print("latest bar", last_day, file=sys.stderr)
    res = {"groups": {}, "asof_bar": last_day.strftime("%Y-%m-%d"),
           "generated": dt.datetime.now().astimezone().isoformat(timespec="minutes"), "probed": len(tick)}
    ok_markets = 0
    for g, l in G.items():
        res["groups"][g] = []
        for root, n, sfx, cyc, hz, u in l:
            rows = []
            for c in cands[root]:
                f = px.get(c["t"])
                if f is None or len(f) < 2: continue
                # live only: last bar within 7 days of the most recent bar across all contracts
                if (last_day - f.index[-1]).days > 7: continue
                cl = f["Close"]
                def at(days):
                    s = cl[cl.index <= last_day - pd.Timedelta(days=days)]
                    return round(float(s.iloc[-1]), 6) if len(s) and (last_day - pd.Timedelta(days=days) - s.index[-1]).days <= 5 else None
                vol_raw = f["Volume"].iloc[-1]
                vol = int(vol_raw) if pd.notna(vol_raw) else 0
                rows.append(dict(t=c["t"], code=c["code"], y=c["y"], m=c["m"], lab=c["lab"],
                    last=round(float(cl.iloc[-1]), 6), prev=round(float(cl.iloc[-2]), 6),
                    d=cl.index[-1].strftime("%Y-%m-%d"), vol=vol,
                    w1=at(7), m1=at(30)))
            if rows:
                ok_markets += 1
            fr = cont.get(root + "=F")
            h = hd = None
            if fr is not None and len(fr) > 30:
                s = fr["Close"].iloc[-260:]
                h = [round(float(x), 6) for x in s]; hd = [x.strftime("%Y-%m-%d") for x in s.index]
            res["groups"][g].append(dict(s=root, n=n, ex=sfx, cyc=cyc, u=u, c=rows, h=h, hd=hd,
                                         hsrc=HSRC.get(root, root + "=F"),
                                         cand=len(cands[root])))
            print(f"{g:11s} {root:4s} {len(rows):2d}/{len(cands[root]):2d} contracts  cont={'y' if h else 'n'}", file=sys.stderr)

    if ok_markets < MIN_MARKETS:
        raise RuntimeError(f"Too few markets returned live curves ({ok_markets} < {MIN_MARKETS}); aborting.")

    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, encoding="utf-8") as fh:
            prev = json.load(fh)
        prev_bar = prev.get("asof_bar")
        if not args.allow_older and prev_bar and res["asof_bar"] < prev_bar:
            raise RuntimeError(f"Futures data regressed: {res['asof_bar']} < {prev_bar}")
        if not args.force and prev.get("asof_bar") == res["asof_bar"] and prev.get("groups") == res["groups"]:
            print("No new futures data; data.json unchanged.", file=sys.stderr)
            return

    tmp_path = DATA_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, separators=(",", ":"))
    os.replace(tmp_path, DATA_PATH)

if __name__ == "__main__":
    main()
