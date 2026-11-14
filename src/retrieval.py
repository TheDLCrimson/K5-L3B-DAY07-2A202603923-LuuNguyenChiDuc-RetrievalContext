"""Four retrieval methods over the same 1,264 Day 6 chunks, behind one interface.

Every method has `name`, `config()` and `search(query, top_k, year=None)`. A search returns
ranked results, each a chunk with `score`, `rank` and `method`, so traces show where every
result came from. All methods apply the same `year` filter, taken from the question.

- DenseRetriever: e5 on the Day 6 pgvector index (src/day6.py), score = cosine.
- Bm25Retriever: BM25 over data/day6/chunks.json with Day 6's tokenizer, score = BM25.
- HybridRetriever: top-N from each, fused by min-max-normalised weighted sum or by RRF;
  raw scores from the two retrievers are never added directly.
- RerankRetriever: the union of both top-N lists, re-scored by a cross-encoder.

Failures raise RetrievalError (index down, model missing, bad input) and are recorded by
the caller; nothing here falls back to a fake or partial result.
"""
import re
import unicodedata
from itertools import pairwise
from typing import Any

from .day6 import YEARS, DenseSearch
from .export_day6 import load_chunks

CANDIDATES = 20  # per side, for hybrid fusion and the rerank pool
ALPHA = 0.7  # dense weight; Day 6's dev choice
RRF_K = 60  # the usual constant; not tuned
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
RERANK_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"  # Hugging Face commit
RERANK_MAX_LENGTH = 512


class RetrievalError(RuntimeError):
    """A search could not run; the trace records the message instead of results."""


def check_input(query: str, top_k: int, year: int | None) -> None:
    if not isinstance(query, str) or not query.strip():
        raise RetrievalError("empty query")
    if not isinstance(top_k, int) or top_k < 1:
        raise RetrievalError(f"top_k must be a positive integer, got {top_k!r}")
    if year is not None and year not in YEARS:
        raise RetrievalError(f"year must be one of {YEARS} or None, got {year!r}")


def as_result(chunk: dict[str, Any], score: float, rank: int, method: str) -> dict[str, Any]:
    return {**chunk, "score": round(float(score), 6), "rank": rank, "method": method}


def tokenize(text: str) -> list[str]:
    """Lower-cased NFC syllables plus adjacent syllable pairs (Day 6; Vietnamese words span syllables)."""
    syllables = re.findall(r"\w+", unicodedata.normalize("NFC", text).lower())
    return syllables + [f"{a}_{b}" for a, b in pairwise(syllables)]


def minmax(scores: dict[str, float]) -> dict[str, float]:
    """Scale one retriever's scores for one query to [0, 1]; all-equal scores become 1."""
    if not scores:
        return {}
    low, high = min(scores.values()), max(scores.values())
    return {k: (v - low) / (high - low) if high > low else 1.0 for k, v in scores.items()}


def ranked(scores: dict[str, float], top_k: int) -> list[tuple[str, float]]:
    """Highest score first; ties broken by chunk ID so every run gives the same order."""
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:top_k]


class DenseRetriever:
    name = "dense"

    def __init__(self, search: DenseSearch | None = None) -> None:
        self.dense = search or DenseSearch()

    def config(self) -> dict[str, Any]:
        return {"method": self.name, "index": "Day 6 pgvector, strategy B, exact cosine",
                "embedding": "intfloat/multilingual-e5-base", "query_prefix": "query: "}

    def search(self, query: str, top_k: int, year: int | None = None) -> list[dict[str, Any]]:
        check_input(query, top_k, year)
        try:
            hits = self.dense.search(query, top_k, year)
        except Exception as exc:  # database or model failure
            raise RetrievalError(f"dense search failed: {type(exc).__name__}: {exc}") from exc
        return [as_result({k: v for k, v in h.items() if k not in ("score", "rank")}, h["score"], h["rank"],
                          self.name) for h in hits]


class Bm25Retriever:
    name = "bm25"

    def __init__(self, chunks: list[dict[str, Any]] | None = None) -> None:
        from rank_bm25 import BM25Okapi

        self.chunks = chunks if chunks is not None else load_chunks()
        self.bm25 = BM25Okapi([tokenize(c["text"]) for c in self.chunks])  # k1=1.5, b=0.75

    def config(self) -> dict[str, Any]:
        return {"method": self.name, "library": "rank_bm25.BM25Okapi", "k1": 1.5, "b": 0.75,
                "tokens": "lower-cased NFC syllables + adjacent syllable pairs"}

    def search(self, query: str, top_k: int, year: int | None = None) -> list[dict[str, Any]]:
        check_input(query, top_k, year)
        scores = self.bm25.get_scores(tokenize(query))
        allowed = {c["id"]: float(scores[i]) for i, c in enumerate(self.chunks)
                   if year is None or c["metadata"]["year"] == year}
        by_id = {c["id"]: c for c in self.chunks}
        return [as_result(by_id[cid], s, r, self.name) for r, (cid, s) in enumerate(ranked(allowed, top_k), 1)]


class HybridRetriever:
    def __init__(self, dense: DenseRetriever, bm25: Bm25Retriever, fusion: str = "weighted",
                 alpha: float = ALPHA, candidates: int = CANDIDATES) -> None:
        if fusion not in ("weighted", "rrf"):
            raise ValueError(f"fusion must be 'weighted' or 'rrf', got {fusion!r}")
        self.dense, self.bm25, self.fusion, self.alpha, self.candidates = dense, bm25, fusion, alpha, candidates
        self.name = "hybrid" if fusion == "weighted" else "hybrid_rrf"

    def config(self) -> dict[str, Any]:
        fused = (f"{self.alpha} * minmax(dense) + {round(1 - self.alpha, 3)} * minmax(bm25)"
                 if self.fusion == "weighted" else f"sum of 1 / ({RRF_K} + rank)")
        return {"method": self.name, "candidates_per_side": self.candidates, "fusion": fused}

    def pool(self, query: str, year: int | None) -> tuple[list[dict], list[dict]]:
        return self.dense.search(query, self.candidates, year), self.bm25.search(query, self.candidates, year)

    def fuse(self, dense: list[dict], keyword: list[dict]) -> dict[str, float]:
        ids = list(dict.fromkeys([h["id"] for h in dense] + [h["id"] for h in keyword]))
        if self.fusion == "rrf":
            ranks = [{h["id"]: h["rank"] for h in side} for side in (dense, keyword)]
            return {i: sum(1 / (RRF_K + r[i]) for r in ranks if i in r) for i in ids}
        d = minmax({h["id"]: h["score"] for h in dense})
        k = minmax({h["id"]: h["score"] for h in keyword})
        return {i: self.alpha * d.get(i, 0.0) + (1 - self.alpha) * k.get(i, 0.0) for i in ids}

    def search(self, query: str, top_k: int, year: int | None = None) -> list[dict[str, Any]]:
        check_input(query, top_k, year)
        dense, keyword = self.pool(query, year)
        by_id = {h["id"]: h for h in keyword + dense}
        return [as_result(self._chunk(by_id[cid]), s, r, self.name)
                for r, (cid, s) in enumerate(ranked(self.fuse(dense, keyword), top_k), 1)]

    @staticmethod
    def _chunk(result: dict) -> dict:
        return {k: v for k, v in result.items() if k not in ("score", "rank", "method")}


class CrossEncoderScorer:
    """bge-reranker-v2-m3 relevance logits for (query, passage) pairs, in fp32.

    fp16 was tried first and was about 5 times slower on the lab's GTX 1650 (a 4096x4096
    matmul ran at 0.34 TFLOPS in fp16 against 1.65 in fp32), so the weights stay fp32 (2.3 GB).
    """

    def __init__(self, device: str | None = None) -> None:
        try:
            from sentence_transformers import CrossEncoder

            self.model = CrossEncoder(RERANK_MODEL, revision=RERANK_REVISION, device=device,
                                      max_length=RERANK_MAX_LENGTH)
        except Exception as exc:
            raise RetrievalError(f"reranker {RERANK_MODEL} failed to load: {type(exc).__name__}: {exc}") from exc
        self.device = str(self.model.device)
        self.tokenizer = self.model.tokenizer

    def truncated(self, query: str, passages: list[str]) -> int:
        """How many pairs exceed max_length and would lose their tail."""
        return sum(len(self.tokenizer(query, p)["input_ids"]) > RERANK_MAX_LENGTH for p in passages)

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [float(s) for s in self.model.predict([(query, p) for p in passages], batch_size=8,
                                                     show_progress_bar=False)]


class RerankRetriever:
    def __init__(self, hybrid: HybridRetriever, scorer: CrossEncoderScorer) -> None:
        self.hybrid, self.scorer = hybrid, scorer
        self.last_truncated = 0
        pool = hybrid.candidates
        self.name = "hybrid_rerank" if pool == CANDIDATES else f"hybrid_rerank_pool{pool}"


    def config(self) -> dict[str, Any]:
        return {"method": self.name, "pool": f"union of dense and bm25 top {self.hybrid.candidates}",
                "reranker": RERANK_MODEL, "revision": RERANK_REVISION, "max_length": RERANK_MAX_LENGTH,
                "input": "question text, chunk text", "score": "cross-encoder logit"}

    def search(self, query: str, top_k: int, year: int | None = None) -> list[dict[str, Any]]:
        check_input(query, top_k, year)
        dense, keyword = self.hybrid.pool(query, year)
        pool = list({h["id"]: HybridRetriever._chunk(h) for h in dense + keyword}.values())
        if not pool:
            return []
        texts = [c["text"] for c in pool]
        try:
            self.last_truncated = self.scorer.truncated(query, texts)
            scores = self.scorer.score(query, texts)
        except Exception as exc:
            raise RetrievalError(f"rerank failed: {type(exc).__name__}: {exc}") from exc
        by_id = {c["id"]: c for c in pool}
        order = ranked({c["id"]: s for c, s in zip(pool, scores)}, top_k)
        return [as_result(by_id[cid], s, r, self.name) for r, (cid, s) in enumerate(order, 1)]
