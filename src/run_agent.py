"""Run the agent on one split for one configuration and write traces and automatic metrics.

Writes results/agent/<split>/<config>/:
- traces.json: one record per question in the starter's agent_metrics.py format
  (query_id, status, events with `event: "search"` per retrieval call, citations) plus
  the answer, every model turn, the final context, tokens, cost and time;
- summary.json / summary.md: the measures that need no human reading. These are tool use,
  call counts, status counts, Context Evidence Rate (gold in the chunks the model saw),
  abstentions and false abstentions by status, citation IDs found in the context, tokens,
  cost and time.
Whether an answer is right and whether each citation supports it is labelled by reading,
in reviews.json, and aggregated by starter/agent_metrics.py; nothing here judges content.

Run from the repo root:  python -m src.run_agent --split dev --config A1_rerank
Test is refused unless --final is given, so it cannot be run by accident while tuning.
"""
import argparse
import json
import statistics
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from .agent import Agent
from .build_benchmark import QUESTIONS_PATH
from .day6 import REPO_ROOT
from .evidence import any_hit, evidence_hit
from .export_day6 import load_chunks
from .providers import Provider
from .retrieval import Bm25Retriever, CrossEncoderScorer, DenseRetriever, HybridRetriever, RerankRetriever

OUT_DIR = REPO_ROOT / "results" / "agent"
CONFIGS = {
    "A0_dense": {"retriever": "dense", "per_version": False,
                 "note": "baseline: the agent with dense search on the Day 6 index"},
    "A1_rerank": {"retriever": "hybrid_rerank", "per_version": False,
                  "note": "the agent with the retrieval chosen in E1"},
    "A3_rerank_per_version": {"retriever": "hybrid_rerank", "per_version": True,
                              "note": "A1, searching each law version when the question names none"},
    "A4_rerank_pool10": {"retriever": "hybrid_rerank_pool10", "per_version": False,
                         "note": "A1 with a rerank pool of the top 10 per side instead of 20"},
    "A5_per_version_pool10": {"retriever": "hybrid_rerank_pool10", "per_version": True,
                              "note": "A3 and A4 combined"},
}


def build_retriever(name: str):
    dense = DenseRetriever()
    if name == "dense":
        return dense
    if name in ("hybrid_rerank", "hybrid_rerank_pool10"):
        pool = 20 if name == "hybrid_rerank" else 10
        return RerankRetriever(HybridRetriever(dense, Bm25Retriever(), candidates=pool), CrossEncoderScorer())
    raise ValueError(f"unknown retriever {name!r}")


def score(record: dict[str, Any], q: dict[str, Any], chunks_by_id: dict[str, dict]) -> dict[str, Any]:
    """Add the gold-based checks to a trace after the run; the agent never sees these."""
    if q["answerable"] and record["status"] != "error":
        hit = lambda ids: any(any_hit(chunks_by_id[i], q["gold"]) for i in ids)
        searches = [e for e in record["events"] if e["event"] == "search"]
        record["context_hit"] = hit(record["context_ids"])
        record["first_search_hit"] = bool(searches) and hit(searches[0]["shown"])
        record["cited_gold"] = hit(record["citations"])
        gold_years = {gold_year(g) for g in q["gold"]}
        record["both_laws_expected"] = not q.get("filter") and gold_years == {2013, 2024}
        record["cited_gold_years"] = sorted({gold_year(g) for g in q["gold"] for i in record["citations"]
                                             if evidence_hit(chunks_by_id[i], g)})
    if record["status"] != "error":
        year = (q.get("filter") or {}).get("year")
        record["filter_year"] = year
        record["wrong_version_citations"] = ([i for i in record["citations"]
                                              if chunks_by_id[i]["metadata"]["year"] != year] if year else [])
    return record


def gold_year(gold: dict[str, Any]) -> int:
    return 2013 if gold["source_id"] == "ldd2013" else 2024


def trace(agent: Agent, q: dict[str, Any], chunks_by_id: dict[str, dict]) -> dict[str, Any]:
    out = agent.run(q["question"])
    record = {"query_id": q["id"], "split": q["split"], "type": q["type"], "answerable": q["answerable"],
              "question": q["question"], **out}
    return score(record, q, chunks_by_id)


def ratio(n: int, total: int) -> dict[str, Any]:
    return {"n": n, "N": total, "rate": round(n / total, 4) if total else None}


def summarize(rows: list[dict]) -> dict[str, Any]:
    ok = [r for r in rows if r["status"] != "error"]
    ans = [r for r in ok if r["answerable"]]
    unans = [r for r in ok if not r["answerable"]]
    answered = [r for r in ok if r["status"] == "answered"]
    searches = [sum(e["event"] == "search" for e in r["events"]) for r in ok]
    events = Counter(e["event"] for r in ok for e in r["events"])
    reasons = Counter(r.get("reason") for r in ok if r["status"] == "abstain")
    return {
        "questions": len(rows),
        "errors": [{"id": r["query_id"], "reason": r["reason"]} for r in rows if r["status"] == "error"],
        "status": dict(Counter(r["status"] for r in rows)),
        "tool_use": ratio(sum(n > 0 for n in searches), len(ok)),
        "retrieval_calls_distribution": dict(sorted(Counter(searches).items())),
        "context_evidence_rate": ratio(sum(r["context_hit"] for r in ans), len(ans)),
        "first_search_evidence": ratio(sum(r["first_search_hit"] for r in ans), len(ans)),
        "answered_citing_a_gold_chunk": ratio(sum(r["cited_gold"] for r in ans if r["status"] == "answered"),
                                             sum(r["status"] == "answered" for r in ans)),
        "both_laws_cited": ratio(sum(len(r["cited_gold_years"]) == 2 for r in ans if r["both_laws_expected"]),
                                 sum(r["both_laws_expected"] for r in ans)),
        "both_laws_missed": [r["query_id"] for r in ans if r["both_laws_expected"] and len(r["cited_gold_years"]) < 2],
        "wrong_version_citations": ratio(sum(len(r["wrong_version_citations"]) for r in ok),
                                         sum(len(r["citations"]) for r in ok if r["filter_year"])),
        "abstained_on_unanswerable": ratio(sum(r["status"] == "abstain" for r in unans), len(unans)),
        "abstained_on_answerable": ratio(sum(r["status"] == "abstain" for r in ans), len(ans)),
        "answers_with_citations": ratio(sum(bool(r["citations"]) for r in answered), len(answered)),
        "abstain_reasons": dict(reasons),
        "events": dict(events),
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
            ("Tool use (questions with a retrieval call / runs without error)", fmt(s["tool_use"])),
            ("Retrieval calls per question", ", ".join(f"{k}: {v}" for k, v in s["retrieval_calls_distribution"].items())),
            ("Context Evidence Rate (answerable)", fmt(s["context_evidence_rate"])),
            ("Gold in the first search's results (answerable)", fmt(s["first_search_evidence"])),
            ("Answered and cited a gold chunk (ID check, not a support label)", fmt(s["answered_citing_a_gold_chunk"])),
            ("Cited gold from both laws (no version named, gold in both)", fmt(s["both_laws_cited"])),
            ("Citations from the other law version (version named)", fmt(s["wrong_version_citations"])),
            ("Abstained on unanswerable (status only; confirmed by reading)", fmt(s["abstained_on_unanswerable"])),
            ("Abstained on answerable", fmt(s["abstained_on_answerable"])),
            ("Answers with citations", fmt(s["answers_with_citations"])),
            ("Model calls per question (mean)", str(s["model_calls_mean"])),
            ("Tokens in / out", f"{s['prompt_tokens']} / {s['completion_tokens']}"),
            ("Cost (USD, as billed by OpenRouter)", f"{s['cost_usd']:.4f}"),
            ("Time per question, median / p90 (ms)", f"{s['ms_median']} / {s['ms_p90']}"),
            ("Errors", str(len(s["errors"])))]
    lines = [f"# Agent {name} on {split}", "", f"`{json.dumps(config, ensure_ascii=False)}`", "",
             "| Measure | Value |", "| --- | --- |", *[f"| {k} | {v} |" for k, v in rows], "",
             f"Context missed: {', '.join(s['context_missed']) or 'none'}.",
             f"Abstained on answerable: {', '.join(s['abstained_answerable_ids']) or 'none'}.",
             f"Answered unanswerable: {', '.join(s['answered_unanswerable_ids']) or 'none'}."]
    return "\n".join(lines) + "\n"


def write_cases(questions: list[dict]) -> None:
    """cases.json for starter/agent_metrics.py: id, split, answerable for every question."""
    path = OUT_DIR / "cases.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    cases = [{"id": q["id"], "split": q["split"], "answerable": q["answerable"]} for q in questions]
    path.write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--config", choices=sorted(CONFIGS), required=True)
    parser.add_argument("--ids", help="comma-separated question IDs, for a smoke run (not a benchmark run)")
    parser.add_argument("--final", action="store_true", help="required for test, once the choice is fixed")
    parser.add_argument("--resummarize", action="store_true",
                        help="recompute gold checks and the summary from saved traces, without calling the model")
    args = parser.parse_args()
    if args.split == "test" and not (args.final or args.resummarize):
        parser.error("test is run once, after the configuration is fixed on dev; pass --final")

    all_questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    write_cases(all_questions)
    questions = [q for q in all_questions if q["split"] == args.split]
    if args.ids:
        wanted = args.ids.split(",")
        questions = [q for q in questions if q["id"] in wanted]
    chunks = load_chunks()
    chunks_by_id = {c["id"]: c for c in chunks}
    if args.resummarize:
        out = OUT_DIR / args.split / args.config
        record = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        by_id = {q["id"]: q for q in all_questions}
        rows = [score(r, by_id[r["query_id"]], chunks_by_id)
                for r in json.loads((out / "traces.json").read_text(encoding="utf-8"))]
        record["summary"] = summarize(rows)
        write_outputs(out, record, rows)
        return
    cfg = CONFIGS[args.config]
    agent = Agent(Provider(), build_retriever(cfg["retriever"]), per_version=cfg["per_version"])
    agent.retriever.search("đất đai", 1)  # load models before timing

    rows = []
    for q in questions:
        rows.append(trace(agent, q, chunks_by_id))
        r = rows[-1]
        print(f"{q['id']}: {r['status']} searches={r['searches']} cites={r['citations']} "
              f"ctx_hit={r.get('context_hit')} ${r['cost_usd']:.5f} {r['ms'] / 1000:.1f}s", flush=True)
    out = OUT_DIR / args.split / (args.config if not args.ids else f"{args.config}_smoke")
    config = {"name": args.config, **agent.config(), "note": cfg["note"]}
    record = {"split": args.split, "config": config, "ran_at": datetime.now(UTC).isoformat(timespec="seconds"),
              "system_prompt": agent.system, "tools": agent.tools, "summary": summarize(rows)}
    write_outputs(out, record, rows)


def write_outputs(out, record: dict, rows: list[dict]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "traces.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                                     newline="\n")
    (out / "summary.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                                      newline="\n")
    md = markdown(record["config"]["name"], record["split"], record["config"], record["summary"])
    (out / "summary.md").write_text(md, encoding="utf-8", newline="\n")
    print(md)


if __name__ == "__main__":
    main()
