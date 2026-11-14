# Code and how to run it

Run every command from the repo root with Python 3.12.
`pip install -r requirements.txt` (install torch for your CPU or GPU first).
On Windows, set `PYTHONUTF8=1` so console output in Vietnamese does not fail.

## Setup

1. Start the Day 6 vector store: in the Day 6 repo's `starter/` folder, `docker compose -p day6_student_starter up -d --wait`.
2. `cp .env.example .env`; it holds only the local Day 6 `DATABASE_URL`.
3. `python -m src.day6` checks the index: 1,264 strategy B rows, `intfloat/multilingual-e5-base`, 768 dimensions.

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

## Tests

`python -m unittest discover -s tests -v` runs the template's tests and [tests/test_benchmark.py](../tests/test_benchmark.py).
They need no database or model.
