"""Parsing of the human review CSV (src/review_sheet.py)."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import review_sheet
from src.review_sheet import grade, parse_support


class ReviewCsvTest(unittest.TestCase):
    def test_support_follows_the_trace_order(self):
        self.assertEqual(parse_support("b=n; a=Y", ["a", "b"], "x"), [True, False])
        self.assertEqual(parse_support("", [], "x"), [])

    def test_missing_extra_or_blank_citation_labels_fail(self):
        for cell in ("a=y", "a=y; b=y; c=n", "a=y; b="):
            with self.assertRaises(ValueError):
                parse_support(cell, ["a", "b"], "x")

    def test_grades_must_be_0_1_or_2(self):
        self.assertEqual(grade(" 2 ", "x"), 2)
        for cell in ("", "3", "1.5"):
            with self.assertRaises(ValueError):
                grade(cell, "x")


class SheetOverwriteTest(unittest.TestCase):
    def test_existing_labels_leave_the_sheet_and_the_csv_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "test"
            out.mkdir()
            (out / "review_labels.csv").write_text("labels", encoding="utf-8")
            (out / "review_sheet.md").write_text("sheet", encoding="utf-8")
            with mock.patch.object(review_sheet, "OUT_DIR", Path(tmp)), self.assertRaises(SystemExit):
                review_sheet.sheet("test", ["A0_dense"])
            self.assertEqual((out / "review_labels.csv").read_text(encoding="utf-8"), "labels")
            self.assertEqual((out / "review_sheet.md").read_text(encoding="utf-8"), "sheet")


if __name__ == "__main__":
    unittest.main()
