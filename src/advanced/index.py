"""The advanced-challenge index: every chunk of the report in pgvector, embedded like Day 6.

Same container, same model and prefixes as the Day 6 index (multilingual-e5-base at the pinned
revision, "passage: " / "query: ", exact cosine), in its own table `adv_chunks`, so the Day 6
`chunks` table is never touched.

What is embedded and searched per chunk (`text` below; BM25 and the reranker read the same):
- text chunks: the page text;
- tables: the title, then the rows (markdown, or rebuilt rows for borderless tables), then the
  region description, marked as model-generated;
- figures: the caption, the text inside the figure (labels, values, legends), then the region
  description, marked as model-generated.
The agent sees the same text, so it knows which part was extracted from the PDF and which was
written by a model; values are read from the crop with the `look` tool before they are used.

Run from the repo root:
  python -m src.advanced.index build   (create the table and embed every chunk)
  python -m src.advanced.index check   (row count, model and size against chunks.json)
"""
import json
import sys
from functools import cached_property
from typing import Any

from psycopg.types.json import Jsonb

from ..day6 import DIMENSIONS, EMBEDDING_MODEL, Day6Index, QueryEmbedder, _vector_literal
from ..retrieval import RetrievalError, as_result, check_input
from .source import DATA_DIR, TITLE

TABLE = "adv_chunks"
SOURCE_ID = "ccdr_vi"
GENERATED = "Mô tả do model tạo (đối chiếu với hình trước khi dùng số liệu)"


def load_chunks() -> list[dict[str, Any]]:
    """Chunks in the lab's chunk format, figures and tables joined with their region description."""
    chunks = json.loads((DATA_DIR / "chunks.json").read_text(encoding="utf-8"))
    described = json.loads((DATA_DIR / "descriptions.json").read_text(encoding="utf-8"))["regions"]
    out = []
    for c in chunks:
        desc = described.get(c["crop"], {}).get("description") if c["crop"] else None
        if c["crop"] and not desc:
            raise SystemExit(f"{c['id']}: no description for {c['crop']}; run python -m src.advanced.describe")
        part = f" (phần {c['part']})" if c.get("part") else ""
        if c["kind"] == "text":
            text = c["text"]
        else:
            text = f"{c['title']}{part}\n{c['text']}\n[{GENERATED}]\n{desc}"
        out.append({"id": c["id"], "text": text, "source_id": SOURCE_ID, "source": TITLE, "page": c["page"],
                    "metadata": {"page_end": c["page"], "page_label": c["page_label"], "kind": c["kind"],
                                 "label": c["label"], "title": c["title"], "bbox": c["bbox"], "crop": c["crop"],
                                 "part": c.get("part"), "year": None}})
    return out


class AdvIndex(Day6Index):
    """The `adv_chunks` table; reuses the Day 6 connection settings."""

    def build(self, embedder: QueryEmbedder) -> int:
        chunks = load_chunks()
        vectors = embedder._encode([f"passage: {c['text']}" for c in chunks])
        with self.connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"DROP TABLE IF EXISTS {TABLE}")
            conn.execute(f"""CREATE TABLE {TABLE} (
                chunk_id text PRIMARY KEY, page int NOT NULL, kind text NOT NULL, text text NOT NULL,
                metadata jsonb NOT NULL, embedding_model text NOT NULL, embedding vector({DIMENSIONS}) NOT NULL)""")
            with conn.cursor() as cur:
                cur.executemany(
                    f"INSERT INTO {TABLE} VALUES (%s, %s, %s, %s, %s, %s, %s::vector)",
                    [(c["id"], c["page"], c["metadata"]["kind"], c["text"], Jsonb(c["metadata"]), EMBEDDING_MODEL,
                      _vector_literal(v)) for c, v in zip(chunks, vectors)])
        return len(chunks)

    def check(self) -> dict[str, Any]:
        expected = len(load_chunks())
        with self.connect() as conn:
            rows, models = conn.execute(f"SELECT count(*), array_agg(DISTINCT embedding_model) FROM {TABLE}").fetchone()
            dims = conn.execute(f"SELECT atttypmod FROM pg_attribute WHERE attrelid = '{TABLE}'::regclass "
                                "AND attname = 'embedding'").fetchone()[0]
        if rows != expected or models != [EMBEDDING_MODEL] or dims != DIMENSIONS:
            raise RuntimeError(f"{TABLE}: {rows} rows (expected {expected}), models {models}, {dims}-d")
        return {"table": TABLE, "rows": rows, "embedding_model": EMBEDDING_MODEL, "dimensions": dims}

    def search(self, query_vector: list[float], top_k: int, year: int | None = None) -> list[dict[str, Any]]:
        vector = _vector_literal(query_vector)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT chunk_id, page, text, metadata, 1 - (embedding <=> %s::vector) FROM {TABLE} "
                "ORDER BY embedding <=> %s::vector, chunk_id LIMIT %s", [vector, vector, top_k]).fetchall()
        return [{"id": r[0], "text": r[2], "source_id": SOURCE_ID, "source": TITLE, "page": r[1], "metadata": r[3],
                 "score": float(r[4]), "rank": i} for i, r in enumerate(rows, 1)]


class AdvDenseRetriever:
    """Dense retrieval on `adv_chunks` with the Day 6 embedding model; same interface as src/retrieval.py."""

    name = "dense"

    def __init__(self, index: AdvIndex | None = None, embedder: QueryEmbedder | None = None) -> None:
        self.index = index or AdvIndex()
        self._embedder = embedder

    @cached_property
    def embedder(self) -> QueryEmbedder:
        return self._embedder or QueryEmbedder()

    def config(self) -> dict[str, Any]:
        return {"method": self.name, "index": f"pgvector table {TABLE}, exact cosine", "embedding": EMBEDDING_MODEL,
                "query_prefix": "query: "}

    def search(self, query: str, top_k: int, year: int | None = None) -> list[dict[str, Any]]:
        check_input(query, top_k, None)
        if year is not None:
            raise RetrievalError("this document has no year filter")
        try:
            hits = self.index.search(self.embedder.embed_query(query), top_k)
        except Exception as exc:
            raise RetrievalError(f"dense search failed: {type(exc).__name__}: {exc}") from exc
        return [as_result({k: v for k, v in h.items() if k not in ("score", "rank")}, h["score"], h["rank"], self.name)
                for h in hits]


def main() -> None:
    index = AdvIndex()
    if sys.argv[1:] == ["build"]:
        print(f"embedded {index.build(QueryEmbedder())} chunks into {TABLE}")
    for key, value in index.check().items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
