"""Reading sheet and pass/fail labels for the advanced agent's answers.

`sheet`   writes results/advanced/<split>/review_sheet.md and review_labels.csv for the given
          configurations. The sheet shows, per question, the question, the expected answer and
          grading rule, the evidence with its crop, and for each configuration the status, the
          answer, every look (question and what the vision model said), and each cited region
          with its crop, so a reader can grade the answer against the picture. The CSV holds IDs
          to fill in, no labels.
`import`  checks the filled CSV and writes results/advanced/<split>/<config>/reviews.json.

Labels (ADVANCED.md section 3), one per question and configuration:
- pass: y or n. Answerable: right and complete with unit, condition and calculation; the citation
  names the page and region and the evidence supports the whole answer; partly right, a wrong
  citation or a refusal is n. Without evidence: y when it refuses and asserts nothing unsupported.
- citation_support: one y/n per cited chunk, "ID=y; ID=n": y only if that chunk states what it is cited for.
- failure: for an n, one of retrieval (the evidence never reached the context), vision (a look
  contradicts the crop), reading (the evidence was in view but the answer misused it), calculation,
  citation, refusal (refused an answerable question), unsupported (added a claim the evidence lacks),
  error (system error).
- note: the reason.

Run from the repo root:
  python -m src.advanced.review_sheet sheet --split dev --configs V0_dense,V1_rerank,V2_rerank_look
  python -m src.advanced.review_sheet import --split dev --labelled-by "<who labelled>"
"""
import argparse
import csv
import json

from .run_agent import OUT_DIR, QUESTIONS
from .source import DATA_DIR

FIELDS = ["query_id", "config", "answerable", "pass", "failure", "citation_support", "note"]
FAILURES = {"retrieval", "vision", "reading", "calculation", "citation", "refusal", "unsupported", "error"}


def load_runs(split: str, configs: list[str]) -> dict[str, dict[str, dict]]:
    return {c: {r["query_id"]: r for r in json.loads((OUT_DIR / split / c / "traces.json").read_text(encoding="utf-8"))}
            for c in configs}


def sheet(split: str, configs: list[str], tag: str = "") -> None:
    out = OUT_DIR / split
    path = out / f"review_labels{tag}.csv"
    if path.exists():
        raise SystemExit(f"{path} exists; not overwriting the sheet or the labels")
    runs = load_runs(split, configs)
    questions = [q for q in json.loads(QUESTIONS.read_text(encoding="utf-8"))
                 if q["split"] == split and all(q["id"] in runs[c] for c in configs)]  # an extension run has a subset
    chunks = {c["id"]: c for c in json.loads((DATA_DIR / "chunks.json").read_text(encoding="utf-8"))}
    rel = "../../../data/advanced/"
    lines = [f"# Review sheet: {split}", "", "Grade each answer against the evidence and the picture; fill in review_labels.csv.", ""]
    for q in questions:
        lines += [f"## {q['id']} ({q['group']}, {'answerable' if q['answerable'] else 'no evidence'})", "",
                  f"**Question:** {q['question']}", ""]
        if q["answerable"]:
            lines += [f"**Expected:** {q['expected_answer']}", "", f"**Grading:** {q['grading']}", ""]
            for e in q["evidence"]:
                first = chunks[e["chunk_ids"][0]]
                lines += [f"- Evidence: {e['need']} (PDF page {e['page']}, {e['locator']}): {e['value']}"]
                if first["crop"]:
                    lines += [f"  ![]({rel}{first['crop']})"]
            lines += [""]
        else:
            lines += [f"**Expected:** {q['expected_behavior']}", "", f"**Why:** {q['absence_check']['why']}", ""]
        for c in configs:
            r = runs[c][q["id"]]
            lines += [f"### {c}: {r['status']} ({r['searches']} searches, {r['look_calls']} looks)", "",
                      r["answer"] or "(no answer)", ""]
            for lk in r["looks"]:
                lines += [f"- look {lk['chunk_id']}: *{lk['question']}* -> {lk['answer']}"]
            for cit in r["citations_at"]:
                lines += [f"- cited {cit['id']} (PDF page {cit['page']}, printed {cit['page_label']})"]
                if cit["crop"]:
                    lines += [f"  ![]({rel}{cit['crop']})"]
            lines += [f"- evidence in context: {r.get('context_hit', 'n/a')}", ""]
    (out / f"review_sheet{tag}.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for q in questions:
            for c in configs:
                r = runs[c][q["id"]]
                w.writerow({"query_id": q["id"], "config": c, "answerable": "y" if q["answerable"] else "n",
                            "citation_support": "; ".join(f"{i}=" for i in r["citations"])})
    print(f"wrote {out / f'review_sheet{tag}.md'} and {path}")


def parse_support(cell: str, citations: list[str], where: str) -> list[bool]:
    pairs = dict(p.strip().split("=", 1) for p in cell.split(";") if p.strip())
    if set(pairs) != set(citations):
        raise ValueError(f"{where}: citation IDs {sorted(pairs)} differ from the trace {sorted(citations)}")
    values = [pairs[i].strip().lower() for i in citations]
    if any(v not in ("y", "n") for v in values):
        raise ValueError(f"{where}: every citation needs y or n, got {values}")
    return [v == "y" for v in values]


def import_labels(split: str, labelled_by: str, tag: str = "") -> None:
    rows = list(csv.DictReader((OUT_DIR / split / f"review_labels{tag}.csv").open(encoding="utf-8")))
    configs = sorted({r["config"] for r in rows})
    runs = load_runs(split, configs)
    reviews: dict[str, list] = {c: [] for c in configs}
    for r in rows:
        where, trace = f"{r['query_id']}/{r['config']}", runs[r["config"]][r["query_id"]]
        verdict = r["pass"].strip().lower()
        if verdict not in ("y", "n"):
            raise ValueError(f"{where}: pass must be y or n")
        failure = r["failure"].strip().lower()
        if verdict == "n" and failure not in FAILURES:
            raise ValueError(f"{where}: a fail needs a failure type from {sorted(FAILURES)}")
        if verdict == "y" and failure:
            raise ValueError(f"{where}: a pass has no failure type")
        if trace["status"] == "error" and verdict == "y":
            raise ValueError(f"{where}: a system error is a fail")
        reviews[r["config"]].append({
            "query_id": r["query_id"], "group": trace["group"], "answerable": r["answerable"] == "y",
            "pass": verdict == "y", "failure": failure or None,
            "citation_support": parse_support(r["citation_support"], trace["citations"], where),
            "reason": r["note"].strip(), "labelled_by": labelled_by})
    for c in configs:
        (OUT_DIR / split / c / "reviews.json").write_text(json.dumps(reviews[c], ensure_ascii=False, indent=1) + "\n",
                                                         encoding="utf-8", newline="\n")
        print(f"{c}: {len(reviews[c])} labels, {sum(x['pass'] for x in reviews[c])} pass")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("sheet")
    s.add_argument("--split", required=True)
    s.add_argument("--configs", required=True)
    s.add_argument("--tag", default="", help="suffix for the sheet and CSV names, e.g. _ext")
    i = sub.add_parser("import")
    i.add_argument("--split", required=True)
    i.add_argument("--labelled-by", required=True)
    i.add_argument("--tag", default="")
    args = parser.parse_args()
    if args.command == "sheet":
        sheet(args.split, args.configs.split(","), args.tag)
    else:
        import_labels(args.split, args.labelled_by, args.tag)


if __name__ == "__main__":
    main()
