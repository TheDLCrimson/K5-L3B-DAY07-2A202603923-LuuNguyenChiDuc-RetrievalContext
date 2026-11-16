"""Extraction helpers and the committed extraction of the advanced-challenge report."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.advanced.check_crops import clipped
from src.advanced.describe import numbers
from src.advanced.extract import EXCLUDED, poor_markdown, split_table, squeeze_markdown
from src.advanced.source import DATA_DIR, PDF_PATH


class HelperTest(unittest.TestCase):
    def test_split_table_repeats_the_header_in_every_part(self):
        md = "\n".join(["|a|b|", "|---|---|"] + [f"|row {i}|{i}|" for i in range(40)])
        parts = split_table(md, limit=120)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(p.startswith("|a|b|\n|---|---|") for p in parts))
        self.assertEqual(sum(p.count("|row ") for p in parts), 40)

    def test_rebuilt_rows_keep_their_header_lines(self):
        rows = ["Đường cơ sở RCP | 2.6", " | 2022 | 2030 | 2040 | 2050"] + [f"Hàng {i} | 1 | 2 | 3 | 4" for i in range(30)]
        parts = split_table("\n".join(rows), limit=200)
        self.assertTrue(all(p.startswith("Đường cơ sở RCP | 2.6\n | 2022") for p in parts))

    def test_empty_columns_are_dropped(self):
        self.assertEqual(squeeze_markdown("|a||b|\n|---|---|---|\n|1||2|"), "|a|b|\n|---|---|\n|1|2|")

    def test_packed_columns_mark_a_table_as_poor(self):
        self.assertTrue(poor_markdown("|x|y|\n|---|---|\n|1<br>2<br>3|4<br>5|"))
        self.assertFalse(poor_markdown("|x|y|\n|---|---|\n|1|2|\n|3|4|"))

    def test_numbers_are_normalised_across_formats(self):
        self.assertEqual(numbers("4.219 triệu, 12,0% và -0,23"), {"4219", "12.0", "0.23"})


class CommittedExtractionTest(unittest.TestCase):
    def setUp(self):
        self.chunks = json.loads((DATA_DIR / "chunks.json").read_text(encoding="utf-8"))

    def test_every_numbered_figure_and_table_is_a_region_with_a_crop(self):
        labels = {c["label"] for c in self.chunks if c["label"]}
        self.assertEqual({f"Hình {i}" for i in range(1, 23)} | {f"Bảng {i}" for i in range(1, 7)}, labels)
        for c in self.chunks:
            if c["crop"]:
                self.assertTrue((DATA_DIR / c["crop"]).exists(), c["crop"])

    def test_ids_are_unique_and_pages_in_range(self):
        ids = [c["id"] for c in self.chunks]
        self.assertEqual(len(ids), len(set(ids)))
        pages = {c["page"] for c in self.chunks}
        self.assertFalse(pages & set(EXCLUDED))
        self.assertTrue(all(1 <= p <= 103 for p in pages))

    def test_every_region_has_a_description(self):
        regions = json.loads((DATA_DIR / "descriptions.json").read_text(encoding="utf-8"))["regions"]
        crops = {c["crop"] for c in self.chunks if c["crop"]}
        self.assertEqual(crops, set(regions))
        self.assertTrue(all(r["description"].strip() for r in regions.values()))

    @unittest.skipUnless(PDF_PATH.exists(), "source PDF not downloaded (python -m src.advanced.source)")
    def test_no_crop_cuts_a_line_of_text_at_its_edges(self):
        import pymupdf

        self.assertEqual(clipped(pymupdf.open(PDF_PATH), self.chunks), [])

    @unittest.skipUnless(PDF_PATH.exists(), "source PDF not downloaded (python -m src.advanced.source)")
    def test_figure_regions_stop_at_their_source_line(self):
        import pymupdf

        page = pymupdf.open(PDF_PATH)[58]  # Hình 14: the map's clip path reaches past the source line
        h14 = next(c for c in self.chunks if c["label"] == "Hình 14")
        source = page.search_for("Nguồn: Ngân hàng Thế giới dựa trên thông tin của chính phủ")[0]
        self.assertLess(h14["bbox"][3], source.y1 + 5)


if __name__ == "__main__":
    unittest.main()
