"""Advanced agent loop checks with a scripted model, a scripted vision model and an in-memory retriever.

The scripted models only exercise the loop's code paths; they never produce reported results.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_agent import ScriptedModel

from src.advanced.agent import ABSTAIN_TEXT, AdvAgent, tool_schemas
from src.advanced.run_agent import covers, score, summarize
from src.retrieval import RetrievalError


def search(query="q"):
    return [("search_doc", {"query": query})]


def finish(status="answered", answer="Đáp án [CCDR-p018-t01]", citations=("CCDR-p018-t01",)):
    return [("finish", {"status": status, "answer": answer, "citations": list(citations)})]


def chunk(cid, kind="text", page=10, crop=None, text="nội dung"):
    return {"id": cid, "text": text, "source_id": "ccdr_vi", "source": "báo cáo", "page": page,
            "metadata": {"page_end": page, "page_label": str(page - 10), "kind": kind, "label": None,
                         "title": "Hình 1: tiêu đề" if kind == "figure" else None, "bbox": [60.0, 70.0, 550.0, 300.0],
                         "crop": crop, "part": None, "year": None}}


CHUNKS = [chunk("CCDR-p013-H1", "figure", 13, "crops/CCDR-p013-H1.png", "Hình 1\n368 tỷ USD"),
          chunk("CCDR-p018-t01", "text", 18, text="Năng lượng 65%"),
          chunk("CCDR-p019-t01", "text", 19), chunk("CCDR-p020-t01", "text", 20), chunk("CCDR-p021-t01", "text", 21)]


class FakeRetriever:
    name = "fake"

    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    def search(self, query, top_k, year=None):
        self.calls.append((query, top_k, year))
        if self.fail:
            raise RetrievalError("dense search failed: connection refused")
        return [{**c, "score": 1.0, "rank": i} for i, c in enumerate(CHUNKS[:top_k], 1)]


class VisionModel:
    def __init__(self):
        self.seen = []

    def describe(self):
        return {"provider": "scripted", "model": "vision"}

    def complete(self, messages, tools):
        self.seen.append(messages)
        return {"message": {"role": "assistant", "content": "Khối giữa ghi 368 tỷ USD."}, "calls": [], "finish": "stop",
                "usage": {"prompt_tokens": 100, "completion_tokens": 10, "cost": 0.001}, "ms": 5.0, "model": "vision"}


def look(chunk_id="CCDR-p013-H1", question="Giá trị trong ô giữa là bao nhiêu?"):
    return [("look", {"chunk_id": chunk_id, "question": question})]


def run(script, with_look=True, retriever=None, **kw):
    vision = VisionModel() if with_look else None
    agent = AdvAgent(ScriptedModel(script), retriever or FakeRetriever(), vision, **kw)
    return agent, vision, agent.run("Câu hỏi?")


class AdvAgentTest(unittest.TestCase):
    def test_search_then_answer_resolves_the_citation_to_page_and_region(self):
        _, _, out = run([search(), finish(answer="Có [CCDR-p018-t01]", citations=["CCDR-p018-t01"])])
        self.assertEqual((out["status"], out["citations"], out["searches"]), ("answered", ["CCDR-p018-t01"], 1))
        self.assertEqual(out["citations_at"][0]["page"], 18)
        self.assertEqual(out["citations_at"][0]["bbox"], [60.0, 70.0, 550.0, 300.0])
        self.assertEqual(out["context_ids"], ["CCDR-p013-H1", "CCDR-p018-t01", "CCDR-p019-t01"])
        event = out["events"][0]
        self.assertEqual([r["rank"] for r in event["results"]], [1, 2, 3, 4, 5])  # every fetched rank is logged

    def test_look_sends_the_crop_and_returns_what_the_vision_model_reads(self):
        agent, vision, out = run([search(), look(), finish(answer="368 [CCDR-p013-H1]", citations=["CCDR-p013-H1"])])
        self.assertEqual((out["look_calls"], out["looked_ids"]), (1, ["CCDR-p013-H1"]))
        content = vision.seen[0][1]["content"]
        self.assertEqual([p["type"] for p in content], ["text", "image_url"])
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))
        tool_reply = json.loads(agent.provider.seen[2][-1]["content"])
        self.assertIn("368", tool_reply["doc_duoc"])
        self.assertAlmostEqual(out["cost_usd"], 0.0003 + 0.001, places=4)  # looks are costed with the agent's turns

    def test_look_is_refused_for_unseen_text_and_beyond_the_limit(self):
        _, _, out = run([search(), look("CCDR-p099-t01"), look("CCDR-p018-t01"), look(), look(), finish()], max_looks=1)
        reasons = [e["reason"] for e in out["events"] if e["event"] == "look_refused"]
        self.assertEqual(reasons, ["chunk_not_shown", "no_crop", "look_limit"])
        self.assertEqual(out["look_calls"], 1)

    def test_without_a_vision_model_look_is_not_offered(self):
        self.assertEqual([t["function"]["name"] for t in tool_schemas(False)], ["search_doc", "finish"])
        agent, _, out = run([search(), look(), finish()], with_look=False)
        self.assertNotIn("look(", agent.system)
        self.assertEqual(out["look_calls"], 0)
        self.assertIn({"event": "unknown_tool", "tool": "look"}, out["events"])

    def test_citation_not_shown_is_dropped_and_the_answer_abstains(self):
        _, _, out = run([search(), finish(answer="x [CCDR-p099-t01]", citations=["CCDR-p099-t01"])])
        self.assertEqual((out["status"], out["reason"]), ("abstain", "no_valid_citation"))
        self.assertIn({"event": "invalid_citations", "ids": ["CCDR-p099-t01"]}, out["events"])

    def test_model_abstention_and_turn_limit(self):
        _, _, out = run([search(), finish(status="insufficient_evidence", answer="Không có.", citations=[])])
        self.assertEqual((out["status"], out["reason"]), ("abstain", "model_abstained"))
        _, _, out = run([search("a"), search("b")], max_turns=2)
        self.assertEqual((out["status"], out["reason"], out["answer"]), ("abstain", "turn_limit", ABSTAIN_TEXT))

    def test_calls_after_finish_are_not_run(self):
        retriever = FakeRetriever()
        _, _, out = run([search() + finish() + search("later")], retriever=retriever)
        self.assertEqual(([c[0] for c in retriever.calls], out["status"]), (["q"], "answered"))  # the first search ran
        self.assertIn({"event": "call_after_finish", "tool": "search_doc"}, out["events"])

    def test_errors_end_the_run_with_status_error(self):
        _, _, out = run([search(), finish()], retriever=FakeRetriever(fail=True))
        self.assertEqual((out["status"], out["answer"]), ("error", None))
        self.assertIn("connection refused", out["reason"])

    def test_leaked_tool_call_markup_is_stripped_from_the_answer(self):
        junk = 'Có [CCDR-p018-t01]</answer> <parameter name="citations">["CCDR-p018-t01"]'
        _, _, out = run([search(), finish(answer=junk)])
        self.assertEqual((out["status"], out["answer"]), ("answered", "Có [CCDR-p018-t01]"))
        self.assertEqual([e["event"] for e in out["events"]][:2], ["search", "answer_markup_stripped"])

    def test_prompt_and_tools_hold_no_benchmark_content(self):
        agent, _, _ = run([search(), finish()])
        bench = json.loads((ROOT / "data" / "advanced" / "benchmark" / "questions.json").read_text(encoding="utf-8"))
        text = agent.system + json.dumps(agent.tools, ensure_ascii=False)
        self.assertEqual(re.findall(r"CCDR-p\d{3}", text), [])
        for q in bench:
            self.assertNotIn(q["question"], text)
            for e in q.get("evidence", []):
                self.assertNotIn(e["value"], text)

    def test_no_benchmark_field_reaches_the_model(self):
        agent, _, _ = run([search(), finish()])

        def keys(x):
            if isinstance(x, dict):
                return set(x) | {k for v in x.values() for k in keys(v)}
            return {k for v in x for k in keys(v)} if isinstance(x, list) else set()

        sent = agent.provider.seen[-1]
        found = keys(sent) | {k for m in sent if m["role"] == "tool" for k in keys(json.loads(m["content"]))}
        self.assertEqual(found & {"gold", "expected_answer", "evidence", "answerable", "absence_check", "grading"}, set())


class ScoreTest(unittest.TestCase):
    ITEMS = ({"chunk_ids": ["a", "a2"]}, {"chunk_ids": ["b"]})

    def test_every_evidence_item_must_be_covered(self):
        self.assertTrue(covers(list(self.ITEMS), ["a2", "b", "z"]))
        self.assertFalse(covers(list(self.ITEMS), ["a", "z"]))

    def test_score_and_summary(self):
        q = {"answerable": True, "evidence": list(self.ITEMS)}
        base = {"status": "answered", "answerable": True, "group": "multi_hop", "searches": 2, "look_calls": 1,
                "model_calls": 3, "prompt_tokens": 1, "completion_tokens": 1, "cost_usd": 0.01, "ms": 100.0,
                "events": [{"event": "search", "shown": ["a"]}, {"event": "search", "shown": ["b"]}]}
        hit = score({**base, "query_id": "x", "context_ids": ["a", "b"], "citations": ["a", "b"]}, q)
        miss = score({**base, "query_id": "y", "context_ids": ["a"], "citations": ["a"]}, q)
        self.assertEqual((hit["context_hit"], hit["first_search_hit"], hit["cited_gold"]), (True, False, True))
        self.assertEqual((miss["context_hit"], miss["evidence_items_in_context"]), (False, 1))
        s = summarize([hit, miss])
        self.assertEqual((s["context_evidence_rate"]["n"], s["context_evidence_rate"]["N"]), (1, 2))
        self.assertEqual(s["context_missed"], ["y"])


if __name__ == "__main__":
    unittest.main()
