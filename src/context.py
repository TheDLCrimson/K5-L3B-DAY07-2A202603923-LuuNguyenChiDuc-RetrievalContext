"""Turn ranked chunks into the context block sent to the model, within a character budget.

Each chunk is labelled with its ID (the citation key), law, source file, page range and
articles, so the model and a reader can check every citation against the original page.
Chunks are taken in rank order; a chunk that does not fit is skipped, never cut, and a
chunk already in the context is not added twice.
"""
from typing import Any

BUDGET_CHARS = 3300  # three Day 6 B chunks (<= 1,000 characters each) always fit with labels
SEPARATOR = "\n\n"


def label(chunk: dict[str, Any]) -> str:
    m = chunk["metadata"]
    pages = f"{chunk['page']}" if chunk["page"] == m["page_end"] else f"{chunk['page']}-{m['page_end']}"
    articles = ", ".join(f"Điều {a}" for a in m.get("articles") or []) or "không rõ điều"
    return f"[{chunk['id']}] Luật Đất đai {m['year']} ({m['law_number']}), {chunk['source_id']} trang {pages}, {articles}"


def block(chunk: dict[str, Any]) -> str:
    return f"{label(chunk)}\n{chunk['text']}"


def pack(chunks: list[dict[str, Any]], budget: int = BUDGET_CHARS,
         already: list[dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (packed chunks, skipped IDs). `already` chunks stay first and count toward the budget."""
    packed = list(already or [])
    seen = {c["id"] for c in packed}
    used = len(render(packed))
    skipped = []
    for c in chunks:
        if c["id"] in seen:
            continue
        extra = len(block(c)) + (len(SEPARATOR) if packed else 0)
        if used + extra <= budget:
            packed.append(c)
            seen.add(c["id"])
            used += extra
        else:
            skipped.append(c["id"])
    return packed, skipped


def render(chunks: list[dict[str, Any]]) -> str:
    return SEPARATOR.join(block(c) for c in chunks)
