"""Checks for the Day 6 connection helpers, the hit rule, the question adapter and the verifier.

No database or model is needed: these run on small fixtures and on the committed exports.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.build_benchmark import QUESTIONS_PATH, convert_day6
from src.day6 import to_chunk
from src.evidence import any_hit, evidence_hit
from src.export_day6 import CHUNKS_PATH, INFO_PATH, load_chunks
from src.verify_benchmark import verify

QUOTE = "phải đăng ký tại cơ quan đăng ký đất đai"


def chunk(cid, text, source="ldd2013", page=10, page_end=10, year=2013, articles=(1,)):
    return {"id": cid, "text": text, "source_id": source, "source": f"{source}.pdf", "page": page,
            "metadata": {"page_end": page_end, "year": year, "articles": list(articles)}}


def answerable(qid, split, articles_chunk, question="Câu hỏi?", year=None, evidence=QUOTE):
    return {"id": qid, "split": split, "answerable": True, "question": question,
            "filter": {"year": year} if year else None,
            "gold": [{"source_id": articles_chunk["source_id"], "page": articles_chunk["page"],
                      "evidence": evidence}]}


def unanswerable(qid, split, term="Hà Nội", matches=0):
    return {"id": qid, "split": split, "answerable": False, "question": "Không có?",
            "absence_reason": "checked", "absence_check": [{"term": term, "matches": matches}]}


def minimal_set(dev_chunk, test_chunk):
    qs = [answerable(f"d{i}", "dev", dev_chunk) for i in range(15)]
    qs += [answerable(f"t{i}", "test", test_chunk) for i in range(5)]
    qs += [unanswerable(f"du{i}", "dev") for i in range(2)] + [unanswerable(f"tu{i}", "test") for i in range(2)]
    return qs


class EvidenceHitTest(unittest.TestCase):
    def test_chunk_starting_a_page_early_still_hits(self):
        c = chunk("c", "Điều 1.\n" + QUOTE + " và có hiệu lực", page=9, page_end=10)
        self.assertTrue(evidence_hit(c, {"source_id": "ldd2013", "page": 10, "evidence": QUOTE}))

    def test_whitespace_differences_are_ignored(self):
        c = chunk("c", "phải đăng ký  tại\ncơ quan đăng ký đất đai")
        self.assertTrue(evidence_hit(c, {"source_id": "ldd2013", "page": 10, "evidence": QUOTE}))

    def test_wrong_source_page_or_partial_quote_misses(self):
        c = chunk("c", QUOTE, page=10, page_end=11)
        self.assertFalse(evidence_hit(c, {"source_id": "ldd2024_cb363", "page": 10, "evidence": QUOTE}))
        self.assertFalse(evidence_hit(c, {"source_id": "ldd2013", "page": 12, "evidence": QUOTE}))
        self.assertFalse(evidence_hit(c, {"source_id": "ldd2013", "page": 10, "evidence": QUOTE + " Sổ"}))

    def test_any_alternative_is_enough(self):
        c = chunk("c", QUOTE, source="ldd2024_cb363", year=2024)
        golds = [{"source_id": "ldd2013", "page": 10, "evidence": QUOTE},
                 {"source_id": "ldd2024_cb363", "page": 10, "evidence": QUOTE}]
        self.assertTrue(any_hit(c, golds))


class AdapterTest(unittest.TestCase):
    def test_alternative_gold_is_kept(self):
        day6 = {"id": "q07", "split": "dev", "type": "dien_dat_lai", "question": "Q?", "expected_answer": "A",
                "gold_source_id": "ldd2013", "gold_page": 34, "evidence_quote": "x", "filter": None,
                "alternative_gold": [{"source_id": "ldd2024_cb363", "page": 81, "evidence_quote": "y"}]}
        q = convert_day6(day6, "benchmark/questions.json")
        self.assertEqual(q["gold"], [{"source_id": "ldd2013", "page": 34, "evidence": "x"},
                                     {"source_id": "ldd2024_cb363", "page": 81, "evidence": "y"}])
        self.assertEqual((q["split"], q["answerable"], q["origin"]["day6_split"]), ("dev", True, "dev"))

    def test_db_row_maps_to_lab7_chunk(self):
        row = {"chunk_id": "B-ldd2013-0001", "document_id": "ldd2013", "source": "f.pdf", "page": 1,
               "page_end": 2, "year": 2013, "law_number": "45/2013/QH13", "article": 2, "chapter": "I",
               "text": "t", "metadata": {"articles": [2], "strategy": "B"}}
        c = to_chunk(row)
        self.assertEqual((c["id"], c["source_id"], c["page"]), ("B-ldd2013-0001", "ldd2013", 1))
        self.assertEqual((c["metadata"]["page_end"], c["metadata"]["articles"]), (2, [2]))


class VerifierTest(unittest.TestCase):
    def setUp(self):
        self.dev_chunk = chunk("a", QUOTE + " Hà Nội không có", articles=(5,))
        self.test_chunk = chunk("b", QUOTE, page=20, page_end=20, articles=(6,))
        self.chunks = [self.dev_chunk, self.test_chunk]

    def test_minimal_valid_set_passes(self):
        qs = minimal_set(self.dev_chunk, self.test_chunk)
        qs = [q if q["answerable"] else unanswerable(q["id"], q["split"], matches=1) for q in qs]
        self.assertEqual(verify(qs, self.chunks)[1], [])

    def test_too_few_questions_fail(self):
        problems = verify([answerable("d0", "dev", self.dev_chunk)], self.chunks)[1]
        self.assertTrue(any("needs 15" in p for p in problems))

    def test_test_gold_on_a_dev_article_fails(self):
        qs = minimal_set(self.dev_chunk, self.dev_chunk)
        self.assertIn("test and dev gold share 2013 Điều 5", verify(qs, self.chunks)[1])

    def test_filter_must_be_named_in_the_question(self):
        qs = minimal_set(self.dev_chunk, self.test_chunk)
        qs[0] = answerable("d0", "dev", self.dev_chunk, year=2013)
        self.assertIn("d0: filter year 2013 is not named in the question", verify(qs, self.chunks)[1])
        qs[0] = answerable("d0", "dev", self.dev_chunk, year=2013, question="Theo Luật Đất đai 2013, ...?")
        self.assertFalse(any(p.startswith("d0:") for p in verify(qs, self.chunks)[1]))

    def test_copied_evidence_and_missing_evidence_fail(self):
        qs = minimal_set(self.dev_chunk, self.test_chunk)
        qs[0] = answerable("d0", "dev", self.dev_chunk, question=f"Có {QUOTE} không?")
        qs[1] = answerable("d1", "dev", self.dev_chunk, evidence="không có trong chunk")
        problems = verify(qs, self.chunks)[1]
        self.assertIn("d0: evidence copied into the question", problems)
        self.assertIn("d1: evidence not found on ldd2013 p10", problems)

    def test_stale_absence_count_fails(self):
        qs = minimal_set(self.dev_chunk, self.test_chunk)
        problems = verify(qs, self.chunks)[1]
        self.assertIn("du0: 'Hà Nội' matches 1 chunks, recorded 0", problems)


@unittest.skipUnless(CHUNKS_PATH.exists() and QUESTIONS_PATH.exists(), "exports not built")
class CommittedBenchmarkTest(unittest.TestCase):
    def test_committed_benchmark_verifies(self):
        questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
        rows, problems = verify(questions, load_chunks())
        self.assertEqual(problems, [])
        self.assertTrue(all(r["chunks"] > 0 for r in rows if r["kind"] == "gold"))

    def test_export_matches_its_record(self):
        info = json.loads(INFO_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(load_chunks()), info["chunks"])
        self.assertEqual(info["reembed_check"]["cosine_to_stored"], 1.0)


if __name__ == "__main__":
    unittest.main()
