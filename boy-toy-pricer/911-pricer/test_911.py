#!/usr/bin/env python3
"""Porsche 911 searches, classifier, and generation filtering."""
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import porsche_911  # noqa: E402
from bat_sold_scraper import FIELDS as BAT_FIELDS  # noqa: E402
from merge_listings_v2 import FIELDS  # noqa: E402
from refresh_911 import refresh_search, searches  # noqa: E402
from saved_store_v2 import read_csv, source_path, write_csv  # noqa: E402

NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)


def listing(title, vin, **extra):
    row = {field: "" for field in FIELDS}
    row.update(listing_id=vin, site_code="cgu", title=title, price="$150,000", mileage="5,000 mi.",
               vin=vin, link=f"https://example.com/{vin}")
    row.update(extra)
    return row


class SearchTests(unittest.TestCase):
    def test_generation_tabs(self):
        found = {search["slug"]: search for search in searches()}
        self.assertEqual(list(found), ["992", "991", "997", "996", "993", "964", "g", "early"])
        for slug, search in found.items():
            self.assertEqual(search["classifier"], "911")
            self.assertEqual(search["generation"], slug)
            self.assertEqual(search["autotrader_urls"], [])
            self.assertTrue(search["bat_urls"], slug)
            for url in search["autotempest_urls"]:
                self.assertIn("make=porsche&model=911&minyear=", url)
        self.assertEqual(len(found["992"]["autotempest_urls"]), 7)
        self.assertEqual(found["early"]["bat_match"], ["\\b196[4-9]\\b;\\b197[0-3]\\b"])


class ClassifyTests(unittest.TestCase):
    def test_classify(self):
        cases = {
            "2018 Porsche 911 GT3 Touring 6-Speed": ("991", "991.2", "GT3 Touring", "Coupe", "Manual", "RWD"),
            "2023 Porsche 911 GT3 RS Weissach": ("992", "992.1", "GT3 RS", "Coupe", "PDK/Auto", "RWD"),
            "2025 Porsche 911 Carrera GTS Cabriolet": ("992", "992.2", "Carrera GTS", "Cabriolet", None, "RWD"),
            "2024 Porsche 911 Targa 4 GTS": ("992", "992.1", "Targa 4 GTS", "Targa", None, "AWD"),
            "2012 Porsche 911 Carrera S Coupe": ("991", "991.1", "Carrera S", "Coupe", None, "RWD"),
            "2012 Porsche 911 Carrera S Cabriolet": ("997", "997.2", "Carrera S", "Cabriolet", None, "RWD"),
            "2005 Porsche 911 Carrera 4S Cabriolet": ("996", None, "Carrera 4S", "Cabriolet", None, "AWD"),
            "1987 Porsche 911 Turbo Coupe": ("g", None, "Turbo", "Coupe", "Manual", "RWD"),
            "1997 Porsche 911 Turbo": ("993", None, "Turbo", None, None, "AWD"),
            "1989 Porsche 911 Carrera 4 Coupe": ("964", None, "Carrera 4", "Coupe", None, "AWD"),
            "1982 Porsche 911SC Targa": ("g", None, "SC", "Targa", "Manual", "RWD"),
            "1973 Porsche 911S 2.4 Coupe": ("early", None, "911S", "Coupe", "Manual", "RWD"),
            "2020 Porsche 911 Carrera 4S": ("992", "992.1", "Carrera 4S", None, None, "AWD"),
            "2020 Porsche 911 Turbo S Cabriolet": ("991", "991.2", "Turbo S", "Cabriolet", "PDK/Auto", "AWD"),
            "1992 Porsche 911 Carrera Coupe": ("964", None, "Carrera 2", "Coupe", None, "RWD"),
            "1996 Porsche 911 Carrera 2 Cabriolet": ("993", None, "Carrera", "Cabriolet", None, "RWD"),
            "1981 Porsche 911 Coupe": ("g", None, "SC", "Coupe", "Manual", "RWD"),
            "1987 Porsche 911 Coupe": ("g", None, "Carrera", "Coupe", "Manual", "RWD"),
            "1976 Porsche 911 Coupe": ("g", None, "911", "Coupe", "Manual", "RWD"),
        }
        for title, expected in cases.items():
            info = porsche_911.classify(title)
            got = tuple(info[key] for key in ("generation", "phase", "trim", "body", "gearbox", "drive"))
            self.assertEqual(got, expected, title)

    def test_not_a_road_911(self):
        for title in ["2022 Porsche 911 GT3 Cup", "1997 Porsche Boxster", "2005 Porsche Carrera GT"]:
            self.assertIsNone(porsche_911.classify(title)["generation"], title)

    def test_gearbox_and_options_from_description(self):
        info = porsche_911.classify("2024 Porsche 911 Carrera T Coupe",
                                    "7-Speed Manual, Paint-to-Sample Brewster Green, owner's manuals, PCCB")
        self.assertEqual(info["gearbox"], "Manual")
        self.assertEqual(info["options"], ["Paint to Sample", "Ceramic brakes"])
        both = porsche_911.classify("2021 Porsche 911 Carrera S", "PDK with manual mode, 6-speed manual available")
        self.assertIsNone(both["gearbox"])

    def test_tags(self):
        row = {"title": "2022 Porsche 911 GT3 Touring", "description": "6-speed manual, Weissach"}
        self.assertEqual(porsche_911.tags(row), ["992.1", "GT3 Touring", "Coupe", "Manual", "RWD", "Weissach"])
        self.assertEqual(porsche_911.tags({"title": "2022 Porsche 911 GT3 Cup"}), [])


class RefreshTests(unittest.TestCase):
    def test_overlap_years_stay_in_their_generation(self):
        """A 2012 window returns 991 and 997 cars; the 997 tab keeps only the 997s."""
        def scrape_at(urls, dest, cache):
            write_csv(dest, [
                listing("2012 Porsche 911 Carrera S Coupe", "WP0AB2A99CS120991"),
                listing("2012 Porsche 911 Turbo S Cabriolet", "WP0CD2A99CS770997"),
                listing("2022 Porsche 911 GT3 Cup", "WP0ZZZ99ZNS199001"),
            ], FIELDS)

        def scrape_bat(urls, matches, dest, cache, since_days=0):
            self.assertEqual(since_days, porsche_911.BAT_SINCE_DAYS)
            rows = [{field: "" for field in BAT_FIELDS} for _ in range(2)]
            rows[0].update(title="2011 Porsche 911 GT3 RS 4.0", price="$500,000", listing_id="b1")
            rows[1].update(title="2016 Porsche 911 GT3 RS", price="$200,000", listing_id="b2")
            write_csv(dest, rows, BAT_FIELDS)

        tab = searches("997")[0]
        with tempfile.TemporaryDirectory() as tmp:
            result = refresh_search(tab, now=NOW, root=Path(tmp), fresh_days=2,
                                    scrape_autotempest=scrape_at, scrape_bat=scrape_bat)
            self.assertTrue(result["ok"])
            merged = read_csv(source_path("997", "merged", Path(tmp)))
            self.assertEqual([row["vin"] for row in merged], ["WP0CD2A99CS770997"])
            bat = read_csv(source_path("997", "bat", Path(tmp)))
            self.assertEqual([row["listing_id"] for row in bat], ["b1"])


if __name__ == "__main__":
    unittest.main()
