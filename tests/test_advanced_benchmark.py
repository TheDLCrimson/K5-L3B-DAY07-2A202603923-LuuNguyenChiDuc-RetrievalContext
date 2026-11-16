"""The committed advanced benchmark passes its own verification and keeps its quotas."""
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.advanced.source import DATA_DIR
from src.advanced.verify_benchmark import TEST_MINIMUM, main


class AdvancedBenchmarkTest(unittest.TestCase):
    def setUp(self):
        self.questions = json.loads((DATA_DIR / "benchmark" / "questions.json").read_text(encoding="utf-8"))

    def test_verification_script_passes(self):
        self.assertEqual(main(), 0)

    def test_test_split_meets_the_challenge_quotas(self):
        test = [q for q in self.questions if q["split"] == "test"]
        self.assertGreaterEqual(len(test), 30)
        self.assertGreaterEqual(sum(q["answerable"] for q in test), 24)
        self.assertGreaterEqual(sum(not q["answerable"] for q in test), 6)
        counts = Counter(q["group"] for q in test if q["answerable"])
        for group, minimum in TEST_MINIMUM.items():
            self.assertGreaterEqual(counts[group], minimum, group)

    def test_no_evidence_leaks_into_question_text(self):
        for q in self.questions:
            if q["answerable"]:
                for e in q["evidence"]:
                    for value in (e["value"],):
                        self.assertNotIn(value.lower(), q["question"].lower(), q["id"])


if __name__ == "__main__":
    unittest.main()
