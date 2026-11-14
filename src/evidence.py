"""The hit rule shared by every retrieval and context metric in this lab.

Taken from the Day 6 lab (starter/src/chunking.py `evidence_hit`, starter/src/benchmark.py
`squash`): a chunk holds a gold evidence when it comes from the gold source, its page range
covers the gold page, and it contains the whole evidence quote, whitespace-insensitively.

The starter's `baseline.hit` instead requires chunk["page"] == gold page, which misses the
237 Day 6 B chunks that start on the page before their evidence.
"""
import re
from typing import Any


def squash(text: str) -> str:
    """Whitespace-insensitive form used for every evidence comparison (as Day 6)."""
    return re.sub(r"\s+", " ", text).strip()


def evidence_hit(chunk: dict[str, Any], gold: dict[str, Any]) -> bool:
    return (chunk["source_id"] == gold["source_id"]
            and chunk["page"] <= gold["page"] <= chunk["metadata"]["page_end"]
            and squash(gold["evidence"]) in squash(chunk["text"]))


def any_hit(chunk: dict[str, Any], golds: list[dict[str, Any]]) -> bool:
    """`gold` entries are alternatives: any one of them is enough."""
    return any(evidence_hit(chunk, g) for g in golds)
