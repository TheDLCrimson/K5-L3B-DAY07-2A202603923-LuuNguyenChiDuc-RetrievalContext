# Retrieval on test

| Method | Hit@1 | Evidence Hit@3 | MRR@10 | Hit@20 | Context Evidence Rate | Median ms | Errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dense | 7/10 (70%) | 8/10 (80%) | 0.75 | 10/10 (100%) | 8/10 (80%) | 37.3 | 0 |
| hybrid_rerank_pool10 | 9/10 (90%) | 10/10 (100%) | 0.9333 | 10/10 (100%) | 10/10 (100%) | 1831.6 | 0 |

Misses at 3:

- dense: t03, t07
- hybrid_rerank_pool10: none

Configurations:

- dense: `{"method": "dense", "index": "Day 6 pgvector, strategy B, exact cosine", "embedding": "intfloat/multilingual-e5-base", "query_prefix": "query: "}`
- hybrid_rerank_pool10: `{"method": "hybrid_rerank_pool10", "pool": "union of dense and bm25 top 10", "reranker": "BAAI/bge-reranker-v2-m3", "revision": "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e", "max_length": 512, "input": "question text, chunk text", "score": "cross-encoder logit"}`
