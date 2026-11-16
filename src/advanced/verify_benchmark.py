"""Checks of the advanced-challenge benchmark against the committed extraction.

Run from the repo root:  python -m src.advanced.verify_benchmark   (exit 1 on any failure)

Checks (ADVANCED.md section 2):
- sizes: test has at least 30 questions, 24 with an answer and 6 without; the answerable test
  questions cover table 6, image or diagram 5, chart 5, multi-hop 4, text 4, one main group each;
  dev has at least 15 answerable and 3 without, and covers every group;
- every evidence item names chunks that exist, on the page it says, and every `check_text`
  string occurs in at least one of those chunks (visual-only items are checked by eye);
- every calculation in an expected answer is recomputed here from the printed values;
- every question without evidence lists terms, and none occurs in any chunk (text, tables or
  the text inside figures); descriptions written by the model are not searched, since they
  are not the document;
- no question text repeats between dev and test, and a multi-hop question has evidence on at
  least two different pages or items.
Writes data/advanced/benchmark/verification.csv.
"""
import csv
import json
import sys
import unicodedata
from collections import Counter

from .source import DATA_DIR

BENCH = DATA_DIR / "benchmark"
TEST_MINIMUM = {"bang": 6, "anh_so_do": 5, "bieu_do": 5, "multi_hop": 4, "text": 4}
DEV_GROUPS = set(TEST_MINIMUM)

# Each calculation in an expected answer: (question id, description, value computed here, expected value, tolerance)
ARITHMETIC = [
    ("ad-d03", "104,5 - 61", 104.5 - 61, 43.5, 0.001),
    ("ad-d07", "sum of the nine cells of Hình 3",
     4219 + 2807 + 1474 + 837 + 518 + 447 + 235 + 218 + 148, 10903, 0),
    ("ad-d11", "184 / 14,5", 184 / 14.5, 12.7, 0.1),
    ("ad-d12", "550 / (59% x 200)", 550 / (0.59 * 200), 4.7, 0.1),
    ("ad-t01", "479,2 - 136,9", 479.2 - 136.9, 342.3, 0.001),
    ("ad-t01", "547,6 - 136,9", 547.6 - 136.9, 410.7, 0.001),
    ("ad-t03", "-1,3 - (-134,9)", -1.3 - -134.9, 133.6, 0.001),
    ("ad-t14", "13,9 - 3,7", 13.9 - 3.7, 10.2, 0.001),
    ("ad-t17", "-19 - 8 + 21 + 8 + 39 + 0 + 3", -19 - 8 + 21 + 8 + 39 + 0 + 3, 44, 0),
    ("ad-t18", "30% x 68", 0.30 * 68, 20.4, 0.001),
]


def norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


def main() -> int:
    questions = json.loads((BENCH / "questions.json").read_text(encoding="utf-8"))
    chunks = {c["id"]: c for c in json.loads((DATA_DIR / "chunks.json").read_text(encoding="utf-8"))}
    all_text = [norm(c["text"] + " " + (c["title"] or "")) for c in chunks.values()]
    problems: list[str] = []
    rows: list[dict] = []

    def fail(qid, msg):
        problems.append(f"{qid}: {msg}")

    ids = [q["id"] for q in questions]
    if len(ids) != len(set(ids)):
        fail("-", "duplicate question ids")
    by_split = {s: [q for q in questions if q["split"] == s] for s in ("dev", "test")}
    for s, minimum_answerable, minimum_absent in (("dev", 15, 3), ("test", 24, 6)):
        qs = by_split[s]
        answerable = [q for q in qs if q["answerable"]]
        if len(answerable) < minimum_answerable or len(qs) - len(answerable) < minimum_absent:
            fail(s, f"{len(answerable)} answerable and {len(qs) - len(answerable)} absent; need "
                    f"{minimum_answerable} and {minimum_absent}")
    counts = Counter(q["group"] for q in by_split["test"] if q["answerable"])
    for g, n in TEST_MINIMUM.items():
        if counts[g] < n:
            fail("test", f"group {g}: {counts[g]} questions, need {n}")
    unknown = set(counts) - set(TEST_MINIMUM)
    if unknown:
        fail("test", f"answerable questions in unknown groups {unknown}")
    dev_groups = {q["group"] for q in by_split["dev"] if q["answerable"]}
    if dev_groups != DEV_GROUPS:
        fail("dev", f"groups covered {sorted(dev_groups)}, want {sorted(DEV_GROUPS)}")
    texts = Counter(norm(q["question"]) for q in questions)
    for t, n in texts.items():
        if n > 1:
            fail("-", f"question text repeats: {t[:60]}")

    for q in questions:
        status = "ok"
        if q["answerable"]:
            if not q["evidence"]:
                fail(q["id"], "no evidence")
            for e in q["evidence"]:
                for cid in e["chunk_ids"]:
                    c = chunks.get(cid)
                    if c is None:
                        fail(q["id"], f"chunk {cid} does not exist")
                        continue
                    if c["page"] != e["page"]:
                        fail(q["id"], f"chunk {cid} is on page {c['page']}, evidence says {e['page']}")
                joined = norm(" ".join(chunks[c]["text"] for c in e["chunk_ids"] if c in chunks))
                for s in e["check_text"]:
                    if norm(s) not in joined:
                        fail(q["id"], f"{s!r} not found in {e['chunk_ids']}")
            if q["group"] == "multi_hop":
                pages = {e["page"] for e in q["evidence"]}
                if len(pages) < 2 and len(q["evidence"]) < 2:
                    fail(q["id"], "multi-hop evidence must come from two pages, tables or figures")
        else:
            terms = q["absence_check"]["terms"]
            if not terms:
                fail(q["id"], "no absence terms")
            for t in terms:
                hits = sum(norm(t) in x for x in all_text)
                if hits:
                    fail(q["id"], f"absence term {t!r} occurs in {hits} chunks")
        rows.append({"id": q["id"], "split": q["split"], "group": q["group"], "answerable": q["answerable"],
                     "evidence_items": len(q.get("evidence", [])), "status": status})
    for qid, what, got, want, tol in ARITHMETIC:
        if abs(got - want) > tol:
            fail(qid, f"{what} = {got}, expected answer says {want}")

    with (BENCH / "verification.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    visual = sum(e["visual_only"] for q in questions for e in q.get("evidence", []))
    print(f"dev {len(by_split['dev'])} (answerable {sum(q['answerable'] for q in by_split['dev'])}), "
          f"test {len(by_split['test'])} (answerable {sum(q['answerable'] for q in by_split['test'])}); "
          f"test groups {dict(counts)}; visual-only evidence items {visual}; calculations checked {len(ARITHMETIC)}")
    for p in problems:
        print("PROBLEM", p)
    print("OK" if not problems else f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
