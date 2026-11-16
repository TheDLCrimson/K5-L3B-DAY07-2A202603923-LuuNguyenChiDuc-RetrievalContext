# Code and how to run it

Run every command from the repo root with Python 3.12.
`pip install -r requirements.txt` (install torch for your CPU or GPU first).
On Windows, set `PYTHONUTF8=1` so console output in Vietnamese does not fail.

## Setup

1. Start the Day 6 vector store: in the Day 6 repo's `starter/` folder, `docker compose -p day6_student_starter up -d --wait`.
2. `cp .env.example .env`; it holds only the local Day 6 `DATABASE_URL`.
3. `python -m src.day6` checks the index: 1,264 strategy B rows, `intfloat/multilingual-e5-base`, 768 dimensions.

## Retrieval experiments

`python -m src.eval_retrieval --split dev` runs every method on dev and writes traces and a summary to `results/retrieval/dev/` ([summary.md](../results/retrieval/dev/summary.md)).
The first run downloads the reranker `BAAI/bge-reranker-v2-m3` (about 2.3 GB); it runs on a GPU if one is available.
Test needs `--final` and is run once, after the configuration is fixed; hypotheses and results are in [EXPERIMENTS.md](../EXPERIMENTS.md).

## Agent runs

Add `PROVIDER`, `MODEL` and the provider's key to `.env` ([.env.example](../.env.example)); the lab used `openrouter` and `anthropic/claude-haiku-5.5`.
`python -m src.run_agent --split dev --config A1_rerank` runs one configuration ([CONFIGS](run_agent.py)); `--ids q01,u01` runs a few questions as a smoke test into a separate `_smoke` folder.
Test needs `--final`. Each run writes `traces.json` in the format `starter/agent_metrics.py` reads, plus `summary.json` and `summary.md`; `results/agent/cases.json` lists every question's split and answerability for that script.

## Test, run once, and human review

The choice made on dev is in [results/agent/selection.json](../results/agent/selection.json); test was run once with `--final`:

```bash
python -m src.eval_retrieval --split test --final --methods dense,hybrid_rerank_pool10
python -m src.run_agent --split test --final --config A0_dense
python -m src.run_agent --split test --final --config A4_rerank_pool10
python -m src.review_sheet sheet --split test --configs A0_dense,A4_rerank_pool10
# fill results/agent/test/review_labels.csv from review_sheet.md, then:
python -m src.review_sheet import --split test --labelled-by "<who labelled>"
python starter/agent_metrics.py --cases results/agent/cases.json --traces results/agent/test/A4_rerank_pool10/traces.json --reviews results/agent/test/A4_rerank_pool10/reviews.json --split test --output results/agent/test/A4_rerank_pool10/agent_metrics.json
```

## Recover search ranks for recorded runs

Runs recorded before the full logging keep score and rank for the top 3 of the 8 chunks each search fetched.
`python -m src.replay_searches --all` replays every logged search without calling the model, checks the replay against the trace, and writes `search_ranks.json` next to each `traces.json` ([EXPERIMENTS.md](../EXPERIMENTS.md) E5).

## Advanced challenge (the 103-page World Bank report)

Needs the Day 6 container, the OpenRouter key in `.env` and, for rerank, a GPU.
Result and hypotheses: [EXPERIMENTS_ADVANCED.md](../EXPERIMENTS_ADVANCED.md); document and index: [data/advanced/README.md](../data/advanced/README.md); benchmark: [data/advanced/benchmark/README.md](../data/advanced/benchmark/README.md).

```bash
python -m src.advanced.source           # download the PDF and check its SHA-256 (the PDF is not committed)
python -m src.advanced.extract          # text, table and figure chunks plus crops -> data/advanced/
python -m src.advanced.describe         # model-written description of each figure and table crop (cached)
python -m src.advanced.index build      # embed every chunk into the pgvector table adv_chunks
python -m src.advanced.verify_benchmark # quotas, evidence chunks, calculations and absence terms
python -m src.advanced.check_crops      # no crop cuts a line of text at its edges
python -m src.advanced.run_agent --split dev --config V2_rerank_look      # V0_dense, V1_rerank, V2_rerank_look, V3_rerank_look_strong
python -m src.advanced.review_sheet sheet --split dev --configs V0_dense,V1_rerank,V2_rerank_look
python -m src.advanced.review_sheet import --split dev --labelled-by "<who labelled>"
python -m src.advanced.metrics --split dev --configs V0_dense,V1_rerank,V2_rerank_look
```

Test needs `--final` and only runs the configurations named in `results/advanced/selection.json`; it was run once, for V1 and V0.
`--ids a,b --folder NAME` runs a subset into its own folder (used for the five dev questions added after the first tie, `--tag _ext` on the sheet and `--extension _ext` on the metrics).

## Rebuild the exports

The chunk export and the benchmark are committed, so these steps only rebuild them.

1. `python -m src.export_day6 --day6-repo <Day 6 clone>` writes `data/day6/chunks.json` and `export_info.json` ([data/day6/README.md](../data/day6/README.md)).
2. `python -m src.build_benchmark --day6-repo <Day 6 clone>`, then `python -m src.verify_benchmark` ([benchmark/README.md](../benchmark/README.md)).

## Modules

| File | Role |
| --- | --- |
| `day6.py` | Day 6 connection: pinned model and index facts, index check, e5 query embedder, dense search on pgvector |
| `evidence.py` | The range-aware hit rule used by every metric |
| `export_day6.py` | Exports the B chunks from pgvector and cross-checks them against Day 6 |
| `build_benchmark.py` | Adapter from the Day 6 question files, plus the new questions |
| `verify_benchmark.py` | Benchmark checks; writes `benchmark/verification.csv` |
| `retrieval.py` | The four retrieval methods: dense, BM25, hybrid (weighted or RRF), hybrid + cross-encoder rerank |
| `context.py` | Labels chunks with their citation key and source, and packs them into the 3,300-character budget |
| `eval_retrieval.py` | Retrieval and context metrics per method; writes `results/retrieval/<split>/` |
| `providers.py` | Chat Completions client (OpenRouter by default), adapted from the Day 4 lab; reports cost and time per call |
| `agent.py` | The tool-calling agent: `search_law` and `finish`, optional per-version search; stop conditions and code guards |
| `run_agent.py` | Runs one agent configuration on a split; writes traces and automatic metrics to `results/agent/<split>/<config>/` |
| `review_sheet.py` | Reading sheet and label CSV for human review; imports the CSV into `reviews.json` and context grades |
| `replay_searches.py` | Replays logged agent searches to recover score and rank for every fetched chunk; writes `search_ranks.json` |
| `advanced/` | The advanced challenge: `source.py` (document, download, hash), `extract.py` (layout to chunks and crops), `describe.py` (vision descriptions), `index.py` (pgvector `adv_chunks`), `agent.py` (search, look, finish), `run_agent.py`, `review_sheet.py`, `metrics.py`, `verify_benchmark.py`, `benchmark_sheet.py` |

## Tests

`python -m unittest discover -s tests -v` runs the template's tests, [tests/test_benchmark.py](../tests/test_benchmark.py), [tests/test_retrieval.py](../tests/test_retrieval.py), [tests/test_agent.py](../tests/test_agent.py), [tests/test_review_sheet.py](../tests/test_review_sheet.py) and [tests/test_replay.py](../tests/test_replay.py), [tests/test_advanced_extract.py](../tests/test_advanced_extract.py), [tests/test_advanced_benchmark.py](../tests/test_advanced_benchmark.py) and [tests/test_advanced_agent.py](../tests/test_advanced_agent.py).
They need no database, model or API key; the agent tests use a scripted model that only exercises the loop.
