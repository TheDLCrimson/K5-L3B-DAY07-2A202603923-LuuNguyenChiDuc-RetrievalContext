# Agent A3_rerank_per_version on dev

`{"name": "A3_rerank_per_version", "provider": "openrouter", "model": "anthropic/claude-haiku-5.5", "retriever": "hybrid_rerank", "per_version": true, "max_turns": 6, "max_searches": 4, "results_per_search": 3, "context_budget_chars_per_result": 3300, "note": "A1, searching each law version when the question names none"}`

| Measure | Value |
| --- | --- |
| Status | answered 30, abstain 3 |
| Tool use (questions with a retrieval call / runs without error) | 33/33 (100%) |
| Retrieval calls per question | 1: 13, 2: 17, 3: 2, 4: 1 |
| Context Evidence Rate (answerable) | 30/30 (100%) |
| Gold in the first search's results (answerable) | 28/30 (93%) |
| Answered and cited a gold chunk (ID check, not a support label) | 30/30 (100%) |
| Cited gold from both laws (no version named, gold in both) | 13/13 (100%) |
| Citations from the other law version (version named) | 0/24 (0%) |
| Abstained on unanswerable (status only; confirmed by reading) | 3/3 (100%) |
| Abstained on answerable | 0/30 (0%) |
| Answers with citations | 30/30 (100%) |
| Model calls per question (mean) | 2.12 |
| Tokens in / out | 216237 / 32636 |
| Cost (USD, as billed by OpenRouter) | 0.0376 |
| Time per question, median / p90 (ms) | 11597.3 / 19523.1 |
| Errors | 0 |

Context missed: none.
Abstained on answerable: none.
Answered unanswerable: none.
