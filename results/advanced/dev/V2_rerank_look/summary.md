# V2_rerank_look on dev

| Measure | Value |
| --- | --- |
| Status | answered 15, abstain 3 |
| Tool use (questions with a search / runs without error) | 18/18 (100%) |
| Searches per question | 1: 10, 2: 6, 4: 2 |
| Looks per question | 0: 7, 1: 10, 2: 1 |
| Evidence in the final context (answerable, every item) | 15/15 (100%) |
| Evidence in the first search | 13/15 (87%) |
| Answered citing every evidence item | 15/15 (100%) |
| Abstained on no-evidence questions | 3/3 (100%) |
| Abstained on answerable questions | 0/15 (0%) |
| Answers with citations | 15/15 (100%) |
| Model calls per question (mean) | 3 |
| Cost (USD) | 0.038493 |
| Time median / p90 (ms) | 12886.5 / 22769.8 |

Evidence in context by group: anh_so_do 3/3 (100%), bang 3/3 (100%), bieu_do 4/4 (100%), multi_hop 2/2 (100%), text 3/3 (100%)

Configuration: `{"name": "V2_rerank_look", "provider": "openrouter", "model": "anthropic/claude-haiku-5.5", "retriever": "hybrid_rerank_pool10", "look": {"provider": "openrouter", "model": "anthropic/claude-haiku-5.5"}, "max_turns": 8, "max_searches": 5, "max_looks": 4, "results_per_search": 3, "context_budget_chars_per_chunk": 3300, "note": "V1 plus the look tool: the agent reads values from the crop with the same model"}`

