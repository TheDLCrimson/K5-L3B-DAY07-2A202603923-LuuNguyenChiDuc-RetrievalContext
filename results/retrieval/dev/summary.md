# Retrieval on dev

| Method | Hit@1 | Evidence Hit@3 | MRR@10 | Hit@20 | Context Evidence Rate | Median ms | Errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dense | 21/30 (70%) | 26/30 (87%) | 0.8028 | 30/30 (100%) | 26/30 (87%) | 41.8 | 0 |
| bm25 | 20/30 (67%) | 23/30 (77%) | 0.7339 | 28/30 (93%) | 23/30 (77%) | 15.1 | 0 |
| hybrid | 24/30 (80%) | 27/30 (90%) | 0.8611 | 30/30 (100%) | 27/30 (90%) | 61.0 | 0 |
| hybrid_rrf | 23/30 (77%) | 25/30 (83%) | 0.8254 | 29/30 (97%) | 25/30 (83%) | 67.6 | 0 |
| hybrid_rerank | 26/30 (87%) | 28/30 (93%) | 0.9111 | 30/30 (100%) | 28/30 (93%) | 4010.8 | 0 |

Misses at 3:

- dense: q12, h05, h06, h10
- bm25: q02, q04, h03, h05, h06, h09, h10
- hybrid: h05, h06, h10
- hybrid_rrf: q02, h05, h06, h09, h10
- hybrid_rerank: h03, h06

Configurations:

- dense: `{"method": "dense", "index": "Day 6 pgvector, strategy B, exact cosine", "embedding": "intfloat/multilingual-e5-base", "query_prefix": "query: "}`
- bm25: `{"method": "bm25", "library": "rank_bm25.BM25Okapi", "k1": 1.5, "b": 0.75, "tokens": "lower-cased NFC syllables + adjacent syllable pairs"}`
- hybrid: `{"method": "hybrid", "candidates_per_side": 20, "fusion": "0.7 * minmax(dense) + 0.3 * minmax(bm25)"}`
- hybrid_rrf: `{"method": "hybrid_rrf", "candidates_per_side": 20, "fusion": "sum of 1 / (60 + rank)"}`
- hybrid_rerank: `{"method": "hybrid_rerank", "pool": "union of dense and bm25 top 20", "reranker": "BAAI/bge-reranker-v2-m3", "revision": "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e", "max_length": 512, "input": "question text, chunk text", "score": "cross-encoder logit"}`
