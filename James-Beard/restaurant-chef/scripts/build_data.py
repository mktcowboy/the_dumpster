#!/usr/bin/env python3
"""Build awards + graph JSON from James Beard public data sources.

Primary: cjwinchester/james-beard CSV (scraped from jamesbeard.org search-past-awards).
Supplement: 2025 Restaurant & Chef winners from the official JBF winners story page.
Never invents fields — blanks stay blank.
"""
from __future__ import annotations

import csv
import json
import re
import hashlib
from collections import defaultdict
from pathlib import Path
from html import unescape

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

def slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "unknown"

def nid(kind: str, *parts: str) -> str:
    base = slug("-".join(p for p in parts if p))
    return f"{kind}:{base}"

def parse_location(loc: str):
    loc = unescape((loc or "").strip())
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
    s = unescape((sub or "").strip())
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

def region_from_category(cat: str) -> str:
    for k, v in REGION_HINTS.items():
        if k.lower() in cat.lower() and cat.lower().startswith("best chef"):
            return v
    return ""

def add_award(awards, **kw):
    awards.append(kw)

def load_csv(awards):
    with RAW.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("category") != "Restaurant & Chef":
                continue
            year = int(row["year"])
            status = row["award_status"].strip()  # Winner / Nominee / Semifinalist
            person = unescape((row.get("recipient_name") or "").strip())
            restaurant = unescape((row.get("restaurant_name") or "").strip())
            # sometimes restaurant is blank and recipient is the restaurant (Outstanding Restaurant etc.)
            subcategory = clean_category(row.get("subcategory") or "")
            location = unescape((row.get("location") or "").strip())
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

def build_graph(awards):
    nodes = {}
    edges = []
    edge_keys = set()

    def ensure(node_id, typ, label, **extra):
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "type": typ, "label": label, **extra}
        else:
            # merge non-empty extras
            for k, v in extra.items():
                if v and not nodes[node_id].get(k):
                    nodes[node_id][k] = v
        return node_id

    def link(src, tgt, rel, **extra):
        if not src or not tgt or src == tgt:
            return
        key = (src, tgt, rel)
        if key in edge_keys:
            return
        edge_keys.add(key)
        edges.append({"source": src, "target": tgt, "rel": rel, **extra})

    for a in awards:
        year = a["year"]
        cat = a["category"] or "Unknown category"
        status = a["status"]
        person = a["person"]
        restaurant = a["restaurant"]
        city = a["city"]
        state = a["state"]
        state_name = a["state_name"]
        region = a["region"]

        yid = ensure(nid("year", str(year)), "year", str(year), year=year)
        cid = ensure(nid("category", cat), "category", cat)

        pid = rid = place_id = state_id = None
        if person:
            pid = ensure(nid("person", person), "person", person)
        if restaurant:
            rid = ensure(nid("restaurant", restaurant, city or "", state or ""), "restaurant", restaurant,
                         city=city, state=state)
        if city and state:
            place_id = ensure(nid("place", city, state), "place", f"{city}, {state}",
                              city=city, state=state, state_name=state_name)
        elif city:
            place_id = ensure(nid("place", city), "place", city, city=city)
        if state:
            state_id = ensure(nid("state", state), "state", state_name or state, state=state)

        # award edges
        rel = {"winner": "won", "nominee": "nominated", "semifinalist": "semifinalist"}.get(status, status)
        subject = pid or rid
        if subject:
            link(subject, cid, rel, year=year, status=status)
            link(subject, yid, "in-year", year=year, status=status)
        if pid and rid:
            link(pid, rid, "works-at", year=year)
        if rid and place_id:
            link(rid, place_id, "located-in")
        elif pid and place_id and not rid:
            link(pid, place_id, "located-in")
        if place_id and state_id:
            link(place_id, state_id, "in-state")
        if region:
            reg_id = ensure(nid("region", region), "region", region)
            if subject:
                link(subject, reg_id, "in-region", year=year)
            link(cid, reg_id, "covers-region")

        # attach award refs onto person/restaurant for profiles
        for target in (pid, rid):
            if not target:
                continue
            nodes[target].setdefault("awards", [])
            nodes[target]["awards"].append({
                "year": year,
                "category": cat,
                "status": status,
                "person": person,
                "restaurant": restaurant,
                "city": city,
                "state": state,
                "region": region,
                "source_url": a.get("source_url", ""),
            })

    # dedupe award lists
    for n in nodes.values():
        if "awards" in n:
            seen = set()
            uniq = []
            for aw in n["awards"]:
                key = (aw["year"], aw["category"], aw["status"], aw.get("person"), aw.get("restaurant"))
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(aw)
            uniq.sort(key=lambda x: (-x["year"], x["category"], x["status"]))
            n["awards"] = uniq
            n["award_count"] = len(uniq)
            n["win_count"] = sum(1 for x in uniq if x["status"] == "winner")

    return {"nodes": list(nodes.values()), "edges": edges}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    awards = []
    load_csv(awards)
    load_2025(awards)

    # Filter: Restaurant & Chef only already; keep all years for data file
    awards.sort(key=lambda a: (a["year"], a["category"], a["status"], a["person"], a["restaurant"]))

    meta = {
        "title": "James Beard Award Graph",
        "description": "Interactive Obsidian-style graph of James Beard Restaurant & Chef Awards recipients and nominees.",
        "generated": "2026-11-05",
        "coverage": {
            "years": sorted({a["year"] for a in awards}),
            "statuses": sorted({a["status"] for a in awards}),
            "award_count": len(awards),
            "winners": sum(1 for a in awards if a["status"] == "winner"),
            "nominees": sum(1 for a in awards if a["status"] == "nominee"),
            "semifinalists": sum(1 for a in awards if a["status"] == "semifinalist"),
            "categories": sorted({a["category"] for a in awards if a["category"]}),
            "sources": [SOURCE_CSV, SOURCE_2025],
            "notes": [
                "Primary dataset: public CSV derived from jamesbeard.org search-past-awards (1991–2024).",
                "2025 Restaurant & Chef winners appended from the official JBF winners story page.",
                "2025 nominees/semifinalists and 2026 cycle not yet included.",
                "Book/Media/Journalism awards excluded from v1 (category filter Restaurant & Chef).",
                "No invented fields; blank when unknown.",
            ],
        },
    }

    with (OUT / "awards.json").open("w", encoding="utf-8") as f:
        json.dump({"meta": meta, "awards": awards}, f, ensure_ascii=False, indent=None, separators=(",", ":"))

    graph = build_graph(awards)
    graph["meta"] = meta
    with (OUT / "graph.json").open("w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=None, separators=(",", ":"))

    # compact stats for README
    stats = {
        "awards": len(awards),
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
        "by_type": {},
    }
    for n in graph["nodes"]:
        stats["by_type"][n["type"]] = stats["by_type"].get(n["type"], 0) + 1
    with (OUT / "stats.json").open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps(stats, indent=2))
    print("years", meta["coverage"]["years"][0], "-", meta["coverage"]["years"][-1])
    print("winners", meta["coverage"]["winners"], "nominees", meta["coverage"]["nominees"], "semi", meta["coverage"]["semifinalists"])

if __name__ == "__main__":
    main()
