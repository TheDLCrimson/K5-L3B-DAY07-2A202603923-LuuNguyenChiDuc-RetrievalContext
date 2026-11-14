# Agent A4_rerank_pool10 on dev

`{"name": "A4_rerank_pool10", "provider": "openrouter", "model": "anthropic/claude-haiku-5.5", "retriever": "hybrid_rerank_pool10", "per_version": false, "max_turns": 6, "max_searches": 4, "results_per_search": 3, "context_budget_chars_per_result": 3300, "note": "A1 with a rerank pool of the top 10 per side instead of 20"}`

| Measure | Value |
| --- | --- |
| Status | answered 30, abstain 3 |
| Tool use (questions with a retrieval call / runs without error) | 33/33 (100%) |
| Retrieval calls per question | 1: 23, 2: 7, 3: 3 |
| Context Evidence Rate (answerable) | 30/30 (100%) |
| Gold in the first search's results (answerable) | 29/30 (97%) |
| Answered and cited a gold chunk (ID check, not a support label) | 30/30 (100%) |
| Cited gold from both laws (no version named, gold in both) | 13/13 (100%) |
| Citations from the other law version (version named) | 0/22 (0%) |
| Abstained on unanswerable (status only; confirmed by reading) | 3/3 (100%) |
| Abstained on answerable | 0/30 (0%) |
| Answers with citations | 30/30 (100%) |
| Model calls per question (mean) | 2.3 |
| Tokens in / out | 208640 / 25621 |
| Cost (USD, as billed by OpenRouter) | 0.0333 |
| Time per question, median / p90 (ms) | 6411.1 / 12139.8 |
| Errors | 0 |

Context missed: none.
Abstained on answerable: none.
Answered unanswerable: none.
