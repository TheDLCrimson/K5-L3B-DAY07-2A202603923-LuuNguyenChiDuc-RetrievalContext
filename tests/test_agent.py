"""Agent loop checks with a scripted model and an in-memory retriever.

The scripted model only exercises the loop's code paths; it never produces reported results.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.agent import ABSTAIN_TEXT, Agent, named_years
from src.providers import ProviderError
from src.retrieval import RetrievalError


def chunk(cid, text, year=2013, articles=(1,), source="ldd2013"):
    return {"id": cid, "text": text, "source_id": source, "source": "f.pdf", "page": 1,
            "metadata": {"page_end": 1, "year": year, "law_number": "45/2013/QH13", "articles": list(articles)}}


CHUNKS = [chunk("B-ldd2013-0001", "Điều 1 khoản 1", articles=(1,)),
          chunk("B-ldd2013-0002", "Điều 1 khoản 2", articles=(1,)),
          chunk("B-ldd2013-0003", "Điều 2", articles=(2,)),
          chunk("B-ldd2024_cb363-0001", "Điều 1 luật 2024", year=2024, articles=(1,), source="ldd2024_cb363")]


class FakeRetriever:
    name = "fake"

    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    def search(self, query, top_k, year=None):
        self.calls.append((query, top_k, year))
        if self.fail:
            raise RetrievalError("dense search failed: connection refused")
        rows = [c for c in CHUNKS if year is None or c["metadata"]["year"] == year]
        return [{**c, "score": 1.0, "rank": i} for i, c in enumerate(rows[:top_k], 1)]


class ScriptedModel:
    """Returns one scripted reply per call: a list of (tool name, arguments) or plain text."""

    def __init__(self, script, fail_at=None):
        self.script, self.fail_at, self.seen = list(script), fail_at, []

    def describe(self):
        return {"provider": "scripted", "model": "none"}

    def complete(self, messages, tools):
        self.seen.append([dict(m) for m in messages])  # snapshot: the loop keeps appending
        if self.fail_at is not None and len(self.seen) - 1 == self.fail_at:
            raise ProviderError("provider returned HTTP 429")
        step = self.script.pop(0)
        if isinstance(step, str):
            return {"message": {"role": "assistant", "content": step}, "calls": [], "finish": "stop",
                    "usage": {}, "ms": 1.0}
        calls = [{"id": f"c{i}", "name": n, "arguments": json.dumps(a, ensure_ascii=False)} for i, (n, a) in enumerate(step)]
        message = {"role": "assistant", "content": None, "tool_calls": [
            {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}}
            for c in calls]}
        return {"message": message, "calls": calls, "finish": "tool_calls",
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.0001}, "ms": 1.0}


def search(query="q", **kw):
    return [("search_law", {"query": query, **kw})]


def finish(status="answered", answer="Đáp án [B-ldd2013-0001]", citations=("B-ldd2013-0001",)):
    return [("finish", {"status": status, "answer": answer, "citations": list(citations)})]


def run(script, question="Câu hỏi?", retriever=None, per_version=False, **kw):
    agent = Agent(ScriptedModel(script, **{k: v for k, v in kw.items() if k == "fail_at"}),
                  retriever or FakeRetriever(), per_version,
                  **{k: v for k, v in kw.items() if k in ("max_turns", "max_searches")})
    return agent, agent.run(question)


class AgentTest(unittest.TestCase):
    def test_search_then_answer_with_a_shown_citation(self):
        _, out = run([search(), finish()])
        self.assertEqual((out["status"], out["citations"], out["searches"]), ("answered", ["B-ldd2013-0001"], 1))
        self.assertEqual([e["event"] for e in out["events"]], ["search", "finish"])
        self.assertEqual(out["context_ids"], ["B-ldd2013-0001", "B-ldd2013-0002", "B-ldd2013-0003"])

    def test_citation_not_shown_is_dropped_and_answer_abstains(self):
        _, out = run([search(), finish(answer="Đáp án [B-ldd2013-0099]", citations=["B-ldd2013-0099"])])
        self.assertEqual((out["status"], out["reason"]), ("abstain", "no_valid_citation"))
        self.assertIn({"event": "invalid_citations", "ids": ["B-ldd2013-0099"]}, out["events"])

    def test_citations_in_the_text_count_too(self):
        _, out = run([search(), finish(answer="A [B-ldd2013-0001], B [B-ldd2013-0002]", citations=[])])
        self.assertEqual(out["citations"], ["B-ldd2013-0001", "B-ldd2013-0002"])

    def test_model_abstention(self):
        _, out = run([search(), finish(status="insufficient_evidence", answer="Không có.", citations=[])])
        self.assertEqual((out["status"], out["reason"]), ("abstain", "model_abstained"))

    def test_year_only_when_the_question_names_it(self):
        retriever = FakeRetriever()
        _, out = run([search(year=2024), search(), finish()], question="Đất ở có thời hạn không?", retriever=retriever)
        self.assertEqual(out["events"][0]["reason"], "year_not_in_question")
        self.assertEqual(retriever.calls[0][2], None)
        retriever = FakeRetriever()
        run([search(year=2024), finish(citations=["B-ldd2024_cb363-0001"],
                                       answer="x [B-ldd2024_cb363-0001]")],
            question="Theo Luật Đất đai 2024, ...?", retriever=retriever)
        self.assertEqual(retriever.calls[0][2], 2024)
        self.assertEqual(named_years("Luật Đất đai năm 2013 và Luật Đất đai 2024"), {2013, 2024})

    def test_search_limit_and_turn_limit(self):
        _, out = run([search("a"), search("b"), finish()], max_searches=1)
        self.assertEqual(out["searches"], 1)
        self.assertEqual(out["events"][1]["reason"], "search_limit")
        _, out = run([search("a"), search("b")], max_turns=2)
        self.assertEqual((out["status"], out["reason"], out["answer"]), ("abstain", "turn_limit", ABSTAIN_TEXT))

    def test_already_shown_chunks_are_not_resent(self):
        agent, _ = run([search(), search(), finish()])
        second = json.loads(agent.provider.seen[2][-1]["content"])
        self.assertEqual((second["results"], len(second["already_shown"])), ([{"id": "B-ldd2024_cb363-0001",
                         "source": second["results"][0]["source"], "text": "Điều 1 luật 2024"}], 3))

    def test_plain_text_reply_is_nudged(self):
        _, out = run(["Tôi nghĩ là...", search(), finish()])
        self.assertEqual((out["status"], out["events"][0]["event"]), ("answered", "no_tool_call"))

    def test_provider_and_retriever_errors_end_with_error_status(self):
        _, out = run([search(), finish()], fail_at=1)
        self.assertEqual((out["status"], out["answer"]), ("error", None))
        self.assertIn("HTTP 429", out["reason"])
        _, out = run([search(), finish()], retriever=FakeRetriever(fail=True))
        self.assertEqual(out["status"], "error")

    def test_per_version_allows_each_version_only_when_the_question_names_none(self):
        retriever = FakeRetriever()
        _, out = run([search(year=2013), search(year=2024), finish()], question="Đất ở có thời hạn không?",
                     retriever=retriever, per_version=True)
        self.assertEqual([c[2] for c in retriever.calls], [2013, 2024])
        self.assertEqual(out["searches"], 2)
        retriever = FakeRetriever()
        _, out = run([search(year=2024), finish()], question="Theo Luật Đất đai 2013, ...?",
                     retriever=retriever, per_version=True)
        self.assertEqual((retriever.calls, out["events"][0]["reason"]), ([], "year_contradicts_question"))

    def test_baseline_prompt_and_tools_are_the_ones_recorded_for_a0_and_a1(self):
        class Describe:
            def describe(self):
                return {}

        for name in ("A0_dense", "A1_rerank"):
            path = ROOT / "results" / "agent" / "dev" / name / "summary.json"
            if not path.exists():
                self.skipTest("dev runs not present")
            recorded = json.loads(path.read_text(encoding="utf-8"))
            agent = Agent(Describe(), FakeRetriever())
            self.assertEqual((agent.system, agent.tools), (recorded["system_prompt"], recorded["tools"]))
        self.assertNotEqual(Agent(Describe(), FakeRetriever(), per_version=True).system, agent.system)

    def test_no_benchmark_field_reaches_the_model(self):
        agent, _ = run([search(), finish()], question="Câu hỏi thật?")

        def keys(x):
            if isinstance(x, dict):
                return set(x) | {k for v in x.values() for k in keys(v)}
            return {k for v in x for k in keys(v)} if isinstance(x, list) else set()

        sent = agent.provider.seen[-1]
        found = keys(sent) | {k for m in sent if m["role"] == "tool" for k in keys(json.loads(m["content"]))}
        self.assertEqual(found & {"gold", "expected_answer", "evidence", "answerable", "absence_reason", "filter"}, set())
        self.assertEqual([m["content"] for m in sent if m["role"] == "user"], ["Câu hỏi thật?"])

if __name__ == "__main__":
    unittest.main()


class ScoreTest(unittest.TestCase):
    """Gold-based checks added to traces after a run (src/run_agent.py score)."""

    def test_both_laws_and_wrong_version_citations(self):
        from src.run_agent import score, summarize

        chunks = {c["id"]: c for c in CHUNKS}
        gold = [{"source_id": "ldd2013", "page": 1, "evidence": "Điều 1 khoản 1"},
                {"source_id": "ldd2024_cb363", "page": 1, "evidence": "Điều 1 luật 2024"}]
        base = {"status": "answered", "events": [{"event": "search", "shown": ["B-ldd2013-0001"]}],
                "context_ids": ["B-ldd2013-0001", "B-ldd2024_cb363-0001"], "model_calls": 2,
                "prompt_tokens": 1, "completion_tokens": 1, "cost_usd": 0.0, "ms": 1.0}
        unfiltered = {"answerable": True, "gold": gold, "filter": None}
        one_law = score({**base, "query_id": "a", "answerable": True, "citations": ["B-ldd2013-0001"]},
                        unfiltered, chunks)
        both = score({**base, "query_id": "b", "answerable": True,
                      "citations": ["B-ldd2013-0001", "B-ldd2024_cb363-0001"]}, unfiltered, chunks)
        filtered = score({**base, "query_id": "c", "answerable": True,
                          "citations": ["B-ldd2013-0001", "B-ldd2024_cb363-0001"]},
                         {"answerable": True, "gold": gold[:1], "filter": {"year": 2013}}, chunks)
        self.assertEqual((one_law["cited_gold_years"], both["cited_gold_years"]), ([2013], [2013, 2024]))
        self.assertEqual(filtered["wrong_version_citations"], ["B-ldd2024_cb363-0001"])
        s = summarize([one_law, both, filtered])
        self.assertEqual((s["both_laws_cited"]["n"], s["both_laws_cited"]["N"], s["both_laws_missed"]), (1, 2, ["a"]))
        self.assertEqual((s["wrong_version_citations"]["n"], s["wrong_version_citations"]["N"]), (1, 2))
