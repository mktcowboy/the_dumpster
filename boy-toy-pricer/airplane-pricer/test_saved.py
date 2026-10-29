#!/usr/bin/env python3
"""Saved snapshots, freshness, and a failed source keeping its last file."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fetch import challenge_reason  # noqa: E402
from listings import apply_listing, blank_row  # noqa: E402
from refresh_searches import refresh_search  # noqa: E402
from saved_store import fresh_days, is_fresh, load_meta, read_csv, source_path, write_csv  # noqa: E402
from listings import FIELDS  # noqa: E402
from fetch import ScrapeError  # noqa: E402

NOW = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)


def listing(**overrides):
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


class FreshnessTests(unittest.TestCase):
    def test_a_couple_of_days_is_still_fresh(self):
        meta = {"scraped_at": (NOW - timedelta(days=2)).isoformat()}
        self.assertTrue(is_fresh(meta, 2, NOW))

    def test_older_than_the_window_is_stale(self):
        meta = {"scraped_at": (NOW - timedelta(days=2, seconds=1)).isoformat()}
        self.assertFalse(is_fresh(meta, 2, NOW))

    def test_missing_snapshot_is_stale(self):
        self.assertFalse(is_fresh(None, 2, NOW))
        self.assertFalse(is_fresh({"scraped_at": NOW.isoformat()}, 2, NOW, merged_exists=False))

    def test_window_can_be_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "freshness.json").write_text(json.dumps({"fresh_days": 5}), encoding="utf-8")
            self.assertEqual(fresh_days(root=root), 5)
            self.assertEqual(fresh_days(explicit=1, root=root), 1)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def scrapers(self, aso):
        def cirrus(_fetch):
            self.calls.append("cirrus")
            return [listing()]

        def aso_fn(_fetch):
            self.calls.append("aso")
            return aso()

        return [("cirrus", "Cirrus", cirrus), ("aso", "ASO", aso_fn)]

    def refresh(self, aso, **kwargs):
        kwargs.setdefault("now", NOW)
        kwargs.setdefault("root", self.root)
        kwargs.setdefault("fresh_days", 2)
        return refresh_search(scrapers=self.scrapers(aso), **kwargs)

    def test_fresh_saved_data_is_not_scraped_again(self):
        first = self.refresh(lambda: [listing(source="aso", listing_id="aso:1", price="$480,000", link="https://www.aso.com/1")])
        self.assertEqual(self.calls, ["cirrus", "aso"])
        self.calls.clear()
        second = self.refresh(lambda: (_ for _ in ()).throw(AssertionError("scraped")), now=NOW + timedelta(days=1))
        self.assertTrue(second["skipped"])
        self.assertEqual(self.calls, [])
        self.assertEqual(second["scraped_at"], first["scraped_at"])

    def test_blocked_source_keeps_the_saved_rows_and_warns(self):
        self.refresh(lambda: [listing(
            source="aso", listing_id="aso:1", price="$480,000", link="https://www.aso.com/1",
        )])
        saved_price = read_csv(source_path("sr22", "aso", self.root))[0]["price"]

        def blocked():
            raise ScrapeError("Cloudflare challenge")

        result = self.refresh(blocked, now=NOW + timedelta(days=3))
        self.assertTrue(result["ok"])
        self.assertTrue(any("ASO failed" in warning for warning in result["warnings"]))
        self.assertEqual(read_csv(source_path("sr22", "aso", self.root))[0]["price"], saved_price)
        merged = read_csv(source_path("sr22", "merged", self.root))
        self.assertEqual(len(merged), 1)
        self.assertIn("aso", merged[0]["sources"])
        meta = load_meta("sr22", self.root)
        self.assertIn("ASO failed", " ".join(meta["warnings"]))
        self.assertTrue(meta["sources"]["cirrus"]["ok"])

    def test_an_empty_scrape_does_not_wipe_a_real_snapshot(self):
        regs = ["N101AB", "N102AB", "N103AB", "N104AB", "N105AB", "N106AB"]
        saved = [listing(listing_id=f"cirrus:{i}", n_number=reg, link=f"https://cirrusaircraft.com/{i}") for i, reg in enumerate(regs)]

        def cirrus_full(_fetch):
            return saved

        def aso(_fetch):
            return [listing(source="aso", listing_id="aso:1", price="$480,000", link="https://www.aso.com/1", n_number="N101AB")]

        refresh_search(
            now=NOW, root=self.root, fresh_days=2,
            scrapers=[("cirrus", "Cirrus", cirrus_full), ("aso", "ASO", aso)],
        )
        self.assertEqual(len(read_csv(source_path("sr22", "cirrus", self.root))), 6)

        def cirrus_empty(_fetch):
            return []

        result = refresh_search(
            now=NOW + timedelta(days=3), root=self.root, fresh_days=2,
            scrapers=[("cirrus", "Cirrus", cirrus_empty), ("aso", "ASO", aso)],
        )
        self.assertTrue(any("Cirrus failed" in warning for warning in result["warnings"]))
        self.assertEqual(len(read_csv(source_path("sr22", "cirrus", self.root))), 6)
        self.assertIn("N106AB", {row["n_number"] for row in read_csv(source_path("sr22", "merged", self.root))})

    def test_a_failed_refresh_with_nothing_saved_does_not_invent_rows(self):
        def broken(_fetch):
            raise ScrapeError("timeout")

        result = refresh_search(
            now=NOW, root=self.root, fresh_days=2,
            scrapers=[("cirrus", "Cirrus", broken)],
        )
        self.assertFalse(result["ok"])
        self.assertFalse(source_path("sr22", "merged", self.root).exists())
        self.assertIn("no saved Cirrus listings", result["warnings"][0])


class VisionJetSnapshotTests(unittest.TestCase):
    def test_vision_jet_snapshot_does_not_replace_the_sr22_folder(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        self.addCleanup(tmp.cleanup)

        def jets(_fetch):
            return [listing(
                title="2022 Cirrus Vision Jet G2+",
                n_number="N50VJ",
                listing_id="cirrus:9",
                link="https://cirrusaircraft.com/jet",
                price="$2,400,000",
                ttaf="300",
            )]

        result = refresh_search(
            {"slug": "sf50", "title": "Cirrus Vision Jet", "families": ("sf50",)},
            now=NOW, root=root, fresh_days=2,
            scrapers=[("cirrus", "Cirrus", jets)],
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["slug"], "sf50")
        rows = read_csv(source_path("sf50", "merged", root))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["n_number"], "N50VJ")
        self.assertEqual(rows[0]["family"], "sf50")
        self.assertEqual(rows[0]["model"], "SF50")
        self.assertFalse(source_path("sr22", "merged", root).exists())


class CubCraftersSnapshotTests(unittest.TestCase):
    def test_cubcrafters_snapshot_does_not_replace_the_sr22_folder(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        self.addCleanup(tmp.cleanup)

        def cubs(_fetch):
            return [listing(
                title="2020 CubCrafters Carbon Cub FX-3",
                n_number="N747FL",
                listing_id="cubcrafters:n747",
                link="https://cubcrafters.com/c/inventory/n747fl/",
                price="$344,000",
                ttaf="824",
                source="cubcrafters",
            )]

        result = refresh_search(
            {"slug": "cubcrafters", "title": "CubCrafters", "families": ("cubcrafters",)},
            now=NOW, root=root, fresh_days=2,
            scrapers=[("cubcrafters", "CubCrafters", cubs)],
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["slug"], "cubcrafters")
        rows = read_csv(source_path("cubcrafters", "merged", root))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["n_number"], "N747FL")
        self.assertEqual(rows[0]["family"], "cubcrafters")
        self.assertEqual(rows[0]["model"], "Carbon Cub")
        self.assertEqual(rows[0]["variant"], "FX-3")
        self.assertFalse(source_path("sr22", "merged", root).exists())
        self.assertFalse(source_path("sf50", "merged", root).exists())


class Pa28SnapshotTests(unittest.TestCase):
    def test_pa28_snapshot_does_not_replace_the_other_folders(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        self.addCleanup(tmp.cleanup)

        def archers(_fetch):
            return [listing(
                title="2001 Piper Archer III PA-28-181",
                n_number="N181AR",
                listing_id="aso:181",
                link="https://www.aso.com/aircraft/181",
                price="$189,000",
                ttaf="2400",
                source="aso",
            )]

        result = refresh_search(
            {"slug": "pa28-180-181", "title": "Piper PA-28-180/181", "families": ("pa28-180-181",)},
            now=NOW, root=root, fresh_days=2,
            scrapers=[("aso", "ASO", archers)],
        )
        self.assertTrue(result["ok"])
        rows = read_csv(source_path("pa28-180-181", "merged", root))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["family"], "pa28-180-181")
        self.assertEqual(rows[0]["model"], "PA-28-181")
        self.assertEqual(rows[0]["variant"], "Archer III")
        self.assertFalse(source_path("sr22", "merged", root).exists())
        self.assertFalse(source_path("cubcrafters", "merged", root).exists())


class BlockTests(unittest.TestCase):
    def test_challenge_pages_are_recognized(self):
        self.assertEqual(challenge_reason("Just a moment...", 403, "cloudflare"), "Cloudflare challenge")
        self.assertEqual(challenge_reason("ERROR: The request could not be satisfied", 403, ""), "bot check")
        self.assertEqual(challenge_reason("Error Page | eBay", 403, "robot"), "blocked automated access")
        self.assertEqual(challenge_reason("Cirrus SR22 for sale", 200, "<article>SR22</article>"), "")


if __name__ == "__main__":
    unittest.main()
