"""Human review of agent answers: a reading sheet, a CSV to fill in, and its import.

`sheet` writes results/agent/<split>/review_sheet.md and review_labels.csv for the given
configurations. The sheet shows, per question, the question, the expected answer (or why
the corpus cannot answer), each configuration's status, answer and citations, and the full
text of every chunk in each final context, so a reader can grade the answer, each citation
and the context without opening the traces. The CSV holds no labels: only IDs to fill in.

`import` checks the filled CSV and writes results/agent/<split>/<config>/reviews.json in the
format starter/agent_metrics.py reads, plus context grades in context_grades.json.

Labels (BENCHMARK.md):
- answer_grade (answerable): 0 wrong, unsupported or refused; 1 partly right; 2 right and complete.
- context_grade (answerable): 0 no evidence in the final context; 1 evidence missing a condition
  or source; 2 enough evidence with its source.
- abstention_correct (unanswerable): y when the answer refuses and asserts nothing unsupported.
- citation_support: one y/n per cited ID, "ID=y; ID=n"; y only if that chunk states what it is cited for.

Run from the repo root:
  python -m src.review_sheet sheet --split test --configs A0_dense,A4_rerank_pool10
  python -m src.review_sheet import --split test --labelled-by "drafted with AI assistance ...; checked by the author"
"""
import argparse
import csv
import json

from . import context
from .build_benchmark import QUESTIONS_PATH
from .export_day6 import load_chunks
from .run_agent import OUT_DIR

FIELDS = ["query_id", "config", "answerable", "answer_grade", "context_grade", "abstention_correct",
          "citation_support", "note"]


def load_runs(split: str, configs: list[str]) -> dict[str, dict[str, dict]]:
    return {c: {r["query_id"]: r for r in json.loads((OUT_DIR / split / c / "traces.json").read_text(encoding="utf-8"))}
            for c in configs}


def sheet(split: str, configs: list[str]) -> None:
    out = OUT_DIR / split
    path = out / "review_labels.csv"
    if path.exists():
        raise SystemExit(f"{path} exists; not overwriting the sheet or the labels")
    questions = [q for q in json.loads(QUESTIONS_PATH.read_text(encoding="utf-8")) if q["split"] == split]
    chunks = {c["id"]: c for c in load_chunks()}
    runs = load_runs(split, configs)
    lines = [f"# Review sheet: {split}", "",
             "Grade each answer from this sheet only; fill in review_labels.csv next to it.",
             ("Scales: answer 0 wrong or unsupported or refused, 1 partly right, 2 right and complete; "
              "context 0 no evidence, 1 evidence missing a condition or source, 2 enough evidence and source; "
              "citation y only if the chunk states what it is cited for."), ""]
    for q in questions:
        lines += [f"## {q['id']} ({'answerable' if q['answerable'] else 'not answerable from the corpus'})", "",
                  f"**Question:** {q['question']}", ""]
        if q["answerable"]:
            lines += [f"**Expected answer:** {q['expected_answer']}", ""]
        else:
            lines += [f"**Why the corpus cannot answer:** {q['absence_reason']}", ""]
        shown: dict[str, list[str]] = {}
        for c in configs:
            r = runs[c][q["id"]]
            lines += [f"### {c}: {r['status']}", "", r["answer"] or "(no answer)", "",
                      f"Citations: {', '.join(r['citations']) or 'none'}", ""]
            for i in r["context_ids"]:
                shown.setdefault(i, []).append(c)
        lines += ["### Chunks in the final contexts", ""]
        for i, seen_by in shown.items():
            lines += [f"**{context.label(chunks[i])}**  (in the context of: {', '.join(seen_by)})", "",
                      "> " + chunks[i]["text"].replace("\n", "\n> "), ""]
    (out / "review_sheet.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for q in questions:
            for c in configs:
                r = runs[c][q["id"]]
                w.writerow({"query_id": q["id"], "config": c, "answerable": "y" if q["answerable"] else "n",
                            "citation_support": "; ".join(f"{i}=" for i in r["citations"])})
    print(f"wrote {out / 'review_sheet.md'} and {path}")


def parse_support(cell: str, citations: list[str], where: str) -> list[bool]:
    pairs = dict(p.strip().split("=", 1) for p in cell.split(";") if p.strip())
    if set(pairs) != set(citations):
        raise ValueError(f"{where}: citation IDs {sorted(pairs)} differ from the trace {sorted(citations)}")
    values = [pairs[i].strip().lower() for i in citations]
    if any(v not in ("y", "n") for v in values):
        raise ValueError(f"{where}: every citation needs y or n, got {values}")
    return [v == "y" for v in values]


def grade(cell: str, where: str) -> int:
    if cell.strip() not in ("0", "1", "2"):
        raise ValueError(f"{where}: grade must be 0, 1 or 2, got {cell!r}")
    return int(cell)


def import_labels(split: str, labelled_by: str) -> None:
    rows = list(csv.DictReader((OUT_DIR / split / "review_labels.csv").open(encoding="utf-8")))
    configs = sorted({r["config"] for r in rows})
    runs = load_runs(split, configs)
    reviews: dict[str, list] = {c: [] for c in configs}
    contexts: dict[str, dict] = {c: {} for c in configs}
    for r in rows:
        where, trace = f"{r['query_id']}/{r['config']}", runs[r["config"]][r["query_id"]]
        rec = {"query_id": r["query_id"],
               "citation_support": parse_support(r["citation_support"], trace["citations"], where)}
        if r["answerable"] == "y":
            rec["answer_grade"] = grade(r["answer_grade"], where)
            if trace["status"] == "abstain" and rec["answer_grade"] != 0:
                raise ValueError(f"{where}: an abstention on an answerable question is graded 0")
            contexts[r["config"]][r["query_id"]] = grade(r["context_grade"], where)
        else:
            if r["abstention_correct"].strip().lower() not in ("y", "n"):
                raise ValueError(f"{where}: abstention_correct must be y or n")
            rec["abstention_correct"] = r["abstention_correct"].strip().lower() == "y"
        rec["reason"] = r["note"].strip()
        rec["labelled_by"] = labelled_by
        reviews[r["config"]].append(rec)
    for c in configs:
        out = OUT_DIR / split / c
        (out / "reviews.json").write_text(json.dumps(reviews[c], ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
        grades = contexts[c]
        summary = {"grades": grades, "counts": {g: sum(v == g for v in grades.values()) for g in (0, 1, 2)},
                   "mean": round(sum(grades.values()) / len(grades), 3) if grades else None}
        (out / "context_grades.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n",
                                                 encoding="utf-8", newline="\n")
        print(f"{c}: {len(reviews[c])} labels, context grades {summary['counts']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("sheet")
    s.add_argument("--split", required=True)
    s.add_argument("--configs", required=True)
    i = sub.add_parser("import")
    i.add_argument("--split", required=True)
    i.add_argument("--labelled-by", required=True)
    args = parser.parse_args()
    if args.command == "sheet":
        sheet(args.split, args.configs.split(","))
    else:
        import_labels(args.split, args.labelled_by)


if __name__ == "__main__":
    main()
