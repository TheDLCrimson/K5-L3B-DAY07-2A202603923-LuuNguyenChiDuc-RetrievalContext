"""Recover score and rank for every chunk each logged agent search fetched.

The agent fetches FETCH_PER_SEARCH (8) chunks per search and shows the first 3 it has not
shown before, so a shown chunk can come from rank 4-8. Runs recorded before full logging
keep score and rank for the top 3 only. This replays every logged search (its query and
filter, exactly as logged) through the configuration's retriever, without calling the
model, and checks the replay against the trace:
- the replayed top 3 IDs equal the logged top 3, with scores within SCORE_TOLERANCE;
- the chunks shown, recomputed from the replay and the chunks shown earlier in the same
  run, equal the logged `shown` and `already_shown`.

Writes results/agent/<split>/<config>/search_ranks.json; traces.json is never edited.
A replay that fails a check is kept in the file with the failure, not dropped.

Run from the repo root (needs the Day 6 database; rerank configurations need the reranker):
  python -m src.replay_searches --split test --configs A0_dense,A4_rerank_pool10
  python -m src.replay_searches --all
"""
import argparse
import json
from datetime import UTC, datetime
from typing import Any

from . import context
from .agent import FETCH_PER_SEARCH, RESULTS_PER_SEARCH
from .retrieval import Bm25Retriever, CrossEncoderScorer, DenseRetriever, HybridRetriever, RerankRetriever
from .run_agent import CONFIGS, OUT_DIR

SCORE_TOLERANCE = 1e-3


class Retrievers:
    """Builds each retriever once; the reranker (2.3 GB) is shared by every rerank configuration."""

    def __init__(self) -> None:
        self.built: dict[str, Any] = {}
        self.parts: dict[str, Any] = {}

    def part(self, name: str):
        if name not in self.parts:
            self.parts[name] = {"dense": DenseRetriever, "bm25": Bm25Retriever, "scorer": CrossEncoderScorer}[name]()
        return self.parts[name]

    def get(self, name: str):
        if name not in self.built:
            if name == "dense":
                self.built[name] = self.part("dense")
            elif name in ("hybrid_rerank", "hybrid_rerank_pool10"):
                pool = 20 if name == "hybrid_rerank" else 10
                hybrid = HybridRetriever(self.part("dense"), self.part("bm25"), candidates=pool)
                self.built[name] = RerankRetriever(hybrid, self.part("scorer"))
            else:
                raise ValueError(f"unknown retriever {name!r}")
        return self.built[name]


def replay_run(trace: dict[str, Any], retriever) -> list[dict[str, Any]]:
    shown: set[str] = set()
    out = []
    for event in (e for e in trace["events"] if e["event"] == "search"):
        results = retriever.search(event["query"], FETCH_PER_SEARCH, event["filter"])
        repeated = [r["id"] for r in results if r["id"] in shown]
        packed, _ = context.pack([r for r in results if r["id"] not in shown][:RESULTS_PER_SEARCH])
        now_shown = [c["id"] for c in packed]
        shown.update(now_shown)
        logged = event["results"][:RESULTS_PER_SEARCH]
        top3_ok = ([r["id"] for r in results[:RESULTS_PER_SEARCH]] == [r["id"] for r in logged]
                   and all(abs(a["score"] - b["score"]) <= SCORE_TOLERANCE for a, b in zip(results, logged)))
        shown_ok = now_shown == event["shown"] and repeated == event["already_shown"]
        out.append({"query": event["query"], "filter": event["filter"], "top3_matches_trace": top3_ok,
                    "shown_matches_trace": shown_ok,
                    "fetched": [{"rank": r["rank"], "id": r["id"], "score": round(r["score"], 6),
                                 "shown": r["id"] in now_shown, "already_shown": r["id"] in repeated}
                                for r in results]})
    return out


def replay(split: str, config: str, retrievers: Retrievers) -> dict[str, Any]:
    traces = json.loads((OUT_DIR / split / config / "traces.json").read_text(encoding="utf-8"))
    retriever = retrievers.get(CONFIGS[config]["retriever"])
    questions = {t["query_id"]: replay_run(t, retriever) for t in traces}
    searches = [s for runs in questions.values() for s in runs]
    shown = [f for s in searches for f in s["fetched"] if f["shown"]]
    report = {"split": split, "config": config, "retriever": retriever.name,
              "replayed_at": datetime.now(UTC).isoformat(timespec="seconds"),
              "searches": len(searches),
              "top3_matches_trace": sum(s["top3_matches_trace"] for s in searches),
              "shown_matches_trace": sum(s["shown_matches_trace"] for s in searches),
              "shown_chunks": len(shown), "shown_below_rank_3": sum(f["rank"] > RESULTS_PER_SEARCH for f in shown),
              "mismatches": [{"query_id": q, "search": i + 1} for q, runs in questions.items()
                             for i, s in enumerate(runs) if not (s["top3_matches_trace"] and s["shown_matches_trace"])],
              "questions": questions}
    path = OUT_DIR / split / config / "search_ranks.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{split}/{config}: {report['searches']} searches, top 3 match {report['top3_matches_trace']}, "
          f"shown match {report['shown_matches_trace']}, shown below rank 3: {report['shown_below_rank_3']}"
          f"/{report['shown_chunks']}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", choices=["dev", "test"])
    parser.add_argument("--configs")
    parser.add_argument("--all", action="store_true", help="every split and configuration with traces")
    args = parser.parse_args()
    if args.all:
        jobs = [(s, c) for s in ("dev", "test") for c in CONFIGS if (OUT_DIR / s / c / "traces.json").exists()]
    elif args.split and args.configs:
        jobs = [(args.split, c) for c in args.configs.split(",")]
    else:
        parser.error("give --all, or --split and --configs")
    retrievers = Retrievers()
    reports = [replay(s, c, retrievers) for s, c in jobs]
    bad = [(r["split"], r["config"], m) for r in reports for m in r["mismatches"]]
    print(f"mismatches: {len(bad)}" + "".join(f"\n  {s}/{c} {m}" for s, c, m in bad))


if __name__ == "__main__":
    main()
