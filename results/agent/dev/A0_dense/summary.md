# Agent A0_dense on dev

`{"name": "A0_dense", "provider": "openrouter", "model": "anthropic/claude-haiku-5.5", "retriever": "dense", "read_neighbors": false, "max_turns": 6, "max_searches": 4, "results_per_search": 3, "context_budget_chars_per_result": 3300, "note": "baseline: the agent with dense search on the Day 6 index"}`

| Measure | Value |
| --- | --- |
| Status | answered 30, abstain 3 |
| Tool use (questions with a retrieval call / runs without error) | 33/33 (100%) |
| Retrieval calls per question | 1: 21, 2: 7, 3: 3, 4: 2 |
| Context Evidence Rate (answerable) | 30/30 (100%) |
| Gold in the first search's results (answerable) | 28/30 (93%) |
| Answered and cited a gold chunk (ID check, not a support label) | 30/30 (100%) |
| Abstained on unanswerable (status only; confirmed by reading) | 3/3 (100%) |
| Abstained on answerable | 0/30 (0%) |
| Answers with citations | 30/30 (100%) |
| Model calls per question (mean) | 2.52 |
| Tokens in / out | 248906 / 28725 |
| Cost (USD, as billed by OpenRouter) | 0.0389 |
| Time per question, median / p90 (ms) | 4930.2 / 9566.7 |
| Errors | 0 |

Context missed: none.
Abstained on answerable: none.
Answered unanswerable: none.
