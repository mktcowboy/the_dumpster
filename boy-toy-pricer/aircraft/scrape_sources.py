#!/usr/bin/env python3
"""Per-source listing scrapers for SR22, Vision Jet, and CubCrafters.

HTML sources (GlobalAir, AircraftDealer, Barnstormers, CubCrafters inventory,
and the sites that block automation) load in Playwright via fetch.html. Cirrus
and ASO expose JSON listings; those are read with fetch.json.
"""
import html as html_lib
import re
import sys
from urllib.parse import quote, urljoin

from fetch import ScrapeError
from listings import apply_listing, blank_row, is_cubcrafters, is_pa28_180_181, number_text, price_number

DEFAULT_FAMILIES = ("sr22", "sr20")
CIRRUS_MODELS = {
    "sr22": (13, 10, 49),  # SR22, SR22T, SR22 TN
    "sr20": (17,),
    "sf50": (186,),  # Vision Jet
}
ASO_MODELS = {
    "sr22": ("1510", "1511", "1512", "22492", "22494", "22496", "22491", "22493", "22495", "22497"),
    "sr20": ("1507", "1508", "1509"),
    "sf50": ("21856",),  # Vision SF50
}
DEALER_CATEGORIES = {
    "sr22": "https://www.aircraftdealer.com/aircraft_for_sale/Cirrus_SR22/101/page-{page}.htm",
    "sr20": "https://www.aircraftdealer.com/aircraft_for_sale/Cirrus_SR20/889/page-{page}.htm",
    "sf50": "https://www.aircraftdealer.com/aircraft_for_sale/Cirrus_Vision_/776/page-{page}.htm",
    "cubcrafters": "https://www.aircraftdealer.com/aircraft_for_sale/Cubcrafters_/640/page-{page}.htm",
    "pa28-180-181": (
        "https://www.aircraftdealer.com/aircraft_for_sale/Piper_Archer/1729/page-{page}.htm",
        "https://www.aircraftdealer.com/aircraft_for_sale/Piper_Cherokee_180/1829/page-{page}.htm",
    ),
}
BARN_MODELS = {
    "sr22": ("SR22", "SR22T"),
    "sr20": ("SR20",),
    "sf50": ("SF50", "Vision"),
}
BARN_CUB_URLS = (
    "https://www.barnstormers.com/cat_search.php?mfg=CubCrafters&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?mfg=Cub+Crafters&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?mfg=CubCrafter&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?model=Carbon+Cub&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?model=XCub&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?model=NXCub&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?model=Top+Cub&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?model=Sport+Cub&search_type=advanced",
)
ASO_CUB_QUERIES = (
    "CubCrafters",
    "Cub Crafters",
    "Carbon Cub",
    "XCub",
    "NXCub",
    "Top Cub",
    "Sport Cub",
)
DEALER_CUB_QUERIES = ("CubCrafters", "Carbon Cub", "XCub", "NXCub", "Top Cub", "Sport Cub")
GLOBALAIR_PAGES = {
    "cirrus": "https://www.globalair.com/aircraft-for-sale/cirrus-aircraft",
    "cubcrafters": "https://www.globalair.com/aircraft-for-sale/cubcrafters",
    "pa28-180-181": "https://www.globalair.com/aircraft-for-sale/piper",
}
ASO_PA28_QUERIES = (
    "PA-28-181",
    "PA-28-180",
    "PA28-181",
    "PA28-180",
    "Piper Archer",
    "Archer II",
    "Archer III",
    "Archer DX",
    "Archer LX",
    "Cherokee 180",
    "Cherokee Archer",
    "Cherokee Challenger",
    "Pilot 100i",
)
DEALER_PA28_QUERIES = (
    "Piper Archer",
    "Archer II",
    "Archer III",
    "Archer LX",
    "Archer DX",
    "Cherokee 180",
    "PA-28-181",
    "PA-28-180",
    "Cherokee Archer",
    "Cherokee Challenger",
)
BARN_PA28_URLS = (
    "https://www.barnstormers.com/cat_search.php?mfg=Piper&model=Archer&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?mfg=Piper&model=Archer+II&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?mfg=Piper&model=Archer+III&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?mfg=Piper&model=Archer+LX&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?mfg=Piper&model=Archer+DX&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?mfg=Piper&model=Cherokee+180&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?mfg=Piper&model=Cherokee+Archer&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?mfg=Piper&model=PA-28-181&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?mfg=Piper&model=PA-28-180&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?mfg=Piper&model=PA28-181&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?mfg=Piper&model=PA28-180&search_type=advanced",
    "https://www.barnstormers.com/cat_search.php?mfg=Piper&model=Challenger&search_type=advanced",
)
CUBCRAFTERS_INVENTORY = "https://cubcrafters.com/c/inventory/"
BLOCKED_BY_FAMILY = {
    "sr22": (
        ("controller", "Controller.com", "https://www.controller.com/listings/for-sale/cirrus/sr22/piston-single-aircraft/6"),
        ("tradeaplane", "Trade-A-Plane", "https://www.trade-a-plane.com/search?make=CIRRUS&model_group=CIRRUS+SR22+SERIES&s-type=aircraft"),
        ("aircraftcom", "Aircraft.com", "https://www.aircraft.com/aircraft/for-sale?make=Cirrus&model=SR22"),
        ("aerotrader", "Aerotrader", "https://www.aerotrader.com/Cirrus/sr22/aircraft-for-sale?zip=73102&radius=any"),
        ("ebay", "eBay Motors", "https://www.ebay.com/sch/i.html?_nkw=cirrus+sr22&_sacat=637"),
    ),
    "sf50": (
        ("controller", "Controller.com", "https://www.controller.com/listings/for-sale/cirrus/sf50/jets"),
        ("tradeaplane", "Trade-A-Plane", "https://www.trade-a-plane.com/search?make=CIRRUS&model=SF50&s-type=aircraft"),
        ("aircraftcom", "Aircraft.com", "https://www.aircraft.com/aircraft/for-sale?make=Cirrus&model=SF50"),
        ("aerotrader", "Aerotrader", "https://www.aerotrader.com/Cirrus/sf50/aircraft-for-sale?zip=73102&radius=any"),
        ("ebay", "eBay Motors", "https://www.ebay.com/sch/i.html?_nkw=cirrus+vision+jet+sf50&_sacat=637"),
    ),
    "cubcrafters": (
        ("controller", "Controller.com", "https://www.controller.com/listings/for-sale/cubcrafters/piston-single-aircraft"),
        ("tradeaplane", "Trade-A-Plane", "https://www.trade-a-plane.com/search?make=CUB+CRAFTERS&s-type=aircraft"),
        ("aircraftcom", "Aircraft.com", "https://www.aircraft.com/aircraft/for-sale?make=CubCrafters"),
        ("aerotrader", "Aerotrader", "https://www.aerotrader.com/CubCrafters/aircraft-for-sale?zip=73102&radius=any"),
        ("ebay", "eBay Motors", "https://www.ebay.com/sch/i.html?_nkw=cubcrafters&_sacat=637"),
    ),
    "pa28-180-181": (
        ("controller", "Controller.com", "https://www.controller.com/listings/for-sale/piper/archer/piston-single-aircraft"),
        ("tradeaplane", "Trade-A-Plane", "https://www.trade-a-plane.com/search?make=PIPER&model=PA-28-181&s-type=aircraft"),
        ("aircraftcom", "Aircraft.com", "https://www.aircraft.com/aircraft/for-sale?make=Piper&model=Archer"),
        ("aerotrader", "Aerotrader", "https://www.aerotrader.com/Piper/archer/aircraft-for-sale?zip=73102&radius=any"),
        ("ebay", "eBay Motors", "https://www.ebay.com/sch/i.html?_nkw=piper+archer+pa-28-181+pa-28-180&_sacat=637"),
    ),
}
# Safety stop if a site never ends. Loops also stop when the site has no next page.
MAX_PAGES = 100

PARTS_TITLE_RE = re.compile(
    r"\b(parts?|seats?|elevator|chutes?|parachutes?|propeller|actuator|head unit|"
    r"pfd|mfd|broker service|ferry|cfi|kelly|air conditioning|wings?|spars?|"
    r"ailerons?|cowling|windshield|canopy|fairings?|servos?|doubler)\b",
    re.I,
)


def _text(fragment):
    raw = re.sub(r"(?is)<script.*?>.*?</script>", " ", fragment or "")
    raw = re.sub(r"(?is)<style.*?>.*?</style>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return html_lib.unescape(re.sub(r"\s+", " ", raw)).strip()


def _abs(base, href):
    return urljoin(base, html_lib.unescape(href or "").strip())


def _keep(row, families=DEFAULT_FAMILIES):
    return row.get("family") in set(families) and (row.get("link") or row.get("title"))


# ---------- Cirrus Approved Pre-Owned ----------

def parse_cirrus_item(item):
    acf = item.get("acf") if isinstance(item.get("acf"), dict) else {}
    if acf.get("is_sold") is True:
        return None
    title = _text((item.get("title") or {}).get("rendered") or "")
    year = str(item.get("year") or "").strip()
    model = str(item.get("model") or "").strip()
    generation = str(item.get("generation") or "").strip()
    variant = str(item.get("variation") or "").strip()
    image = ""
    media = ((item.get("_embedded") or {}).get("wp:featuredmedia") or [None])[0] or {}
    if isinstance(media, dict):
        sizes = (media.get("media_details") or {}).get("sizes") or {}
        large = (sizes.get("large") or {}).get("source_url") if isinstance(sizes.get("large"), dict) else ""
        image = large or media.get("source_url") or ""
    logo = item.get("logo") if isinstance(item.get("logo"), dict) else {}
    notes = []
    if acf.get("is_pending_sale") is True:
        notes.append("Pending sale")
    availability = str(acf.get("incoming_availability") or "").strip()
    if availability:
        notes.append(availability)
    row = blank_row()
    row.update({
        "listing_id": f"cirrus:{item.get('id')}",
        "source": "cirrus",
        "title": " ".join(part for part in (year, title) if part),
        "price": str(acf.get("price") or ""),
        "year": year,
        "model": model,
        "generation": generation,
        "variant": variant,
        "n_number": str(acf.get("registration_number") or ""),
        "serial_number": str(acf.get("serial_number") or ""),
        "ttaf": str(acf.get("flight_hours") or ""),
        "avionics": str(item.get("avionics") or ""),
        "fiki": "yes" if item.get("has_fiki") is True else "",
        "air_conditioning": "yes" if item.get("has_ac") is True else "",
        "location": str(item.get("location") or ""),
        "seller": str(logo.get("alt") or ""),
        "posted_date": str(item.get("date") or "")[:10],
        "price_note": "; ".join(notes),
        "link": str(item.get("link") or ""),
        "image_url": image,
    })
    return apply_listing(row)


def scrape_cirrus(fetch, families=DEFAULT_FAMILIES):
    rows = []
    seen = set()
    model_ids = []
    for name in families:
        model_ids.extend(CIRRUS_MODELS[name])
    for model_id in model_ids:
        page = 1
        while page <= MAX_PAGES:
            url = (
                "https://cirrusaircraft.com/wp-json/wp/v2/aircraft-listings"
                f"?aircraft-model={model_id}&per_page=50&page={page}&_embed=1"
            )
            try:
                payload, headers = fetch.json(url, timeout=120000)
            except ScrapeError:
                if page == 1:
                    raise
                break
            if not isinstance(payload, list):
                raise ScrapeError("Cirrus listings response was not a list")
            for item in payload:
                if not isinstance(item, dict):
                    continue
                listing_id = str(item.get("id") or "")
                if listing_id in seen:
                    continue
                seen.add(listing_id)
                row = parse_cirrus_item(item)
                if row and _keep(row, families):
                    rows.append(row)
            total_pages = int(headers.get("x-wp-totalpages") or 1)
            if page >= total_pages or not payload:
                break
            page += 1
    if not rows:
        raise ScrapeError("Cirrus returned no matching listings")
    return rows


# ---------- CubCrafters inventory ----------

def _stated_hours(value):
    """A numeric time, or blank when the listing only gives a range."""
    raw = re.sub(r"\s+", " ", str(value or "")).strip()
    if not raw or re.match(r"(?i)less than|more than|about|approx(?:imately)?|under|over|~", raw):
        return "", ""
    match = re.match(
        r"([0-9][0-9,]*(?:\.\d+)?)(?:\s*(?:hrs?|hours))?(?:\s+(SNEW|SMOH|TSOH|SPOH))?",
        raw,
        re.I,
    )
    if not match:
        return "", ""
    return number_text(match.group(1)), (match.group(2) or "").upper()


def _labeled_fields(block):
    pairs = re.findall(
        r"<span[^>]*>\s*([^<:]+):\s*</span>\s*<span[^>]*>\s*(.*?)\s*</span>",
        block or "",
        re.S,
    )
    return {label.strip(): _text(value) for label, value in pairs}


def parse_cubcrafters_card(href, block, page_url):
    title = _text(re.search(r"<h5>(.*?)</h5>", block, re.S).group(1)) if re.search(r"<h5>", block) else ""
    if re.match(r"(?i)\s*sold\b", title):
        return None
    fields = _labeled_fields(block)
    make = fields.get("Make") or ""
    model = fields.get("Model") or ""
    if not is_cubcrafters(" ".join((title, make, model)), ""):
        return None
    image_match = re.search(r"""<img[^>]+src=["']([^"']+)["']""", block)
    notes = []
    price_drop = ""
    if re.match(r"(?i)\s*pending\b", title):
        notes.append("Pending sale")
    if re.search(r"(?i)\breduced\b", title):
        price_drop = "Price reduced"
    slug = href.rstrip("/").rsplit("/", 1)[-1]
    ttaf, _ttaf_type = _stated_hours(fields.get("TTAF"))
    engine_hours, engine_type = _stated_hours(fields.get("TTE"))
    raw_times = []
    for label in ("TTAF", "TTE"):
        stated = fields.get(label) or ""
        if stated and stated not in raw_times:
            raw_times.append(f"{label}: {stated}")
    row = blank_row()
    row.update({
        "listing_id": f"cubcrafters:{slug or href}",
        "source": "cubcrafters",
        "title": title,
        "price": fields.get("Price") or "",
        "year": fields.get("Year") or "",
        "model": " ".join(part for part in (make, model) if part),
        "ttaf": ttaf,
        "engine_hours": engine_hours,
        "engine_time_type": engine_type,
        "description": " ".join(raw_times),
        "price_note": "; ".join(notes),
        "price_drop": price_drop,
        "link": _abs(page_url, href),
        "image_url": image_match.group(1) if image_match else "",
    })
    return apply_listing(row)


def parse_cubcrafters_html(page_html, page_url):
    rows = []
    seen = set()
    cards = re.findall(
        r"""<a href=["'](https://cubcrafters.com/c/inventory/[^"']+)["'] class=["']column aircraft[^"']*["']>(.*?)</a>""",
        page_html or "",
        re.S,
    )
    for href, block in cards:
        row = parse_cubcrafters_card(href, block, page_url)
        if not row or row["link"] in seen or not _keep(row, ("cubcrafters",)):
            continue
        seen.add(row["link"])
        rows.append(row)
    return rows


def parse_cubcrafters_detail(page_html, row):
    """Copy specs the detail page states onto a list-card row."""
    overview = re.search(r"<h4>\s*Overview\s*</h4>\s*<ul>(.*?)</ul>", page_html or "", re.S | re.I)
    fields = _labeled_fields(overview.group(1) if overview else "")
    updated = dict(row)
    make = fields.get("Make") or ""
    model = fields.get("Model") or ""
    if make or model:
        updated["model"] = " ".join(part for part in (make, model) if part)
    if fields.get("Year"):
        updated["year"] = fields["Year"]
    if fields.get("N Number"):
        updated["n_number"] = fields["N Number"]
    if fields.get("Serial"):
        updated["serial_number"] = fields["Serial"]
    if fields.get("Location"):
        updated["location"] = fields["Location"]
    ttaf, _kind = _stated_hours(fields.get("TTAF"))
    if ttaf:
        updated["ttaf"] = ttaf
    engine_hours, engine_type = _stated_hours(fields.get("TTE"))
    if engine_hours:
        updated["engine_hours"] = engine_hours
    if engine_type:
        updated["engine_time_type"] = engine_type
    desc = re.search(r"<h4>\s*Description\s*</h4>(.*?)<h4>", page_html or "", re.S | re.I)
    narrative = _text(desc.group(1)) if desc else ""
    if narrative:
        updated["description"] = narrative
    engine = fields.get("Engine") or ""
    if engine and engine.lower() not in (updated.get("description") or "").lower():
        updated["description"] = " ".join(part for part in (updated.get("description") or "", "Engine: " + engine) if part)
    contact = re.search(r"<h4>\s*Contact\s*</h4>(.*?)</div>", page_html or "", re.S | re.I)
    if contact and not updated.get("seller"):
        seller = _text(contact.group(1)).split("  ")[0].strip()
        seller = re.split(r"\s{2,}|\s+\d{3}[-.)]", seller)[0].strip(" -")
        if seller and len(seller) < 80:
            updated["seller"] = seller
    if fields.get("Price") and not updated.get("price"):
        updated["price"] = fields["Price"]
    return apply_listing(updated)


def scrape_cubcrafters(fetch, families=DEFAULT_FAMILIES):
    if "cubcrafters" not in set(families):
        return []
    page_html = fetch.html(CUBCRAFTERS_INVENTORY)
    rows = parse_cubcrafters_html(page_html, CUBCRAFTERS_INVENTORY)
    detailed = []
    for index, row in enumerate(rows, start=1):
        if row.get("link"):
            try:
                detail = fetch.html(row["link"], timeout=30000)
                row = parse_cubcrafters_detail(detail, row)
            except ScrapeError as exc:
                print(f"[warn] CubCrafters detail skipped ({exc})", file=sys.stderr)
        if _keep(row, families):
            detailed.append(row)
        if index == 1 or index % 10 == 0:
            print(f"[cubcrafters] {index}/{len(rows)}", file=sys.stderr)
    if not detailed:
        raise ScrapeError("CubCrafters returned no matching listings")
    return detailed


# ---------- ASO ----------

def parse_aso_item(item):
    location = item.get("location") if isinstance(item.get("location"), dict) else {}
    city = str(location.get("city") or "").strip()
    state = str(location.get("state") or "").strip()
    display = str(location.get("displayText") or "").strip()
    country = str(location.get("countryCode") or "").strip()
    if country and country not in {"US", "USA"}:
        state = ""
    where = ", ".join(part for part in (city, state or display) if part)
    suffix = str(item.get("modelSuffix") or "").strip()
    row = blank_row()
    row.update({
        "listing_id": f"aso:{item.get('listingId')}",
        "source": "aso",
        "title": str(item.get("title") or ""),
        "price": str(item.get("priceLabel") or ""),
        "year": str(item.get("year") or ""),
        "model": str(item.get("model") or ""),
        "variant": suffix,
        "n_number": str(item.get("registrationNumber") or ""),
        "serial_number": str(item.get("serialNumber") or ""),
        "ttaf": str(item.get("totalTime") or ""),
        "city": city,
        "state": state if len(state) == 2 and country in {"US", "USA", ""} else "",
        "location": where or display,
        "seller": str(item.get("sellerName") or ""),
        "posted_date": str(item.get("publishedDate") or ""),
        "link": f"https://www.aso.com/aircraft/{item.get('listingId')}",
        "image_url": str(item.get("thumbnailUrl") or ""),
    })
    return apply_listing(row)


def _aso_pages(fetch, url_for_page, seen, families):
    rows = []
    page = 1
    total = None
    while page <= MAX_PAGES:
        payload, _headers = fetch.json(url_for_page(page))
        if not isinstance(payload, dict):
            raise ScrapeError("ASO results response was not an object")
        items = payload.get("items") or []
        total = payload.get("totalItems") if total is None else total
        for item in items:
            if not isinstance(item, dict):
                continue
            listing_id = str(item.get("listingId") or "")
            if not listing_id or listing_id in seen:
                continue
            seen.add(listing_id)
            row = parse_aso_item(item)
            if _keep(row, families):
                rows.append(row)
        if not items or (total is not None and page * 50 >= int(total)):
            break
        page += 1
    return rows


def scrape_aso(fetch, families=DEFAULT_FAMILIES):
    rows = []
    seen = set()
    wanted = set(families)
    if wanted & set(ASO_MODELS):
        models = []
        for name in families:
            models.extend(ASO_MODELS.get(name, ()))
        def url_for_page(page, models=models):
            query = "&".join(
                ["page=%s" % page, "pageSize=50", "sort=date-desc", "make=124"]
                + [f"model={model}" for model in models]
            )
            return "https://www.aso.com/aso/api/marketplace/results?" + query
        rows.extend(_aso_pages(fetch, url_for_page, seen, families))
    if "pa28-180-181" in wanted:
        for text in ASO_PA28_QUERIES:
            def url_for_page(page, text=text):
                query = "&".join([
                    "page=%s" % page,
                    "pageSize=50",
                    "sort=date-desc",
                    "q=" + quote(text),
                ])
                return "https://www.aso.com/aso/api/marketplace/results?" + query
            rows.extend(_aso_pages(fetch, url_for_page, seen, families))
    if "cubcrafters" in wanted:
        for text in ASO_CUB_QUERIES:
            def url_for_page(page, text=text):
                query = "&".join([
                    "page=%s" % page,
                    "pageSize=50",
                    "sort=date-desc",
                    "q=" + quote(text),
                ])
                return "https://www.aso.com/aso/api/marketplace/results?" + query
            rows.extend(_aso_pages(fetch, url_for_page, seen, families))
    if not rows:
        raise ScrapeError("ASO returned no matching listings")
    return rows


# ---------- GlobalAir ----------

def parse_globalair_card(card, page_url):
    title_match = re.search(r'class="afs-card__title"[^>]*>(.*?)</h3>', card, re.S)
    link_match = re.search(r'class="afs-card__title-link[^"]*"\s+href="([^"]+)"', card)
    price_match = re.search(r'class="afs-card__price-value"[^>]*>(.*?)</span>', card, re.S)
    seller_match = re.search(r'class="afs-card__seller[^"]*"[^>]*>.*?<span>(.*?)</span>', card, re.S)
    location_match = re.search(r'class="afs-card__location"[^>]*>.*?<span>(.*?)</span>', card, re.S)
    summary_match = re.search(r'class="afs-card__summary-text"[^>]*>(.*?)</span>', card, re.S)
    image_match = re.search(r'<img[^>]+src="([^"]+)"', card)
    badges = [_text(item) for item in re.findall(r'class="afs-card__badge[^"]*"[^>]*>(.*?)</span>', card, re.S)]
    specs = _text(card)
    title = _text(title_match.group(1) if title_match else "")
    href = _abs(page_url, link_match.group(1) if link_match else "")
    listing_match = re.search(r'/(\d+)(?:\?|$)', href)
    notes = [badge for badge in badges if badge]
    row = blank_row()
    row.update({
        "listing_id": f"globalair:{listing_match.group(1) if listing_match else href}",
        "source": "globalair",
        "title": title,
        "price": _text(price_match.group(1) if price_match else ""),
        "location": _text(location_match.group(1) if location_match else ""),
        "seller": _text(seller_match.group(1) if seller_match else ""),
        "description": _text(summary_match.group(1) if summary_match else ""),
        "price_note": "; ".join(notes),
        "link": href,
        "image_url": html_lib.unescape(image_match.group(1)) if image_match else "",
    })
    tt = re.search(r"\bTT:\s*([0-9][0-9,]*(?:\.\d+)?)", specs, re.I)
    sn = re.search(r"\bSN:\s*([0-9]{3,5})", specs, re.I)
    rn = re.search(r"\bRN:\s*([A-Z0-9-]+)", specs, re.I)
    updated = re.search(r"Last Updated:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", specs, re.I)
    if tt:
        row["ttaf"] = number_text(tt.group(1))
    if sn:
        row["serial_number"] = sn.group(1)
    if rn:
        row["n_number"] = rn.group(1)
    if updated:
        row["posted_date"] = updated.group(1)
    if any(badge.lower() == "price change" for badge in badges):
        row["price_note"] = "; ".join(dict.fromkeys([*notes, "Price change"]))
    applied = apply_listing(row)
    if "price reduced" in applied["description"].lower() or any("reduced" in badge.lower() for badge in badges):
        if not applied["price_drop"]:
            applied["price_drop"] = "Price reduced"
    return applied


def parse_globalair_html(page_html, page_url, families=DEFAULT_FAMILIES):
    rows = []
    for card in re.findall(r'<article class="afs-card">(.*?)</article>', page_html, re.S):
        row = parse_globalair_card(card, page_url)
        if _keep(row, families):
            rows.append(row)
    return rows


def _next_globalair(page_html, page_url):
    match = re.search(r'rel="next"\s+href="([^"]+)"', page_html)
    if not match:
        match = re.search(r'href="([^"]+)"[^>]*rel="next"', page_html)
    if not match:
        return ""
    return _abs(page_url, match.group(1))


def _scrape_globalair_url(fetch, start, families, seen):
    url = start
    rows = []
    seen_urls = set()
    for _page in range(MAX_PAGES):
        if url in seen_urls:
            break
        seen_urls.add(url)
        page_html = fetch.html(url)
        for row in parse_globalair_html(page_html, url, families):
            if row["listing_id"] in seen:
                continue
            seen.add(row["listing_id"])
            rows.append(row)
        nxt = _next_globalair(page_html, url)
        if not nxt or nxt in seen_urls:
            break
        url = nxt
    return rows


def scrape_globalair(fetch, families=DEFAULT_FAMILIES):
    wanted = set(families)
    starts = []
    if wanted & {"sr22", "sr20", "sf50"}:
        starts.append(GLOBALAIR_PAGES["cirrus"])
    if "cubcrafters" in wanted:
        starts.append(GLOBALAIR_PAGES["cubcrafters"])
    if "pa28-180-181" in wanted:
        starts.append(GLOBALAIR_PAGES["pa28-180-181"])
    rows = []
    seen = set()
    for start in starts:
        rows.extend(_scrape_globalair_url(fetch, start, families, seen))
    if not rows:
        raise ScrapeError("GlobalAir returned no matching listings")
    return rows


# ---------- AircraftDealer ----------

def parse_dealer_list_block(block, page_url):
    title_match = re.search(r"""<a class=["']admeta["'] href=["']([^"']+)["'][^>]*>(.*?)</a>""", block, re.S)
    if not title_match:
        return None
    link = _abs(page_url, title_match.group(1))
    title = _text(title_match.group(2))
    metas = [_text(item) for item in re.findall(r'<h3 class="admeta"[^>]*>(.*?)</h3>', block, re.S)]
    price = next((item for item in metas if "$" in item or "£" in item or "€" in item), "")
    location = next((item for item in metas if item and item != price and "$" not in item), "")
    image_match = re.search(r"""<img[^>]+src=["']([^"']+)["']""", block)
    desc_match = re.search(r"""text-left["']>(.*?)</div>""", block, re.S)
    seller_match = re.search(r"<h4>(.*?)</h4>", block, re.S)
    id_match = re.search(r"/(\d+)\.htm", link)
    seller = _text(seller_match.group(1) if seller_match else "")
    seller = re.sub(r"\s+-\s*[\d().+\- ]*$", "", seller).strip(" -")
    row = blank_row()
    row.update({
        "listing_id": f"aircraftdealer:{id_match.group(1) if id_match else link}",
        "source": "aircraftdealer",
        "title": title,
        "price": price,
        "location": location,
        "seller": seller,
        "description": _text(desc_match.group(1) if desc_match else ""),
        "link": link,
        "image_url": image_match.group(1) if image_match else "",
    })
    return apply_listing(row)


def parse_dealer_list_html(page_html, page_url, families=DEFAULT_FAMILIES):
    rows = []
    seen = set()
    parts = re.split(r"""<div class=["']row product-list-item["']""", page_html)
    for block in parts[1:]:
        row = parse_dealer_list_block(block, page_url)
        if not row or not _keep(row, families) or row["link"] in seen:
            continue
        seen.add(row["link"])
        rows.append(row)
    return rows


def parse_dealer_detail(page_html, row):
    """Add registration, total time, and the description the detail page states."""
    reg = re.search(r"Reg\s*#\s*([A-Z0-9-]+)", page_html, re.I)
    sku = re.search(r'"sku"\s*:\s*"([^"]+)"', page_html)
    desc = re.search(r'class="col-md-12 text-start">(.*?)</div>', page_html, re.S)
    updated = dict(row)
    if reg:
        updated["n_number"] = reg.group(1)
    elif sku and not updated.get("n_number"):
        updated["n_number"] = sku.group(1)
    if desc:
        text = _text(desc.group(1))
        if len(text) > len(updated.get("description") or ""):
            updated["description"] = text
    return apply_listing(updated)


def _dealer_last_page(page_html):
    numbers = [int(item) for item in re.findall(r"page-(\d+)\.htm", page_html)]
    return max(numbers) if numbers else 1


def _dealer_collect(fetch, pattern):
    first = pattern.format(page=1)
    page_html = fetch.html(first)
    last = min(_dealer_last_page(page_html), MAX_PAGES)
    bodies = [(first, page_html)]
    for number in range(2, last + 1):
        page = pattern.format(page=number)
        bodies.append((page, fetch.html(page)))
    return bodies


def _dealer_details(fetch, found, families):
    detailed = []
    for index, row in enumerate(found, start=1):
        if row.get("link") and not (row.get("n_number") and row.get("ttaf")):
            try:
                detail = fetch.html(row["link"], timeout=30000)
                row = parse_dealer_detail(detail, row)
            except ScrapeError as exc:
                print(f"[warn] AircraftDealer detail skipped ({exc})", file=sys.stderr)
        if _keep(row, families):
            detailed.append(row)
        if index == 1 or index % 25 == 0:
            print(f"[aircraftdealer] {index}/{len(found)}", file=sys.stderr)
    return detailed


def scrape_aircraftdealer(fetch, families=DEFAULT_FAMILIES):
    found = []
    seen = set()
    errors = []
    for family in families:
        pattern = DEALER_CATEGORIES.get(family)
        patterns = pattern if isinstance(pattern, (tuple, list)) else ((pattern,) if pattern else ())
        for one in patterns:
            try:
                for page_url, body in _dealer_collect(fetch, one):
                    for row in parse_dealer_list_html(body, page_url, families):
                        if row["listing_id"] in seen:
                            continue
                        seen.add(row["listing_id"])
                        found.append(row)
            except ScrapeError as exc:
                errors.append(f"{family}: {exc}")
                print(f"[warn] AircraftDealer {family} failed ({exc})", file=sys.stderr)
    if "pa28-180-181" in set(families):
        for query in DEALER_PA28_QUERIES:
            url = (
                "https://www.aircraftdealer.com/view-ad-list.php?searchVal="
                + quote(query) + "&search=Search"
            )
            try:
                page_html = fetch.html(url)
            except ScrapeError as exc:
                errors.append(f"{query}: {exc}")
                print(f"[warn] AircraftDealer search {query} failed ({exc})", file=sys.stderr)
                continue
            for row in parse_dealer_list_html(page_html, url, families):
                if row["listing_id"] in seen:
                    continue
                seen.add(row["listing_id"])
                found.append(row)
    if "cubcrafters" in set(families):
        for query in DEALER_CUB_QUERIES:
            url = (
                "https://www.aircraftdealer.com/view-ad-list.php?searchVal="
                + quote(query) + "&search=Search"
            )
            try:
                page_html = fetch.html(url)
            except ScrapeError as exc:
                errors.append(f"{query}: {exc}")
                print(f"[warn] AircraftDealer search {query} failed ({exc})", file=sys.stderr)
                continue
            for row in parse_dealer_list_html(page_html, url, families):
                if row["listing_id"] in seen:
                    continue
                seen.add(row["listing_id"])
                found.append(row)
    rows = _dealer_details(fetch, found, families)
    if not rows:
        detail = "; ".join(errors) if errors else "no listings"
        raise ScrapeError(f"AircraftDealer returned no matching listings ({detail})")
    return rows


# ---------- Barnstormers ----------

def _stated_price(block):
    """First currency figure in an ad. A trailing k means thousands."""
    match = re.search(r"([\$£€])\s*([\d,]+(?:\.\d+)?)(\s*[kK])?", block or "")
    if not match:
        return ""
    symbol, digits, kilo = match.group(1), match.group(2).replace(",", ""), match.group(3)
    try:
        amount = float(digits)
    except ValueError:
        return ""
    if kilo:
        amount *= 1000
    if amount < 1000:
        return ""
    if symbol == "$":
        from listings import format_usd
        return format_usd(amount)
    shown = f"{int(amount):,}" if amount.is_integer() else f"{amount:,.2f}"
    return f"{symbol}{shown}"


def _title_matches_families(title, families, description=""):
    wanted = set(families)
    is_jet = re.search(r"\bSF-?50\b|vision\s*jet", title or "", re.I)
    is_piston = re.search(r"\bSR22T?\b|\bSR20\b", title or "", re.I)
    is_cub = is_cubcrafters(title or "", description or "")
    is_pa = is_pa28_180_181(title or "", description or "")
    cirrus = bool(wanted & {"sr22", "sr20", "sf50"})
    cub = "cubcrafters" in wanted
    pa = "pa28-180-181" in wanted
    if pa and not cirrus and not cub:
        return is_pa
    if cub and not cirrus:
        return is_cub
    if "sf50" in wanted and not ({"sr22", "sr20"} & wanted):
        return bool(is_jet) and not is_piston
    if not cub and not pa:
        return bool(is_piston) and not is_jet
    return bool(is_jet or is_piston or is_cub or is_pa)


def _barn_is_aircraft(title, action, price, families=DEFAULT_FAMILIES, description=""):
    if not _title_matches_families(title, families, description):
        return False
    if PARTS_TITLE_RE.search(title or ""):
        return False
    action_l = (action or "").lower()
    if any(word in action_l for word in ("part", "service", "ferry")):
        return False
    if re.search(r"\b(ferry|prebuy|pre-buy)\b", title or "", re.I):
        return False
    amount = price_number(price)
    pa_only = "pa28-180-181" in set(families) and not (set(families) & {"sr22", "sr20", "sf50", "cubcrafters"})
    if amount is not None and amount < (5000 if pa_only else 40000):
        return False
    identity = f"{title or ''} {description or ''}"
    if amount is None and not re.search(
        r"\b(?:19|20)\d{2}\b|\bG[1-7]\b|\bSR22T\b|\bSF-?50\b|vision\s*jet|"
        r"cub\s*-?\s*crafters?|carbon\s+cub|\bx-?\s*cub\b|\bnx-?\s*cub\b|sport\s+cub|top\s+cub|"
        r"\barcher\b|cher(?:okee)?\s+180|pa\s*-?\s*28\s*-?\s*18[01]",
        identity,
        re.I,
    ):
        return False
    return True


def parse_barnstormers_block(block, page_url, families=DEFAULT_FAMILIES):
    id_match = re.search(r'data-adid="(\d+)"', block)
    title_match = re.search(r"""class=["']listing_header["'][^>]*href=["']([^"']+)["'][^>]*>(.*?)</a>""", block, re.S)
    if not title_match:
        return None
    title = _text(title_match.group(2))
    action_match = re.search(r"""class=["']action_phrase["'][^>]*>(.*?)</span>""", block, re.S)
    action = _text(action_match.group(1) if action_match else "")
    body_match = re.search(r"""class=["']body["'][^>]*>(.*?)</span>""", block, re.S)
    body = _text(body_match.group(1) if body_match else "")
    price = _stated_price(block)
    if not _barn_is_aircraft(title, action, price, families, body):
        return None
    contact_html = ""
    contact_match = re.search(r"""class=["']contact["'](.*?)(?:class=["']listinglinks["']|Posted\s+)""", block, re.S)
    if contact_match:
        contact_html = contact_match.group(1)
    contact = _text(contact_html)
    located = re.search(r"located\s+([^,<]+),\s*([A-Z]{2})\b", contact)
    seller_match = re.search(r""">\s*([^<]{2,80})\s*</a>\s*,""", block)
    image = ""
    for src in re.findall(r"""<img[^>]+src=["']([^"']+)["']""", block):
        low = src.lower()
        if any(token in low for token in ("logo", "banner", "userbann")):
            continue
        image = src
        break
    posted = re.search(r"Posted\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", block)
    ad_id = id_match.group(1) if id_match else title_match.group(1)
    city = located.group(1).strip() if located else ""
    state = located.group(2) if located else ""
    row = blank_row()
    row.update({
        "listing_id": f"barnstormers:{ad_id}",
        "source": "barnstormers",
        "title": title,
        "price": price,
        "description": body,
        "city": city,
        "state": state,
        "location": ", ".join(part for part in (city, state) if part),
        "seller": _text(seller_match.group(1) if seller_match else ""),
        "posted_date": posted.group(1) if posted else "",
        "price_drop": "Price reduced" if "reduced" in action.lower() else "",
        "link": _abs(page_url, title_match.group(1)),
        "image_url": image,
    })
    return apply_listing(row)


def parse_barnstormers_html(page_html, page_url, families=DEFAULT_FAMILIES):
    rows = []
    seen = set()
    parts = re.split(r"""<div class=["']classified_single""", page_html)
    for part in parts[1:]:
        row = parse_barnstormers_block('<div class="classified_single' + part, page_url, families)
        if not row or row["listing_id"] in seen or not _keep(row, families):
            continue
        seen.add(row["listing_id"])
        rows.append(row)
    return rows


def scrape_barnstormers(fetch, families=DEFAULT_FAMILIES):
    rows = []
    seen = set()
    urls = []
    for name in families:
        for model in BARN_MODELS.get(name, ()):
            urls.append(
                "https://www.barnstormers.com/cat_search.php?mfg=Cirrus&model="
                + quote(model) + "&search_type=advanced"
            )
    if "cubcrafters" in set(families):
        urls.extend(BARN_CUB_URLS)
    if "pa28-180-181" in set(families):
        urls.extend(BARN_PA28_URLS)
    for url in urls:
        page_html = fetch.html(url)
        for row in parse_barnstormers_html(page_html, url, families):
            if row["listing_id"] in seen:
                continue
            seen.add(row["listing_id"])
            rows.append(row)
    if not rows:
        raise ScrapeError("Barnstormers returned no matching aircraft ads")
    return rows


# ---------- Sites that block automation ----------

def scrape_blocked(fetch, label, url):
    try:
        page_html = fetch.html(url, timeout=20000)
    except ScrapeError as exc:
        raise ScrapeError(f"{label} blocked automated access ({exc})") from exc
    if re.search(
        r"\bSR22\b|\bSF-?50\b|vision\s*jet|cub\s*-?\s*crafters?|carbon\s+cub|\bx-?\s*cub\b",
        page_html,
        re.I,
    ):
        raise ScrapeError(f"{label} returned a page but no listing parser matched it")
    raise ScrapeError(f"{label} did not return listings")


def sources_for(families):
    """One scraper tuple per source, limited to these aircraft families."""
    fam = tuple(families)

    def bind(fn):
        def run(fetch):
            return fn(fetch, families=fam)
        return run

    specs = []
    if any(name in CIRRUS_MODELS for name in fam):
        specs.append(("cirrus", "Cirrus", bind(scrape_cirrus)))
    if "cubcrafters" in fam:
        specs.append(("cubcrafters", "CubCrafters", bind(scrape_cubcrafters)))
    specs.extend([
        ("aso", "ASO", bind(scrape_aso)),
        ("globalair", "GlobalAir", bind(scrape_globalair)),
        ("aircraftdealer", "AircraftDealer", bind(scrape_aircraftdealer)),
        ("barnstormers", "Barnstormers", bind(scrape_barnstormers)),
    ])
    if "pa28-180-181" in fam and not any(name in {"sr22", "sr20", "sf50", "cubcrafters"} for name in fam):
        blocked_key = "pa28-180-181"
    elif "cubcrafters" in fam and not any(name in {"sr22", "sr20", "sf50"} for name in fam):
        blocked_key = "cubcrafters"
    elif "sf50" in fam and "sr22" not in fam:
        blocked_key = "sf50"
    else:
        blocked_key = "sr22"
    short = {
        "controller": "Controller",
        "tradeaplane": "Trade-A-Plane",
        "aircraftcom": "Aircraft.com",
        "aerotrader": "Aerotrader",
        "ebay": "eBay",
    }
    for name, label, url in BLOCKED_BY_FAMILY[blocked_key]:
        specs.append((name, short[name],
                      (lambda fetch, label=label, url=url: scrape_blocked(fetch, label, url))))
    return tuple(specs)


SOURCES = sources_for(DEFAULT_FAMILIES)
