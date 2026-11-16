"""Pass rates from the labels: overall and per group, with the rubric's counting rules.

Reads results/advanced/<split>/<config>/traces.json and reviews.json and writes
metrics.json / metrics.md in the same folder (ADVANCED.md section 3):
- pass rate = passes / all questions of the split, errors included in the denominator;
- n/N overall and per group (including the no-evidence questions);
- errors, time and cost reported separately; abstention and false abstention;
- citation support (cited chunks that state what they are cited for) and failure types.

Run from the repo root:  python -m src.advanced.metrics --split dev --configs V0_dense,V1_rerank
The pass rate is never rounded: 27/30 is the threshold on a 30-question test.
"""
import argparse
import json
from collections import Counter

from .run_agent import OUT_DIR, fmt, ratio


def metrics(split: str, config: str, extension: str = "") -> dict:
    """Pass rates for one configuration; with `extension` (a folder suffix such as _ext) the traces and
    labels of that second run of extra questions are added, and the files are named metrics_with<suffix>."""
    folder = OUT_DIR / split / config
    traces, reviews = {}, []
    for f in [folder] + ([OUT_DIR / split / f"{config}{extension}"] if extension else []):
        traces.update({r["query_id"]: r for r in json.loads((f / "traces.json").read_text(encoding="utf-8"))})
        reviews += json.loads((f / "reviews.json").read_text(encoding="utf-8"))
    if {r["query_id"] for r in reviews} != set(traces):
        raise SystemExit(f"{config}: labels cover {len(reviews)} questions, traces {len(traces)}")
    groups = sorted({r["group"] for r in reviews})
    ans = [r for r in reviews if r["answerable"]]
    unans = [r for r in reviews if not r["answerable"]]
    cites = [s for r in reviews for s in r["citation_support"]]
    out = {
        "config": config, "split": split,
        "pass_rate": ratio(sum(r["pass"] for r in reviews), len(reviews)),
        "pass_by_group": {g: ratio(sum(r["pass"] for r in reviews if r["group"] == g),
                                   sum(r["group"] == g for r in reviews)) for g in groups},
        "pass_answerable": ratio(sum(r["pass"] for r in ans), len(ans)),
        "pass_no_evidence": ratio(sum(r["pass"] for r in unans), len(unans)),
        "errors": sum(t["status"] == "error" for t in traces.values()),
        "false_abstention": ratio(sum(traces[r["query_id"]]["status"] == "abstain" for r in ans), len(ans)),
        "citation_support": ratio(sum(cites), len(cites)),
        "failure_types": dict(Counter(r["failure"] for r in reviews if not r["pass"])),
        "failed": [r["query_id"] for r in reviews if not r["pass"]],
        "cost_usd": round(sum(t["cost_usd"] for t in traces.values()), 6),
        "cost_per_question_usd": round(sum(t["cost_usd"] for t in traces.values()) / len(traces), 5),
        "ms_median": sorted(t["ms"] for t in traces.values())[len(traces) // 2],
        "context_evidence_rate": ratio(sum(t.get("context_hit", False) for t in traces.values() if t["answerable"]),
                                       sum(t["answerable"] for t in traces.values())),
    }
    lines = [f"# {config} on {split}: pass or fail by reading", "", "| Measure | Value |", "| --- | --- |",
             f"| Pass rate | {fmt(out['pass_rate'])} |"]
    lines += [f"| Pass, {g} | {fmt(v)} |" for g, v in out["pass_by_group"].items()]
    lines += [f"| Pass, answerable | {fmt(out['pass_answerable'])} |",
              f"| Pass, no evidence | {fmt(out['pass_no_evidence'])} |", f"| System errors | {out['errors']} |",
              f"| False abstention | {fmt(out['false_abstention'])} |",
              f"| Cited chunks that support the answer | {fmt(out['citation_support'])} |",
              f"| Evidence in context | {fmt(out['context_evidence_rate'])} |",
              f"| Failure types | {', '.join(f'{k} {v}' for k, v in out['failure_types'].items()) or 'none'} |",
              f"| Failed | {', '.join(out['failed']) or 'none'} |",
              f"| Cost per question (USD) | {out['cost_per_question_usd']} |", f"| Time median (ms) | {out['ms_median']} |", ""]
    (folder / f"metrics{'_with' + extension if extension else ''}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    (folder / f"metrics{'_with' + extension if extension else ''}.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"{config}/{split}: pass {fmt(out['pass_rate'])}; by group "
          + ", ".join(f"{g} {v['n']}/{v['N']}" for g, v in out["pass_by_group"].items()))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", required=True)
    parser.add_argument("--configs", required=True)
    parser.add_argument("--extension", default="", help="folder suffix of an extra run to add, e.g. _ext")
    args = parser.parse_args()
    for c in args.configs.split(","):
        metrics(args.split, c, args.extension)


if __name__ == "__main__":
    main()
