# V0_dense on dev

| Measure | Value |
| --- | --- |
| Status | abstain 2, answered 3 |
| Tool use (questions with a search / runs without error) | 5/5 (100%) |
| Searches per question | 1: 2, 2: 3 |
| Looks per question | 0: 5 |
| Evidence in the final context (answerable, every item) | 5/5 (100%) |
| Evidence in the first search | 4/5 (80%) |
| Answered citing every evidence item | 3/3 (100%) |
| Abstained on no-evidence questions | 0/0 (n/a) |
| Abstained on answerable questions | 2/5 (40%) |
| Answers with citations | 3/3 (100%) |
| Model calls per question (mean) | 2.4 |
| Cost (USD) | 0.008878 |
| Time median / p90 (ms) | 8319.1 / 36902.5 |

Evidence in context by group: anh_so_do 2/2 (100%), bieu_do 3/3 (100%)

Configuration: `{"name": "V0_dense", "provider": "openrouter", "model": "anthropic/claude-haiku-5.5", "retriever": "dense", "look": null, "max_turns": 8, "max_searches": 5, "max_looks": 4, "results_per_search": 3, "context_budget_chars_per_chunk": 3300, "note": "baseline: dense search only, the agent reads extracted text and descriptions"}`

