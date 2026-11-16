# V1_rerank on dev

| Measure | Value |
| --- | --- |
| Status | answered 4, abstain 1 |
| Tool use (questions with a search / runs without error) | 5/5 (100%) |
| Searches per question | 1: 4, 2: 1 |
| Looks per question | 0: 5 |
| Evidence in the final context (answerable, every item) | 5/5 (100%) |
| Evidence in the first search | 5/5 (100%) |
| Answered citing every evidence item | 4/4 (100%) |
| Abstained on no-evidence questions | 0/0 (n/a) |
| Abstained on answerable questions | 1/5 (20%) |
| Answers with citations | 4/4 (100%) |
| Model calls per question (mean) | 2.2 |
| Cost (USD) | 0.007101 |
| Time median / p90 (ms) | 9679.1 / 26098.0 |

Evidence in context by group: anh_so_do 2/2 (100%), bieu_do 3/3 (100%)

Configuration: `{"name": "V1_rerank", "provider": "openrouter", "model": "anthropic/claude-haiku-5.5", "retriever": "hybrid_rerank_pool10", "look": null, "max_turns": 8, "max_searches": 5, "max_looks": 4, "results_per_search": 3, "context_budget_chars_per_chunk": 3300, "note": "V0 with the base lab's best retrieval (hybrid, top 10 per side, cross-encoder rerank)"}`

