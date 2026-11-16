"""Check that no figure or table crop cuts a line of text at its edges.

For every region crop, any text line of the page that overlaps the region vertically and
crosses its left or right edge, or crosses its bottom edge inside its width, is reported
(body-size paragraphs are ignored: they belong to the page, not the figure). The crop
boxes come from data/advanced/chunks.json, the lines from the PDF.

Run from the repo root:  python -m src.advanced.check_crops   (exit 1 if any line is cut)
"""
import json
import sys

from .extract import BODY_SIZE, page_lines
from .source import DATA_DIR, open_pdf


def clipped(doc, chunks: list[dict]) -> list[tuple[str, str]]:
    found, seen = [], set()
    for c in chunks:
        if not c["crop"] or c["crop"] in seen:
            continue
        seen.add(c["crop"])
        x0, y0, x1, y1 = c["bbox"]
        for line in page_lines(doc[c["page"] - 1]):
            r = line["rect"]
            if line["size"] >= BODY_SIZE:
                continue
            vertical = r[1] < y1 and r[3] > y0
            side = vertical and (r[0] < x0 - 1 < r[2] or r[0] < x1 + 1 < r[2])
            bottom = r[0] >= x0 - 1 and r[2] <= x1 + 1 and r[1] < y1 - 1 < r[3]
            if side or bottom:
                found.append((c["id"], line["text"][:60]))
    return found


def main() -> int:
    chunks = json.loads((DATA_DIR / "chunks.json").read_text(encoding="utf-8"))
    problems = clipped(open_pdf(), chunks)
    for cid, text in problems:
        print(f"{cid}: cut line {text!r}")
    print(f"{len({c['crop'] for c in chunks if c['crop']})} crops checked, {len(problems)} cut lines")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
