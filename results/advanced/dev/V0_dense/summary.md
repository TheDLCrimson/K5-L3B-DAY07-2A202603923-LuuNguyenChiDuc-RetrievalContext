# V0_dense on dev

| Measure | Value |
| --- | --- |
| Status | answered 15, abstain 3 |
| Tool use (questions with a search / runs without error) | 18/18 (100%) |
| Searches per question | 1: 8, 2: 6, 3: 3, 4: 1 |
| Looks per question | 0: 18 |
| Evidence in the final context (answerable, every item) | 15/15 (100%) |
| Evidence in the first search | 13/15 (87%) |
| Answered citing every evidence item | 15/15 (100%) |
| Abstained on no-evidence questions | 3/3 (100%) |
| Abstained on answerable questions | 0/15 (0%) |
| Answers with citations | 15/15 (100%) |
| Model calls per question (mean) | 2.44 |
| Cost (USD) | 0.026782 |
| Time median / p90 (ms) | 6049.6 / 13193.2 |

Evidence in context by group: anh_so_do 3/3 (100%), bang 3/3 (100%), bieu_do 4/4 (100%), multi_hop 2/2 (100%), text 3/3 (100%)

Configuration: `{"name": "V0_dense", "provider": "openrouter", "model": "anthropic/claude-haiku-5.5", "retriever": "dense", "look": null, "max_turns": 8, "max_searches": 5, "max_looks": 4, "results_per_search": 3, "context_budget_chars_per_chunk": 3300, "note": "baseline: dense search only, the agent reads extracted text and descriptions"}`

