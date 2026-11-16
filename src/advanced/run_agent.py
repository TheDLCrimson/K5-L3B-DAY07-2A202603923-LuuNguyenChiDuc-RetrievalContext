"""Run the advanced agent on one split for one configuration; write traces and automatic metrics.

Writes results/advanced/<split>/<config>/:
- traces.json: one record per question: status, answer, citations (with page and region), every
  search with all fetched ranks, every look (question, answer, model, cost), the final context,
  tokens, cost and time, and the gold-based checks added after the run (the agent never sees them);
- summary.json / summary.md: measures that need no reading: tool use, call counts, status counts,
  evidence in the final context (every evidence item of the question has a chunk in it), abstentions,
  tokens, cost and time, overall and per group.
Whether an answer passes (right, complete, supported by the cited region) is decided by reading
and recorded in reviews.json (src/advanced/review_sheet.py, src/advanced/metrics.py).

Run from the repo root:  python -m src.advanced.run_agent --split dev --config V2_rerank_look
Test needs --final, and only the two configurations named in results/advanced/selection.json
(the chosen one and the baseline) may run on it.
"""
import argparse
import json
import statistics
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ..day6 import REPO_ROOT
from ..providers import Provider
from ..retrieval import Bm25Retriever, CrossEncoderScorer, HybridRetriever, RerankRetriever
from .agent import AdvAgent
from .index import AdvDenseRetriever, load_chunks
from .source import DATA_DIR

OUT_DIR = REPO_ROOT / "results" / "advanced"
QUESTIONS = DATA_DIR / "benchmark" / "questions.json"
STRONG_LOOK_MODEL = "anthropic/claude-sonnet-5.5"
CONFIGS = {
    "V0_dense": {"retriever": "dense", "look": None,
                 "note": "baseline: dense search only, the agent reads extracted text and descriptions"},
    "V1_rerank": {"retriever": "hybrid_rerank_pool10", "look": None,
                  "note": "V0 with the base lab's best retrieval (hybrid, top 10 per side, cross-encoder rerank)"},
    "V2_rerank_look": {"retriever": "hybrid_rerank_pool10", "look": "same",
                       "note": "V1 plus the look tool: the agent reads values from the crop with the same model"},
    "V3_rerank_look_strong": {"retriever": "hybrid_rerank_pool10", "look": STRONG_LOOK_MODEL,
                              "note": "V2 with a stronger vision model behind look"},
}


def build_retriever(name: str, parts: dict[str, Any]):
    if "dense" not in parts:
        parts["dense"] = AdvDenseRetriever()
    if name == "dense":
        return parts["dense"]
    if name == "hybrid_rerank_pool10":
        parts.setdefault("bm25", Bm25Retriever(load_chunks()))
        parts.setdefault("scorer", CrossEncoderScorer())
        return RerankRetriever(HybridRetriever(parts["dense"], parts["bm25"], candidates=10), parts["scorer"])
    raise ValueError(f"unknown retriever {name!r}")


def build_agent(config: str, parts: dict[str, Any]) -> AdvAgent:
    spec = CONFIGS[config]
    provider = Provider()
    look = None
    if spec["look"]:
        look = provider if spec["look"] == "same" else Provider(model=spec["look"])
    return AdvAgent(provider, build_retriever(spec["retriever"], parts), look)


def covers(items: list[dict], ids) -> bool:
    return all(any(c in ids for c in item["chunk_ids"]) for item in items)


def score(record: dict[str, Any], q: dict[str, Any]) -> dict[str, Any]:
    """Gold-based checks added after the run: is every evidence item in the context, was it cited."""
    if q["answerable"] and record["status"] != "error":
        items = q["evidence"]
        searches = [e for e in record["events"] if e["event"] == "search"]
        record["context_hit"] = covers(items, record["context_ids"])
        record["first_search_hit"] = bool(searches) and covers(items, searches[0]["shown"])
        record["cited_gold"] = covers(items, record["citations"])
        record["evidence_items"] = len(items)
        record["evidence_items_in_context"] = sum(any(c in record["context_ids"] for c in i["chunk_ids"]) for i in items)
    return record


def ratio(n: int, total: int) -> dict[str, Any]:
    return {"n": n, "N": total, "rate": round(n / total, 4) if total else None}


def summarize(rows: list[dict]) -> dict[str, Any]:
    ok = [r for r in rows if r["status"] != "error"]
    ans = [r for r in ok if r["answerable"]]
    unans = [r for r in ok if not r["answerable"]]
    answered = [r for r in ok if r["status"] == "answered"]
    groups = sorted({r["group"] for r in ans})
    return {
        "questions": len(rows),
        "errors": [{"id": r["query_id"], "reason": r["reason"]} for r in rows if r["status"] == "error"],
        "status": dict(Counter(r["status"] for r in rows)),
        "tool_use": ratio(sum(r["searches"] > 0 for r in ok), len(ok)),
        "search_distribution": dict(sorted(Counter(r["searches"] for r in ok).items())),
        "look_distribution": dict(sorted(Counter(r["look_calls"] for r in ok).items())),
        "context_evidence_rate": ratio(sum(r["context_hit"] for r in ans), len(ans)),
        "context_evidence_by_group": {g: ratio(sum(r["context_hit"] for r in ans if r["group"] == g),
                                               sum(r["group"] == g for r in ans)) for g in groups},
        "first_search_evidence": ratio(sum(r["first_search_hit"] for r in ans), len(ans)),
        "answered_citing_all_evidence": ratio(sum(r["cited_gold"] for r in ans if r["status"] == "answered"),
                                              sum(r["status"] == "answered" for r in ans)),
        "abstained_on_unanswerable": ratio(sum(r["status"] == "abstain" for r in unans), len(unans)),
        "abstained_on_answerable": ratio(sum(r["status"] == "abstain" for r in ans), len(ans)),
        "answers_with_citations": ratio(sum(bool(r["citations"]) for r in answered), len(answered)),
        "events": dict(Counter(e["event"] for r in ok for e in r["events"])),
        "model_calls_mean": round(statistics.mean(r["model_calls"] for r in ok), 2) if ok else None,
        "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
        "completion_tokens": sum(r["completion_tokens"] for r in rows),
        "cost_usd": round(sum(r["cost_usd"] for r in rows), 6),
        "ms_median": round(statistics.median(r["ms"] for r in ok), 1) if ok else None,
        "ms_p90": round(statistics.quantiles([r["ms"] for r in ok], n=10)[-1], 1) if len(ok) > 1 else None,
        "context_missed": [r["query_id"] for r in ans if not r["context_hit"]],
        "abstained_answerable_ids": [r["query_id"] for r in ans if r["status"] == "abstain"],
        "answered_unanswerable_ids": [r["query_id"] for r in unans if r["status"] == "answered"],
    }


def fmt(x: dict) -> str:
    return f"{x['n']}/{x['N']} ({x['rate']:.0%})" if x["N"] else "0/0 (n/a)"


def markdown(name: str, split: str, config: dict, s: dict) -> str:
    rows = [("Status", ", ".join(f"{k} {v}" for k, v in s["status"].items())),
            ("Tool use (questions with a search / runs without error)", fmt(s["tool_use"])),
            ("Searches per question", ", ".join(f"{k}: {v}" for k, v in s["search_distribution"].items())),
            ("Looks per question", ", ".join(f"{k}: {v}" for k, v in s["look_distribution"].items())),
            ("Evidence in the final context (answerable, every item)", fmt(s["context_evidence_rate"])),
            ("Evidence in the first search", fmt(s["first_search_evidence"])),
            ("Answered citing every evidence item", fmt(s["answered_citing_all_evidence"])),
            ("Abstained on no-evidence questions", fmt(s["abstained_on_unanswerable"])),
            ("Abstained on answerable questions", fmt(s["abstained_on_answerable"])),
            ("Answers with citations", fmt(s["answers_with_citations"])),
            ("Model calls per question (mean)", s["model_calls_mean"]),
            ("Cost (USD)", s["cost_usd"]), ("Time median / p90 (ms)", f"{s['ms_median']} / {s['ms_p90']}")]
    lines = [f"# {name} on {split}", "", "| Measure | Value |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in rows]
    lines += ["", "Evidence in context by group: " + ", ".join(f"{g} {fmt(v)}" for g, v in s["context_evidence_by_group"].items()),
              "", f"Configuration: `{json.dumps(config, ensure_ascii=False)}`", ""]
    return "\n".join(lines)


def write_outputs(split: str, name: str, agent: AdvAgent, rows: list[dict], spec: dict, folder: str) -> None:
    out = OUT_DIR / split / folder
    out.mkdir(parents=True, exist_ok=True)
    (out / "traces.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    summary = summarize(rows)
    config = {"name": name, **agent.config(), "note": spec["note"]}
    (out / "summary.json").write_text(json.dumps(
        {"config": config, "ran_at": datetime.now(UTC).isoformat(timespec="seconds"), "system_prompt": agent.system,
         "tools": agent.tools, "summary": summary}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    (out / "summary.md").write_text(markdown(name, split, config, summary) + "\n", encoding="utf-8", newline="\n")
    print(f"{split}/{folder}: {summary['questions']} questions, errors {len(summary['errors'])}, "
          f"context evidence {fmt(summary['context_evidence_rate'])}, cost ${summary['cost_usd']}, "
          f"median {summary['ms_median']} ms")


def allowed_on_test(config: str) -> bool:
    path = OUT_DIR / "selection.json"
    if not path.exists():
        return False
    chosen = json.loads(path.read_text(encoding="utf-8"))
    return config in (chosen["chosen"], chosen["baseline_for_test"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", required=True, choices=["dev", "test"])
    parser.add_argument("--config", required=True, choices=sorted(CONFIGS))
    parser.add_argument("--ids", help="comma-separated question ids for a smoke test (written to a _smoke folder)")
    parser.add_argument("--final", action="store_true", help="required for test")
    args = parser.parse_args()
    if args.split == "test" and not args.final:
        raise SystemExit("test is run once, after the choice is frozen: pass --final")
    if args.split == "test" and not allowed_on_test(args.config):
        raise SystemExit("test runs only the configurations named in results/advanced/selection.json")
    questions = [q for q in json.loads(QUESTIONS.read_text(encoding="utf-8")) if q["split"] == args.split]
    if args.ids:
        wanted = set(args.ids.split(","))
        questions = [q for q in questions if q["id"] in wanted]
    parts: dict[str, Any] = {}
    agent = build_agent(args.config, parts)
    rows = []
    for q in questions:
        out = agent.run(q["question"])
        rows.append(score({"query_id": q["id"], "split": q["split"], "group": q["group"], "answerable": q["answerable"],
                           "question": q["question"], **out}, q))
        print(f"  {q['id']}: {out['status']} ({out['searches']} searches, {out['look_calls']} looks, "
              f"{out['ms'] / 1000:.1f} s, ${out['cost_usd']:.4f})")
    write_outputs(args.split, args.config, agent, rows, CONFIGS[args.config],
                  f"{args.config}_smoke" if args.ids else args.config)


if __name__ == "__main__":
    main()
