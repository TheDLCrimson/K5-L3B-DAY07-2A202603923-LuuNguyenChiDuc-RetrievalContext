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

## Tests

`python -m unittest discover -s tests -v` runs the template's tests, [tests/test_benchmark.py](../tests/test_benchmark.py) and [tests/test_retrieval.py](../tests/test_retrieval.py).
They need no database or model.
