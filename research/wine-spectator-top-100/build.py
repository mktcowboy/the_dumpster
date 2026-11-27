#!/usr/bin/env python3
"""Build the Wine Spectator Top 100 report from the fetch.py cache.

Outputs (next to this file):
  wine-spectator-top-100.html   self-contained report
  data/top100.csv               every wine, factual fields + links
  data/top100.json              same records, as used by the report

Tasting-note text is Wine Spectator's copyrighted writing, so it is not copied
into the outputs. The build reads each note only to pull the drinking window and
case counts; every wine links to its full review on winespectator.com.

Usage: python3 build.py
"""
import csv
import html
import json
import re
import statistics
import unicodedata
from collections import Counter
from pathlib import Path

from grapes import grape

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
OUT_HTML = HERE / "wine-spectator-top-100.html"
OUT_DIR = HERE / "data"
PULLED = "November 26, 2026"

US_STATES = {"California", "Washington", "Oregon", "New York"}
REGION_STATE = {
    "Napa": "California", "Sonoma": "California", "South Coast": "California",
    "Other California": "California", "Carneros": "California",
    "Bay Area/Central Coast": "California", "Mendocino/Lake": "California",
    "Santa Barbara": "California", "Paso Robles": "California",
    "Mendocino County": "California", "Other Central Coast": "California",
    "Sierra Foothills": "California", "Monterey County": "California",
    "Central Valley-California": "California", "Other North Coast": "California",
    "San Benito County": "California", "California": "California",
    "Oregon": "Oregon", "Willamette Valley": "Oregon", "Other Oregon": "Oregon",
    "Washington": "Washington", "Columbia Valley": "Washington",
    "Walla Walla Valley": "Washington", "Yakima Valley": "Washington",
    "Finger Lakes": "New York", "Long Island": "New York", "New York": "New York",
    "New Mexico": "New Mexico",
}
COLOR = {"red": "Red", "white": "White", "sparkling": "Sparkling",
         "dessert": "Dessert", "rosé": "Rosé", "blush": "Rosé"}
# Names for the most frequent initials. The source data carries initials only.
TASTERS = {
    "JL": "James Laube", "JM": "James Molesworth", "BS": "Bruce Sanderson",
    "JS": "James Suckling", "HS": "Harvey Steiman", "KM": "Kim Marcus",
    "AN": "Alison Napjus", "TF": "Tim Fish", "TM": "Thomas Matthews",
    "MW": "MaryAnn Worobiec", "PM": "Per-Henrik Mansson",
}


def fold(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def key(s):
    return re.sub(r"[^a-z0-9]+", " ", fold(s).lower()).strip()


def clean(s):
    return re.sub(r"\s+", " ", (s or "").replace("´", "")).strip()


def drink_window(note, list_year):
    """Return (display, end_year) parsed from a tasting note's drinking advice."""
    t = re.sub(r"<[^>]+>", "", note or "")
    pats = [
        (r"\b(?:Best|Drink) (?:from|between) (\d{4}) (?:through|and|to) (\d{4})", "range"),
        (r"\bDrink (\d{4}) (?:through|to) (\d{4})", "range"),
        (r"(?i)\b(?:Drink|Best|Drinkable|Tempting) now (?:through|to) (\d{4})", "now-to"),
        (r"\bBest (?:now )?through (\d{4})", "now-to"),
        (r"\bDrink now (?:and|or) (?:over|for) the next (\w+) years", "now-n"),
        (r"\b(?:Best|Drink|Try|Better|At its best) (?:after|from) (\d{4})", "after"),
        (r"\bBest to (?:wait|cellar) until (\d{4})", "after"),
        (r"\b(?:Try|Drink) in (\d{4})", "after"),
        (r"\b(?:Drink|Drinkable) now\b", "now"),
    ]
    for p, kind in pats:
        m = re.search(p, t)
        if not m:
            continue
        if kind == "range":
            return f"{m.group(1)}–{m.group(2)}", int(m.group(2))
        if kind == "now-to":
            return f"Now–{m.group(1)}", int(m.group(1))
        if kind == "after":
            return f"From {m.group(1)}", None
        if kind == "now":
            return "Now", list_year
        if kind == "now-n":
            words = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "eight": 8, "ten": 10}
            n = words.get(m.group(1).lower())
            if n:
                return f"Now–{list_year + n}", list_year + n
    return "", None


def cases(note):
    t = note or ""
    made = re.search(r"([\d,]+) cases made", t)
    imp = re.search(r"([\d,]+) cases imported", t)
    num = lambda m: int(m.group(1).replace(",", "")) if m else None  # noqa: E731
    return num(made), num(imp)


def load():
    stories = json.loads((CACHE / "editorial" / "stories.json").read_text())
    story_url = {(int(y), e["rank"]): e["url"]
                 for y, v in stories.items() for e in v["top10"]}
    rows = []
    for f in sorted((CACHE / "years").glob("wines-*.json")):
        for w in json.loads(f.read_text()):
            y = int(w["top100_year"])
            rank = int(w["top100_rank"])
            country, region = clean(w["country"]), clean(w["region"])
            state = ""
            if country in US_STATES or country == "Other US":
                state = country if country in US_STATES else REGION_STATE.get(region, "")
                country = "United States"
            elif country == "United States":
                state = REGION_STATE.get(region, "")
            if region in (country, state, "Other US"):
                region = ""
            color = COLOR.get(clean(w["color"]).lower())
            wtype = w.get("wine_type") or ("sparkling" if color == "Sparkling" else
                                           "dessert" if color == "Dessert" else "still")
            color_filled = False
            if not color:
                color = {"dessert": "Dessert", "sparkling": "Sparkling"}.get(wtype, "Red")
                color_filled = True
            price = w["price"] if isinstance(w["price"], (int, float)) else None
            dw, dend = drink_window(w["note"], y)
            made, imported = cases(w["note"])
            v = str(w["vintage"]).strip()
            rows.append({
                "y": y, "r": rank, "id": str(w["id"]),
                "w": clean(w["winery_full"]), "n": clean(w["wine_full"]),
                "v": v, "s": int(w["score"]), "p": price,
                "b": clean(w["alternate_bottle_size"] or ""),
                "c": color, "cf": color_filled, "t": wtype,
                "co": country, "st": state, "rg": region,
                "tz": clean(w["taster_initials"]),
                "is": clean(w["issue_date"]), "lb": w.get("label_url") or "",
                "dw": dw, "de": dend, "cm": made, "ci": imported,
                "sk": story_url.get((y, rank), "") if rank <= 10 else "",
                "g": grape(color, clean(w["wine_full"]), region, country),
            })
    # A 1998 quirk: the source repeats ranks, so story matching by rank is off.
    for r in rows:
        if r["y"] == 1998:
            r["sk"] = ""
    rows.sort(key=lambda r: (-r["y"], r["r"], r["w"]))
    return rows, stories


def write_data(rows):
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "top100.json").write_text(json.dumps(rows, ensure_ascii=False))
    cols = [("year", "y"), ("rank", "r"), ("winery", "w"), ("wine", "n"),
            ("vintage", "v"), ("score", "s"), ("price_usd", "p"),
            ("bottle_size", "b"), ("color", "c"), ("type", "t"),
            ("country", "co"), ("us_state", "st"), ("region", "rg"),
            ("taster", "tz"), ("issue_date", "is"), ("drink_window", "dw"),
            ("cases_made", "cm"), ("cases_imported", "ci"),
            ("grape_or_style_inferred", "g")]
    with open(OUT_DIR / "top100.csv", "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow([c for c, _ in cols] + ["ws_review_url", "ws_year_list_url",
                                            "ws_top10_story_url", "label_url"])
        for r in rows:
            wr.writerow([r[k] if r[k] is not None else "" for _, k in cols] + [
                f"https://www.winespectator.com/wine/detail/note_id/{r['id']}",
                f"https://top100-list.winespectator.com/?year={r['y']}",
                r["sk"], r["lb"]])


def main():
    rows, stories = load()
    write_data(rows)
    years = sorted({r["y"] for r in rows})
    parsed = sum(1 for r in rows if r["dw"])
    meta = {
        "pulled": PULLED, "first": years[0], "last": years[-1],
        "count": len(rows), "years": len(years),
        "dwParsed": parsed, "tasters": TASTERS,
        "labels": sum(1 for r in rows if r["lb"]),
        "storyYears": sorted(int(y) for y in stories),
        "video": [int(y) for y, v in stories.items() if v.get("video")],
    }
    tpl = (HERE / "template.html").read_text()
    out = (tpl.replace("/*__DATA__*/[]", json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
              .replace("/*__META__*/{}", json.dumps(meta, ensure_ascii=False)))
    OUT_HTML.write_text(out)
    lc = Counter(r["y"] for r in rows)
    print(f"{len(rows)} wines, {len(years)} lists, drink window parsed {parsed}, "
          f"labels {meta['labels']}, html {OUT_HTML.stat().st_size/1e6:.2f} MB")
    assert all(v == 100 for v in lc.values()), lc
    med = statistics.median(r["p"] for r in rows if r["y"] == years[-1] and r["p"])
    print("latest median price", med)


if __name__ == "__main__":
    main()
