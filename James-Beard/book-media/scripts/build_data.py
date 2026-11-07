#!/usr/bin/env python3
"""Build Book / Broadcast Media / Journalism awards + graph JSON from raw CSV."""
from __future__ import annotations
import csv, json, re
from pathlib import Path
from collections import Counter, defaultdict
from html import unescape

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "james-beard-awards.csv"
OUT = ROOT / "data"
SOURCE_CSV = "https://github.com/cjwinchester/james-beard (from jamesbeard.org/awards/search-past-awards)"
SOURCE_URL = "https://www.jamesbeard.org/awards/search-past-awards"
MEDIA_CATS = {"Book", "Broadcast Media", "Journalism"}

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
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "unknown"

def nid(kind: str, *parts: str) -> str:
    return f"{kind}:{slug('-'.join(p for p in parts if p))}"

def clean(s: str) -> str:
    # Repair first: collapsing whitespace would also flatten the non-breaking spaces inside garbled text
    return re.sub(r"\s+", " ", clean_text(s))

def clean_subcat(s: str) -> str:
    s = clean(s)
    return re.sub(r"\s+presented by .+$", "", s, flags=re.I)

def main():
    awards = []
    with RAW.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("category") not in MEDIA_CATS:
                continue
            program = row["category"]
            year = int(row["year"])
            status = row["award_status"].strip()
            status_norm = "semifinalist" if status == "Semifinalist" else status.lower()
            person = clean(row.get("recipient_name") or "")
            book = clean(row.get("book_title") or "")
            publisher = clean(row.get("publisher") or "")
            publication = clean(row.get("publication") or "")
            show = clean(row.get("show") or "")
            company = clean(row.get("company") or "")
            project = clean(row.get("project") or "")
            subcategory = clean_subcat(row.get("subcategory") or "")
            work, work_type = "", ""
            if program == "Book" and book:
                work, work_type = book, "book"
            elif program == "Broadcast Media" and show:
                work, work_type = show, "show"
            elif program == "Broadcast Media" and project:
                work, work_type = project, "show"
            outlet, outlet_type = "", ""
            if program == "Book" and publisher:
                outlet, outlet_type = publisher, "publisher"
            elif program == "Journalism" and publication:
                outlet, outlet_type = publication, "publication"
            elif program == "Broadcast Media" and company:
                outlet, outlet_type = company, "outlet"
            awards.append({
                "year": year, "program": program, "category": subcategory,
                "status": status_norm, "person": person, "book": book, "show": show,
                "publication": publication, "publisher": publisher, "company": company,
                "project": project, "work": work, "work_type": work_type,
                "outlet": outlet, "outlet_type": outlet_type,
                "source": SOURCE_CSV, "source_url": SOURCE_URL,
            })
    awards.sort(key=lambda a: (a["year"], a["program"], a["category"], a["status"], a["person"], a["work"]))

    nodes, edges, edge_keys = {}, [], set()
    node_years, node_awards, node_wins = defaultdict(set), Counter(), Counter()

    def ensure(node_id, typ, label, **extra):
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "type": typ, "label": label, **extra}
        else:
            for k, v in extra.items():
                if v and not nodes[node_id].get(k):
                    nodes[node_id][k] = v
        return node_id

    def link(src, tgt, rel, **extra):
        if not src or not tgt or src == tgt:
            return
        key = (src, tgt, rel, extra.get("year"), extra.get("status"))
        if key in edge_keys:
            return
        edge_keys.add(key)
        edges.append({"source": src, "target": tgt, "rel": rel, **extra})

    for a in awards:
        yid = ensure(nid("year", str(a["year"])), "year", str(a["year"]), year=a["year"])
        prog_id = ensure(nid("program", a["program"]), "program", a["program"])
        cat_label = a["category"] or "Uncategorized"
        cid = ensure(nid("category", a["program"], cat_label), "category", cat_label, program=a["program"])
        link(cid, prog_id, "in-program")
        pid = ensure(nid("person", a["person"]), "person", a["person"]) if a["person"] else None
        wid = ensure(nid(a["work_type"] or "work", a["work"]), a["work_type"] or "work", a["work"]) if a["work"] else None
        oid = ensure(nid(a["outlet_type"] or "outlet", a["outlet"]), a["outlet_type"] or "outlet", a["outlet"]) if a["outlet"] else None
        rel = {"winner": "won", "nominee": "nominated", "semifinalist": "semifinalist"}.get(a["status"], a["status"])
        subject = pid or wid or oid
        if subject:
            link(subject, cid, rel, year=a["year"], status=a["status"], program=a["program"])
            link(subject, yid, "in-year", year=a["year"], status=a["status"])
            link(subject, prog_id, "in-program", year=a["year"])
        if pid and wid:
            link(pid, wid, "authored" if a["program"] == "Book" else "credited-on", year=a["year"])
        if wid and oid:
            link(wid, oid, "published-by" if a["program"] == "Book" else ("aired-on" if a["program"] == "Broadcast Media" else "appeared-in"), year=a["year"])
        if pid and oid and not wid:
            link(pid, oid, "wrote-for" if a["program"] == "Journalism" else "affiliated-with", year=a["year"])
        for k in (pid, wid, oid):
            if not k:
                continue
            node_awards[k] += 1
            if a["status"] == "winner":
                node_wins[k] += 1
            node_years[k].add(a["year"])

    for k, n in node_awards.items():
        nodes[k]["award_count"] = n
        nodes[k]["win_count"] = node_wins.get(k, 0)
        ys = sorted(node_years[k])
        nodes[k]["year_min"], nodes[k]["year_max"] = ys[0], ys[-1]

    meta = {
        "title": "James Beard Media Award Graph",
        "description": "Obsidian-style graph of James Beard Book, Broadcast Media, and Journalism awards.",
        "generated": "2026-11-05",
        "coverage": {
            "years": sorted({a["year"] for a in awards}),
            "programs": sorted({a["program"] for a in awards}),
            "statuses": sorted({a["status"] for a in awards}),
            "award_count": len(awards),
            "winners": sum(1 for a in awards if a["status"] == "winner"),
            "nominees": sum(1 for a in awards if a["status"] == "nominee"),
            "semifinalists": sum(1 for a in awards if a["status"] == "semifinalist"),
            "by_program": dict(Counter(a["program"] for a in awards)),
            "categories": sorted({a["category"] for a in awards if a["category"]}),
            "sources": [SOURCE_CSV, SOURCE_URL],
            "notes": [
                "Primary dataset: public CSV from jamesbeard.org search-past-awards via cjwinchester/james-beard (through 2024).",
                "Includes Book, Broadcast Media, and Journalism only — not Restaurant & Chef.",
                "2025 media winners exist on JBF site but are not yet merged into this v1 CSV-based build.",
                "No invented fields; blank when unknown.",
                "Journalism rows typically have person + publication (outlet); article titles are often absent from the source CSV.",
            ],
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump({"meta": meta, "awards": awards}, (OUT / "awards.json").open("w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump({"meta": meta, "nodes": list(nodes.values()), "edges": edges}, (OUT / "graph.json").open("w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    stats = {"awards": len(awards), "nodes": len(nodes), "edges": len(edges), "by_type": dict(Counter(n["type"] for n in nodes.values())), "by_program": meta["coverage"]["by_program"]}
    json.dump(stats, (OUT / "stats.json").open("w"), indent=2)
    print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    main()
