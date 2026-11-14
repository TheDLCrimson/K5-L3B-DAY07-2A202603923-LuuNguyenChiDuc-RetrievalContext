"""Retrieval methods, fusion and context packing on small fixtures (no database or model)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import context
from src.eval_retrieval import summarize, trace_one
from src.export_day6 import CHUNKS_PATH, load_chunks
from src.retrieval import (
    Bm25Retriever,
    DenseRetriever,
    HybridRetriever,
    RerankRetriever,
    RetrievalError,
    minmax,
    tokenize,
)


def chunk(cid, text, year=2013, page=1):
    return {"id": cid, "text": text, "source_id": "ldd2013" if year == 2013 else "ldd2024_cb363",
            "source": "f.pdf", "page": page,
            "metadata": {"page_end": page, "year": year, "law_number": "45/2013/QH13", "articles": [1]}}


CHUNKS = [
    chunk("c1", "Hòa giải tranh chấp đất đai tại xã trong 45 ngày", 2013),
    chunk("c2", "Hòa giải tranh chấp đất đai tại xã trong 30 ngày", 2024),
    chunk("c3", "Hạn mức giao đất nông nghiệp cho cá nhân", 2013),
    chunk("c4", "Thời hạn sử dụng đất ở ổn định lâu dài", 2024),
]


class FakeDenseSearch:
    """Stands in for pgvector: fixed cosine scores per chunk, same filter semantics."""

    def __init__(self, scores, fail=False):
        self.scores, self.fail = scores, fail

    def search(self, query, top_k, year=None):
        if self.fail:
            raise ConnectionError("connection refused")
        rows = [c for c in CHUNKS if year is None or c["metadata"]["year"] == year]
        rows = sorted(rows, key=lambda c: (-self.scores[c["id"]], c["id"]))[:top_k]
        return [{**c, "score": self.scores[c["id"]], "rank": i} for i, c in enumerate(rows, 1)]


class FakeScorer:
    def __init__(self, prefer):
        self.prefer = prefer

    def truncated(self, query, passages):
        return 0

    def score(self, query, passages):
        return [1.0 if self.prefer in p else 0.0 for p in passages]


def dense(scores=None, fail=False):
    return DenseRetriever(FakeDenseSearch(scores or {"c1": 0.9, "c2": 0.8, "c3": 0.5, "c4": 0.4}, fail))


class RetrieverTest(unittest.TestCase):
    def test_bm25_prefers_shared_words_and_respects_the_filter(self):
        bm25 = Bm25Retriever(CHUNKS)
        self.assertEqual(bm25.search("hạn mức giao đất nông nghiệp", 1)[0]["id"], "c3")
        self.assertTrue(all(r["metadata"]["year"] == 2024 for r in bm25.search("hòa giải", 4, 2024)))

    def test_tokens_include_syllable_pairs(self):
        self.assertEqual(tokenize("Đất Đai"), ["đất", "đai", "đất_đai"])

    def test_results_are_ranked_and_labelled(self):
        out = dense().search("q", 2)
        self.assertEqual([(r["id"], r["rank"], r["method"]) for r in out], [("c1", 1, "dense"), ("c2", 2, "dense")])

    def test_bad_input_and_backend_failure_raise_retrieval_error(self):
        for args in (("", 3, None), ("q", 0, None), ("q", 3, 2020)):
            with self.assertRaises(RetrievalError):
                dense().search(*args)
        with self.assertRaisesRegex(RetrievalError, "connection refused"):
            dense(fail=True).search("q", 3)

    def test_minmax_scales_each_side_and_handles_ties(self):
        self.assertEqual(minmax({"a": 2.0, "b": 4.0, "c": 3.0}), {"a": 0.0, "b": 1.0, "c": 0.5})
        self.assertEqual(minmax({"a": 7.0}), {"a": 1.0})

    def test_weighted_fusion_uses_normalised_scores(self):
        hybrid = HybridRetriever(dense({"c1": 0.90, "c2": 0.89, "c3": 0.1, "c4": 0.0}), Bm25Retriever(CHUNKS),
                                 alpha=0.5)
        d = [{"id": "c1", "score": 0.90, "rank": 1}, {"id": "c2", "score": 0.89, "rank": 2}]
        k = [{"id": "c2", "score": 12.0, "rank": 1}, {"id": "c1", "score": 2.0, "rank": 2}]
        fused = hybrid.fuse(d, k)  # raw BM25 12.0 would swamp cosine; normalised it does not
        self.assertAlmostEqual(fused["c1"], 0.5)
        self.assertAlmostEqual(fused["c2"], 0.5)

    def test_rrf_and_deterministic_ties(self):
        hybrid = HybridRetriever(dense(), Bm25Retriever(CHUNKS), fusion="rrf")
        fused = hybrid.fuse([{"id": "b", "score": 1, "rank": 1}], [{"id": "a", "score": 1, "rank": 1}])
        self.assertEqual(fused["a"], fused["b"])
        self.assertEqual([r["id"] for r in hybrid.search("hòa giải tranh chấp", 2, 2013)][:1], ["c1"])

    def test_rerank_orders_the_pool_by_the_scorer(self):
        hybrid = HybridRetriever(dense(), Bm25Retriever(CHUNKS))
        out = RerankRetriever(hybrid, FakeScorer("ổn định lâu dài")).search("đất ở", 2)
        self.assertEqual((out[0]["id"], out[0]["method"]), ("c4", "hybrid_rerank"))


class ContextTest(unittest.TestCase):
    def test_pack_skips_what_does_not_fit_and_dedupes(self):
        big = chunk("big", "x" * 500)
        small = chunk("s", "y")
        packed, skipped = context.pack([big, small, small], budget=len(context.block(small)) + 10)
        self.assertEqual(([c["id"] for c in packed], skipped), (["s"], ["big"]))

    def test_label_names_law_pages_and_articles(self):
        c = chunk("B-x", "t", 2013, page=9)
        c["metadata"]["page_end"] = 10
        self.assertEqual(context.label(c), "[B-x] Luật Đất đai 2013 (45/2013/QH13), ldd2013 trang 9-10, Điều 1")

    @unittest.skipUnless(CHUNKS_PATH.exists(), "export not built")
    def test_budget_fits_the_three_longest_real_chunks(self):
        longest = sorted(load_chunks(), key=lambda c: len(context.block(c)))[-3:]
        packed, skipped = context.pack(longest)
        self.assertEqual((len(packed), skipped), (3, []))


class EvalTest(unittest.TestCase):
    def test_trace_scores_hits_and_keeps_unanswerable_out_of_denominators(self):
        q_ans = {"id": "a", "split": "dev", "type": "truc_tiep", "answerable": True, "question": "hòa giải",
                 "filter": {"year": 2024}, "gold": [{"source_id": "ldd2024_cb363", "page": 1, "evidence": "30 ngày"}]}
        q_un = {"id": "u", "split": "dev", "type": "thieu_bang_chung", "answerable": False, "question": "giá đất"}
        rows = [trace_one(dense(), q_ans), trace_one(dense(), q_un), trace_one(dense(fail=True), q_ans)]
        self.assertEqual((rows[0]["first_hit_rank"], rows[0]["context_hit"]), (1, True))
        self.assertEqual(rows[2]["status"], "error")
        s = summarize(rows)
        self.assertEqual((s["evidence_hit_at_3"]["N"], s["unanswerable_traced"], len(s["errors"])), (1, 1, 1))


if __name__ == "__main__":
    unittest.main()
