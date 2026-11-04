#!/usr/bin/env python3
"""What each saved search tracks: how to search each site, which listings
count, and how a listing is bucketed into a variant.

Two models:
  "5711"     Patek Philippe Nautilus 5711, every variant (watch_common_v2).
  "aquanaut" Patek Philippe Aquanaut with a blue or green dial, grouped by
             reference family + dial (5168G white gold - Blue, ...).

The scrapers take a Model and call model.match(...) to keep a listing and
model.finish(row, when) to fill reference/variant/dial; finish returns None
for a listing outside the model (for the Aquanaut: a black or brown dial).
"""
import re

import watch_common_v2 as wc


class Model:
    key = ""
    noun = ""             # "5711s", used in notes like "listed no 5711s"
    term = ""             # plain search term for dealer sites
    chrono24_urls = []    # page templates with {page}

    def match(self, *texts):
        raise NotImplementedError

    def finish(self, row, when):
        raise NotImplementedError

    def variant_key(self, variant):
        return (99, variant)


class Nautilus5711(Model):
    key = "5711"
    noun = "5711s"
    term = "5711"
    chrono24_urls = [("https://www.chrono24.com/search/index.htm?query=patek+philippe+5711"
                      "&dosearch=true&pageSize=120&showpage={page}", "")]

    def match(self, *texts):
        return wc.is_5711(*texts)

    def finish(self, row, when):
        return wc.finish_row(row, when)

    def variant_key(self, variant):
        order = wc.VARIANT_ORDER
        return (order.index(variant), variant) if variant in order else (99, variant)


# ------------------------------------------------------------------ Aquanaut

AQ_BASES = ("5060", "5062", "5064", "5065", "5165", "5066", "5067", "5068", "5069", "5072", "5087",
            "5088", "5089", "5164", "5167", "5168", "5260", "5261", "5267", "5268", "5269",
            "5650", "5968", "4960", "4961", "5061", "7968", "4968")
AQ_RE = re.compile(r"\b(" + "|".join(AQ_BASES) + r")\s*(?:/\s*(\d{1,3}))?\s*([AGRJT])\s*[-\s]?\s*(0\d\d)?(?![\dA-Z])", re.I)

CASE_WORD = {"A": "steel", "G": "white gold", "R": "rose gold", "J": "yellow gold", "T": "titanium"}
FAMILY_NAMES = {
    "5167A": "5167A steel, strap",
    "5167/1A": "5167/1A steel, bracelet",
    "5167R": "5167R rose gold",
    "5168G": "5168G white gold 42 mm",
    "5968A": "5968A steel chronograph",
    "5968G": "5968G white gold chronograph",
    "5968R": "5968R rose gold chronograph",
    "5164A": "5164A steel Travel Time",
    "5164G": "5164G white gold Travel Time",
    "5164R": "5164R rose gold Travel Time",
    "5267/200A": "5267/200A Luce chronograph, steel",
    "5261R": "5261R Luce annual calendar, rose gold",
    "5269R": "5269R Luce, rose gold",
    "5269/200R": "5269/200R Luce, rose gold, diamonds",
    "5268/200R": "5268/200R Luce, rose gold, diamonds",
    "5268/461G": "5268/461G Luce, white gold, diamonds",
    "5067A": "5067A Luce, steel, diamonds",
    "5068R": "5068R Luce, rose gold",
    "5650G": "5650G Advanced Research",
    "5066A": "5066A steel (vintage, 36 mm)",
    "5065A": "5065A steel (vintage, 38 mm)",
    "5060A": "5060A steel (vintage)",
    "4960A": "4960A steel, ladies",
    "7968/300R": "7968/300R Luce chronograph, rose gold, diamonds",
    "5065/1A": "5065/1A steel, bracelet (vintage)",
}
# Dial by full reference, from Patek's numbering and checked against what the
# Chrono24 detail pages say (see README). The reference wins over a seller's
# dial wording when both are present.
SUFFIX_DIAL = {
    "5168G-001": "Blue", "5168G-010": "Green",
    "5968G-001": "Blue", "5968G-010": "Green",
    "5164G-001": "Blue",
    "5267/200A-011": "Green",
    "5167A-001": "Black", "5167/1A-001": "Black", "5167R-001": "Brown",
    "5968A-001": "Black", "5164A-001": "Black", "5164R-001": "Brown",
    "5261R-001": "Blue", "5269R-001": "Blue", "5650G-001": "Blue",
    "5268/461G-001": "Blue", "5067A-014": "Blue", "5067A-017": "Blue", "5067A-022": "Blue",
}
BLUE_WORDS = ("blue", "navy", "azure")
GREEN_WORDS = ("green", "khaki", "olive")


def aq_refs(text):
    out = []
    for m in AQ_RE.finditer(str(text or "")):
        base, mid, case, suffix = m.group(1), m.group(2), m.group(3).upper(), m.group(4)
        fam = f"{base}/{mid}{case}" if mid else f"{base}{case}"
        out.append(f"{fam}-{suffix}" if suffix else fam)
    return out


def aq_reference(*texts):
    """First text naming an Aquanaut reference wins; later texts may add the suffix."""
    best = ""
    for text in texts:
        for ref in aq_refs(text):
            if not best or (ref.startswith(best) and len(ref) > len(best)):
                best = ref
    return best


def family_of(ref):
    return ref.split("-")[0] if ref else ""


def dial_word(text):
    low = str(text or "").lower()
    low = re.sub(r"blue (?:hands|lume|luminescent|accents?|seconds)", "", low)
    g = any(w in low for w in GREEN_WORDS)
    b = any(w in low for w in BLUE_WORDS)
    if g and not b:
        return "Green"
    if b and not g:
        return "Blue"
    return ""


class AquanautBlueGreen(Model):
    key = "aquanaut"
    noun = "blue or green Aquanauts"
    term = "aquanaut"
    # Chrono24's own dial-colour pages for the Aquanaut model.
    chrono24_urls = [
        ("https://www.chrono24.com/patekphilippe/aquanaut-blue--mod92-dc710.htm?pageSize=120&showpage={page}", "Blue"),
        ("https://www.chrono24.com/patekphilippe/aquanaut-green--mod92-dc716.htm?pageSize=120&showpage={page}", "Green"),
    ]

    def match(self, *texts):
        joined = " ".join(str(t or "") for t in texts)
        return bool(aq_reference(joined)) or "aquanaut" in joined.lower()

    def finish(self, row, when):
        title = str(row.get("title") or "")
        desc = str(row.get("description") or "")
        ref = aq_reference(row.get("reference"), title, desc)
        joined = " ".join([title, str(row.get("reference") or ""), desc]).lower()
        if not ref and "aquanaut" not in joined:
            return None
        if "nautilus" in joined and "aquanaut" not in joined and not ref:
            return None
        dial = SUFFIX_DIAL.get(ref, "")
        if not dial:
            dial = dial_word(row.get("dial")) or dial_word(title) or row.get("dial_hint", "")
        if dial not in ("Blue", "Green"):
            return None
        fam = family_of(ref)
        name = FAMILY_NAMES.get(fam) or (f"{fam} {CASE_WORD.get(fam[-1:], '')}".strip() if fam else
                                         "Aquanaut, reference not given")
        row["reference"] = ref or "Aquanaut (ref. not given)"
        row["dial"] = dial
        row["variant"] = f"{name} · {dial}"
        if not row.get("box_papers"):
            row["box_papers"] = wc.box_papers_from(" ".join([title, desc]))
        p = wc.price_int(row.get("price"))
        row["price"] = str(p) if p else ""
        row.setdefault("currency", "USD")
        row["scraped_at"] = when
        row.pop("description", None)
        row.pop("dial_hint", None)
        return row

    def variant_key(self, variant):
        fam = variant.split(" ")[0]
        return (1 if fam.startswith("Aquanaut") else 0, fam, variant)


MODELS = {"5711": Nautilus5711(), "aquanaut": AquanautBlueGreen()}
