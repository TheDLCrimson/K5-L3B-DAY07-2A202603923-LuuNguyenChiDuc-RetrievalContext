"""Parsing of the human review CSV (src/review_sheet.py)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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


if __name__ == "__main__":
    unittest.main()
