"""Replay of logged agent searches (src/replay_searches.py) with the scripted model of test_agent."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_agent import FakeRetriever, finish, run, search

from src.replay_searches import replay_run


class ReplayTest(unittest.TestCase):
    def test_replay_of_the_same_retriever_matches_and_ranks_every_shown_chunk(self):
        _, out = run([search(), search(), finish()])
        out["events"] = [{**e, "results": e["results"][:3]} if e["event"] == "search" else e for e in out["events"]]
        replayed = replay_run(out, FakeRetriever())
        self.assertTrue(all(s["top3_matches_trace"] and s["shown_matches_trace"] for s in replayed))
        shown = [(f["rank"], f["id"]) for f in replayed[1]["fetched"] if f["shown"]]
        self.assertEqual(shown, [(4, "B-ldd2024_cb363-0001")])

    def test_a_different_ranking_is_flagged(self):
        _, out = run([search(), finish()])

        class Reversed(FakeRetriever):
            def search(self, query, top_k, year=None):
                rows = list(reversed(super().search(query, top_k, year)))
                return [{**r, "rank": i} for i, r in enumerate(rows, 1)]

        replayed = replay_run(out, Reversed())
        self.assertEqual((replayed[0]["top3_matches_trace"], replayed[0]["shown_matches_trace"]), (False, False))


if __name__ == "__main__":
    unittest.main()
