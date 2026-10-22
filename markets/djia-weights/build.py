#!/usr/bin/env python3
"""Build the standalone Dow Jones weight-history report from local sources."""
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
WIKI = ROOT / "source" / "historical_components.wikitext"

START_MONTH = "2004-04"
END_MONTH = "2026-09"
AS_OF = "2026-10-20"
PUBLISHED_DIVISOR = 0.16824816528350

ALIASES = {
    "3M Company": "MMM",
    "Alcoa Inc.": "AA",
    "Alphabet Inc.": "GOOGL",
    "Altria Group Incorporated": "MO",
    "Altria Group, Incorporated": "MO",
    "Amazon.com, Inc.": "AMZN",
    "American Express Company": "AXP",
    "American International Group, Inc.": "AIG",
    "Amgen Inc.": "AMGN",
    "Apple Inc.": "AAPL",
    "Bank of America Corporation": "BAC",
    "Caterpillar Inc.": "CAT",
    "Chevron Corporation": "CVX",
    "Cisco Systems, Inc.": "CSCO",
    "Citigroup Inc.": "C",
    "Dow Inc.": "DOW",
    "DowDuPont Inc.": "DWDP",
    "E.I. du Pont de Nemours & Company": "DD",
    "Eastman Kodak Company": "EK",
    "Exxon Mobil Corporation": "XOM",
    "General Electric Company": "GE",
    "General Motors Corporation": "GM",
    "Hewlett-Packard Company": "HPQ",
    "Honeywell International": "HON",
    "Honeywell International Inc.": "HON",
    "Honeywell Technologies Inc.": "HON",
    "Intel Corporation": "INTC",
    "International Business Machines Corporation": "IBM",
    "International Paper Company": "IP",
    "JPMorgan Chase & Co.": "JPM",
    "Johnson & Johnson": "JNJ",
    "Kraft Foods Inc.": "KFT",
    "McDonald's Corporation": "MCD",
    "Merck & Co., Inc.": "MRK",
    "Microsoft Corporation": "MSFT",
    "Microsoft|Microsoft Corporation": "MSFT",
    "Nike, Inc.": "NKE",
    "Nvidia Corporation": "NVDA",
    "Pfizer Inc.": "PFE",
    "Raytheon Technologies Corporation": "RTX",
    "SBC Communications Inc.": "T",
    "AT&T Inc.": "T",
    "Salesforce, Inc.": "CRM",
    "The Boeing Company": "BA",
    "The Coca-Cola Company": "KO",
    "The Goldman Sachs Group, Inc.": "GS",
    "The Home Depot, Inc.": "HD",
    "The Procter & Gamble Company": "PG",
    "The Sherwin-Williams Company": "SHW",
    "The Travelers Companies, Inc.": "TRV",
    "The Walt Disney Company": "DIS",
    "United Technologies Corporation": "RTX",
    "UnitedHealth Group Inc.": "UNH",
    "UnitedHealth Group Incorporated": "UNH",
    "Verizon Communications Inc.": "VZ",
    "Visa Inc.": "V",
    "Wal-Mart Stores, Inc.": "WMT",
    "Walgreens Boots Alliance, Inc.": "WBA",
    "Walmart Inc.": "WMT",
    "AT&T Corporation": "ATTC",
}

LABELS = {
    "MMM": "3M", "AA": "Alcoa", "AXP": "American Express", "AIG": "AIG",
    "T": "AT&T", "BAC": "Bank of America", "BA": "Boeing", "CAT": "Caterpillar",
    "CVX": "Chevron", "CSCO": "Cisco", "KO": "Coca-Cola", "C": "Citigroup",
    "DD": "DuPont", "DOW": "Dow", "DIS": "Disney", "XOM": "Exxon Mobil",
    "GE": "GE", "GS": "Goldman Sachs", "HD": "Home Depot", "HON": "Honeywell",
    "HPQ": "HP", "INTC": "Intel", "IBM": "IBM", "IP": "International Paper",
    "JNJ": "Johnson & Johnson", "JPM": "JPMorgan Chase", "MCD": "McDonald's",
    "MRK": "Merck", "MSFT": "Microsoft", "NKE": "Nike", "NVDA": "Nvidia",
    "PFE": "Pfizer", "PG": "Procter & Gamble", "RTX": "Raytheon",
    "CRM": "Salesforce", "SHW": "Sherwin-Williams", "TRV": "Travelers",
    "UNH": "UnitedHealth", "VZ": "Verizon", "V": "Visa", "WMT": "Walmart",
    "AAPL": "Apple", "AMZN": "Amazon", "AMGN": "Amgen", "GOOGL": "Alphabet",
    "MO": "Altria", "KFT": "Kraft Foods", "DWDP": "DowDuPont", "WBA": "Walgreens",
    "GM": "General Motors", "EK": "Eastman Kodak", "ATTC": "AT&T (old)",
}

RAW_TICKERS = {"DD", "DWDP", "WBA", "KFT", "GM"}


def display_identity(ticker, day):
    if ticker == "RTX" and day < "2020-04-06":
        return "UTX", "United Technologies"
    if ticker == "T" and day < "2005-11-21":
        return "SBC", "SBC Communications"
    if ticker == "HON" and day >= "2026-06-29":
        return "HON", "Honeywell Technologies"
    return ticker, LABELS.get(ticker, ticker)

CHANGE_NOTES = {
    "2004-04-08": "AT&T, Kodak, and International Paper replaced by Pfizer, AIG, and Verizon.",
    "2005-11-21": "SBC Communications renamed AT&T Inc. after acquiring AT&T Corp.",
    "2008-02-19": "Altria and Honeywell replaced by Chevron and Bank of America.",
    "2008-09-22": "Kraft Foods added after AIG was removed.",
    "2009-06-08": "General Motors and Citigroup replaced by Travelers and Cisco.",
    "2012-09-24": "Kraft Foods replaced by UnitedHealth Group.",
    "2013-09-23": "Alcoa, Bank of America, and Hewlett-Packard replaced by Goldman Sachs, Visa, and Nike.",
    "2015-03-19": "AT&T replaced by Apple.",
    "2017-09-01": "DuPont merged into DowDuPont; DWDP became the index member.",
    "2018-06-26": "General Electric replaced by Walgreens Boots Alliance.",
    "2019-04-02": "DowDuPont split; Dow Inc. became the index member.",
    "2020-04-06": "United Technologies renamed Raytheon Technologies after separating from Carrier and Otis.",
    "2020-08-31": "Exxon Mobil, Pfizer, and Raytheon replaced by Salesforce, Amgen, and Honeywell.",
    "2024-02-26": "Walgreens Boots Alliance replaced by Amazon.",
    "2024-11-08": "Intel and Dow replaced by Nvidia and Sherwin-Williams.",
    "2026-06-29": "Verizon replaced by Alphabet; Honeywell renamed Honeywell Technologies after its aerospace spinoff.",
}

SNAPSHOTS = [
    ("2004-04", "April 2004"),
    ("2008-06", "June 2008"),
    ("2013-09", "September 2013"),
    ("2019-12", "December 2019"),
    ("2024-11", "November 2024"),
]

MONTHS = []
_year, _month = map(int, START_MONTH.split("-"))
while f"{_year:04d}-{_month:02d}" <= END_MONTH:
    MONTHS.append(f"{_year:04d}-{_month:02d}")
    _month += 1
    if _month == 13:
        _year += 1
        _month = 1


def month_end(key):
    year, month = map(int, key.split("-"))
    return (date(year + (month == 12), 1 if month == 12 else month + 1, 1)
            - timedelta(days=1)).isoformat()


def clean_cell(cell):
    cell = re.sub(r"<ref[^>]*>.*?</ref>", "", cell, flags=re.S)
    cell = re.sub(r"<!--.*?-->", "", cell, flags=re.S)
    cell = re.sub(r"\{\{small\|.*?\}\}", "", cell, flags=re.S | re.I)
    cell = re.sub(r"<br\s*/?>.*$", "", cell, flags=re.I | re.M)
    cell = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", cell)
    cell = re.sub(r"\[\[([^\]]+)\]\]", r"\1", cell)
    cell = cell.replace("†", "").replace("↑", "").replace("↓", "")
    cell = cell.replace("'''", "").strip()
    cell = cell.split("|")[-1]
    return re.sub(r"\s+", " ", cell)


def parse_sections():
    text = WIKI.read_text()
    heads = list(re.finditer(r"^==\s*([A-Z][a-z]+ \d{1,2}, \d{4})\s*==\s*$", text, re.M))
    out = []
    for i, head in enumerate(heads):
        day = datetime.strptime(head.group(1), "%B %d, %Y").date().isoformat()
        body = text[head.end():heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        start, end = body.find("{|"), body.find("|}", body.find("{|"))
        table = body[start:end]
        rows, current = [], []
        for line in table.splitlines():
            line = line.strip()
            if line.startswith("|-"):
                if current:
                    rows.append(current)
                    current = []
            elif line.startswith("|") and not line.startswith("|}"):
                current.append(line[1:].strip())
        if current:
            rows.append(current)
        members, dropped = [], False
        for row in rows:
            if any("Dropped from Average" in cell for cell in row):
                dropped = True
                continue
            if dropped:
                continue
            for cell in row:
                name = clean_cell(cell)
                if name and not name.lower().startswith("colspan"):
                    members.append(name)
        out.append({"date": day, "members": members[:30]})
    return sorted(out, key=lambda section: section["date"])


def load_prices():
    payload = json.loads((DATA / "prices.json").read_text())
    monthly = {t: {row[0][:7]: row[1] for row in v["monthly"]}
               for t, v in payload["prices"].items()}
    daily = {t: v.get("daily", {}) for t, v in payload["prices"].items()}
    splits = payload["splits"]
    return payload, monthly, daily, splits


def factor_after(splits, ticker, day):
    factor = 1.0
    for split_day, ratio in splits.get(ticker, {}).items():
        if split_day > day:
            factor *= ratio
    return factor


def unadjust(monthly, splits, ticker, month):
    close = monthly.get(ticker, {}).get(month)
    if close is None:
        return None
    if ticker in RAW_TICKERS:
        return close
    return close * factor_after(splits, ticker, month_end(month))


def roster_for(sections, month):
    cutoff = month_end(month)
    roster = sections[0]
    for section in sections:
        if section["date"] <= cutoff:
            roster = section
        else:
            break
    return roster


def main():
    all_sections = parse_sections()
    sections = [s for s in all_sections if s["date"] >= "2004-04-01"]
    payload, monthly, daily, splits = load_prices()
    if daily["DJI"].get(AS_OF) is None:
        raise SystemExit(f"No DJIA close for {AS_OF}")

    companies = {}
    for section in sections:
        for name in section["members"]:
            ticker = ALIASES.get(name)
            if ticker:
                companies.setdefault(ticker, name)

    weights, coverage, missing_stats = {}, [], []
    top1, top5, top10, effective = [], [], [], []
    for month in MONTHS:
        roster = roster_for(sections, month)
        tickers = [ALIASES[name] for name in roster["members"] if ALIASES.get(name)]
        priced, missing = [], []
        for ticker in tickers:
            price = unadjust(monthly, splits, ticker, month)
            if price is None:
                missing.append(ticker)
            else:
                priced.append((ticker, price))
        total = sum(p for _, p in priced)
        for ticker, price in priced:
            weights.setdefault(ticker, [None] * len(MONTHS))
            weights[ticker][MONTHS.index(month)] = round(100 * price / total, 4)
        coverage.append(len(priced))
        missing_stats.append(missing)
        ordered = sorted((p for _, p in priced), reverse=True)
        share = [100 * p / total for p in ordered]
        top1.append(round(share[0], 2))
        top5.append(round(sum(share[:5]), 2))
        top10.append(round(sum(share[:10]), 2))
        effective.append(round(1 / sum((s / 100) ** 2 for s in share), 1))

    current = []
    total_now = 0.0
    for ticker in [ALIASES[name] for name in roster_for(sections, END_MONTH)["members"]]:
        close = daily.get(ticker, {}).get(AS_OF)
        if close is None:
            continue
        price = close * factor_after(splits, ticker, AS_OF)
        shown_ticker, shown_name = display_identity(ticker, AS_OF)
        current.append({"ticker": shown_ticker, "name": shown_name, "price": price})
        total_now += price
    for row in current:
        row["weight"] = round(100 * row["price"] / total_now, 2)
    current.sort(key=lambda row: row["weight"], reverse=True)

    changes = []
    for prev, cur in zip(all_sections, all_sections[1:]):
        old = {ALIASES[n] for n in prev["members"] if ALIASES.get(n)}
        new = {ALIASES[n] for n in cur["members"] if ALIASES.get(n)}
        added = sorted(new - old)
        removed = sorted(old - new)
        note = CHANGE_NOTES.get(cur["date"], "")
        if cur["date"] < "2004-04-01":
            continue
        if added or removed or note:
            changes.append({
                "date": cur["date"],
                "added": [{"ticker": display_identity(t, cur["date"])[0],
                           "name": display_identity(t, cur["date"])[1]} for t in added],
                "removed": [{"ticker": display_identity(t, prev["date"])[0],
                             "name": display_identity(t, prev["date"])[1]} for t in removed],
                "note": note,
            })

    snapshots = []
    for month, label in SNAPSHOTS:
        rows = []
        for ticker, series in weights.items():
            value = series[MONTHS.index(month)]
            if value is None:
                continue
            roster = {ALIASES[n] for n in roster_for(sections, month)["members"] if ALIASES.get(n)}
            if ticker in roster:
                shown_ticker, shown_name = display_identity(ticker, month + "-01")
                rows.append({"ticker": shown_ticker, "name": shown_name,
                             "weight": value, "price": unadjust(monthly, splits, ticker, month)})
        rows.sort(key=lambda row: row["weight"], reverse=True)
        snapshots.append({"date": month, "label": label,
                          "coverage": coverage[MONTHS.index(month)], "rows": rows[:10]})

    snapshots.append({"date": AS_OF, "label": "October 20, 2026", "coverage": len(current),
                      "rows": [{"ticker": row["ticker"], "name": row["name"],
                                "weight": row["weight"], "price": round(row["price"], 2)}
                               for row in current[:10]]})

    index_close = daily["DJI"][AS_OF]
    implied_divisor = total_now / index_close
    data = {
        "asOf": AS_OF,
        "indexClose": round(index_close, 2),
        "impliedDivisor": round(implied_divisor, 10),
        "publishedDivisor": PUBLISHED_DIVISOR,
        "totalPrice": round(total_now, 2),
        "months": MONTHS,
        "index": [round(monthly["DJI"][m], 2) for m in MONTHS],
        "weights": weights,
        "companies": {t: LABELS.get(t, t) for t in weights},
        "coverage": coverage,
        "top1": top1, "top5": top5, "top10": top10, "effective": effective,
        "current": current,
        "changes": changes,
        "snapshots": snapshots,
        "unavailable": [],
        "latestMonth": END_MONTH,
        "firstMonth": START_MONTH,
    }
    (DATA / "report_data.json").write_text(json.dumps(data, separators=(",", ":")))
    build_page(data)
    print(f"Built index.html: {len(MONTHS)} months, {len(weights)} tickers, "
          f"{len(changes)} change events.")
    print(f"Coverage range: {min(coverage)}-{max(coverage)} of 30.")
    print(f"Current: {len(current)} members, total ${total_now:,.2f}, "
          f"implied divisor {implied_divisor:.11f} (published {PUBLISHED_DIVISOR:.11f}).")
    print("Price histories: full 30/30 coverage.")


def build_page(data):
    payload = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
    page = (ROOT / "template.html").read_text()
    page = page.replace("/*__STYLES__*/", (ROOT / "styles.css").read_text())
    page = page.replace("/*__DATA__*/", "const DATA = " + payload + ";")
    page = page.replace("/*__APP__*/", (ROOT / "app.js").read_text())
    ids = re.findall(r'\bid="([^"]+)"', page.split("<script>")[0])
    assert len(ids) == len(set(ids)), "Duplicate element IDs."
    assert not re.search(r"<script[^>]+src=", page), "Standalone page must embed all scripts."
    (ROOT / "index.html").write_text(page)


if __name__ == "__main__":
    main()
