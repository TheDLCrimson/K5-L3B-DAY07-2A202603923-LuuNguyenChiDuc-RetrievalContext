"""Export the Day 6 strategy B chunks from pgvector to data/day6/chunks.json.

The export is read from the database, so it is exactly what dense search ranks; lexical
methods read this file, so every method searches the same 1,264 chunks. With --day6-repo
it is also compared, chunk by chunk, against the Day 6 lab's own results/chunks/B.jsonl,
and one stored vector is re-embedded here to prove the query side uses the same model.

Run from the repo root:  python -m src.export_day6 --day6-repo ../K5-L3B-DAY06-2A202603923-DataIngestion
"""
import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from . import day6

OUT_DIR = day6.REPO_ROOT / "data" / "day6"
CHUNKS_PATH = OUT_DIR / "chunks.json"
INFO_PATH = OUT_DIR / "export_info.json"


def load_chunks(path: Path = CHUNKS_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def cross_check(chunks: list[dict], day6_repo: Path) -> int:
    """Same IDs, text, pages and content hashes as the Day 6 chunk file."""
    path = day6_repo / "results" / "chunks" / "B.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    theirs = {r["chunk_id"]: r for r in rows}
    ours = {c["id"]: c for c in chunks}
    if set(theirs) != set(ours):
        raise RuntimeError(f"chunk IDs differ: {len(set(theirs) ^ set(ours))} not in both")
    for cid, c in ours.items():
        r = theirs[cid]
        same = (r["text"] == c["text"] and r["document_id"] == c["source_id"] and r["page"] == c["page"]
                and r["metadata"]["page_end"] == c["metadata"]["page_end"]
                and r["metadata"]["content_hash"] == c["metadata"]["content_hash"])
        if not same:
            raise RuntimeError(f"{cid} differs between pgvector and {path}")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--day6-repo", type=Path, help="local clone of the Day 6 lab, for the cross-check")
    args = parser.parse_args()

    index = day6.Day6Index()
    info = index.check()
    chunks = index.all_chunks()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(chunks, ensure_ascii=False, indent=1) + "\n"
    CHUNKS_PATH.write_text(payload, encoding="utf-8", newline="\n")

    embedder = day6.QueryEmbedder()
    probe = chunks[len(chunks) // 2]
    cosine = day6.compatibility_check(index, embedder, probe)
    if cosine < 0.999:
        raise RuntimeError(f"re-embedded {probe['id']} has cosine {cosine:.5f} to its stored vector")

    info.update(
        day6_repo=day6.DAY6_REPO, day6_commit=day6.DAY6_COMMIT,
        query_prefix=day6.QUERY_PREFIX, passage_prefix=day6.PASSAGE_PREFIX,
        chunks=len(chunks),
        sources=sorted({c["source_id"] for c in chunks}),
        spanning_a_page_break=sum(c["page"] != c["metadata"]["page_end"] for c in chunks),
        reembed_check={"chunk_id": probe["id"], "cosine_to_stored": round(cosine, 6)},
        cross_checked_against_day6_B_jsonl=cross_check(chunks, args.day6_repo) if args.day6_repo else None,
        sha256=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        exported_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    INFO_PATH.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
