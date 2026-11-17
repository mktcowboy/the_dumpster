#!/usr/bin/env python3
"""Porsche 911 generations, trims and spec tags for the 911 report.

The 911 report has one tab per generation. Each tab's search covers that
generation's model years on AutoTempest and its Bring a Trailer pages; years
shared by two generations (1989, 2005, 2012, 2013, 2020) are scraped by both
and classify() keeps each car in one tab.

classify() reads the title first and the description second:
  generation  early, g, 964, 993, 996, 997, 991, 992 (model year + trim)
  phase       997.1, 991.2, 992.2 ... where Porsche split a generation
  trim        Carrera S, GT3 Touring, Turbo S, Targa 4 GTS ...
  body        Coupe, Cabriolet, Targa
  gearbox     Manual or PDK/Auto (stated, or the only gearbox the trim had)
  drive       RWD or AWD (from the trim)
  options     Weissach, Paint to Sample, Ceramic brakes ...

tags(row) flattens those into the chip names the report filters on.
TAG_GROUPS tells the report how to lay the chips out and which ones go into
the market-value model. Phase and drive follow from the year and trim, so
they are filters only.
"""
import re

# key, tab title, AutoTempest year windows, Bring a Trailer model pages (under /porsche/), BaT title rule
GENERATIONS = [
    ("992", "992 (2020+)", [(y, y) for y in range(2020, 2027)], [
        "992-911", "992-911-carrera", "992-911-carrera-4", "992-911-carrera-4s", "992-911-carrera-t",
        "992-911-carrera-t-club-coupe", "992-911-carrera-gts", "992-911-carrera-4-gts",
        "992-911-carrera-gts-cabriolet-america-edition", "992-911-targa-4", "992-911-targa-4s",
        "992-911-targa-4-gts", "992-911-targa-4s-heritage-design-edition",
        "992-911-targa-edition-50-years-porsche-design", "992-turbo", "992-911-turbo-s",
        "992-911-turbo-50-years", "992-gt3", "992-911-dakar", "992-911-st", "992-911-sport-classic",
        "992-911-spirit-70",
    ], ""),
    ("991", "991 (2012-19)", [(2012, 2013), (2014, 2015), (2016, 2017), (2018, 2020)], [
        "991-911", "991-911-carrera", "991-911-carrera-4", "991-911-carrera-4s", "991-911-carrera-t",
        "991-911-carrera-gts", "991-911-carrera-4-gts", "991-911-carrera-gts-club-coupe",
        "991-911-carrera-gts-rennsport-reunion", "991-911-carrera-black-edition",
        "991-911-carrera-s-endurance-racing-edition", "991-911-50th-anniversary", "991-911-targa-4",
        "991-911-targa-4s", "991-911-targa-4-gts", "991-911-targa-4-gts-exclusive-manufaktur-edition",
        "991-911-targa-4s-exclusive-design-edition", "991-911-turbo", "991-911-turbo-s",
        "991-911-turbo-s-exclusive-series", "991-911-r", "991-911-speedster", "991-gt3", "991-gt2",
    ], ""),
    ("997", "997 (2005-12)", [(2005, 2008), (2009, 2013)], [
        "997-911", "997-911-carrera", "997-911-carrera-4", "997-911-carrera-4s", "997-911-carrera-gts",
        "997-911-carrera-4-gts", "997-911-carrera-black-edition", "997-911-carrera-s-club-coupe",
        "997-911-targa-4", "997-911-targa-4s", "997-turbo", "997-911-turbo-s",
        "997-911-turbo-s-edition-918-spyder", "997-911-speedster", "997-911-sport-classic", "997-gt3",
        "997-gt2",
    ], ""),
    ("996", "996 (1999-2005)", [(1999, 2005)], [
        "996-911", "996-911-carrera-4", "996-911-carrera-4s", "996-911-carrera-targa",
        "996-911-carrera-4-millennium-edition", "996-911-40th-anniversary-edition", "996-turbo",
        "996-911-turbo-s", "996-gt3", "996-gt2",
    ], ""),
    ("993", "993 (1995-98)", [(1994, 1998)], [
        "993", "993-911-carrera-4", "993-911-carrera-4s", "993-911-carrera-s", "993-911-carrera-rs",
        "993-911-carrera-s-coupe-vesuvio-edition", "993-turbo", "993-911-turbo-s", "993-gt2",
    ], ""),
    ("964", "964 (1989-94)", [(1989, 1994)], [
        "964", "964-911-carrera-4", "964-911-america-roadster", "964-911-carrera-4-coupe-30th-anniversary-jubilee",
        "964-911-carrera-4-leichtbau", "964-911-carrera-4-widebody", "964-911-speedster", "964-911-turbo-33",
        "964-911-turbo-36", "964-911-turbo-s-36", "964-911-turbo-s2", "964-carrera-rs", "911-rs-america",
    ], ""),
    ("g", "G-body & 930 (1974-89)", [(1974, 1989)], [
        "911-carrera-1974-1977", "911sc", "911-carrera-3-2", "930-turbo", "911-speedster-1989",
    ], ""),
    # BaT has no early-911 page; the all-911 page is filtered to 1964-73 titles.
    ("early", "Early 911 (1965-73)", [(1964, 1973)], ["911"], "\\b196[4-9]\\b;\\b197[0-3]\\b"),
]

AT_URL = "https://www.autotempest.com/results?localization=country&make=porsche&model=911&minyear={lo}&maxyear={hi}&zip=73102"
BAT_URL = "https://bringatrailer.com/porsche/{page}/"
# Bring a Trailer sales older than this are left out of the 911 overlay.
BAT_SINCE_DAYS = 3 * 365


def search_lines():
    """Search lines for refresh_911.SEARCHES, one per generation tab (slug = generation key)."""
    lines = []
    for key, title, windows, pages, bat_match in GENERATIONS:
        urls = " ".join(AT_URL.format(lo=lo, hi=hi) for lo, hi in windows)
        bat = " ".join(BAT_URL.format(page=page) for page in pages)
        lines.append(f"{urls}|{title}|{key}|{bat}|{bat_match}||||911:{key}")
    return lines


def _rx(pattern):
    return re.compile(pattern, re.I)


NOT_A_911 = _rx(r"\b(?:912e?|914|718|boxster|cayman|cayenne|macan|panamera|taycan|356|924|928|944|968|carrera gt|959)\b"
                r"|\bcup\b|\brace ?car\b|\bliterature\b")
YEAR_BEFORE_MAKE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\s+porsche\b", re.I)
ANY_YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")

# (trim, title regex, generations it applies to or None). Most specific first.
TRIMS = [
    ("GT2 RS", r"\bgt2 ?rs\b", None),
    ("GT2", r"\bgt2\b", None),
    ("GT3 RS", r"\bgt3 ?rs\b", None),
    ("GT3 Touring", r"\bgt3\b.*\btouring\b|\btouring\b.*\bgt3\b", None),
    ("GT3", r"\bgt3\b", None),
    ("911 R", r"\b911 r\b", ("991",)),
    ("S/T", r"\bs/t\b", ("992",)),
    ("Dakar", r"\bdakar\b", ("992",)),
    ("Sport Classic", r"\bsport classic\b", None),
    ("Speedster", r"\bspeedster\b", None),
    ("America Roadster", r"\bamerica roadster\b", ("964",)),
    ("RS America", r"\brs america\b", ("964",)),
    ("Carrera RS", r"\bcarrera rs\b|\brs 2\.7\b|\b2\.7 rs\b", ("early", "g", "964", "993")),
    ("Turbo S", r"\bturbo s\b", None),
    ("Turbo", r"\bturbo\b|\b930\b", None),
    ("Targa 4 GTS", r"\btarga 4 gts\b", None),
    ("Carrera 4 GTS", r"\b(?:carrera 4|c4) gts\b", None),
    ("Carrera GTS", r"\bgts\b", None),
    ("Targa 4S", r"\btarga 4 ?s\b", None),
    ("Targa 4", r"\btarga 4\b", None),
    ("Carrera 4S", r"\bcarrera 4 ?s\b|\bc4s\b|\b911 4s\b", None),
    ("Carrera 4", r"\bcarrera 4\b|\bc4\b", None),
    ("Carrera T", r"\bcarrera t\b", ("991", "992")),
    ("Carrera S", r"\bcarrera s\b|\b911 s\b", ("993", "996", "997", "991", "992")),
    ("Carrera 2", r"\bcarrera 2\b|\bc2\b", ("964", "993")),
    ("SC", r"\b911 ?sc\b|\bsc\b", ("g",)),
    ("911S", r"\b911 ?s\b", ("early", "g")),
    ("911E", r"\b911 ?e\b", ("early",)),
    ("911T", r"\b911 ?t\b", ("early",)),
    ("911L", r"\b911 ?l\b", ("early",)),
    ("Carrera", r"\bcarrera\b", None),
]
TRIMS = [(name, _rx(pattern), gens) for name, pattern, gens in TRIMS]
# Titles that name no trim are the base car.
BASE_TRIM = {"early": "911", "g": "911", "964": "Carrera 2", "993": "Carrera", "996": "Carrera",
             "997": "Carrera", "991": "Carrera", "992": "Carrera"}

TRIM_ORDER = [
    "911", "911T", "911E", "911L", "911S", "SC", "Carrera", "Carrera 2", "Carrera T", "Carrera S",
    "Carrera 4", "Carrera 4S", "Targa 4", "Targa 4S", "Carrera GTS", "Carrera 4 GTS", "Targa 4 GTS",
    "Turbo", "Turbo S", "Carrera RS", "RS America", "America Roadster", "Speedster", "Sport Classic",
    "Dakar", "S/T", "911 R", "GT3", "GT3 Touring", "GT3 RS", "GT2", "GT2 RS",
]
COUPE_ONLY = {"GT3", "GT3 Touring", "GT3 RS", "GT2", "GT2 RS", "911 R", "S/T", "Dakar", "Carrera RS",
              "RS America", "Carrera T"}

CABRIOLET = _rx(r"\bcabrio(?:let)?\b|\bconvertible\b|\bspeedster\b|\broadster\b")
TARGA = _rx(r"\btarga\b")
COUPE = _rx(r"\bcoupe\b")

PDK = _rx(r"\bpdk\b|\btiptronic\b|\bautomatic\b|\bdual[- ]clutch\b|\bauto\b|\b8[ -]speed\b|\bsportomatic\b")
MANUAL = _rx(r"\b[4-7][ -]speed manual\b|\bmanual (?:transmission|gearbox|trans)\b|\bmanual\b(?! mode)"
             r"|\bstick ?shift\b|\b[67]mt\b|\bg50\b|\b915\b")
SPEEDS = _rx(r"\b[4-7][ -]speed\b")
OWNERS_MANUAL = _rx(r"owner'?s'? manuals?|\bmanuals\b|manual (?:mode|shift mode|shifting mode)")

OPTIONS = [
    ("Weissach", r"\bweissach\b"),
    ("Lightweight", r"\blightweight\b|\bleichtbau\b"),
    ("Clubsport", r"\bclub ?sport\b"),
    ("Paint to Sample", r"\bpaint[ -]to[ -]sample\b|\bpts\b"),
    ("Ceramic brakes", r"\bpccb\b|\bceramic (?:composite )?brakes?\b|\bceramic composite\b"),
    ("Bucket seats", r"\bbucket seats?\b|\bfull buckets?\b|\bcarbon (?:fiber )?buckets?\b|\blwb seats?\b"),
    ("Front lift", r"\bfront[- ]axle lift\b|\bfront lift\b|\bnose lift\b|\blift system\b"),
    ("Sport Chrono", r"\bsport chrono\b"),
    ("Burmester", r"\bburmester\b"),
    ("Special edition", r"\b(?:black|club coupe|heritage design|50 years|50th anniversary|40th anniversary|"
                        r"anniversary|jubil[a-z]*|spirit 70|endurance racing|america edition|vesuvio|918 spyder)\b"),
    ("Exclusive Series", r"\bexclusive series\b|\bexclusive manufaktur\b"),
    ("CPO", r"\bcertified\b|\bcpo\b"),
    ("PPF", r"\bppf\b|\bpaint protection film\b|\bclear bra\b|\bxpel\b"),
]
OPTIONS = [(name, _rx(pattern)) for name, pattern in OPTIONS]

PHASES = ["997.1", "997.2", "991.1", "991.2", "992.1", "992.2"]
TAG_GROUPS = [
    {"key": "phase", "label": "Phase", "names": PHASES, "exclusive": True, "model": []},
    {"key": "trim", "label": "Trim", "names": TRIM_ORDER, "exclusive": True, "model": "ref"},
    {"key": "body", "label": "Body", "names": ["Coupe", "Cabriolet", "Targa"], "exclusive": True, "model": ["Cabriolet"]},
    {"key": "gearbox", "label": "Gearbox", "names": ["Manual", "PDK/Auto"], "exclusive": True, "model": ["Manual"]},
    {"key": "drive", "label": "Drive", "names": ["RWD", "AWD"], "exclusive": True, "model": []},
    {"key": "options", "label": "Options", "names": [name for name, _ in OPTIONS], "exclusive": False, "model": "all"},
]


def model_year(title):
    match = YEAR_BEFORE_MAKE.search(title or "") or ANY_YEAR.search(title or "")
    return int(match.group(1)) if match else None


def _norm(text):
    return re.sub(r"\s+", " ", (text or "").lower().replace("-", " ").replace("–", " "))


def _trim(title, gen):
    for name, rx, gens in TRIMS:
        if (gens is None or gen is None or gen in gens) and rx.search(title):
            return name
    return None


def generation(year, title):
    """Generation key for a model year and title, or None when it is not a road-going 911."""
    t = _norm(title)
    if year is None or NOT_A_911.search(t):
        return None
    special = _trim(t, None)
    if year <= 1973:
        return "early"
    if year <= 1988:
        return "g"
    if year == 1989:
        return "964" if re.search(r"\bcarrera 4\b|\bc4\b|\b964\b", t) else "g"
    if year <= 1994:
        return "964"
    if year <= 1998:
        return "993"
    if year <= 2004:
        return "996"
    if year == 2005:
        old = special in {"Turbo", "Turbo S", "GT2", "GT3", "Carrera 4S"} or re.search(r"\btarga\b|\b40th\b|\b996\b", t)
        return "996" if old and "997" not in t else "997"
    if year <= 2011:
        return "997"
    if year == 2012:
        if re.search(r"\b991\b|7 speed manual", t):
            return "991"
        if re.search(r"\b997\b", t) or special not in {None, "Carrera", "Carrera S"}:
            return "997"
        return "997" if CABRIOLET.search(t) else "991"
    if year == 2013:
        return "997" if special in {"Turbo", "Turbo S", "GT2", "GT2 RS"} else "991"
    if year <= 2019:
        return "991"
    if year == 2020:
        return "991" if special in {"Turbo", "Turbo S", "Speedster", "GT3", "GT3 Touring", "GT3 RS", "GT2 RS"} else "992"
    return "992"


def phase(gen, year, trim):
    if gen == "997":
        late = 2010 if trim in {"Turbo", "Turbo S", "GT3", "GT3 RS", "GT2", "GT2 RS"} else 2009
        return "997.2" if year >= late else "997.1"
    if gen == "991":
        return "991.2" if year >= 2017 else "991.1"
    if gen == "992":
        if trim in {"GT3 RS", "Dakar", "S/T", "Sport Classic"}:
            return "992.1"
        late = 2026 if trim in {"Turbo", "Turbo S"} else 2025
        return "992.2" if year >= late else "992.1"
    return None


def _gearbox(title, description, gen, trim):
    t, d = _norm(title), OWNERS_MANUAL.sub(" ", _norm(description))
    if PDK.search(t):
        return "PDK/Auto"
    if MANUAL.search(OWNERS_MANUAL.sub(" ", t)) or SPEEDS.search(t):
        return "Manual"
    pdk, manual = bool(PDK.search(d)), bool(MANUAL.search(d))
    if pdk != manual:
        return "PDK/Auto" if pdk else "Manual"
    # Trims that only came with one gearbox.
    if trim in {"S/T", "911 R", "Carrera RS", "RS America", "America Roadster"} or gen in {"early", "g"}:
        return "Manual"
    if trim in {"GT2", "GT3", "GT3 RS"} and gen in {"996", "997"}:
        return "Manual"
    if trim == "Sport Classic" or (trim == "Speedster" and gen == "991"):
        return "Manual"
    if trim in {"GT3 RS", "GT2 RS", "Dakar"} and gen in {"991", "992"}:
        return "PDK/Auto"
    if trim in {"Turbo", "Turbo S"} and gen in {"991", "992"}:
        return "PDK/Auto"
    return None


def _drive(gen, trim):
    if not trim:
        return None
    if " 4" in trim or trim == "Dakar":
        return "AWD"
    if trim in {"Turbo", "Turbo S"}:
        return "RWD" if gen in {"g", "964"} else "AWD"
    return "RWD"


def _body(title, trim):
    t = _norm(title)
    if CABRIOLET.search(t) or trim in {"Speedster", "America Roadster"}:
        return "Cabriolet"
    if TARGA.search(t):
        return "Targa"
    if COUPE.search(t) or trim in COUPE_ONLY:
        return "Coupe"
    return None


def classify(title, description="", year=None):
    """Generation, phase, trim, body, gearbox, drive and options of one listing."""
    year = year or model_year(title)
    gen = generation(year, title)
    if gen is None:
        return {"generation": None}
    t = _norm(title)
    trim = _trim(t, gen) or BASE_TRIM[gen]
    # Same car, two names: the 964 base car is the Carrera 2, the 993's is just Carrera,
    # and an untrimmed G-body is an SC (1978-83) or a 3.2 Carrera (1984-89) by year.
    if gen == "964" and trim == "Carrera":
        trim = "Carrera 2"
    elif gen == "993" and trim == "Carrera 2":
        trim = "Carrera"
    elif gen == "g" and trim == "911" and year >= 1978:
        trim = "SC" if year <= 1983 else "Carrera"
    text = t + " " + _norm(description)
    if trim == "GT3" and re.search(r"\bgt3 touring\b", text):
        trim = "GT3 Touring"
    return {
        "generation": gen,
        "phase": phase(gen, year, trim),
        "trim": trim,
        "body": _body(title, trim),
        "gearbox": _gearbox(title, description, gen, trim),
        "drive": _drive(gen, trim),
        "options": [name for name, rx in OPTIONS if rx.search(text)],
    }


def tags(row):
    """Chip names for one listing row (title/description dict)."""
    info = classify(row.get("title", ""), row.get("description", ""))
    if not info.get("generation"):
        return []
    out = [info[key] for key in ("phase", "trim", "body", "gearbox", "drive") if info.get(key)]
    return out + info["options"]


def add_tags(rows):
    """Add a "tags" list to each row dict and return the rows."""
    for row in rows:
        row["tags"] = tags(row)
    return rows


def in_generation(row, gen):
    return classify(row.get("title", ""), row.get("description", "")).get("generation") == gen
