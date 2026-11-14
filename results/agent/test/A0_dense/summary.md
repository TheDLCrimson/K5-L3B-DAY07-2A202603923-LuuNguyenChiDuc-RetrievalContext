# Agent A0_dense on test

`{"name": "A0_dense", "provider": "openrouter", "model": "anthropic/claude-haiku-5.5", "retriever": "dense", "per_version": false, "max_turns": 6, "max_searches": 4, "results_per_search": 3, "context_budget_chars_per_result": 3300, "note": "baseline: the agent with dense search on the Day 6 index"}`

| Measure | Value |
| --- | --- |
| Status | answered 10, abstain 3 |
| Tool use (questions with a retrieval call / runs without error) | 13/13 (100%) |
| Retrieval calls per question | 1: 5, 2: 3, 3: 2, 4: 3 |
| Context Evidence Rate (answerable) | 10/10 (100%) |
| Gold in the first search's results (answerable) | 7/10 (70%) |
| Answered and cited a gold chunk (ID check, not a support label) | 10/10 (100%) |
| Cited gold from both laws (no version named, gold in both) | 3/3 (100%) |
| Citations from the other law version (version named) | 0/14 (0%) |
| Abstained on unanswerable (status only; confirmed by reading) | 3/3 (100%) |
| Abstained on answerable | 0/10 (0%) |
| Answers with citations | 10/10 (100%) |
| Model calls per question (mean) | 3 |
| Tokens in / out | 138625 / 14962 |
| Cost (USD, as billed by OpenRouter) | 0.0211 |
| Time per question, median / p90 (ms) | 7289.4 / 12161.5 |
| Errors | 0 |

Context missed: none.
Abstained on answerable: none.
Answered unanswerable: none.
