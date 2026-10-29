#!/usr/bin/env python3
"""Build the self-contained aircraft HTML report from saved snapshots and README.md."""
import argparse
import html as html_lib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from listings import clean_registration, number_text, price_number
from saved_store import HERE, format_as_of, fresh_days as resolve_fresh_days, load_meta, read_csv, source_path

TEMPLATE_PATH = HERE / "report_template.html"
README_PATH = HERE / "README.md"
DEFAULT_REPORT = HERE / "output" / "report.html"


def js_json(obj):
    """JSON safe to embed inside a <script> block."""
    return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _sources(row):
    raw = row.get("sources") or ""
    try:
        data = json.loads(raw) if raw else []
    except (TypeError, ValueError):
        data = []
    if not isinstance(data, list) or not data:
        data = [{
            "source": (row.get("source") or "").split(",")[0],
            "price": row.get("price") or "",
            "link": row.get("link") or "",
            "listing_id": row.get("listing_id") or "",
        }]
    cleaned = []
    for item in data:
        if not isinstance(item, dict):
            continue
        cleaned.append({
            "source": item.get("source") or "",
            "price": item.get("price") or "",
            "link": item.get("link") or "",
            "listing_id": item.get("listing_id") or "",
        })
    return cleaned


def _num(value):
    text = number_text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


SITE_LABELS = {
    "cirrus": "Cirrus",
    "cubcrafters": "CubCrafters",
    "aso": "ASO",
    "globalair": "GlobalAir",
    "aircraftdealer": "AircraftDealer",
    "barnstormers": "Barnstormers",
    "controller": "Controller",
    "tradeaplane": "Trade-A-Plane",
    "aircraftcom": "Aircraft.com",
    "aerotrader": "Aerotrader",
    "ebay": "eBay",
}


def site_label(name):
    return SITE_LABELS.get(name, name or "")


def _hours(value):
    number = _num(value)
    if number is None:
        return None
    return int(number) if number == int(number) else number


def _stated_notes(row, description):
    """Copy structured facts into the text the spec chips read, when not already there."""
    text = description or ""
    low = text.lower()
    extra = []
    if row.get("fiki") == "yes" and "fiki" not in low:
        extra.append("FIKI")
    if row.get("tks") == "yes" and "tks" not in low:
        extra.append("TKS")
    if row.get("air_conditioning") == "yes" and "air conditioning" not in low and "a/c" not in low:
        extra.append("air conditioning")
    for key in ("avionics", "adsb", "taws", "autopilot", "exterior", "interior"):
        value = str(row.get(key) or "").strip()
        if value and value.lower() not in low:
            extra.append(value)
    if row.get("landings") and "landing" not in low:
        extra.append(f"{row['landings']} landings")
    if row.get("engine_cycles") and "cycle" not in low:
        extra.append(f"{row['engine_cycles']} cycles")
    if row.get("jet_support") and "jet support" not in low:
        extra.append(f"Cirrus Jet Support {row['jet_support']}")
    label = " ".join(part for part in (row.get("model"), row.get("variant")) if part)
    if label and label.lower() not in low:
        extra.append(label)
    if row.get("gear") and str(row["gear"]).lower() not in low:
        extra.append(row["gear"])
    for key in ("engine_make", "engine_model"):
        value = str(row.get(key) or "").strip()
        if value and value.lower() not in low:
            extra.append(value)
    if extra:
        text = (text + " " + " ".join(extra)).strip()
    return text[:800]


def _price_drop(row):
    notes = []
    stated = str(row.get("price_drop") or "").strip()
    if stated:
        notes.append(stated)
    observed = str(row.get("observed_drop") or "").strip()
    if observed:
        prior = str(row.get("prior_price") or "").strip()
        line = f"Down {observed}" + (f" from {prior}" if prior else "")
        if line not in notes:
            notes.append(line)
    return "; ".join(notes)


def client_row(row):
    """One airplane in the car-tab row shape.

    `mileage` is total time in hours and `vin` is the N-number, so the same
    tab renderer can be dropped into the car report later. The primary `link`
    is the lowest-priced listing; each entry in `sources` keeps its own URL.
    """
    sources = []
    for item in _sources(row):
        label = site_label(item.get("source") or "")
        sources.append({
            "site": label,
            "price": price_number(item.get("price")),
            "price_with_fees": None,
            "link": item.get("link") or "",
            "listing_id": item.get("listing_id") or "",
        })
    city = str(row.get("city") or "").strip()
    state = str(row.get("state") or "").strip()
    airport = str(row.get("airport") or "").strip()
    where = ", ".join(part for part in (city, state) if part) or str(row.get("location") or "").strip()
    if airport and airport not in where:
        where = f"{where} · {airport}".strip(" ·")
    names = []
    for item in sources:
        if item["site"] and item["site"] not in names:
            names.append(item["site"])
    if not names and row.get("source"):
        names = [site_label(part) for part in str(row["source"]).split(",") if part]
    return {
        "listing_id": row.get("listing_id") or "",
        "title": row.get("title") or "",
        "year": int(row["year"]) if str(row.get("year") or "").isdigit() else None,
        "price": price_number(row.get("price")),
        "mileage": _hours(row.get("ttaf")),
        "deal_rating": "",
        "is_hot": False,
        "is_new": str(row.get("is_new") or "").lower() == "yes",
        "price_drop": _price_drop(row),
        "posted_date": row.get("posted_date") or "",
        "city": where,
        "distance": "",
        "dealer": row.get("seller") or "",
        "site_code": ", ".join(names),
        "description": _stated_notes(row, row.get("description") or ""),
        "link": row.get("link") or "",
        "image_url": row.get("image_url") or "",
        "msrp": None,
        "msrp_source": "",
        "vin": clean_registration(row.get("n_number")),
        "extra_sites": "",
        "sources": sources,
        "family": row.get("family") or "",
        "serial": row.get("serial_number") or "",
    }


def client_rows(rows):
    return [client_row(row) for row in rows]


def _inline_md(text):
    """Inline markdown. Code spans are escaped and not formatted further."""
    parts = []
    cursor = 0
    for match in re.finditer(r"`([^`]+)`", text):
        parts.append(_inline_prose(text[cursor:match.start()]))
        parts.append("<code>" + html_lib.escape(match.group(1)) + "</code>")
        cursor = match.end()
    parts.append(_inline_prose(text[cursor:]))
    return "".join(parts)


def _inline_prose(text):
    escaped = html_lib.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    def link(match):
        label, url = match.group(1), html_lib.unescape(match.group(2))
        if not re.match(r"https?://", url):
            return match.group(0)
        return '<a href="' + html_lib.escape(url, quote=True) + '">' + label + "</a>"
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, escaped)


def _table_html(rows):
    def cells(line):
        body = line.strip().strip("|")
        return [cell.strip() for cell in body.split("|")]
    head = cells(rows[0])
    body_rows = rows[2:] if len(rows) > 1 and re.match(r"^[\s|:-]+$", rows[1]) else rows[1:]
    html = ["<table>", "<thead><tr>"]
    html.extend("<th>" + _inline_md(cell) + "</th>" for cell in head)
    html.append("</tr></thead><tbody>")
    for line in body_rows:
        html.append("<tr>")
        html.extend("<td>" + _inline_md(cell) + "</td>" for cell in cells(line))
        html.append("</tr>")
    html.append("</tbody></table>")
    return "".join(html)


def markdown_to_html(text):
    """The README subset this report uses: headings, lists, tables, code, links."""
    lines = text.replace("\r\n", "\n").split("\n")
    blocks = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            fence = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                fence.append(html_lib.escape(lines[index]))
                index += 1
            if index < len(lines):
                index += 1
            blocks.append("<pre><code>" + "\n".join(fence) + "</code></pre>")
            continue
        if not line.strip():
            index += 1
            continue
        if line.startswith("|"):
            table = []
            while index < len(lines) and lines[index].startswith("|"):
                table.append(lines[index])
                index += 1
            blocks.append(_table_html(table))
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{_inline_md(heading.group(2).strip())}</h{level}>")
            index += 1
            continue
        if re.match(r"^[-*]\s+", line) or re.match(r"^\d+\.\s+", line):
            ordered = bool(re.match(r"^\d+\.\s+", line))
            tag = "ol" if ordered else "ul"
            items = []
            pattern = r"^\d+\.\s+(.*)$" if ordered else r"^[-*]\s+(.*)$"
            while index < len(lines) and re.match(pattern, lines[index]):
                items.append("<li>" + _inline_md(re.match(pattern, lines[index]).group(1)) + "</li>")
                index += 1
            blocks.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        if re.match(r"^---+$", line.strip()):
            blocks.append("<hr>")
            index += 1
            continue
        para = [line.strip()]
        index += 1
        while index < len(lines) and lines[index].strip() and not lines[index].startswith(("```", "|", "#", "- ", "* ")) and not re.match(r"^\d+\.\s+", lines[index]) and not re.match(r"^---+$", lines[index].strip()):
            para.append(lines[index].strip())
            index += 1
        blocks.append("<p>" + _inline_md(" ".join(para)) + "</p>")
    return "\n".join(blocks)


def readme_tab():
    """The last report tab. HTML is rendered from README.md when the report is built."""
    try:
        text = README_PATH.read_text(encoding="utf-8")
    except OSError:
        text = ""
    return {
        "title": "README",
        "slug": "readme",
        "kind": "readme",
        "saved_slug": "",
        "scraped_at": "",
        "warnings": [],
        "rows": [],
        "html": markdown_to_html(text),
        "url": "",
        "bat": [],
        "autotrader_url": "",
    }


def _tab_dict(rows, meta):
    meta = dict(meta or {})
    slug = meta.get("slug") or "sr22"
    return {
        "title": meta.get("title") or slug,
        "slug": slug,
        "saved_slug": slug,
        "scraped_at": meta.get("scraped_at") or "",
        "warnings": list(meta.get("warnings") or []),
        "rows": client_rows(rows),
        "url": "",
        "bat": [],
        "autotrader_url": "",
    }


def render_tabs(tab_pairs, output, fresh_days=2, search_api="http://127.0.0.1:8766"):
    """Write the report. Each pair is (csv rows, meta dict) and becomes one tab."""
    tabs = [_tab_dict(rows, meta) for rows, meta in tab_pairs]
    tabs.append(readme_tab())
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    page_title = "Aircraft for sale" if len(tabs) > 1 else (tabs[0]["title"] + " for sale")
    fresh = float(fresh_days)
    fresh_js = str(int(fresh)) if fresh.is_integer() else str(fresh)
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    stamps = [tab["scraped_at"] for tab in tabs if tab.get("scraped_at")]
    # ISO timestamps sort chronologically. The header uses the oldest, like the car report.
    as_of = format_as_of(min(stamps)) if stamps else ""
    data_as_of = ("Data as of " + as_of + " · ") if as_of else ""
    html = (
        template
        .replace("__PAGE_TITLE__", page_title)
        .replace("__DATA_AS_OF__", data_as_of)
        .replace("__GENERATED_AT__", generated_at)
        .replace("__NOW_MS__", str(int(datetime.now(timezone.utc).timestamp() * 1000)))
        .replace("__FRESH_DAYS__", fresh_js)
        .replace("__SEARCH_API__", js_json(search_api or None))
        .replace("__DEFAULT_ZIP__", js_json(""))
        .replace("__TABS_JSON__", js_json(tabs))
    )
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    count = sum(len(tab["rows"]) for tab in tabs)
    print(f"[done] wrote {output} ({len(tabs)} tabs, {count} airplanes)", file=sys.stderr)
    return output


def build_report(rows, meta, output, fresh_days=2, search_api="http://127.0.0.1:8766"):
    return render_tabs([(rows, meta)], output, fresh_days=fresh_days, search_api=search_api)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", default=str(DEFAULT_REPORT))
    parser.add_argument("--fresh-days", default=None)
    parser.add_argument("--search-api", default="http://127.0.0.1:8766")
    parser.add_argument("--root", default="")
    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else None
    pairs = []
    from refresh_searches import SEARCHES
    for search in SEARCHES:
        slug, title = search["slug"], search["title"]
        merged = source_path(slug, "merged", root)
        if not merged.exists():
            continue
        meta = load_meta(slug, root) or {"slug": slug, "title": title}
        meta.setdefault("slug", slug)
        meta.setdefault("title", title)
        pairs.append((read_csv(merged), meta))
    if not pairs:
        print("no saved listings — run refresh_searches.py first", file=sys.stderr)
        return 1
    render_tabs(
        pairs,
        args.output,
        fresh_days=resolve_fresh_days(args.fresh_days, root),
        search_api=args.search_api,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
