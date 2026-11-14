"""Verify benchmark/questions.json against the exported Day 6 chunks, before any retrieval run.

Fails if any of these does not hold:
- IDs are unique, splits are dev/test, and BENCHMARK.md's minimums are met
  (dev 15 answerable + 2 unanswerable, test 5 + 2);
- every gold evidence of an answerable question is found in at least one chunk under the
  hit rule in src/evidence.py, and no evidence quote is copied into its question;
- a `year` filter is the version the question itself names ("Luật Đất đai 2013/2024"),
  so it is user-supplied rather than read from the gold, and some gold is from that year;
- no test gold shares an article (law year, Điều) with any dev gold, judged on the
  articles of the chunks that hold the evidence;
- every unanswerable question has no gold, an absence_reason, and absence_check term
  counts that still match the corpus (case- and whitespace-insensitive substring search).

Writes benchmark/verification.csv. Run from the repo root:  python -m src.verify_benchmark
"""
import csv
import json
import sys
from collections import Counter

from .build_benchmark import BENCHMARK_DIR, QUESTIONS_PATH
from .day6 import YEARS
from .evidence import evidence_hit, squash
from .export_day6 import load_chunks

VERIFICATION_PATH = BENCHMARK_DIR / "verification.csv"
MINIMUMS = {("dev", True): 15, ("dev", False): 2, ("test", True): 5, ("test", False): 2}


def term_matches(chunks: list[dict], term: str) -> int:
    needle = squash(term).casefold()
    return sum(needle in squash(c["text"]).casefold() for c in chunks)


def verify(questions: list[dict], chunks: list[dict]) -> tuple[list[dict], list[str]]:
    problems: list[str] = []
    rows: list[dict] = []
    ids = Counter(q["id"] for q in questions)
    problems += [f"duplicate id {i}" for i, n in ids.items() if n > 1]
    problems += [f"{q['id']}: split {q['split']!r}" for q in questions if q["split"] not in ("dev", "test")]
    counts = Counter((q["split"], q["answerable"]) for q in questions)
    for key, minimum in MINIMUMS.items():
        if counts[key] < minimum:
            problems.append(f"{key[0]} has {counts[key]} {'answerable' if key[1] else 'unanswerable'}, "
                            f"needs {minimum}")

    articles: dict[str, set] = {"dev": set(), "test": set()}
    for q in questions:
        if not q["answerable"]:
            if q.get("gold"):
                problems.append(f"{q['id']}: unanswerable question has gold")
            if not q.get("absence_reason", "").strip():
                problems.append(f"{q['id']}: no absence_reason")
            for check in q.get("absence_check", []):
                found = term_matches(chunks, check["term"])
                if found != check["matches"]:
                    problems.append(f"{q['id']}: {check['term']!r} matches {found} chunks, "
                                    f"recorded {check['matches']}")
                rows.append({"id": q["id"], "split": q["split"], "kind": "absence_term",
                             "source_id": "", "page": "", "detail": check["term"], "chunks": found,
                             "articles": ""})
            if not q.get("absence_check"):
                problems.append(f"{q['id']}: no absence_check")
            continue

        question_text = squash(q["question"]).casefold()
        year = (q.get("filter") or {}).get("year")
        if set(q.get("filter") or {}) - {"year"}:
            problems.append(f"{q['id']}: filter fields other than year")
        if year is not None:
            if year not in YEARS:
                problems.append(f"{q['id']}: filter year {year}")
            if f"luật đất đai {year}" not in question_text:
                problems.append(f"{q['id']}: filter year {year} is not named in the question")
        gold_years = set()
        for g in q["gold"]:
            if squash(g["evidence"]).casefold() in question_text:
                problems.append(f"{q['id']}: evidence copied into the question")
            hits = [c for c in chunks if evidence_hit(c, g)]
            if not hits:
                problems.append(f"{q['id']}: evidence not found on {g['source_id']} p{g['page']}")
            arts = sorted({(c["metadata"]["year"], a) for c in hits for a in c["metadata"]["articles"]})
            gold_years |= {c["metadata"]["year"] for c in hits}
            articles[q["split"]] |= set(arts)
            rows.append({"id": q["id"], "split": q["split"], "kind": "gold", "source_id": g["source_id"],
                         "page": g["page"], "detail": " ".join(c["id"] for c in hits), "chunks": len(hits),
                         "articles": " ".join(f"{y}:Điều {a}" for y, a in arts)})
        if year is not None and year not in gold_years:
            problems.append(f"{q['id']}: no gold from the filtered year {year}")

    shared = sorted(articles["dev"] & articles["test"])
    problems += [f"test and dev gold share {y} Điều {a}" for y, a in shared]
    return rows, problems


def main() -> None:
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    rows, problems = verify(questions, load_chunks())
    with VERIFICATION_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    counts = Counter((q["split"], "answerable" if q["answerable"] else "unanswerable") for q in questions)
    for (split, kind), n in sorted(counts.items()):
        print(f"{split} {kind}: {n}")
    golds = [r for r in rows if r["kind"] == "gold"]
    print(f"gold evidence found in a chunk: {sum(r['chunks'] > 0 for r in golds)}/{len(golds)}")
    print(f"wrote {VERIFICATION_PATH.name}")
    if problems:
        print("PROBLEMS:\n- " + "\n- ".join(problems))
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
