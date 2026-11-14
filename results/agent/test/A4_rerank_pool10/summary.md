# Agent A4_rerank_pool10 on test

`{"name": "A4_rerank_pool10", "provider": "openrouter", "model": "anthropic/claude-haiku-5.5", "retriever": "hybrid_rerank_pool10", "per_version": false, "max_turns": 6, "max_searches": 4, "results_per_search": 3, "context_budget_chars_per_result": 3300, "note": "A1 with a rerank pool of the top 10 per side instead of 20"}`

| Measure | Value |
| --- | --- |
| Status | answered 9, abstain 4 |
| Tool use (questions with a retrieval call / runs without error) | 13/13 (100%) |
| Retrieval calls per question | 1: 5, 2: 3, 3: 3, 4: 2 |
| Context Evidence Rate (answerable) | 9/10 (90%) |
| Gold in the first search's results (answerable) | 9/10 (90%) |
| Answered and cited a gold chunk (ID check, not a support label) | 8/9 (89%) |
| Cited gold from both laws (no version named, gold in both) | 3/3 (100%) |
| Citations from the other law version (version named) | 0/14 (0%) |
| Abstained on unanswerable (status only; confirmed by reading) | 3/3 (100%) |
| Abstained on answerable | 1/10 (10%) |
| Answers with citations | 9/9 (100%) |
| Model calls per question (mean) | 3.15 |
| Tokens in / out | 153301 / 16713 |
| Cost (USD, as billed by OpenRouter) | 0.0234 |
| Time per question, median / p90 (ms) | 9993.7 / 20241.5 |
| Errors | 0 |

Context missed: t07.
Abstained on answerable: t10.
Answered unanswerable: none.
