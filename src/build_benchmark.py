"""Build benchmark/questions.json: the Day 6 questions as dev, plus the new hand-written questions.

All 30 Day 6 questions (its dev, its already-seen test, and its holdout) become dev here:
they were all read during Day 6, so none can judge Lab 7 independently, but they are fine
for tuning. The starter's convert_day6.py keeps only the primary gold and drops Day 6's
`alternative_gold`; this adapter puts the primary and every alternative into `gold`, any
one of which is a valid hit.

The new questions in benchmark/new_questions.json (the test split and every unanswerable
question) were written on 14/11/2026 from articles no dev gold uses, before any Lab 7 run.

Run from the repo root:  python -m src.build_benchmark --day6-repo ../K5-L3B-DAY06-2A202603923-DataIngestion
"""
import argparse
import json
from pathlib import Path

from .day6 import REPO_ROOT

BENCHMARK_DIR = REPO_ROOT / "benchmark"
QUESTIONS_PATH = BENCHMARK_DIR / "questions.json"
NEW_PATH = BENCHMARK_DIR / "new_questions.json"
DAY6_FILES = ("benchmark/questions.json", "benchmark/holdout.json")


def convert_day6(question: dict, day6_file: str) -> dict:
    gold = [{"source_id": question["gold_source_id"], "page": question["gold_page"],
             "evidence": question["evidence_quote"]}]
    gold += [{"source_id": a["source_id"], "page": a["page"], "evidence": a["evidence_quote"]}
             for a in question.get("alternative_gold", [])]
    return {"id": question["id"], "split": "dev", "type": question["type"],
            "question": question["question"], "expected_answer": question["expected_answer"],
            "gold": gold, "filter": question["filter"], "answerable": True,
            "expected_behavior": "search_and_answer",
            "origin": {"day6_file": day6_file, "day6_split": question["split"]}}


def complete_new(question: dict) -> dict:
    q = dict(question)
    if q.get("answerable", True):
        q.update(answerable=True, expected_behavior="search_and_answer")
    q["origin"] = {"written": "2026-11-14, before any Lab 7 run"}
    return q


def build(day6_repo: Path) -> list[dict]:
    questions = []
    for name in DAY6_FILES:
        rows = json.loads((day6_repo / name).read_text(encoding="utf-8"))
        questions += [convert_day6(q, name) for q in rows]
    questions += [complete_new(q) for q in json.loads(NEW_PATH.read_text(encoding="utf-8"))]
    order = {"dev": 0, "test": 1}
    return sorted(questions, key=lambda q: order[q["split"]])  # stable: keeps the order within a split


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--day6-repo", type=Path, required=True, help="local clone of the Day 6 lab")
    args = parser.parse_args()
    questions = build(args.day6_repo)
    QUESTIONS_PATH.write_text(json.dumps(questions, ensure_ascii=False, indent=1) + "\n",
                              encoding="utf-8", newline="\n")
    print(f"wrote {len(questions)} questions to {QUESTIONS_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
