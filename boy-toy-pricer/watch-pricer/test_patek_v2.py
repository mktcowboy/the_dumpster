#!/usr/bin/env python3
"""Offline checks for reference parsing and the cross-site merge. python3 -m pytest test_patek_v2.py"""
import json

from merge_listings_v2 import merge_rows
from watch_common_v2 import parse_reference, variant_for


def test_reference_forms():
    assert parse_reference("57111A010") == "5711/1A-010"
    assert parse_reference("Steel Mens Watch 5711 5711A Box Papers") == "5711/1A"
    assert parse_reference("5711R-001") == "5711R-001"
    assert parse_reference("5711/113P-001") == "5711/113P-001"
    assert parse_reference("5712R-001") == ""
    # first field wins; a later one can only add detail
    assert parse_reference("Nautilus White Gold 5711G", "alt text 5711/1A-001") == "5711G"
    assert parse_reference("5711 5711A", "5711/1A-010") == "5711/1A-010"


def test_variants():
    assert variant_for("5711/1A-014").startswith("5711/1A-014")
    assert variant_for("5711/1A", "olive green dial").startswith("5711/1A-014")
    assert variant_for("5711", "18k white gold").startswith("5711G")


def _row(site, lid, price, seller="", year="", variant="V"):
    return {"site_code": site, "listing_id": lid, "price": str(price), "seller": seller,
            "year": year, "variant": variant, "status": "For sale"}


def test_dealer_folds_into_its_own_chrono24_listing():
    rows = [_row("chrono24", "1", 599950, "The 1916 Company"),
            _row("the1916", "a", 599950, "The 1916 Company (WatchBox)")]
    out = merge_rows(rows)
    assert len(out) == 1 and out[0]["site_code"] == "chrono24,the1916"
    assert len(json.loads(out[0]["sources"])) == 2


def test_price_match_with_different_seller_stays_apart():
    rows = [_row("chrono24", "1", 101069, "HONGKONG TRADE"), _row("swe", "s", 101260, "Swiss Watch Expo")]
    assert len(merge_rows(rows)) == 2


def test_two_chrono24_listings_never_merge():
    rows = [_row("chrono24", "1", 100000, "A"), _row("chrono24", "2", 100000, "A")]
    assert len(merge_rows(rows)) == 2


def test_dealers_merge_on_price_and_year():
    rows = [_row("bobs", "b", 100000, "Bob's", "2018"), _row("swe", "s", 101000, "SWE", "2018"),
            _row("davidsw", "d", 101000, "DavidSW", "2019")]
    out = merge_rows(rows)
    assert len(out) == 2


# ------------------------------------------------------------------ Aquanaut
from models_v2 import MODELS, aq_reference  # noqa: E402

AQ = MODELS["aquanaut"]


def test_aquanaut_references():
    assert aq_reference("Aquanaut 5168G010") == "5168G-010"
    assert aq_reference("5267/200A-011 Luce") == "5267/200A-011"
    assert aq_reference("Aquanaut 5167/1A") == "5167/1A"
    assert aq_reference("Nautilus 5711/1A-010") == ""


def test_aquanaut_keeps_only_blue_or_green():
    assert AQ.finish({"title": "Aquanaut 5168G-010"}, "t")["dial"] == "Green"
    assert AQ.finish({"title": "Aquanaut 5168G-001", "dial": "Green"}, "t")["dial"] == "Blue"  # reference wins
    assert AQ.finish({"title": "Aquanaut 5167A-001"}, "t") is None  # black
    assert AQ.finish({"title": "Aquanaut 5167A", "dial": "Blue"}, "t")["variant"] == "5167A steel, strap · Blue"
    assert AQ.finish({"title": "Patek Aquanaut", "dial_hint": "Green"}, "t")["reference"] == "Aquanaut (ref. not given)"


def test_chrono24_scope_of_delivery():
    from chrono24_scraper_v2 import scope_to_bp
    assert scope_to_bp("Original box, original papers") == "Box & papers"
    assert scope_to_bp("No original box, no original papers") == "Watch only"
    assert scope_to_bp("Original papers, no original box") == "Papers"
    assert scope_to_bp("Original box, no original papers") == "Box"
