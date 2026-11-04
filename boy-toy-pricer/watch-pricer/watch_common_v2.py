#!/usr/bin/env python3
"""Shared helpers for the Patek 5711 scanner (v2 style).

Every source scraper writes rows with FIELDS. The reference parser turns the
many ways sites write a 5711 reference (5711/1A-010, 57111A010, 5711A,
5711 1A 010) into one canonical reference and a variant bucket.
"""
import re
import time

FIELDS = [
    "listing_id", "site_code", "title", "reference", "variant", "dial", "year",
    "box_papers", "condition", "price", "currency", "status", "seller", "location",
    "link", "image_url", "serial", "scraped_at", "sources",
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")


class ScrapeError(Exception):
    """A source failed or is blocked. The refresh keeps that source's last file."""


# Canonical variant buckets, in report order. Key: canonical reference prefix.
VARIANTS = [
    ("5711/1A-010", "5711/1A-010 steel, blue dial", "Blue"),
    ("5711/1A-001", "5711/1A-001 steel, blue dial (early)", "Blue"),
    ("5711/1A-011", "5711/1A-011 steel, white dial", "White"),
    ("5711/1A-014", "5711/1A-014 steel, olive green dial", "Olive green"),
    ("5711/1A-018", "5711/1A-018 Tiffany blue dial", "Tiffany blue"),
    ("5711/1A", "5711/1A steel, suffix not given", ""),
    ("5711/1300A", "5711/1300A steel, diamond bezel", "Blue"),
    ("5711/1R", "5711/1R-001 rose gold bracelet", "Brown"),
    ("5711R", "5711R-001 rose gold strap", "Brown"),
    ("5711G", "5711G white gold", ""),
    ("5711J", "5711J yellow gold", ""),
    ("5711/1P", "5711/1P 40th anniversary platinum", "Blue"),
    ("5711/112P", "5711/112P platinum", "Blue"),
    ("5711/110P", "5711/110P platinum, baguette bezel", ""),
    ("5711/113P", "5711/113P platinum, emerald bezel", "Black"),
    ("5711", "5711 other / unclear", ""),
]
VARIANT_ORDER = [v[1] for v in VARIANTS]

# 5711 followed by an optional case code and optional -0xx suffix.
REF_RE = re.compile(
    r"\b5711\s*[/\-\s]?\s*(1300A|113G|113P|112P|110P|1P|1A|1R|1J|R|G|J|A|P)?\s*[-\s]?\s*(0\d\d)?(?!\d)",
    re.I,
)
COMPACT_RE = re.compile(r"\b5711(1300A|113P|112P|110P|1P|1A|1R)(0\d\d)\b", re.I)
YEAR_RE = re.compile(r"\b(19[89]\d|20[0-2]\d)\b")
PRICE_RE = re.compile(r"(\d[\d,]*(?:\.\d\d)?)")


def _refs_in(text):
    found = []
    for m in list(COMPACT_RE.finditer(text)) + list(REF_RE.finditer(text)):
        case, suffix = (m.group(1) or "").upper(), m.group(2) or ""
        if case == "A":
            case = "1A"  # SWE writes 5711A for 5711/1A
        if case in ("1J", "113G"):
            case = case[-1]
        if not case:
            ref = "5711"
        elif case in ("R", "G", "J"):
            ref = f"5711{case}"
        else:
            ref = f"5711/{case}"
        if suffix:
            ref = f"{ref}-{suffix}"
        found.append(ref)
    return found


def parse_reference(*texts):
    """Canonical 5711 reference, or ''.

    The first text that names a 5711 wins (callers pass the most reliable field
    first). A later text can only add detail to it: 5711/1A can become
    5711/1A-010, but 5711G never becomes 5711/1A-001.
    """
    best = ""
    for text in texts:
        for ref in _refs_in(str(text or "")):
            if not best or (ref.startswith(best) and len(ref) > len(best)):
                best = ref
    return best


def variant_for(reference, text=""):
    ref = reference or ""
    low = str(text or "").lower()
    if ref in ("5711/1A", "5711") or ref.startswith("5711/1A") and ref not in [v[0] for v in VARIANTS[:5]]:
        # Suffix missing: guess from dial words only when unambiguous.
        if "tiffany" in low:
            return VARIANTS[4][1]
        if "olive" in low or "green" in low:
            return VARIANTS[3][1]
        if "white" in low and "white gold" not in low:
            return VARIANTS[2][1]
    if ref == "5711":
        if "rose gold" in low or "pink gold" in low:
            return VARIANTS[7][1] if "bracelet" in low else VARIANTS[8][1]
        if "white gold" in low:
            return VARIANTS[9][1]
        if "yellow gold" in low:
            return VARIANTS[10][1]
        if "steel" in low:
            return VARIANTS[5][1]
    for prefix, name, _dial in VARIANTS:
        if ref == prefix or ref.startswith(prefix + "-") or (prefix == "5711" and ref.startswith("5711")):
            return name
        if ref.startswith(prefix) and prefix not in ("5711", "5711/1A"):
            return name
    if ref.startswith("5711/1A"):
        return VARIANTS[5][1]
    return VARIANTS[-1][1] if ref else ""


DIAL_WORDS = [
    ("tiffany", "Tiffany blue"), ("olive", "Olive green"), ("green", "Olive green"),
    ("blue", "Blue"), ("white dial", "White"), ("silver", "White"), ("black", "Black"),
    ("brown", "Brown"), ("chocolate", "Brown"), ("grey", "Grey"), ("gray", "Grey"),
    ("slate", "Grey"), ("charcoal", "Grey"),
]


def dial_for(reference, *texts):
    for prefix, _name, dial in VARIANTS:
        if dial and reference and (reference == prefix or reference.startswith(prefix + "-") or
                                   (prefix not in ("5711", "5711/1A") and reference.startswith(prefix))):
            return dial
    low = " ".join(str(t or "") for t in texts).lower().replace("white gold", "")
    for word, dial in DIAL_WORDS:
        if word in low:
            return dial
    return ""


def year_from(*texts):
    for text in texts:
        m = YEAR_RE.search(str(text or ""))
        if m:
            return m.group(1)
    return ""


def box_papers_from(text):
    low = str(text or "").lower()
    box = any(k in low for k in ("box & papers", "box and papers", "box/papers", "b&p", "box papers",
                                  "original box", "with box", "full set", "fullset", "full kit"))
    papers = any(k in low for k in ("papers", "certificate", "warranty card", "b&p", "full set", "fullset"))
    no_papers = any(k in low for k in ("no papers", "without papers", "watch only", "watch-only",
                                        "box and papers are not", "no box"))
    if no_papers and not ("original box, original papers" in low):
        if "box" in low and "no box" not in low and "watch only" not in low and "not part" not in low:
            return "Box only"
        return "Watch only"
    if box and papers:
        return "Box & papers"
    if papers:
        return "Papers"
    if box:
        return "Box"
    return ""


def price_int(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(round(value))
    m = PRICE_RE.search(str(value).replace("$", ""))
    if not m:
        return None
    try:
        return int(round(float(m.group(1).replace(",", ""))))
    except ValueError:
        return None


AUCTION_HOUSES = ("christie", "phillips", "sotheby", "bonhams", "antiquorum", "monaco legend", "heritage auctions")


MIN_WATCH_PRICE = 5000  # below this it is a strap, buckle or other part, not a watch


def keep_row(row):
    """Asking rows always; sold or out-of-stock rows only when they carry a price.
    Rows priced under MIN_WATCH_PRICE are parts and are dropped."""
    p = price_int(row.get("price"))
    if p is not None and p < MIN_WATCH_PRICE:
        return False
    return row.get("status", "For sale") in ("For sale", "Auction live", "Buy-now (auction ended unsold)") or bool(row.get("price"))


def is_5711(*texts):
    return bool(parse_reference(*texts))


def finish_row(row, when):
    """Fill reference, variant and dial from the row text."""
    text = " ".join(str(row.get(k) or "") for k in ("title", "reference", "description"))
    ref = parse_reference(row.get("reference"), row.get("title"), row.get("description"))
    row["reference"] = ref
    row["variant"] = variant_for(ref, text)
    if not row.get("dial"):
        row["dial"] = dial_for(ref, text)
    if not row.get("year"):
        row["year"] = ""
    if not row.get("box_papers"):
        row["box_papers"] = box_papers_from(text)
    p = price_int(row.get("price"))
    row["price"] = str(p) if p else ""
    row.setdefault("currency", "USD")
    row["scraped_at"] = when
    row.pop("description", None)
    return row


def session():
    from curl_cffi import requests as creq
    return creq.Session(impersonate="chrome")


def get(sess, url, *, tries=2, pause=1.0, ok=(200,)):
    last = None
    for attempt in range(tries):
        try:
            resp = sess.get(url, timeout=40)
        except Exception as exc:  # network errors
            last = f"{type(exc).__name__}: {str(exc)[:120]}"
        else:
            if resp.status_code in ok:
                return resp
            last = f"HTTP {resp.status_code}"
            if resp.status_code in (401, 403, 429):
                break
        time.sleep(pause * (attempt + 1))
    raise ScrapeError(f"{url} -> {last}")
