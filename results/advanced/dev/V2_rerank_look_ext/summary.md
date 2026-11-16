# V2_rerank_look on dev

| Measure | Value |
| --- | --- |
| Status | answered 5 |
| Tool use (questions with a search / runs without error) | 5/5 (100%) |
| Searches per question | 1: 4, 2: 1 |
| Looks per question | 1: 5 |
| Evidence in the final context (answerable, every item) | 5/5 (100%) |
| Evidence in the first search | 5/5 (100%) |
| Answered citing every evidence item | 5/5 (100%) |
| Abstained on no-evidence questions | 0/0 (n/a) |
| Abstained on answerable questions | 0/5 (0%) |
| Answers with citations | 5/5 (100%) |
| Model calls per question (mean) | 3 |
| Cost (USD) | 0.011103 |
| Time median / p90 (ms) | 15843.6 / 21815.0 |

Evidence in context by group: anh_so_do 2/2 (100%), bieu_do 3/3 (100%)

Configuration: `{"name": "V2_rerank_look", "provider": "openrouter", "model": "anthropic/claude-haiku-5.5", "retriever": "hybrid_rerank_pool10", "look": {"provider": "openrouter", "model": "anthropic/claude-haiku-5.5"}, "max_turns": 8, "max_searches": 5, "max_looks": 4, "results_per_search": 3, "context_budget_chars_per_chunk": 3300, "note": "V1 plus the look tool: the agent reads values from the crop with the same model"}`

