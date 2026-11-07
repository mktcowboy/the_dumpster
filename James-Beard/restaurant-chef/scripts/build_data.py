#!/usr/bin/env python3
"""Build the awards JSON for the Restaurant & Chef graph from James Beard public data sources.

Primary: cjwinchester/james-beard CSV (scraped from jamesbeard.org search-past-awards).
Supplement: 2025 Restaurant & Chef winners from the official JBF winners story page.
Never invents fields — blanks stay blank.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from html import unescape
from collections import Counter
from difflib import SequenceMatcher
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "james-beard-awards.csv"
OUT = ROOT / "data"
SOURCE_CSV = "https://github.com/cjwinchester/james-beard (from jamesbeard.org/awards/search-past-awards)"
SOURCE_2025 = "https://www.jamesbeard.org/stories/the-2025-james-beard-award-winners"

# Normalize US state names / abbreviations for place nodes
STATE_ABBR = {
    "alabama":"AL","alaska":"AK","arizona":"AZ","arkansas":"AR","california":"CA",
    "colorado":"CO","connecticut":"CT","delaware":"DE","florida":"FL","georgia":"GA",
    "hawaii":"HI","idaho":"ID","illinois":"IL","indiana":"IN","iowa":"IA","kansas":"KS",
    "kentucky":"KY","louisiana":"LA","maine":"ME","maryland":"MD","massachusetts":"MA",
    "michigan":"MI","minnesota":"MN","mississippi":"MS","missouri":"MO","montana":"MT",
    "nebraska":"NE","nevada":"NV","new hampshire":"NH","new jersey":"NJ","new mexico":"NM",
    "new york":"NY","north carolina":"NC","north dakota":"ND","ohio":"OH","oklahoma":"OK",
    "oregon":"OR","pennsylvania":"PA","rhode island":"RI","south carolina":"SC",
    "south dakota":"SD","tennessee":"TN","texas":"TX","utah":"UT","vermont":"VT",
    "virginia":"VA","washington":"WA","west virginia":"WV","wisconsin":"WI","wyoming":"WY",
    "district of columbia":"DC","washington dc":"DC","washington, d.c.":"DC","d.c.":"DC","dc":"DC",
    "puerto rico":"PR",
}
ABBR_TO_NAME = {v:k.title() for k,v in STATE_ABBR.items() if len(v)==2}
ABBR_TO_NAME.update({"DC":"District of Columbia","PR":"Puerto Rico"})

REGION_HINTS = {
    "California":"California",
    "Great Lakes":"Great Lakes",
    "Mid-Atlantic":"Mid-Atlantic",
    "Midwest":"Midwest",
    "Mountain":"Mountain",
    "New York":"New York State",
    "Northeast":"Northeast",
    "Northwest":"Northwest & Pacific",
    "South":"South",
    "Southeast":"Southeast",
    "Southwest":"Southwest",
    "Texas":"Texas",
}

# The source CSV has UTF-8 text that was decoded as Windows-1252 (sometimes repeatedly),
# e.g. "Bullyâ€™s" for "Bully’s". Reverse that until the telltale pairs are gone.
MOJIBAKE = re.compile("[ÃÂâÆË][\x80-\xbf\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc\u2013-\u203a\u20ac\u2122]")
# Garbled past repair (truncated mid-character); every other row names it this way.
TEXT_OVERRIDES = {"Union Square CafÃƒÆ’Ã‹â€": "Union Square Cafe"}
# Garbled text whose non-breaking space was flattened to a plain space, so it no longer round-trips.
FRAGMENT_FIXES = [("Â ", " "), ("LÃ Trattoria", "Là Trattoria"), ("TavolÃ ta", "Tavolàta")]

def cp1252_bytes(s: str) -> bytes:
    out = bytearray()
    for c in s:
        try:
            out += c.encode("cp1252")
        except UnicodeEncodeError:
            if ord(c) > 0xFF:
                raise
            out.append(ord(c))  # bytes cp1252 leaves undefined (0x81, 0x8d, ...)
    return bytes(out)

def clean_text(s: str) -> str:
    s = unescape((s or "").strip())
    if s in TEXT_OVERRIDES:
        return TEXT_OVERRIDES[s]
    for bad, good in FRAGMENT_FIXES:
        s = s.replace(bad, good)
    for _ in range(4):
        if not MOJIBAKE.search(s):
            break
        try:
            s = cp1252_bytes(s).decode("utf-8")
        except UnicodeError:
            break
    # Some names are doubled around a pipe ("Jose Enrique|Jose Enrique")
    parts = s.split("|")
    if len(parts) > 1 and len(set(parts)) == 1:
        s = parts[0]
    return s

def slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "unknown"

def nid(kind: str, *parts: str) -> str:
    base = slug("-".join(p for p in parts if p))
    return f"{kind}:{base}"

def parse_location(loc: str):
    loc = clean_text(loc)
    if not loc:
        return "", "", ""
    # "City, State" or "City, ST"
    parts = [p.strip() for p in loc.split(",")]
    if len(parts) >= 2:
        city = parts[0]
        state_raw = parts[-1]
        st = STATE_ABBR.get(state_raw.lower()) or (state_raw.upper() if len(state_raw)==2 else "")
        if not st and state_raw.lower() in STATE_ABBR:
            st = STATE_ABBR[state_raw.lower()]
        # already abbr?
        if len(state_raw) == 2 and state_raw.upper() in ABBR_TO_NAME:
            st = state_raw.upper()
        state_name = ABBR_TO_NAME.get(st, state_raw)
        return city, st, state_name
    # single token — maybe state only
    if loc.lower() in STATE_ABBR:
        st = STATE_ABBR[loc.lower()]
        return "", st, ABBR_TO_NAME.get(st, loc)
    return loc, "", ""

def clean_category(sub: str) -> str:
    s = clean_text(sub)
    s = re.sub(r"\s+", " ", s)
    # strip sponsor suffixes later if needed
    s = re.sub(r"\s+presented by .+$", "", s, flags=re.I)
    # normalize Best Chef variants
    s = s.replace("Best Chefs", "Best Chef")  # umbrella sometimes
    if s.startswith("Best Chef:") or s.startswith("Best Chef "):
        s = s.replace("Best Chef:", "Best Chef").strip()
        # "Best Chef California" already ok
    s = s.replace("Northwest and Pacific", "Northwest & Pacific")
    s = s.replace("Northwest & Pacific", "Northwest & Pacific")
    return s

REGIONS = {**{v: v for v in REGION_HINTS.values()}, **REGION_HINTS}

def region_from_category(cat: str) -> str:
    # Exact match on the part after "Best Chef": a substring match would file "Southeast" under "South"
    if not cat.lower().startswith("best chef"):
        return ""
    return REGIONS.get(cat[len("Best Chef"):].strip(" :"), "")

def add_award(awards, **kw):
    awards.append(kw)

def load_csv(awards):
    with RAW.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("category") != "Restaurant & Chef":
                continue
            year = int(row["year"])
            status = row["award_status"].strip()  # Winner / Nominee / Semifinalist
            person = clean_text(row.get("recipient_name"))
            restaurant = clean_text(row.get("restaurant_name"))
            # sometimes restaurant is blank and recipient is the restaurant (Outstanding Restaurant etc.)
            subcategory = clean_category(row.get("subcategory") or "")
            location = clean_text(row.get("location"))
            city, state, state_name = parse_location(location)
            # Heuristic: restaurant-only awards often put restaurant in recipient_name
            restaurant_only_cats = {
                "Outstanding Restaurant", "Best New Restaurant", "Outstanding Bakery",
                "Outstanding Bar", "Outstanding Bar Program", "Outstanding Hospitality",
                "Outstanding Service", "Outstanding Wine Service", "Outstanding Wine Program",
                "Outstanding Wine & Other Beverages Program", "America's Classics",
                "Best New Bar",
            }
            if not restaurant and person and subcategory in restaurant_only_cats:
                restaurant = person
                person = ""
            region = region_from_category(subcategory)
            add_award(
                awards,
                year=year,
                category=subcategory,
                status=status.lower() if status != "Semifinalist" else "semifinalist",
                person=person,
                restaurant=restaurant,
                city=city,
                state=state,
                state_name=state_name,
                region=region,
                location=location,
                source=SOURCE_CSV,
                source_url="https://www.jamesbeard.org/awards/search-past-awards",
            )

# Hand-curated 2025 winners from official JBF page (verified against story page)
WINNERS_2025 = [
    ("Outstanding Restaurateur", "Lee Hanson", "Frenchette / Le Veau d'Or / Le Rock", "New York, NY"),
    ("Outstanding Restaurateur", "Riad Nasr", "Frenchette / Le Veau d'Or / Le Rock", "New York, NY"),
    ("Outstanding Chef", "Jungsik Yim", "Jungsik", "New York, NY"),
    ("Outstanding Restaurant", "", "Frasca Food and Wine", "Boulder, CO"),
    ("Emerging Chef", "Phila Lorn", "Mawn", "Philadelphia, PA"),
    ("Best New Restaurant", "", "Bûcheron", "Minneapolis, MN"),
    ("Outstanding Bakery", "", "JinJu Patisserie", "Portland, OR"),
    ("Outstanding Pastry Chef or Baker", "Cat Cox", "Country Bird Bakery", "Tulsa, OK"),
    ("Outstanding Hospitality", "", "Atomix", "New York, NY"),
    ("Outstanding Wine & Other Beverages Program", "", "Charleston", "Baltimore, MD"),
    ("Outstanding Bar", "", "Kumiko", "Chicago, IL"),
    ("Best New Bar", "", "Identidad Cocktail Bar", "San Juan, PR"),
    ("Outstanding Professional in Beverage Service", "Arjav Ezekiel", "Birdie's", "Austin, TX"),
    ("Outstanding Professional in Cocktail Service", 'Ignacio "Nacho" Jimenez', "Superbueno", "New York, NY"),
    ("Best Chef California", "Jon Yao", "Kato", "Los Angeles, CA"),
    ("Best Chef Great Lakes", "Noah Sandoval", "Oriole", "Chicago, IL"),
    ("Best Chef Mid-Atlantic", "Carlos Delgado", "Causa and Amazonia", "Washington, DC"),
    ("Best Chef Midwest", "Karyn Tomlinson", "Myriel", "St. Paul, MN"),
    ("Best Chef Mountain", "Salvador Alamilla", "Amano", "Caldwell, ID"),
    ("Best Chef New York State", "Vijay Kumar", "Semma", "New York, NY"),
    ("Best Chef Northeast", "Sky Haneul Kim", "Gift Horse", "Providence, RI"),
    ("Best Chef Northwest & Pacific", "Timothy Wastell", "Antica Terra", "Amity, OR"),
    ("Best Chef South", "Nando Chang", "Itamae AO", "Miami, FL"),
    ("Best Chef Southeast", "Jake Howell", "Peninsula", "Nashville, TN"),
    ("Best Chef Southwest", "Yotaka Martin", "Lom Wong", "Phoenix, AZ"),
    ("Best Chef Texas", "Thomas Bille", "Belly of the Beast", "Spring, TX"),
]

def load_2025(awards):
    for cat, person, restaurant, location in WINNERS_2025:
        city, state, state_name = parse_location(location)
        add_award(
            awards,
            year=2025,
            category=clean_category(cat),
            status="winner",
            person=person,
            restaurant=restaurant,
            city=city,
            state=state,
            state_name=state_name,
            region=region_from_category(cat),
            location=location,
            source="James Beard Foundation 2025 winners story",
            source_url=SOURCE_2025,
        )

# Fields dropped from the published rows: the page derives them or reads them from meta.
DROP_FIELDS = {"location", "source", "state_name"}
SOURCE_URLS = ["https://www.jamesbeard.org/awards/search-past-awards", SOURCE_2025]


def compact(a):
    """Published row: blank fields omitted; `src` indexes meta.sources (omitted for the CSV)."""
    row = {k: v for k, v in a.items() if k not in DROP_FIELDS and k != "source_url" and v not in ("", None)}
    src = SOURCE_URLS.index(a["source_url"])
    if src:
        row["src"] = src
    return row


# ---- Spelling variants -------------------------------------------------------------------------
# The source spells many names several ways ("Charlie Trotter's" / "Charlie Trotters", "Magnolia Grill" /
# "Magnolia Grlll", "Rob" / "Robert Connoley"). Variants are merged so each restaurant and person has one record:
#   restaurants: same city, and identical once case/accents/punctuation are ignored, or ≥ RESTAURANT_SIMILARITY alike;
#   people: identical once folded, or ≥ PERSON_SIMILARITY alike while credited at the same restaurant.
# Pairs below were reviewed and are different restaurants or people despite similar names.
RESTAURANT_SIMILARITY = 0.85
PERSON_SIMILARITY = 0.8
KEEP_APART = {
    frozenset({"Momofuku", "Momofuku Ko"}),
    frozenset({"Public", "Republic"}),
    frozenset({"Itamae", "Itamae AO"}),
    frozenset({"Bin 36", "Bin 365"}),
    frozenset({"The Dining Room at Chico Hot Springs", "The Tasting Room at Chico Hot Springs"}),
    frozenset({"Fisher's at Orange Beach Marina", "Fisher's Upstairs at Orange Beach Marina"}),
    frozenset({"Fisher's at Orange Beach Marina", "Fisher’s Upstairs at Orange Beach Marina"}),
    frozenset({"Diana Widjojo", "Ena Widjojo"}),      # siblings
    frozenset({"Quynh-Vy Pham", "Yenvy Pham"}),       # siblings
    frozenset({"Quynh-Vy Pham", "YENVY PHAM"}),
}
# Reviewed spellings to keep when the source used a typo more often than the correct form.
PREFERRED = {
    "Saffron de Twah", "The Original Ninfa's on Navigation", "Yabu Pushelberg",
    "Old Chatham Sheepherding Co. Inn", "BJ Lieberman", "Clare de Boer", "Louise Fili, Ltd.",
}
GARBLED = re.compile("[?\ufffd–Ÿžç«Œ]")  # leftovers of text damaged past repair, e.g. "Caf?Juanita"


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.replace("’", "'"))
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


class Clusters:
    """Union-find over names."""
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)


def similar(a: str, b: str, threshold: float) -> bool:
    fa, fb = fold(a), fold(b)
    if fa == fb:
        return True
    if min(len(fa), len(fb)) < 5 or frozenset({a, b}) in KEEP_APART:
        return False
    m = SequenceMatcher(None, fa, fb)
    return m.real_quick_ratio() >= threshold and m.quick_ratio() >= threshold and m.ratio() >= threshold


def canonical(names, rows_of):
    """Spelling to keep: a reviewed one, else never a garbled one if a clean one exists, then the most used, then the most recent."""
    return max(names, key=lambda n: (n in PREFERRED, not GARBLED.search(n), len(rows_of[n]), max(a["year"] for a in rows_of[n])))


def merge_variants(awards, field, groups, threshold):
    """Rewrite `field` so every variant in a cluster uses its canonical spelling. Returns names merged away."""
    rows_of = {}
    for a in awards:
        if a[field]:
            rows_of.setdefault(a[field], []).append(a)
    clusters = Clusters()
    for names in groups:
        names = sorted(names)
        for i, x in enumerate(names):
            for y in names[i + 1:]:
                if similar(x, y, threshold):
                    clusters.union(x, y)
    members = {}
    for name in rows_of:
        members.setdefault(clusters.find(name), []).append(name)
    merged = 0
    for names in members.values():
        if len(names) < 2:
            continue
        keep = canonical(names, rows_of)
        for name in names:
            if name != keep:
                merged += 1
                for a in rows_of[name]:
                    a[field] = keep
    return merged


def merge_name_variants(awards):
    by_city = {}
    for a in awards:
        if a["restaurant"]:
            by_city.setdefault((a["city"], a["state"]), set()).add(a["restaurant"])
    restaurants = merge_variants(awards, "restaurant", by_city.values(), RESTAURANT_SIMILARITY)

    # People: case/punctuation variants anywhere, near matches only among people credited at the same restaurant.
    by_fold = {}
    by_restaurant = {}
    for a in awards:
        if a["person"]:
            by_fold.setdefault(fold(a["person"]), set()).add(a["person"])
            if a["restaurant"]:
                by_restaurant.setdefault((a["restaurant"], a["city"]), set()).add(a["person"])
    people = merge_variants(awards, "person", [*by_fold.values(), *by_restaurant.values()], PERSON_SIMILARITY)
    return restaurants, people


def dedupe(awards):
    """The CSV repeats some awards under different recipient IDs; keep one of each identical published row."""
    seen = set()
    out = []
    for a in awards:
        key = tuple(sorted(compact(a).items()))
        if key not in seen:
            seen.add(key)
            out.append(a)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    awards = []
    load_csv(awards)
    load_2025(awards)
    raw_count = len(awards)
    restaurants_merged, people_merged = merge_name_variants(awards)
    awards = dedupe(awards)

    # Filter: Restaurant & Chef only already; keep all years for data file
    awards.sort(key=lambda a: (a["year"], a["category"], a["status"], a["person"], a["restaurant"]))

    meta = {
        "title": "James Beard Award Graph",
        "description": "Interactive Obsidian-style graph of James Beard Restaurant & Chef Awards recipients and nominees.",
        "generated": "2026-11-05",
        "sources": [
            {"label": "JBF search-past-awards (via cjwinchester/james-beard CSV)", "url": SOURCE_URLS[0]},
            {"label": "James Beard Foundation 2025 winners story", "url": SOURCE_URLS[1]},
        ],
        "state_names": dict(sorted({a["state"]: a["state_name"] for a in awards if a["state"]}.items())),
        "coverage": {
            "years": sorted({a["year"] for a in awards}),
            "award_count": len(awards),
            "duplicates_merged": raw_count - len(awards),
            "name_variants_merged": {"restaurants": restaurants_merged, "people": people_merged},
            "winners": sum(1 for a in awards if a["status"] == "winner"),
            "nominees": sum(1 for a in awards if a["status"] == "nominee"),
            "semifinalists": sum(1 for a in awards if a["status"] == "semifinalist"),
            "notes": [
                "Primary dataset: public CSV derived from jamesbeard.org search-past-awards (1991–2024).",
                "2025 Restaurant & Chef winners appended from the official JBF winners story page.",
                "2025 nominees/semifinalists and 2026 cycle not yet included.",
                "Book/Media/Journalism awards excluded (category filter Restaurant & Chef).",
                "No invented fields; omitted when unknown.",
            ],
        },
    }

    # The page builds the graph from these rows in the browser.
    with (OUT / "awards.json").open("w", encoding="utf-8") as f:
        json.dump({"meta": meta, "awards": [compact(a) for a in awards]}, f,
                  ensure_ascii=False, indent=None, separators=(",", ":"))
    print(json.dumps(meta["coverage"] | {"years": f"{meta['coverage']['years'][0]}-{meta['coverage']['years'][-1]}"}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
