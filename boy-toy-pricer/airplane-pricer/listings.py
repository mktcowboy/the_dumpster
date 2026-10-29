#!/usr/bin/env python3
"""Listing fields and text extraction for the SR22 scanner.

Numbers and options are copied only when a listing states them. A blank
field means the listing did not say, not that the value is zero or absent.
"""
import re

FIELDS = [
    "listing_id",
    "source",
    "title",
    "price",
    "year",
    "model",
    "generation",
    "variant",
    "gear",
    "family",
    "turbo",
    "n_number",
    "serial_number",
    "ttaf",
    "engine_make",
    "engine_model",
    "engine_hours",
    "engine_time_type",
    "engine_tbo",
    "prop_time",
    "landings",
    "engine_cycles",
    "jet_support",
    "avionics",
    "fiki",
    "tks",
    "air_conditioning",
    "taws",
    "adsb",
    "autopilot",
    "caps_repack",
    "interior",
    "exterior",
    "city",
    "state",
    "airport",
    "location",
    "seller",
    "posted_date",
    "days_on_market",
    "price_drop",
    "price_note",
    "description",
    "link",
    "image_url",
    "is_new",
    "prior_price",
    "observed_drop",
    "sources",
]

US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME",
    "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
STATE_ABBREV = set(US_STATES.values())

# Longest phrase first so "Perspective+" is not also stored as "Perspective".
AVIONICS_PHRASES = [
    "Cirrus Perspective Touch+",
    "Cirrus Perspective Touch",
    "Perspective Touch+",
    "Perspective Touch",
    "Cirrus Perspective+",
    "Cirrus Perspective",
    "Perspective+",
    "Garmin G1000 NXi",
    "Garmin G1000",
    "Garmin GTN 750",
    "Garmin GTN 650",
    "Garmin G500 TXi",
    "Garmin G500",
    "Garmin G5",
    "Avidyne Entegra",
    "Avidyne",
    "Garmin GTN",
    "GTN 750",
    "GTN 650",
    "GNS 530W",
    "GNS 530",
    "GNS 430",
    "Aspen Evolution",
    "Aspen",
    "IFD440",
    "IFD550",
    "Perspective",
]
GEN_RE = re.compile(r"\bG\s*([1-7])(?![A-Za-z0-9])(\s*\+|\s*plus)?", re.I)
GEN_WORD_RE = re.compile(r"\bgeneration\s*([1-7])(?![A-Za-z0-9])(\s*\+|\s*plus)?", re.I)
YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
LABELED_REG_RE = re.compile(
    r"(?:registration(?:\s*(?:number|#|no\.?))?|reg\.?\s*#|\bRN)\s*[:#]?\s*([A-Z0-9-]{3,10})",
    re.I,
)
BARE_N_RE = re.compile(r"\b(N[0-9][A-Z0-9]{0,6})\b", re.I)
SERIAL_RE = re.compile(
    r"(?:serial(?:\s*number)?|s\s*/\s*n|\bs/?n\b|c\s*/\s*n)\s*[:#]?\s*([0-9]{3,5})\b",
    re.I,
)
TT_RE = re.compile(
    r"(?:total\s*time|ttaf|aftt|ttsn|actt|airframe(?:\s*time)?)\s*[:#]?\s*([0-9][0-9,]*(?:\.\d+)?)",
    re.I,
)
TT_TAIL_RE = re.compile(
    r"\b([0-9][0-9,]*(?:\.\d+)?)\s*(?:hrs?|hours)?\s*(?:TT|TTSN|TTAF|ACTT)\b",
    re.I,
)
ENGINE_TIME_RE = re.compile(
    r"engine(?:\s*\d)?(?:\s*time)?\s*[:#]?\s*([0-9][0-9,]*(?:\.\d+)?)\s*(SNEW|SMOH|TSOH|SPOH|TSN|TTSN)?",
    re.I,
)
ENGINE_TYPE_RE = re.compile(
    r"\b([0-9][0-9,]*(?:\.\d+)?)\s*(SNEW|SMOH|TSOH|SPOH)\b",
    re.I,
)
ENGINE_TYPE_FIRST_RE = re.compile(
    r"\b(SNEW|SMOH|TSOH|SPOH)\s*[:#]\s*([0-9][0-9,]*(?:\.\d+)?)",
    re.I,
)
ENGINE_MAKE_RE = re.compile(
    r"\b(Continental|Lycoming)\b(?:\s+((?:TSIO|TSIOF|IO|IOF|O)-?\d{3}[A-Z0-9-]*))?",
    re.I,
)
TBO_RE = re.compile(
    r"\bTBO\b\s*(?:at|of|is|:)?\s*([0-9][0-9,]{2,})|\b([0-9][0-9,]{2,})\s*(?:hour|hr)?\s*TBO\b",
    re.I,
)
PROP_RE = re.compile(
    r"\bprops?(?:eller)?(?:\s+(?:time|tsn|tsoh|tsmoh|spoh|snew|smoh))?\s*[:#]?\s*([0-9][0-9,]*(?:\.\d+)?)",
    re.I,
)
LANDINGS_RE = re.compile(r"\b([0-9][0-9,]*)\s+landings\b", re.I)
CYCLES_RE = re.compile(
    r"\b(?:engine\s+)?cycles\s*[:#]?\s*([0-9][0-9,]*)|\b([0-9][0-9,]*)\s+(?:engine\s+)?cycles\b",
    re.I,
)
JET_SUPPORT_RE = re.compile(
    r"(?:cirrus\s+jet\s+support|\bcjs\b|jet\s+support)[^\n.]{0,50}?"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{1,2}/\d{4}|\d{4})",
    re.I,
)
CAPS_RE = re.compile(
    r"CAPS[^\n.]{0,60}?(?:due|repack)[^\n.]{0,40}?"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{1,2}/\d{4}|\d{4})",
    re.I,
)
POSTED_RE = re.compile(
    r"(?:posted|updated|listed|last\s+updated)\s*[:\-]?\s*"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
    r"|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})",
    re.I,
)
DOM_RE = re.compile(r"\b(\d{1,4})\s+days?\s+on\s+(?:the\s+)?market\b", re.I)
REDUCED_RE = re.compile(r"(?:reduced\s+to|price\s+reduced\s+to)\s*(\$[\d,]+)", re.I)
AIRPORT_RE = re.compile(
    r"(?:based(?:\s+at)?|airport|located\s+at)\s*(K[A-Z]{3})\b|\((K[A-Z]{3})\)",
    re.I,
)
INTERIOR_RE = re.compile(r"\bInterior\s*[:\-]\s*([^.\n]{3,80})", re.I)
EXTERIOR_RE = re.compile(r"\bExterior\s*[:\-]\s*([^.\n]{3,80})", re.I)


def blank_row():
    return {key: "" for key in FIELDS}


def us_n_number(token):
    """True for a US registration, using the FAA digit/letter length rules."""
    match = re.fullmatch(r"N([1-9]\d{0,4})([A-HJ-NP-Z]{0,2})", token or "")
    if not match:
        return False
    digits, letters = match.group(1), match.group(2)
    pairs = {1: 2, 2: 2, 3: 2, 4: 1, 5: 0}
    return len(letters) <= pairs.get(len(digits), -1)


def clean_registration(value):
    """A stated US N-number or a hyphenated foreign registration, else blank."""
    raw = re.sub(r"[^A-Za-z0-9-]", "", str(value or "")).upper()
    if us_n_number(raw):
        return raw
    prefix, _, suffix = raw.partition("-")
    if prefix in {"IO", "O", "TSIO", "IOF", "TSIOF", "LTSIO", "AEIO"}:
        return ""
    if re.fullmatch(r"[A-Z]{1,2}-[A-Z0-9]{2,5}", raw) and re.search(r"[A-Z]", suffix):
        return raw
    return ""


def price_number(value):
    """USD asking price as a float, or None when no USD figure is stated."""
    text = str(value or "").strip()
    if not text or re.search(r"[£€]|GBP|EUR|\bCAD\b|\bAUD\b", text, re.I):
        return None
    match = re.search(r"(?<!\d)([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,})(?:\.\d+)?", text.replace("$", ""))
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def format_usd(value):
    number = float(value)
    if number.is_integer():
        return f"${int(number):,}"
    return f"${number:,.2f}"


def number_text(value):
    match = re.search(r"[0-9][0-9,]*(?:\.\d+)?", str(value or ""))
    return match.group(0).replace(",", "") if match else ""


def _generation_hits(text):
    hits = []
    for pattern in (GEN_RE, GEN_WORD_RE):
        for match in pattern.finditer(text or ""):
            gen = "G" + match.group(1)
            if match.group(2):
                gen += "+"
            if gen not in hits:
                hits.append(gen)
    return hits


def generation_name(text):
    """Generation stated in a title or model string. Conflicts stay blank."""
    hits = _generation_hits(text)
    if not hits:
        return ""
    if len(hits) == 1:
        return hits[0]
    bases = {item.rstrip("+") for item in hits}
    if len(bases) == 1 and any(item.endswith("+") for item in hits):
        return next(item for item in hits if item.endswith("+"))
    return ""


def model_name(text):
    blob = text or ""
    has_jet = re.search(r"\bSF-?50\b|vision\s*jet", blob, re.I)
    has20 = re.search(r"\bSR20\b", blob, re.I)
    has22 = re.search(r"\bSR22", blob, re.I)
    if has_jet and (has20 or has22):
        return ""
    if has_jet:
        return "SF50"
    if has20 and has22:
        return ""
    if has20:
        return "SR20"
    if re.search(r"\bSR22\s*TN\b", text or "", re.I):
        return "SR22 TN"
    if re.search(r"\bSR22T\b", text or "", re.I):
        return "SR22T"
    if has22:
        return "SR22"
    return ""


def turbo_flag(text):
    blob = text or ""
    named = re.search(r"\bSR22T\b|\bSR22\s*TN\b", blob, re.I)
    negated = re.search(r"non[-\s]?turbo|normally aspirated|\bno turbo\b", blob, re.I)
    if named:
        return "yes"
    if negated:
        return ""
    if re.search(r"\bturbo\b", blob, re.I):
        return "yes"
    return ""


def variant_name(text):
    found = []
    if re.search(r"\bGTS\b", text or "", re.I):
        found.append("GTS")
    if re.search(r"\bXi\b", text or ""):
        found.append("Xi")
    if re.search(r"\bPremium\b", text or ""):
        found.append("Premium")
    if re.search(r"\barriv[eé]e\b", text or "", re.I):
        found.append("Arrivee")
    return " ".join(found)


# Marketing names and CubCrafters type-certificate codes. A bare "Cub" is not enough:
# Piper Super Cubs, J-3s, and other makers' cubs stay out.
_CUB_BRAND_RE = re.compile(r"cub\s*-?\s*crafters?", re.I)
_CUB_NAME_RE = re.compile(
    r"\bcarbon\s+cub\b|\btop\s+cub\b|\bnx-?\s*cub\b|\bx-?\s*cub\b|\bsport\s+cub\b",
    re.I,
)
_CUB_CODE_RE = re.compile(
    r"\b(?:CC11-160|CC11-100|CC18-180|CC19-180|CC19-215|"
    r"CCK-1865|CCK-2000|CCK-2300|CCX-1865|CCX-2000|CCX-2300)\b",
    re.I,
)
_OTHER_CUB_RE = re.compile(
    r"\bpiper\b|\bsuper\s+cub\b|\bpa-?18\b|\bj-?3\b|\bamerican\s+legend\b|"
    r"\blegend\s+cub\b|\baviat\b|\bhusky\b|\bmackey\b|\bcessna\b|\bkitfox\b",
    re.I,
)
_CUB_MODEL_ONLY = {
    "CC11-160", "CC11-100", "CC18-180", "CC19-180", "CC19-215",
    "CCK-1865", "CCK-2000", "CCK-2300", "CCX-1865", "CCX-2000", "CCX-2300",
}


def _cub_product(text):
    return bool(_CUB_NAME_RE.search(text or "") or _CUB_CODE_RE.search(text or ""))


def is_cubcrafters(identity, description=""):
    """True when the title, make, or model is a CubCrafters airplane.

    Piper Super Cubs and other makers stay out, including Piper airframes that
    a CubCrafters dealer happens to be advertising. A description can identify
    the airplane when the title itself does not name another maker.
    """
    identity = identity or ""
    description = description or ""
    piper_airframe = re.search(r"\bpa-?18\b|\bsuper\s+cub\b|\bj-?3\b", identity, re.I)
    if _cub_product(identity) and not piper_airframe:
        return True
    if _CUB_BRAND_RE.search(identity) and not _OTHER_CUB_RE.search(identity):
        return True
    if _OTHER_CUB_RE.search(identity):
        return False
    return bool(_CUB_BRAND_RE.search(description) or _cub_product(description))


def _carbon_variant(text):
    if re.search(r"\bFX-?\s*3\b", text, re.I):
        return "FX-3"
    if re.search(r"\bFX-?\s*2\b", text, re.I):
        return "FX-2"
    if re.search(r"\bEX-?\s*3\b", text, re.I):
        return "EX-3"
    if re.search(r"\bEX-?\s*2\b", text, re.I):
        return "EX-2"
    if re.search(r"\bFX\b", text):
        return "FX"
    if re.search(r"\bEX\b", text):
        return "EX"
    if re.search(r"\bSS\b", text):
        return "SS"
    if re.search(r"\bUL\b", text):
        return "UL"
    return ""


def cub_model_variant(identity, description=""):
    """Stated CubCrafters line and subtype. A type code alone is not renamed."""
    if not is_cubcrafters(identity, description):
        return "", ""
    identity = identity or ""
    # A marketing name in the title wins. A bare type code can take the name
    # the description actually uses (CC19-215 described as an XCub).
    if _CUB_NAME_RE.search(identity) or re.search(r"\b(?:EX|FX)(?:-?\s*[23])?\b|\bSS\b|\bS2\b", identity or ""):
        text = identity
    else:
        text = f"{identity} {description or ''}"
    variant = ""
    if re.search(r"\bnx-?\s*cub\b", text, re.I):
        model = "NXCub"
    elif re.search(r"\bx-?\s*cub\b", text, re.I):
        model = "XCub"
    elif re.search(r"\btop\s+cub\b|\bcc18-180\b", text, re.I):
        model = "Top Cub"
        if re.search(r"\branger\b", text, re.I):
            variant = "Ranger"
    elif re.search(r"\branger\s+cub\b", text, re.I):
        model = "Ranger Cub"
    elif re.search(r"\bsport\s+cub\b", text, re.I):
        model = "Sport Cub"
        if re.search(r"\bS2\b", text):
            variant = "S2"
        elif re.search(r"\bSS\b", text):
            variant = "SS"
    elif re.search(r"\bcarbon\s+cub\b|\b(?:EX|FX)-?\s*[23]\b|\b(?:EX|FX|SS)\b", text, re.I):
        model = "Carbon Cub"
        variant = _carbon_variant(text)
    else:
        code = _CUB_CODE_RE.search(text)
        model = code.group(0).upper() if code else "CubCrafters"
        if model not in _CUB_MODEL_ONLY and model != "CubCrafters":
            model = "CubCrafters"
    if not variant and description:
        if model == "Sport Cub" and re.search(r"\bS2\b", description):
            variant = "S2"
        elif model == "Carbon Cub":
            variant = _carbon_variant(description)
        elif model == "Top Cub" and re.search(r"\branger\b", description, re.I):
            variant = "Ranger"
    return model, variant


# PA-28-180 and PA-28-181 only. Warrior, Arrow, Dakota, Cruiser, and the
# other Cherokee horsepowers stay out, including a 140 with a 180 hp engine.
_PA28_180_RE = re.compile(r"\bPA\s*-?\s*28\s*-?\s*180(?:\s*[A-G])?\b", re.I)
_PA28_181_RE = re.compile(r"\bPA\s*-?\s*28\s*-?\s*181(?:\s*[A-G])?\b", re.I)
_PA28_ARROW_RE = re.compile(r"\bPA\s*-?\s*28\s*R\b|\bArrow\b", re.I)
_PA28_OTHER_RE = re.compile(
    r"\bPA\s*-?\s*28\s*-?\s*(?:140|150|151|160|161|235|236)\b|"
    r"\bWarrior\b|\bDakota\b|\bCruiser\b|"
    r"\bCherokee\s+(?:140|150|160|235|236|Six)\b",
    re.I,
)
_PA28_NAME_RE = re.compile(
    r"\bArcher(?:\s+(?:LX|DX|III|II))?\b|"
    r"\bCherokee\s+Archer\b|"
    r"\bCher(?:okee)?\s+180(?:\s*[A-G])?\b|"
    r"\bCherokee\s+Challenger\b|"
    r"\bPilot\s+100i\b",
    re.I,
)


def _pa28_rejected(text):
    """Another PA-28, unless the same text also states a 180 or 181 type code."""
    text = text or ""
    coded = bool(_PA28_180_RE.search(text) or _PA28_181_RE.search(text))
    if _PA28_ARROW_RE.search(text) and not coded:
        return True
    if _PA28_OTHER_RE.search(text) and not coded:
        return True
    return False


def _pa28_accepted(text):
    if not text or _pa28_rejected(text):
        return False
    return bool(_PA28_180_RE.search(text) or _PA28_181_RE.search(text) or _PA28_NAME_RE.search(text))


def is_pa28_180_181(identity, description=""):
    """True when the title or model is a Cherokee 180 or Archer, any year.

    A parts ad that only mentions PA-28-181 in the body is not an airplane.
    `description` is accepted so callers can pass it; it does not by itself
    qualify a row.
    """
    del description
    identity = identity or ""
    if _pa28_rejected(identity):
        return False
    return _pa28_accepted(identity)


def pa28_model_variant(identity, description=""):
    """Stated 180/181 code and the marketing name. A 140 is not relabeled 180."""
    if not is_pa28_180_181(identity, description):
        return "", ""
    identity = identity or ""
    # Marketing names come from the title. A description that says "evolution of
    # the Cherokee 180" must not relabel an Archer. A stated PA-28-180/181 code
    # in the description still counts.
    code_text = identity
    if not (_PA28_180_RE.search(identity) or _PA28_181_RE.search(identity)):
        if not _pa28_rejected(description or ""):
            code_text = f"{identity} {description or ''}"
    text = identity
    has180 = bool(_PA28_180_RE.search(code_text))
    has181 = bool(_PA28_181_RE.search(code_text))
    code = ""
    if has181 and not has180:
        code = "PA-28-181"
    elif has180 and not has181:
        code = "PA-28-180"
    letter = ""
    letter_match = re.search(
        r"(?:PA\s*-?\s*28\s*-?\s*180|Cher(?:okee)?\s+180)\s*([A-G])\b",
        text,
        re.I,
    )
    if letter_match:
        letter = letter_match.group(1).upper()
    names = []
    if re.search(r"\bArcher\s+LX\b", text, re.I):
        names.append("Archer LX")
    elif re.search(r"\bArcher\s+DX\b", text, re.I):
        names.append("Archer DX")
    elif re.search(r"\bArcher\s+III\b", text, re.I):
        names.append("Archer III")
    elif re.search(r"\bArcher\s+II\b", text, re.I):
        names.append("Archer II")
    elif re.search(r"\bCherokee\s+Archer\b", text, re.I):
        names.append("Cherokee Archer")
    elif re.search(r"\bArcher\b", text, re.I):
        names.append("Archer")
    if re.search(r"\bPilot\s+100i\b", text, re.I):
        names.append("Pilot 100i")
    if re.search(r"\bCher(?:okee)?\s+180", text, re.I):
        names.append("Cherokee 180" + letter)
    if re.search(r"\bChallenger\b", text, re.I) and re.search(r"Cherokee|PA\s*-?\s*28|\b180\b", text, re.I):
        names.append("Challenger")
    if code:
        variant = " ".join(names)
        if letter and letter not in variant:
            variant = (variant + " " + letter).strip()
        return code, variant
    if names:
        return names[0], " ".join(names[1:])
    return "", ""


def gear_text(text):
    """Gear the listing states. Bushwheels stay Bushwheels; nothing is inferred."""
    found = []
    if re.search(r"\btundra(?:\s+tires?)?\b", text or "", re.I):
        found.append("Tundra tires")
    if re.search(r"\bbush\s*-?\s*wheels?\b", text or "", re.I):
        found.append("Bushwheels")
    if re.search(r"\bamphib(?:ian|ious)?\b", text or "", re.I):
        found.append("Amphibious")
    if re.search(r"\bfloats?\b", text or "", re.I):
        found.append("Floats")
    if re.search(r"\bskis\b|\bon skis\b", text or "", re.I):
        found.append("Skis")
    return "; ".join(found)


def split_location(text):
    """City and US state when the location string states them."""
    raw = re.sub(r"\s+", " ", str(text or "")).strip(" ,")
    if not raw:
        return "", "", ""
    match = re.fullmatch(r"([^,]+),\s*([A-Z]{2})", raw)
    if match and match.group(2) in STATE_ABBREV:
        return match.group(1).strip(), match.group(2), raw
    match = re.fullmatch(r"([^,]+),\s*([A-Za-z .]+)", raw)
    if match and match.group(2).strip().lower() in US_STATES:
        return match.group(1).strip(), US_STATES[match.group(2).strip().lower()], raw
    match = re.fullmatch(r"([A-Za-z .]+)\s*\((?:USA|United States|US)\)", raw)
    if match and match.group(1).strip().lower() in US_STATES:
        return "", US_STATES[match.group(1).strip().lower()], raw
    match = re.fullmatch(r"([A-Z]{2}),\s*(?:US|USA)", raw)
    if match and match.group(1) in STATE_ABBREV:
        return "", match.group(1), raw
    if raw.lower() in US_STATES:
        return "", US_STATES[raw.lower()], raw
    return "", "", raw


def _fill(row, key, value):
    if value and not str(row.get(key) or "").strip():
        row[key] = str(value).strip()


def _exact_number(match, text):
    """Skip a figure that the listing only bounds ('less than 100 TT')."""
    prefix = (text or "")[max(0, match.start() - 24):match.start()]
    if re.search(r"less than|more than|about|approx|under|over|~", prefix, re.I):
        return ""
    return number_text(match.group(1))


def _avionics(text):
    found = []
    low = text.lower()
    for phrase in AVIONICS_PHRASES:
        if phrase.lower() in low:
            found.append(phrase)
    kept = []
    for phrase in found:
        if any(phrase != other and phrase.lower() in other.lower() and other in found for other in found):
            continue
        kept.append(phrase)
    return "; ".join(kept)


def _autopilot(text):
    found = []
    low = text.lower().replace("gfc700", "gfc 700").replace("dfc90", "dfc 90").replace("dfc100", "dfc 100")
    for phrase in ("GFC 700", "DFC 100", "DFC 90", "S-TEC 55X", "S-TEC", "STEC 55"):
        if phrase.lower() in low and phrase not in found:
            if phrase == "S-TEC" and any(item.startswith("S-TEC") and item != "S-TEC" for item in found):
                continue
            found.append(phrase)
    if "S-TEC" in found and any(item.startswith("S-TEC ") for item in found):
        found = [item for item in found if item != "S-TEC"]
    return "; ".join(found)


def _one_registration(text):
    labeled = []
    for match in LABELED_REG_RE.finditer(text or ""):
        reg = clean_registration(match.group(1))
        if reg and reg not in labeled:
            labeled.append(reg)
    if len(labeled) == 1:
        return labeled[0]
    if len(labeled) > 1:
        return ""
    bare = []
    for match in BARE_N_RE.finditer(text or ""):
        # O-360-N4M is an engine suffix, not a registration.
        if match.start() > 0 and (text or "")[match.start() - 1] in "-/":
            continue
        reg = clean_registration(match.group(1).upper())
        if reg and reg not in bare:
            bare.append(reg)
    return bare[0] if len(bare) == 1 else ""


def enrich(row):
    """Fill still-blank spec fields from text the listing already contains."""
    text = " ".join(str(row.get(key) or "") for key in ("title", "description", "price_note"))
    _fill(row, "n_number", _one_registration(text))
    serial = SERIAL_RE.search(text)
    if serial:
        _fill(row, "serial_number", serial.group(1))
    total = TT_RE.search(text) or TT_TAIL_RE.search(text)
    if total:
        _fill(row, "ttaf", _exact_number(total, text))
    engine_time = ENGINE_TIME_RE.search(text)
    if engine_time:
        _fill(row, "engine_hours", number_text(engine_time.group(1)))
        if engine_time.group(2):
            _fill(row, "engine_time_type", engine_time.group(2).upper())
    elif not row.get("engine_hours"):
        typed = ENGINE_TYPE_RE.search(text)
        if typed and number_text(typed.group(1)) != (row.get("ttaf") or ""):
            _fill(row, "engine_hours", number_text(typed.group(1)))
            _fill(row, "engine_time_type", typed.group(2).upper())
        else:
            labeled = ENGINE_TYPE_FIRST_RE.search(text)
            if labeled:
                _fill(row, "engine_hours", number_text(labeled.group(2)))
                _fill(row, "engine_time_type", labeled.group(1).upper())
    make = ENGINE_MAKE_RE.search(text)
    if make:
        _fill(row, "engine_make", make.group(1).title())
        if make.group(2):
            _fill(row, "engine_model", make.group(2).upper())
    rotax = re.search(r"\bRotax\b(?:\s+(9\d{2}[A-Z0-9]*))?", text, re.I)
    if rotax:
        _fill(row, "engine_make", "Rotax")
        if rotax.group(1):
            _fill(row, "engine_model", rotax.group(1).upper())
    cc_engine = re.search(r"\bCC\s*(\d{3})\s*(i)?\b", text, re.I)
    if cc_engine:
        _fill(row, "engine_model", "CC" + cc_engine.group(1) + ("i" if cc_engine.group(2) else ""))
    if re.search(r"\bTitan\b", text, re.I):
        _fill(row, "engine_make", "Titan")
    yio = re.search(r"\b(YIO-\d{3}[A-Z0-9-]*)\b", text, re.I)
    if yio:
        _fill(row, "engine_model", yio.group(1).upper())
    cub_serial = re.search(
        r"(?:serial(?:\s*number)?|\bs\s*/\s*n|\bs/?n\b)\s*[:#]?\s*"
        r"(CC(?:X|K)?-?\d{2,4}-\d{2,5})\b",
        text,
        re.I,
    )
    if cub_serial and cub_serial.group(1).upper() not in _CUB_MODEL_ONLY:
        _fill(row, "serial_number", cub_serial.group(1).upper())
    _fill(row, "gear", gear_text(text))
    tbo = TBO_RE.search(text)
    if tbo:
        _fill(row, "engine_tbo", number_text(tbo.group(1) or tbo.group(2)))
    prop = PROP_RE.search(text)
    if prop:
        _fill(row, "prop_time", number_text(prop.group(1)))
    _fill(row, "avionics", _avionics(text))
    if re.search(r"no[-\s]?fiki|non[-\s]?fiki|without\s+fiki", text, re.I):
        _fill(row, "fiki", "no")
    elif re.search(r"\bFIKI\b|known\s+icing|flight\s+into\s+known\s+ice", text, re.I):
        _fill(row, "fiki", "yes")
    if re.search(r"\bTKS\b", text):
        _fill(row, "tks", "yes")
    if re.search(r"\bA/C\b|air[-\s]?conditioning|factory\s+air\b", text, re.I):
        _fill(row, "air_conditioning", "yes")
    if re.search(r"E-?\s*TAWS", text, re.I):
        _fill(row, "taws", "E-TAWS")
    elif re.search(r"\bTAWS\b", text):
        _fill(row, "taws", "TAWS")
    if re.search(r"ADS-?\s*B", text, re.I):
        if re.search(r"ADS-?\s*B[^\n.]{0,24}(in\s*(?:&|and|/)\s*out|in/out)", text, re.I) or (
            re.search(r"ADS-?\s*B\s*In", text, re.I) and re.search(r"ADS-?\s*B\s*Out", text, re.I)
        ):
            _fill(row, "adsb", "ADS-B In/Out")
        else:
            _fill(row, "adsb", "ADS-B")
    _fill(row, "autopilot", _autopilot(text))
    landings = LANDINGS_RE.search(text)
    if landings:
        _fill(row, "landings", number_text(landings.group(1)))
    cycles = CYCLES_RE.search(text)
    if cycles:
        _fill(row, "engine_cycles", number_text(cycles.group(1) or cycles.group(2)))
    support = JET_SUPPORT_RE.search(text)
    if support:
        _fill(row, "jet_support", re.sub(r"\s+", " ", support.group(1)).strip())
    caps = CAPS_RE.search(text)
    if caps:
        _fill(row, "caps_repack", re.sub(r"\s+", " ", caps.group(1)).strip())
    interior = INTERIOR_RE.search(text)
    if interior:
        _fill(row, "interior", interior.group(1).strip(" -"))
    exterior = EXTERIOR_RE.search(text)
    if exterior:
        _fill(row, "exterior", exterior.group(1).strip(" -"))
    posted = POSTED_RE.search(text)
    if posted:
        _fill(row, "posted_date", re.sub(r"\s+", " ", posted.group(1)).strip())
    days = DOM_RE.search(text)
    if days:
        _fill(row, "days_on_market", days.group(1))
    reduced = REDUCED_RE.search(text)
    if reduced:
        _fill(row, "price_drop", f"Reduced to {reduced.group(1)}")
    elif re.search(r"price\s+reduced|\bprice\s+drop\b", text, re.I):
        _fill(row, "price_drop", "Price reduced")
    airport = AIRPORT_RE.search(text)
    if airport:
        _fill(row, "airport", (airport.group(1) or airport.group(2) or "").upper())
    if not row.get("state"):
        city, state, _location = split_location(row.get("location") or "")
        _fill(row, "city", city)
        _fill(row, "state", state)
    year = YEAR_RE.search(row.get("title") or "")
    if year:
        _fill(row, "year", year.group(1))
    return row


def clean_image(url):
    text = str(url or "").strip()
    low = text.lower()
    if not text:
        return ""
    if any(token in low for token in ("image-coming-soon", "placeholder", "no-image", "noimage", "/logo")):
        return ""
    return text


def apply_listing(row):
    """Normalize one scraped listing. Does not invent missing specs."""
    item = blank_row()
    item.update({key: "" if row.get(key) is None else str(row.get(key)) for key in FIELDS})
    stated = " ".join(item.get(key) or "" for key in ("title", "model", "generation", "variant"))
    description = item.get("description") or ""
    model = model_name(stated)
    generation = generation_name(stated)
    item["generation"] = generation
    item["turbo"] = turbo_flag(stated)
    variant = variant_name(stated)
    if model == "SR20":
        item["model"] = model
        item["variant"] = variant
        item["family"] = "sr20"
    elif model in {"SR22", "SR22T", "SR22 TN"}:
        item["model"] = model
        item["variant"] = variant
        item["family"] = "sr22"
    elif model == "SF50":
        item["model"] = model
        item["variant"] = variant
        item["family"] = "sf50"
    elif is_cubcrafters(stated, description):
        cub_model, cub_variant = cub_model_variant(stated, description)
        item["model"] = cub_model
        item["variant"] = " ".join(part for part in (variant, cub_variant) if part)
        item["family"] = "cubcrafters"
        item["turbo"] = turbo_flag(stated + " " + description)
    elif is_pa28_180_181(stated, description):
        pa_model, pa_variant = pa28_model_variant(stated, description)
        item["model"] = pa_model
        item["variant"] = " ".join(part for part in (variant, pa_variant) if part)
        item["family"] = "pa28-180-181"
        # Garmin G5 / G500 are avionics. This airframe has no G1–G7 generation.
        item["generation"] = ""
        item["turbo"] = turbo_flag(stated)
    else:
        item["model"] = ""
        item["variant"] = variant
        item["family"] = ""
    item["n_number"] = clean_registration(item.get("n_number"))
    item["image_url"] = clean_image(item.get("image_url"))
    enrich(item)
    item["n_number"] = clean_registration(item.get("n_number"))
    amount = price_number(item.get("price"))
    if amount is not None:
        item["price"] = format_usd(amount)
    elif item.get("price") and not re.search(r"\d", item["price"]):
        item["price"] = ""
    for key in ("ttaf", "engine_hours", "engine_tbo", "prop_time", "landings", "engine_cycles"):
        if item.get(key):
            item[key] = number_text(item[key])
    item["description"] = re.sub(r"\s+", " ", item.get("description") or "").strip()
    return item


def serial_key(value):
    digits = re.sub(r"\D", "", str(value or ""))
    stripped = digits.lstrip("0")
    if len(stripped) < 3:
        return ""
    return stripped


def row_key(row):
    registration = clean_registration(row.get("n_number"))
    if registration:
        return "n:" + registration
    serial = serial_key(row.get("serial_number"))
    if serial:
        return "s:" + serial
    listing = str(row.get("listing_id") or "").strip()
    return "id:" + listing if listing else ""
