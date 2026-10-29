#!/usr/bin/env python3
"""Parser, merge, and report tests. No network."""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from generate_report import build_report, markdown_to_html, readme_tab  # noqa: E402
from listings import (  # noqa: E402
    apply_listing,
    blank_row,
    clean_registration,
    generation_name,
    price_number,
    us_n_number,
)
from merge_listings import annotate_changes, merge_rows  # noqa: E402
from saved_store import format_as_of  # noqa: E402
from scrape_sources import (  # noqa: E402
    parse_aso_item,
    parse_barnstormers_html,
    parse_cirrus_item,
    parse_cubcrafters_detail,
    parse_cubcrafters_html,
    parse_dealer_detail,
    parse_dealer_list_html,
    parse_globalair_html,
    sources_for,
)


def aircraft(**overrides):
    row = blank_row()
    row.update({
        "listing_id": "cirrus:1",
        "source": "cirrus",
        "title": "2019 Cirrus SR22 G6 GTS",
        "price": "$500,000",
        "n_number": "N100AB",
        "link": "https://cirrusaircraft.com/1",
    })
    row.update(overrides)
    return apply_listing(row)


class FieldTests(unittest.TestCase):
    def test_n_number_rules(self):
        self.assertTrue(us_n_number("N100AB"))
        self.assertTrue(us_n_number("N12345"))
        self.assertTrue(us_n_number("N1234A"))
        self.assertFalse(us_n_number("N1234AB"))
        self.assertFalse(us_n_number("N123IO"))
        self.assertEqual(clean_registration("n100ab"), "N100AB")
        self.assertEqual(clean_registration("XB-CRL"), "XB-CRL")
        self.assertEqual(clean_registration("IO-550"), "")

    def test_year_does_not_become_a_generation(self):
        row = apply_listing({
            "title": "2004 Cirrus SR22",
            "description": "A clean airplane with fresh annual.",
        })
        self.assertEqual(row["generation"], "")
        self.assertEqual(row["model"], "SR22")
        self.assertEqual(row["turbo"], "")
        self.assertEqual(row["year"], "2004")

    def test_stated_specs_are_kept_and_unstated_ones_stay_blank(self):
        row = apply_listing({
            "title": "2014 Cirrus SR22T G5 GTS",
            "description": (
                "Serial Number: 0851. Total Time: 1,200. Engine 1 Time: 1,147.8 SMOH. "
                "Continental TSIO-550-K. TBO 2,200. FIKI. TKS. Air conditioning. "
                "Cirrus Perspective+ by Garmin. GFC 700 autopilot. ADS-B In/Out. "
                "CAPS repack due December 2031. Interior: black leather. "
                "Price reduced to $675,000. Based at KHEF."
            ),
            "price": "$675,000",
        })
        self.assertEqual(row["model"], "SR22T")
        self.assertEqual(row["generation"], "G5")
        self.assertEqual(row["variant"], "GTS")
        self.assertEqual(row["turbo"], "yes")
        self.assertEqual(row["serial_number"], "0851")
        self.assertEqual(row["ttaf"], "1200")
        self.assertEqual(row["engine_hours"], "1147.8")
        self.assertEqual(row["engine_time_type"], "SMOH")
        self.assertEqual(row["engine_make"], "Continental")
        self.assertEqual(row["engine_model"], "TSIO-550-K")
        self.assertEqual(row["engine_tbo"], "2200")
        self.assertEqual(row["fiki"], "yes")
        self.assertEqual(row["tks"], "yes")
        self.assertEqual(row["air_conditioning"], "yes")
        self.assertIn("Perspective+", row["avionics"])
        self.assertNotIn("Perspective;", row["avionics"])
        self.assertEqual(row["autopilot"], "GFC 700")
        self.assertEqual(row["adsb"], "ADS-B In/Out")
        self.assertEqual(row["caps_repack"], "December 2031")
        self.assertEqual(row["interior"], "black leather")
        self.assertEqual(row["exterior"], "")
        self.assertEqual(row["airport"], "KHEF")
        self.assertEqual(row["price_drop"], "Reduced to $675,000")
        self.assertEqual(row["prop_time"], "")
        self.assertEqual(row["days_on_market"], "")

    def test_g7_plus_beats_a_plain_g7_in_the_same_title(self):
        self.assertEqual(generation_name("SR22T G7+ GTS G7"), "G7+")

    def test_foreign_currency_is_not_treated_as_dollars(self):
        self.assertIsNone(price_number("£370,000"))
        self.assertEqual(price_number("$274,900"), 274900)

    def test_two_n_numbers_are_not_guessed(self):
        row = apply_listing({"title": "2008 Cirrus SR22", "description": "See N123AB or N456CD."})
        self.assertEqual(row["n_number"], "")

    def test_placeholder_image_is_dropped(self):
        row = apply_listing({
            "title": "2001 Cirrus SR22",
            "image_url": "https://www.aircraftdealer.com/images/Image-Coming-Soon.png",
        })
        self.assertEqual(row["image_url"], "")


class MergeTests(unittest.TestCase):
    def test_same_n_number_is_one_airplane_with_both_prices(self):
        cirrus = aircraft(price="$520,000", source="cirrus", listing_id="cirrus:1")
        aso = aircraft(
            price="$500,000", source="aso", listing_id="aso:9",
            link="https://www.aso.com/aircraft/9", ttaf="800", serial_number="4689",
        )
        merged = merge_rows([cirrus, aso])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["n_number"], "N100AB")
        self.assertEqual(merged[0]["price"], "$500,000")
        self.assertEqual(merged[0]["link"], "https://www.aso.com/aircraft/9")
        self.assertEqual(merged[0]["ttaf"], "800")
        sources = json.loads(merged[0]["sources"])
        self.assertEqual([item["source"] for item in sources], ["aso", "cirrus"])
        self.assertEqual(sources[0]["price"], "$500,000")
        self.assertEqual(sources[1]["price"], "$520,000")

    def test_serial_joins_when_one_side_has_no_n_number(self):
        priced = aircraft(n_number="N100AB", serial_number="0851", source="aso")
        bare = aircraft(n_number="", serial_number="851", source="globalair", listing_id="globalair:1", price="$480,000", link="https://www.globalair.com/1")
        merged = merge_rows([priced, bare])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["n_number"], "N100AB")
        self.assertIn("globalair", merged[0]["sources"])

    def test_different_n_numbers_stay_apart(self):
        one = aircraft(n_number="N100AB", serial_number="0851")
        two = aircraft(n_number="N200CD", serial_number="0851", listing_id="cirrus:2", link="https://cirrusaircraft.com/2")
        merged = merge_rows([one, two])
        self.assertEqual(len(merged), 2)

    def test_serial_only_rows_group_together(self):
        one = aircraft(n_number="", serial_number="10647", source="aso", listing_id="aso:1")
        two = aircraft(n_number="", serial_number="10647", source="globalair", listing_id="globalair:2", price="$610,000", link="https://www.globalair.com/2")
        merged = merge_rows([one, two])
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(json.loads(merged[0]["sources"])), 2)

    def test_new_and_price_drop_against_the_previous_snapshot(self):
        previous = [aircraft(price="$520,000")]
        current = merge_rows([
            aircraft(price="$500,000"),
            aircraft(n_number="N200CD", listing_id="cirrus:2", link="https://cirrusaircraft.com/2", title="2020 Cirrus SR22 G6"),
        ])
        annotate_changes(current, previous)
        by_n = {row["n_number"]: row for row in current}
        self.assertEqual(by_n["N100AB"]["is_new"], "")
        self.assertEqual(by_n["N100AB"]["observed_drop"], "$20,000")
        self.assertEqual(by_n["N100AB"]["prior_price"], "$520,000")
        self.assertEqual(by_n["N200CD"]["is_new"], "yes")
        fresh = annotate_changes(current, [])
        self.assertTrue(all(row["is_new"] == "" for row in fresh))


GLOBAL_CARD = """
<article class="afs-card">
  <span class="afs-card__badge afs-card__badge--price">Price change</span>
  <a class="afs-card__title-link result-title" href="/aircraft-for-sale/listing-detail/2003-cirrus-sr22-singles/141253">
    <h3 class="afs-card__title">2003 Cirrus SR22</h3>
  </a>
  <span class="afs-card__price-value">$274,900</span>
  <div class="afs-card__location"><span>Florida (USA)</span></div>
  <a class="afs-card__seller result-seller" href="/seller"><span>Aerista</span></a>
  <div class="afs-card__specs"><div><b>TT:</b> 2,210 hrs</div><div><b>SN:</b> 0693</div><div><b>RN:</b> N415GE</div><div><b>Last Updated:</b> 10/12/2026</div></div>
  <span class="afs-card__summary-text">TKS and ADS-B In &amp; Out. No FIKI.</span>
  <img src="https://resources.globalair.com/aircraftforsale/images/ads/141253.webp?width=525&amp;height=350">
</article>
<article class="afs-card">
  <h3 class="afs-card__title">2019 Cirrus Vision Jet</h3>
  <a class="afs-card__title-link" href="/aircraft-for-sale/listing-detail/vision/9"></a>
  <span class="afs-card__price-value">$2,000,000</span>
</article>
"""

DEALER_PAGE = """
<div class='row product-list-item' ><div class='col-md-12'>
  <h3><a class="admeta" href='https://www.aircraftdealer.com/aircraft-for-sale-detail/Cirrus_SR22/2001-CIRRUS-SR22/95222.htm'>2001 CIRRUS SR22</a></h3>
  <h3 class="admeta" style='color:white;'>CA, US</h3>
  <h3 class="admeta" style='color:white;'>$199,900</h3>
  <img src="https://www.aircraftdealer.com/images/Image-Coming-Soon.png">
  <div class='col-md-12 text-left'>Garmin G5 upgrade.</div>
  <h4>OCR Aviation - <a href='tel:562-426-5331'>562-426-5331</a></h4>
</div></div></div>
"""

DEALER_DETAIL = """
<h3 class="ad-detail-title">Reg # N748CD</h3>
<div class="col-md-12 text-start">Airframe: Total Time: 5,093. Serial Number: 0166. FIKI.</div>
"""

BARN_PAGE = """
<div class='classified_single ' data-adid="2067291">
  <a class='listing_header' href='/classified-2067291-2008-Cirrus-SR22-G3-GTS-Turbo.html'>2008 CIRRUS SR22 G3 GTS TURBO</a>
  <span class='action_phrase'>PRICE REDUCED</span>
  <span class='body'>AFTT:2060 SMOH:12 Cirrus Perspective. $429,900</span>
  <span class='contact'>Contact <a href='/x'><span>Chris Swathwood</span></a> - <a href='/y'>ALTIVATION AIRCRAFT SALES</a> , Broker - located Venice, FL 34285</span>
  <span class='listinglinks'>Posted October 1, 2026</span>
</div>
<div class='classified_single ' data-adid="9">
  <a class='listing_header' href='/classified-9-elevator.html'>SR22 RH ELEVATOR</a>
  <span class='action_phrase'>FOR SALE</span>
  <span class='body'>Elevator for an SR22. $1,200</span>
</div>
<div class='classified_single ' data-adid="8">
  <a class='listing_header' href='/classified-8-ferry.html'>FERRY PILOT AND CFI</a>
  <span class='action_phrase'>SERVICES OFFERED</span>
  <span class='body'>Cirrus SR22 training. $399</span>
</div>
"""


class ParserTests(unittest.TestCase):
    def test_globalair_card_keeps_stated_fields_and_drops_a_jet(self):
        rows = parse_globalair_html(GLOBAL_CARD, "https://www.globalair.com/aircraft-for-sale/cirrus-sr22")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["n_number"], "N415GE")
        self.assertEqual(row["serial_number"], "0693")
        self.assertEqual(row["ttaf"], "2210")
        self.assertEqual(row["price"], "$274,900")
        self.assertEqual(row["state"], "FL")
        self.assertEqual(row["seller"], "Aerista")
        self.assertEqual(row["fiki"], "no")
        self.assertEqual(row["tks"], "yes")
        self.assertEqual(row["posted_date"], "10/12/2026")
        self.assertIn("Price change", row["price_note"])
        self.assertIn("141253.webp", row["image_url"])
        self.assertTrue(row["link"].startswith("https://www.globalair.com/"))

    def test_aso_item(self):
        row = parse_aso_item({
            "listingId": "abc",
            "title": "2007 Cirrus SR22-G3 Turbo GTS",
            "year": 2007,
            "make": "Cirrus",
            "model": "SR22-G3",
            "modelSuffix": "Turbo GTS",
            "priceLabel": "$360,000",
            "location": {"displayText": "MX", "city": None, "state": "MX", "countryCode": "MX"},
            "sellerName": "Flight Source International",
            "thumbnailUrl": "https://example.com/1.jpg",
            "publishedDate": "2026-10-28",
            "totalTime": 2514,
            "registrationNumber": "XB-CRL",
            "serialNumber": "2339",
        })
        self.assertEqual(row["n_number"], "XB-CRL")
        self.assertEqual(row["model"], "SR22")
        self.assertEqual(row["generation"], "G3")
        self.assertEqual(row["turbo"], "yes")
        self.assertEqual(row["variant"], "GTS")
        self.assertEqual(row["state"], "")
        self.assertEqual(row["ttaf"], "2514")
        self.assertEqual(row["link"], "https://www.aso.com/aircraft/abc")
        self.assertEqual(row["family"], "sr22")

    def test_cirrus_structured_flags_and_sold_skip(self):
        row = parse_cirrus_item({
            "id": 79918,
            "date": "2026-10-16T12:54:42",
            "link": "https://cirrusaircraft.com/aircraft-listings/n343cb/",
            "title": {"rendered": "SR22T G7 GTS"},
            "model": "SR22T",
            "generation": "G7",
            "variation": "GTS",
            "year": "2024",
            "avionics": "Cirrus Perspective+™ by Garmin®",
            "has_fiki": True,
            "has_ac": False,
            "location": "United States",
            "logo": {"alt": "Cirrus Next"},
            "acf": {
                "is_sold": False,
                "flight_hours": "700",
                "registration_number": "N343CB",
                "serial_number": "9851",
                "price": "$ 1,050,000",
            },
            "_embedded": {"wp:featuredmedia": [{"source_url": "https://cirrusaircraft.com/wp-content/uploads/n.png"}]},
        })
        self.assertEqual(row["n_number"], "N343CB")
        self.assertEqual(row["generation"], "G7")
        self.assertEqual(row["model"], "SR22T")
        self.assertEqual(row["fiki"], "yes")
        self.assertEqual(row["air_conditioning"], "")
        self.assertEqual(row["price"], "$1,050,000")
        self.assertEqual(row["ttaf"], "700")
        self.assertEqual(row["seller"], "Cirrus Next")
        self.assertEqual(row["state"], "")
        self.assertIsNone(parse_cirrus_item({"acf": {"is_sold": True}, "title": {"rendered": "SR22"}, "model": "SR22"}))

    def test_dealer_list_and_detail(self):
        rows = parse_dealer_list_html(DEALER_PAGE, "https://www.aircraftdealer.com/aircraft_for_sale/Cirrus_SR22/101/page-1.htm")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["price"], "$199,900")
        self.assertEqual(rows[0]["state"], "CA")
        self.assertEqual(rows[0]["seller"], "OCR Aviation")
        self.assertEqual(rows[0]["image_url"], "")
        detailed = parse_dealer_detail(DEALER_DETAIL, rows[0])
        self.assertEqual(detailed["n_number"], "N748CD")
        self.assertEqual(detailed["ttaf"], "5093")
        self.assertEqual(detailed["serial_number"], "0166")
        self.assertEqual(detailed["fiki"], "yes")

    def test_barnstormers_reads_a_thousands_suffix_and_drops_a_wing(self):
        page = """
        <div class="classified_single " data-adid="1">
          <a class="listing_header" href="/classified-1-sr20.html">2010 CIRRUS SR20 G3 FOR SALE</a>
          <span class="action_phrase">FOR SALE</span>
          <span class="body">2393FH, €250k, Garmin Perspective</span>
        </div>
        <div class="classified_single " data-adid="2">
          <a class="listing_header" href="/classified-2-wing.html">2022 CIRRUS SR20 WING</a>
          <span class="action_phrase">FOR SALE</span>
          <span class="body">Needs repairs. $55,000</span>
        </div>
        """
        rows = parse_barnstormers_html(page, "https://www.barnstormers.com/cat_search.php")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["price"], "€250,000")
        self.assertEqual(rows[0]["model"], "SR20")

    def test_barnstormers_keeps_the_airplane_and_drops_parts(self):
        rows = parse_barnstormers_html(BARN_PAGE, "https://www.barnstormers.com/cat_search.php")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["generation"], "G3")
        self.assertEqual(row["turbo"], "yes")
        self.assertEqual(row["price"], "$429,900")
        self.assertEqual(row["price_drop"], "Price reduced")
        self.assertEqual(row["state"], "FL")
        self.assertEqual(row["city"], "Venice")
        self.assertEqual(row["ttaf"], "2060")
        self.assertEqual(row["engine_hours"], "12")
        self.assertEqual(row["engine_time_type"], "SMOH")
        self.assertIn("Perspective", row["avionics"])


class VisionJetTests(unittest.TestCase):
    def test_sf50_is_not_an_sr22_and_keeps_stated_jet_fields(self):
        row = apply_listing({
            "title": "2021 Cirrus Vision Jet G2+",
            "description": (
                "SF50. 450 landings. Engine cycles: 420. "
                "Cirrus Jet Support due December 2028. CAPS due June 2030."
            ),
            "price": "$2,750,000",
            "n_number": "N28VJ",
        })
        self.assertEqual(row["model"], "SF50")
        self.assertEqual(row["family"], "sf50")
        self.assertEqual(row["generation"], "G2+")
        self.assertEqual(row["landings"], "450")
        self.assertEqual(row["engine_cycles"], "420")
        self.assertEqual(row["jet_support"], "December 2028")
        self.assertEqual(row["caps_repack"], "June 2030")
        self.assertEqual(row["turbo"], "")
        piston = apply_listing({"title": "2019 Cirrus SR22 G6 GTS"})
        self.assertEqual(piston["family"], "sr22")
        self.assertEqual(piston["landings"], "")
        self.assertEqual(apply_listing({"title": "1990 Learjet 55"})["family"], "")

    def test_arrivee_is_a_stated_variant(self):
        row = apply_listing({"title": "2024 Cirrus Vision Jet G3 Arrivee", "n_number": "N3ARR"})
        self.assertEqual(row["family"], "sf50")
        self.assertEqual(row["generation"], "G3")
        self.assertIn("Arrivee", row["variant"])

    def test_barnstormers_vision_jet_search_drops_an_sr22(self):
        page = """
        <div class="classified_single " data-adid="1">
          <a class="listing_header" href="/classified-1-jet.html">2020 CIRRUS VISION JET G2+</a>
          <span class="action_phrase">FOR SALE</span>
          <span class="body">SF50, 800 hours, $2,100,000</span>
        </div>
        <div class="classified_single " data-adid="2">
          <a class="listing_header" href="/classified-2-sr22.html">2019 CIRRUS SR22 G6</a>
          <span class="action_phrase">FOR SALE</span>
          <span class="body">$500,000</span>
        </div>
        """
        from scrape_sources import parse_barnstormers_html
        rows = parse_barnstormers_html(page, "https://www.barnstormers.com/cat_search.php", ("sf50",))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["family"], "sf50")
        self.assertEqual(rows[0]["generation"], "G2+")
        self.assertEqual(rows[0]["price"], "$2,100,000")


class CubCraftersTests(unittest.TestCase):
    def test_models_stay_on_the_stated_name_and_piper_cubs_are_excluded(self):
        fx = apply_listing({
            "title": "2019 Carbon Cub FX-3",
            "model": "CUBCRAFTERS CCX-2000 - Carbon Cub FX-3",
            "description": "29 inch Alaskan Bushwheels. Engine: CC363i. Wipline floats in the hangar.",
            "n_number": "N441JM",
            "serial_number": "CCX-2000-0058",
        })
        self.assertEqual(fx["family"], "cubcrafters")
        self.assertEqual(fx["model"], "Carbon Cub")
        self.assertEqual(fx["variant"], "FX-3")
        self.assertEqual(fx["engine_model"], "CC363i")
        self.assertIn("Bushwheels", fx["gear"])
        self.assertIn("Floats", fx["gear"])
        self.assertEqual(fx["generation"], "")
        self.assertEqual(fx["serial_number"], "CCX-2000-0058")

        self.assertEqual(apply_listing({"title": "2020 XCub", "model": "CCX-2300"})["model"], "XCub")
        nxcub = apply_listing({"title": "2021 NX Cub", "model": "CCX-2300 NX Cub"})
        self.assertEqual(nxcub["model"], "NXCub")
        self.assertEqual(nxcub["variant"], "")
        self.assertEqual(apply_listing({"title": "CCX-2300", "model": "CUBCRAFTERS CCX-2300"})["model"], "CCX-2300")
        top = apply_listing({"title": "CubCrafters Ranger Cub CC18-180"})
        self.assertEqual(top["model"], "Top Cub")
        self.assertEqual(top["variant"], "Ranger")
        sport = apply_listing({"title": "2011 CubCrafters Sport Cub S2", "n_number": "N11SC"})
        self.assertEqual(sport["model"], "Sport Cub")
        self.assertEqual(sport["variant"], "S2")
        bare = apply_listing({"title": "Garmin G3X panel", "model": "CC11-160"})
        self.assertEqual(bare["family"], "cubcrafters")
        self.assertEqual(bare["model"], "CC11-160")
        self.assertEqual(bare["generation"], "")

        piper = apply_listing({
            "title": "2012 PA-18 Super Cub",
            "model": "PIPER PA-18-150",
            "description": "Hangared next to a Carbon Cub.",
        })
        self.assertEqual(piper["family"], "")
        legend = apply_listing({"title": "2008 American Legend Cub", "model": "Legend Cub"})
        self.assertEqual(legend["family"], "")
        self.assertEqual(apply_listing({"title": "2019 Cirrus SR22 G6"})["family"], "sr22")
        code_only = apply_listing({"title": "CCX-2300", "model": "CUBCRAFTERS"})
        self.assertEqual(code_only["model"], "CCX-2300")
        named = apply_listing({
            "title": "2022 CubCrafters CC19-215",
            "description": "2022 big-engine XCub, Lycoming 393i.",
        })
        self.assertEqual(named["model"], "XCub")
        s2 = apply_listing({
            "title": "CubCrafters Sport Cub",
            "description": "2009 CubCrafters Sport Cub S2. Tach Time: 887.3.",
        })
        self.assertEqual(s2["model"], "Sport Cub")
        self.assertEqual(s2["variant"], "S2")
        self.assertEqual(s2["ttaf"], "")
        titan = apply_listing({
            "title": "2016 Carbon Cub SS",
            "description": "Only 400 hours ACTT. Engine: Titan CC340 (180 HP). 35 inch Bushwheels.",
        })
        self.assertEqual(titan["ttaf"], "400")
        self.assertEqual(titan["engine_make"], "Titan")
        self.assertEqual(titan["engine_model"], "CC340")
        self.assertEqual(apply_listing({"title": "Ranger Cub", "model": "CC18-180", "description": "73.2 ttsn"})["ttaf"], "73.2")

    def test_unstated_gear_and_approximate_time_stay_blank(self):
        row = apply_listing({"title": "2018 CubCrafters Carbon Cub SS", "description": "A clean airplane."})
        self.assertEqual(row["gear"], "")
        self.assertEqual(row["engine_model"], "")
        self.assertEqual(row["variant"], "SS")
        from scrape_sources import _stated_hours
        self.assertEqual(_stated_hours("Less than 100 TT"), ("", ""))
        self.assertEqual(_stated_hours("375.4 hrs"), ("375.4", ""))
        self.assertEqual(_stated_hours("535 SNEW"), ("535", "SNEW"))

    def test_inventory_page_drops_sold_and_piper_and_keeps_a_carbon_cub(self):
        page = """
        <a href="https://cubcrafters.com/c/inventory/n747fl-2020-carbon-cub-fx-3/" class="column aircraft cf">
          <img src="https://cubcrafters.com/c/wp-content/uploads/n747.jpg" />
          <h5>N747FL &#8211; 2020 Carbon Cub FX-3</h5>
          <ul>
            <li><span>Make:</span><span>CUBCRAFTERS</span></li>
            <li><span>Model:</span><span>CCX-2000 - Carbon Cub FX-3</span></li>
            <li><span>Year:</span><span>2020</span></li>
            <li><span>TTAF:</span><span>824 hrs</span></li>
            <li><span>TTE:</span><span>824 hrs</span></li>
            <li><span>Price:</span><span>$344,000</span></li>
          </ul>
        </a>
        <a href="https://cubcrafters.com/c/inventory/n49rp-piper/" class="column aircraft cf">
          <h5>N49RP &#8211; 2012 PA-18 Super Cub</h5>
          <ul>
            <li><span>Make:</span><span>PIPER</span></li>
            <li><span>Model:</span><span>PA-18-150</span></li>
            <li><span>Year:</span><span>2012</span></li>
            <li><span>Price:</span><span>$229,000</span></li>
          </ul>
        </a>
        <a href="https://cubcrafters.com/c/inventory/sold-nxcub/" class="column aircraft cf">
          <h5>SOLD &#8211; N292CC &#8211; 2022 NXCub</h5>
          <ul>
            <li><span>Make:</span><span>CUBCRAFTERS</span></li>
            <li><span>Model:</span><span>CC19-215 NXCub</span></li>
            <li><span>Price:</span><span>$459,000</span></li>
          </ul>
        </a>
        <a href="https://cubcrafters.com/c/inventory/n11gl-xcub/" class="column aircraft cf">
          <h5>REDUCED &#8211; N11GL &#8211; 2022 XCub</h5>
          <ul>
            <li><span>Make:</span><span>CUBCRAFTERS</span></li>
            <li><span>Model:</span><span>CCX-2300 XCUB</span></li>
            <li><span>TTAF:</span><span>Less than 100 TT</span></li>
            <li><span>Price:</span><span>$400,000</span></li>
          </ul>
        </a>
        """
        rows = parse_cubcrafters_html(page, "https://cubcrafters.com/c/inventory/")
        self.assertEqual([row["n_number"] for row in rows], ["N747FL", "N11GL"])
        self.assertEqual(rows[0]["model"], "Carbon Cub")
        self.assertEqual(rows[0]["variant"], "FX-3")
        self.assertEqual(rows[0]["ttaf"], "824")
        self.assertEqual(rows[0]["price"], "$344,000")
        self.assertEqual(rows[1]["model"], "XCub")
        self.assertEqual(rows[1]["ttaf"], "")
        self.assertEqual(rows[1]["price_drop"], "Price reduced")
        detail = """
        <h4>Overview</h4>
        <ul>
          <li><span>Location:</span><span>Chicago, IL</span></li>
          <li><span>Serial:</span><span>CCX-2000-0058</span></li>
          <li><span>Make:</span><span>CUBCRAFTERS</span></li>
          <li><span>Model:</span><span>CCX-2000 - Carbon Cub FX-3</span></li>
          <li><span>N Number:</span><span>N747FL</span></li>
          <li><span>TTAF:</span><span>824 hrs</span></li>
          <li><span>Engine:</span><span>CC363i Engine, 186HP</span></li>
        </ul>
        <h4>Description</h4>
        <p>31 inch Bushwheels and ready for skis.</p>
        <h4>Contact</h4>
        <div>Southern Cubs</div>
        """
        merged = parse_cubcrafters_detail(detail, rows[0])
        self.assertEqual(merged["serial_number"], "CCX-2000-0058")
        self.assertEqual(merged["city"], "Chicago")
        self.assertEqual(merged["state"], "IL")
        self.assertEqual(merged["engine_model"], "CC363i")
        self.assertIn("Bushwheels", merged["gear"])
        self.assertIn("Skis", merged["gear"])
        self.assertEqual(merged["seller"], "Southern Cubs")

    def test_barnstormers_keeps_cubcrafters_and_drops_other_cubs(self):
        page = """
        <div class="classified_single " data-adid="1">
          <a class="listing_header" href="/classified-1-fx.html">2022 CARBON CUB EX-3</a>
          <span class="action_phrase">FOR SALE</span>
          <span class="body">CubCrafters, 26 inch tundra tires, $349,900</span>
        </div>
        <div class="classified_single " data-adid="2">
          <a class="listing_header" href="/classified-2-piper.html">1977 PIPER SUPER CUB</a>
          <span class="action_phrase">FOR SALE</span>
          <span class="body">PA-18, $150,000</span>
        </div>
        <div class="classified_single " data-adid="3">
          <a class="listing_header" href="/classified-3-mackey.html">MACKEY SQ-4 ULTIMATE SUPER CUB</a>
          <span class="action_phrase">FOR SALE</span>
          <span class="body">$220,000</span>
        </div>
        <div class="classified_single " data-adid="4">
          <a class="listing_header" href="/classified-4-ferry.html">CUB PREBUYS AND FERRY PILOT</a>
          <span class="action_phrase">SERVICE</span>
          <span class="body">CubCrafters ferry flights</span>
        </div>
        <div class="classified_single " data-adid="5">
          <a class="listing_header" href="/classified-5-sr22.html">2019 CIRRUS SR22 G6</a>
          <span class="action_phrase">FOR SALE</span>
          <span class="body">$500,000</span>
        </div>
        """
        rows = parse_barnstormers_html(page, "https://www.barnstormers.com/cat_search.php", ("cubcrafters",))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["family"], "cubcrafters")
        self.assertEqual(rows[0]["model"], "Carbon Cub")
        self.assertEqual(rows[0]["variant"], "EX-3")
        self.assertIn("Tundra tires", rows[0]["gear"])
        cirrus = parse_barnstormers_html(page, "https://www.barnstormers.com/cat_search.php", ("sr22", "sr20"))
        self.assertEqual(len(cirrus), 1)
        self.assertEqual(cirrus[0]["family"], "sr22")

    def test_cub_search_uses_cubcrafters_sources_and_not_the_cirrus_feed(self):
        cubs = [name for name, _label, _fn in sources_for(("cubcrafters",))]
        self.assertEqual(cubs[0], "cubcrafters")
        self.assertNotIn("cirrus", cubs)
        self.assertIn("aso", cubs)
        self.assertIn("globalair", cubs)
        self.assertIn("aircraftdealer", cubs)
        self.assertIn("barnstormers", cubs)
        self.assertIn("controller", cubs)
        cirrus = [name for name, _label, _fn in sources_for(("sr22", "sr20"))]
        self.assertEqual(cirrus[0], "cirrus")
        self.assertNotIn("cubcrafters", cirrus)


class Pa28Tests(unittest.TestCase):
    def test_180_and_181_are_kept_and_other_cherokees_are_not(self):
        archer = apply_listing({
            "title": "2001 Piper Archer III",
            "model": "PA-28-181",
            "description": "Lycoming O-360. 420 SMOH. Garmin GTN 750. Garmin G5. ADS-B In/Out.",
            "n_number": "N181AR",
        })
        self.assertEqual(archer["family"], "pa28-180-181")
        self.assertEqual(archer["model"], "PA-28-181")
        self.assertEqual(archer["variant"], "Archer III")
        self.assertEqual(archer["generation"], "")
        self.assertEqual(archer["engine_make"], "Lycoming")
        self.assertEqual(archer["engine_model"], "O-360")
        self.assertEqual(archer["engine_hours"], "420")
        self.assertEqual(archer["engine_time_type"], "SMOH")
        self.assertIn("GTN 750", archer["avionics"])
        self.assertIn("Garmin G5", archer["avionics"])

        cherokee = apply_listing({"title": "1968 PIPER CHEROKEE 180D", "n_number": "N180D"})
        self.assertEqual(cherokee["family"], "pa28-180-181")
        self.assertEqual(cherokee["model"], "Cherokee 180D")
        coded = apply_listing({"title": "1966 PIPER CHEROKEE PA-28-180C"})
        self.assertEqual(coded["model"], "PA-28-180")
        self.assertIn("C", coded["variant"])
        challenge = apply_listing({"title": "1973 Piper Cherokee 180 Challenger"})
        self.assertEqual(challenge["family"], "pa28-180-181")
        self.assertIn("Challenger", challenge["variant"] + challenge["model"])
        self.assertEqual(apply_listing({"title": "2019 Piper Archer LX PA-28-181"})["variant"], "Archer LX")
        self.assertEqual(apply_listing({"title": "1979 PIPER ARCHER II"})["model"], "Archer II")
        pilot = apply_listing({"title": "2021 Piper Pilot 100i PA-28-181"})
        self.assertEqual(pilot["model"], "PA-28-181")
        self.assertIn("Pilot 100i", pilot["variant"])
        self.assertEqual(apply_listing({"title": "1974 Piper Cherokee Archer 180"})["model"], "Cherokee Archer")

        for title in (
            "1968 Piper Cherokee 140",
            "1968 Piper Cherokee 140 180 HP Conversion",
            "1978 Piper Warrior II PA-28-161",
            "1969 Cherokee PA-28-235",
            "1975 Piper Dakota PA-28-236",
            "2001 Piper Arrow PA-28R-201",
            "1968 Piper Arrow PA-28R-180",
            "1972 Piper Cherokee Cruiser",
            "1969 PIPER CHEROKEE 235",
        ):
            self.assertEqual(apply_listing({"title": title})["family"], "", title)
        self.assertEqual(apply_listing({"title": "2019 Cirrus SR22 G6"})["family"], "sr22")

    def test_barnstormers_archer_search_drops_ferry_parts_and_warriors(self):
        page = """
        <div class="classified_single " data-adid="1">
          <a class="listing_header" href="/classified-1-archer.html">1977 PIPER ARCHER II</a>
          <span class="action_phrase">FOR SALE</span>
          <span class="body">PA-28-181, 2400 TT, 300 SMOH, $139,000</span>
        </div>
        <div class="classified_single " data-adid="2">
          <a class="listing_header" href="/classified-2-cher.html">1972 CHER 180</a>
          <span class="action_phrase">FOR SALE</span>
          <span class="body">Nice Cherokee. $55,000</span>
        </div>
        <div class="classified_single " data-adid="3">
          <a class="listing_header" href="/classified-3-warrior.html">1978 PIPER WARRIOR II</a>
          <span class="action_phrase">FOR SALE</span>
          <span class="body">PA-28-161, $69,000</span>
        </div>
        <div class="classified_single " data-adid="4">
          <a class="listing_header" href="/classified-4-ferry.html">INSURED PIPER FERRY PILOT</a>
          <span class="action_phrase">SERVICE</span>
          <span class="body">Archer and Cherokee ferry flights</span>
        </div>
        <div class="classified_single " data-adid="5">
          <a class="listing_header" href="/classified-5-140.html">1968 PIPER CHEROKEE 140 180 HP</a>
          <span class="action_phrase">FOR SALE</span>
          <span class="body">Conversion. $42,000</span>
        </div>
        """
        rows = parse_barnstormers_html(page, "https://www.barnstormers.com/cat_search.php", ("pa28-180-181",))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["model"], "PA-28-181")
        self.assertIn("Archer II", rows[0]["variant"])
        self.assertEqual(rows[1]["model"], "Cherokee 180")
        self.assertEqual(rows[0]["family"], "pa28-180-181")
        self.assertEqual(rows[0]["engine_hours"], "300")
        self.assertEqual(rows[0]["engine_time_type"], "SMOH")
        self.assertEqual(rows[0]["ttaf"], "2400")
        servos = apply_listing({
            "title": "GARMIN GMC 507 2 SERVOS A/P",
            "description": "Guaranteed. PA28-181.",
            "price": "$15,000",
        })
        self.assertEqual(servos["family"], "")
        registered = apply_listing({
            "title": "1977 PIPER ARCHER | N38840",
            "description": "PA-28-181. Lycoming O-360-N4M. 1098 TT.",
        })
        self.assertEqual(registered["n_number"], "N38840")
        self.assertEqual(registered["model"], "PA-28-181")

    def test_pa28_search_does_not_use_the_cirrus_feed(self):
        names = [name for name, _label, _fn in sources_for(("pa28-180-181",))]
        self.assertNotIn("cirrus", names)
        self.assertNotIn("cubcrafters", names)
        for source in ("aso", "globalair", "aircraftdealer", "barnstormers", "controller"):
            self.assertIn(source, names)


class ReportTests(unittest.TestCase):
    def test_report_shows_the_saved_time_prices_and_sr20_toggle(self):
        rows = merge_rows([
            aircraft(price="$500,000", source="aso", listing_id="aso:1", link="https://www.aso.com/aircraft/1"),
            aircraft(price="$520,000"),
            aircraft(title="2016 Cirrus SR20 G3", n_number="N300EF", listing_id="cirrus:20", link="https://cirrusaircraft.com/20", price="$250,000", source="cirrus"),
        ])
        when = "2026-10-22T18:17:00+00:00"
        report = HERE / "output" / "report-test.html"
        try:
            build_report(rows, {
                "slug": "sr22",
                "title": "Cirrus SR22",
                "scraped_at": when,
                "warnings": ["Controller.com blocked automated access (Cloudflare challenge)"],
                "sources": {"cirrus": {"ok": True, "rows": 2}, "aso": {"ok": True, "rows": 1}},
            }, report, fresh_days=2, search_api="http://127.0.0.1:8766")
            html = report.read_text(encoding="utf-8")
        finally:
            if report.exists():
                report.unlink()
        self.assertIn("Data as of " + format_as_of(when), html)
        self.assertIn("Cloudflare challenge", html)
        self.assertIn("UPDATE", html)
        self.assertIn("refreshIfStale", html)
        self.assertIn('id="sr20"', html)
        self.assertIn('data-f="sr20"', html)
        self.assertNotIn('data-f="sr20" checked', html)
        self.assertNotIn('id="sr20" checked', html)
        self.assertIn("N100AB", html)
        self.assertIn("N300EF", html)
        self.assertIn("500000", html)
        self.assertIn("520000", html)
        self.assertIn("const FRESH_DAYS = 2", html)
        self.assertIn("{ key: 'mileage', label: 'Hours'", html)
        self.assertIn("{ key: 'vin', label: 'N-number'", html)
        self.assertNotIn(" mi.", html)
        self.assertIn('target="_blank"', html)
        self.assertIn("https://www.aso.com/aircraft/1", html)
        self.assertIn("https://cirrusaircraft.com/1", html)
        self.assertIn('data-href="', html)
        self.assertIn("window.open(link, '_blank', 'noopener')", html)
        self.assertIn("window.open(tr.getAttribute('data-href'), '_blank', 'noopener')", html)
        self.assertIn('class="title-link"', html)
        self.assertIn('class="thumb"', html)
        self.assertIn('"kind": "readme"', html)
        self.assertIn("127.0.0.1:8766", html)
        self.assertIn("boy-toy-pricer/aircraft/output/report.html", html)

    def test_readme_markdown_covers_setup_and_stays_html(self):
        html = markdown_to_html(
            "# Title\n\nSee **Hours** and `python3`.\n\n"
            "- one\n- two\n\n"
            "| A | B |\n| --- | --- |\n| 1 | 2 |\n\n"
            "```bash\necho hi\n```\n\n"
            "A [site](https://example.com/a).\n"
        )
        self.assertIn("<h1>Title</h1>", html)
        self.assertIn("<strong>Hours</strong>", html)
        self.assertIn("<code>python3</code>", html)
        self.assertIn("<li>one</li>", html)
        self.assertIn("<td>1</td>", html)
        self.assertIn("<pre><code>echo hi</code></pre>", html)
        self.assertIn('href="https://example.com/a"', html)
        self.assertNotIn("<script", html.lower())
        tab = readme_tab()
        self.assertEqual(tab["kind"], "readme")
        self.assertEqual(tab["slug"], "readme")
        self.assertEqual(tab["saved_slug"], "")
        self.assertEqual(tab["rows"], [])
        body = tab["html"]
        for phrase in (
            "Cirrus SR22",
            "Cirrus Vision Jet",
            "CubCrafters",
            "python3 -m pip install -r requirements.txt",
            "python3 -m playwright install chromium",
            "python3 refresh_searches.py --slug cubcrafters",
            "python3 search_server.py",
            "127.0.0.1:8766",
            "boy-toy-pricer/aircraft/output/report.html",
            "com.example.aircraft-scan",
            "Controller.com",
            "could not launch a browser",
            "Add a new airplane tab",
        ):
            self.assertIn(phrase, body, phrase)


if __name__ == "__main__":
    unittest.main()
