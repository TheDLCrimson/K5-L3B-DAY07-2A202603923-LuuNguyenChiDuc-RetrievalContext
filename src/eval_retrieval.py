"""Retrieval and context metrics for every method on one split, from the original questions.

Per method it writes results/retrieval/<split>/<method>/traces.jsonl (one line per question:
query, filter, top 20 with scores and hits, packed context, time, error) and a combined
results/retrieval/<split>/summary.json and summary.md.

Measures, over answerable questions only (unanswerable ones are traced, never counted):
Hit@1, Evidence Hit@3, MRR@10, Hit@20, and Context Evidence Rate for the top results packed
into the context budget. Errors are counted separately and are not scored as misses.

Run from the repo root:  python -m src.eval_retrieval --split dev
Test is refused unless --final is given, so it cannot be run by accident while tuning.
"""
import argparse
import json
import statistics
import time
from datetime import UTC, datetime
from typing import Any

from . import context
from .build_benchmark import QUESTIONS_PATH
from .day6 import REPO_ROOT
from .evidence import any_hit
from .retrieval import (
    Bm25Retriever,
    CrossEncoderScorer,
    DenseRetriever,
    HybridRetriever,
    RerankRetriever,
    RetrievalError,
)

OUT_DIR = REPO_ROOT / "results" / "retrieval"
DEPTH = 20  # results kept per query; Hit@1/@3, MRR@10 and Hit@20 are read from this list
CONTEXT_TOP = 3  # results offered to the packer, in rank order
METHODS = ("dense", "bm25", "hybrid", "hybrid_rrf", "hybrid_rerank", "hybrid_rerank_pool10")


def build(methods: list[str]) -> dict[str, Any]:
    dense, bm25 = DenseRetriever(), Bm25Retriever()
    built = {"dense": dense, "bm25": bm25, "hybrid": HybridRetriever(dense, bm25, "weighted"),
             "hybrid_rrf": HybridRetriever(dense, bm25, "rrf")}
    if {"hybrid_rerank", "hybrid_rerank_pool10"} & set(methods):
        scorer = CrossEncoderScorer()
        built["hybrid_rerank"] = RerankRetriever(built["hybrid"], scorer)
        built["hybrid_rerank_pool10"] = RerankRetriever(HybridRetriever(dense, bm25, candidates=10), scorer)
    return {m: built[m] for m in methods}


def trace_one(retriever, q: dict) -> dict[str, Any]:
    year = (q.get("filter") or {}).get("year")
    row = {"id": q["id"], "split": q["split"], "type": q["type"], "answerable": q["answerable"],
           "query": q["question"], "filter": q.get("filter"), "method": retriever.name}
    start = time.perf_counter()
    try:
        results = retriever.search(q["question"], DEPTH, year)
    except RetrievalError as exc:
        return {**row, "status": "error", "error": str(exc), "ms": round((time.perf_counter() - start) * 1000, 1)}
    ms = round((time.perf_counter() - start) * 1000, 1)
    golds = q.get("gold", [])
    packed, skipped = context.pack(results[:CONTEXT_TOP])
    row.update(status="ok", ms=ms,
               results=[{"rank": r["rank"], "id": r["id"], "score": r["score"], "source_id": r["source_id"],
                         "page": r["page"], "page_end": r["metadata"]["page_end"], "year": r["metadata"]["year"],
                         "articles": r["metadata"]["articles"], "hit": any_hit(r, golds) if golds else None}
                        for r in results],
               context_ids=[c["id"] for c in packed], context_skipped=skipped,
               context_chars=len(context.render(packed)))
    if getattr(retriever, "last_truncated", 0):
        row["rerank_pairs_truncated"] = retriever.last_truncated
    if q["answerable"]:
        first = next((r["rank"] for r in row["results"] if r["hit"]), None)
        row.update(first_hit_rank=first, hit_at_1=first == 1, hit_at_3=first is not None and first <= 3,
                   context_hit=any(any_hit(c, golds) for c in packed))
    else:
        row["top_score"] = results[0]["score"] if results else None
    return row


def ratio(n: int, total: int) -> dict[str, Any]:
    return {"n": n, "N": total, "rate": round(n / total, 4) if total else None}


def summarize(rows: list[dict]) -> dict[str, Any]:
    ok = [r for r in rows if r["status"] == "ok"]
    ans = [r for r in ok if r["answerable"]]
    n = len(ans)
    ranks = [r["first_hit_rank"] for r in ans]
    return {
        "answerable": n, "unanswerable_traced": sum(not r["answerable"] for r in ok),
        "errors": [{"id": r["id"], "error": r["error"]} for r in rows if r["status"] == "error"],
        "hit_at_1": ratio(sum(r["hit_at_1"] for r in ans), n),
        "evidence_hit_at_3": ratio(sum(r["hit_at_3"] for r in ans), n),
        "mrr_at_10": round(sum(1 / k for k in ranks if k and k <= 10) / n, 4) if n else None,
        "hit_at_20": ratio(sum(k is not None for k in ranks), n),
        "context_evidence_rate": ratio(sum(r["context_hit"] for r in ans), n),
        "misses_at_3": [r["id"] for r in ans if not r["hit_at_3"]],
        "ms_median": round(statistics.median(r["ms"] for r in ok), 1) if ok else None,
        "ms_p90": round(statistics.quantiles([r["ms"] for r in ok], n=10)[-1], 1) if len(ok) > 1 else None,
        "context_chars_max": max((r["context_chars"] for r in ok), default=0),
        "by_type": {t: ratio(sum(r["hit_at_3"] for r in ans if r["type"] == t), sum(r["type"] == t for r in ans))
                    for t in sorted({r["type"] for r in ans})},
    }


def fmt(x: dict) -> str:
    return f"{x['n']}/{x['N']} ({x['rate']:.0%})" if x["N"] else "0/0"


def markdown(split: str, summaries: dict[str, dict], configs: dict[str, dict]) -> str:
    lines = [f"# Retrieval on {split}", "",
             "| Method | Hit@1 | Evidence Hit@3 | MRR@10 | Hit@20 | Context Evidence Rate | Median ms | Errors |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for m, s in summaries.items():
        lines.append(f"| {m} | {fmt(s['hit_at_1'])} | {fmt(s['evidence_hit_at_3'])} | {s['mrr_at_10']} | "
                     f"{fmt(s['hit_at_20'])} | {fmt(s['context_evidence_rate'])} | {s['ms_median']} | "
                     f"{len(s['errors'])} |")
    lines += ["", "Misses at 3:", ""]
    lines += [f"- {m}: {', '.join(s['misses_at_3']) or 'none'}" for m, s in summaries.items()]
    lines += ["", "Configurations:", ""]
    lines += [f"- {m}: `{json.dumps(c, ensure_ascii=False)}`" for m, c in configs.items()]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--methods", default=",".join(METHODS))
    parser.add_argument("--final", action="store_true", help="required for test, once the choice is fixed")
    args = parser.parse_args()
    if args.split == "test" and not args.final:
        parser.error("test is run once, after the configuration is fixed on dev; pass --final")
    methods = [m.strip() for m in args.methods.split(",")]
    unknown = set(methods) - set(METHODS)
    if unknown:
        parser.error(f"unknown methods {sorted(unknown)}")

    questions = [q for q in json.loads(QUESTIONS_PATH.read_text(encoding="utf-8")) if q["split"] == args.split]
    retrievers = build(methods)
    for r in retrievers.values():  # warm up so model loading is not counted in per-query time
        r.search("đất đai", 1)
    out = OUT_DIR / args.split
    summaries, configs = {}, {}
    for m, retriever in retrievers.items():
        rows = [trace_one(retriever, q) for q in questions]
        (out / m).mkdir(parents=True, exist_ok=True)
        with (out / m / "traces.jsonl").open("w", encoding="utf-8", newline="\n") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        summaries[m], configs[m] = summarize(rows), retriever.config()
        print(f"{m}: Hit@1 {fmt(summaries[m]['hit_at_1'])}, Hit@3 {fmt(summaries[m]['evidence_hit_at_3'])}, "
              f"errors {len(summaries[m]['errors'])}")
    ran_at = datetime.now(UTC).isoformat(timespec="seconds")
    previous = out / "summary.json"
    if previous.exists():  # keep methods run earlier; each method records when it ran
        old = json.loads(previous.read_text(encoding="utf-8"))
        old_ran = old.get("method_ran_at", {m: old["ran_at"] for m in old["summaries"]})
        summaries = {**{m: s for m, s in old["summaries"].items() if m not in summaries}, **summaries}
        configs = {**{m: c for m, c in old["configs"].items() if m not in configs}, **configs}
        method_ran_at = {**old_ran, **{m: ran_at for m in retrievers}}
    else:
        method_ran_at = {m: ran_at for m in retrievers}
    order = [m for m in METHODS if m in summaries]
    summaries, configs = {m: summaries[m] for m in order}, {m: configs[m] for m in order}
    record = {"split": args.split, "ran_at": ran_at, "method_ran_at": {m: method_ran_at[m] for m in order},
              "context_budget_chars": context.BUDGET_CHARS, "context_top": CONTEXT_TOP, "depth": DEPTH,
              "configs": configs, "summaries": summaries}
    (out / "summary.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                                      newline="\n")
    (out / "summary.md").write_text(markdown(args.split, summaries, configs), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
