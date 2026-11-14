# Agent A1_rerank on dev

`{"name": "A1_rerank", "provider": "openrouter", "model": "anthropic/claude-haiku-5.5", "retriever": "hybrid_rerank", "read_neighbors": false, "max_turns": 6, "max_searches": 4, "results_per_search": 3, "context_budget_chars_per_result": 3300, "note": "the agent with the retrieval chosen in E1"}`

| Measure | Value |
| --- | --- |
| Status | answered 30, abstain 3 |
| Tool use (questions with a retrieval call / runs without error) | 33/33 (100%) |
| Retrieval calls per question | 1: 22, 2: 8, 3: 1, 4: 2 |
| Context Evidence Rate (answerable) | 30/30 (100%) |
| Gold in the first search's results (answerable) | 30/30 (100%) |
| Answered and cited a gold chunk (ID check, not a support label) | 30/30 (100%) |
| Abstained on unanswerable (status only; confirmed by reading) | 3/3 (100%) |
| Abstained on answerable | 0/30 (0%) |
| Answers with citations | 30/30 (100%) |
| Model calls per question (mean) | 2.52 |
| Tokens in / out | 243243 / 27013 |
| Cost (USD, as billed by OpenRouter) | 0.0375 |
| Time per question, median / p90 (ms) | 8730.4 / 18860.3 |
| Errors | 0 |

Context missed: none.
Abstained on answerable: none.
Answered unanswerable: none.
