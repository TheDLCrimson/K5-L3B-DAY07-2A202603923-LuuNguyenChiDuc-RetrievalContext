# V0_dense on test

| Measure | Value |
| --- | --- |
| Status | answered 22, abstain 8 |
| Tool use (questions with a search / runs without error) | 30/30 (100%) |
| Searches per question | 1: 13, 2: 13, 3: 2, 4: 2 |
| Looks per question | 0: 30 |
| Evidence in the final context (answerable, every item) | 24/24 (100%) |
| Evidence in the first search | 20/24 (83%) |
| Answered citing every evidence item | 22/22 (100%) |
| Abstained on no-evidence questions | 6/6 (100%) |
| Abstained on answerable questions | 2/24 (8%) |
| Answers with citations | 22/22 (100%) |
| Model calls per question (mean) | 2.6 |
| Cost (USD) | 0.044375 |
| Time median / p90 (ms) | 6339.7 / 11041.3 |

Evidence in context by group: anh_so_do 5/5 (100%), bang 6/6 (100%), bieu_do 5/5 (100%), multi_hop 4/4 (100%), text 4/4 (100%)

Configuration: `{"name": "V0_dense", "provider": "openrouter", "model": "anthropic/claude-haiku-5.5", "retriever": "dense", "look": null, "max_turns": 8, "max_searches": 5, "max_looks": 4, "results_per_search": 3, "context_budget_chars_per_chunk": 3300, "note": "baseline: dense search only, the agent reads extracted text and descriptions"}`

