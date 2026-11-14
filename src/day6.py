"""Connection to the Day 6 index: strategy B chunks in pgvector, embedded with multilingual-e5-base.

Day 6 repo: TheDLCrimson/K5-L3B-DAY06-2A202603923-DataIngestion (commit DAY6_COMMIT).
Its configuration C (strategy B chunks, exact cosine search, `year` filter in SQL) is what
this lab reuses. Nothing is re-indexed here: queries are embedded with the same model and
revision, with the "query: " prefix that matches the "passage: " prefix used at index time.

`Day6Index.check()` refuses a database whose rows, model or vector size differ from the
Day 6 run, so a wrong or half-loaded index fails loudly instead of scoring badly.

Run from the repo root:  python -m src.day6   (prints the index check)
"""
import os
from functools import cached_property
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]

DAY6_REPO = "https://github.com/TheDLCrimson/K5-L3B-DAY06-2A202603923-DataIngestion"
DAY6_COMMIT = "5b5acdc5af86fcd65eac08f3d677eefbeac30c13"
STRATEGY = "B"
EXPECTED_ROWS = 1264
EMBEDDING_MODEL = "intfloat/multilingual-e5-base"
EMBEDDING_REVISION = "d128750597153bb5987e10b1c3493a34e5a4502a"  # Hugging Face commit, as Day 6
DIMENSIONS = 768
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "
YEARS = (2013, 2024)

_COLUMNS = ["chunk_id", "document_id", "source", "page", "page_end", "year", "law_number",
            "article", "chapter", "text", "metadata"]


def database_url() -> str:
    load_dotenv(REPO_ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set; copy .env.example to .env")
    return url


def to_chunk(row: dict[str, Any]) -> dict[str, Any]:
    """A Day 6 row in the Lab 7 chunk format (data/README.md), Day 6 metadata kept."""
    meta = dict(row["metadata"])
    meta.update(page_end=row["page_end"], year=row["year"], law_number=row["law_number"],
                article=row["article"], chapter=row["chapter"])
    return {"id": row["chunk_id"], "text": row["text"], "source_id": row["document_id"],
            "source": row["source"], "page": row["page"], "metadata": meta}


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in vector) + "]"


class QueryEmbedder:
    """e5 query vectors, L2-normalised like the stored passage vectors (cosine = dot)."""

    def __init__(self, device: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(EMBEDDING_MODEL, revision=EMBEDDING_REVISION, device=device)
        if self.model.get_embedding_dimension() != DIMENSIONS:
            raise ValueError(f"{EMBEDDING_MODEL} gives {self.model.get_embedding_dimension()}-d "
                             f"vectors, the index stores {DIMENSIONS}-d")

    def _encode(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True,
                                 show_progress_bar=False).tolist()

    def embed_query(self, query: str) -> list[float]:
        return self._encode([QUERY_PREFIX + query])[0]

    def embed_passage(self, text: str) -> list[float]:
        """Only for the compatibility check: re-embed a stored chunk the way Day 6 did."""
        return self._encode([PASSAGE_PREFIX + text])[0]


class Day6Index:
    def __init__(self, url: str | None = None) -> None:
        self.url = url or database_url()

    def connect(self) -> psycopg.Connection:
        return psycopg.connect(self.url, connect_timeout=5)

    def check(self) -> dict[str, Any]:
        """Rows, model and vector size of strategy B must match the Day 6 run."""
        with self.connect() as conn:
            rows, models = conn.execute(
                "SELECT count(*), array_agg(DISTINCT embedding_model) FROM chunks WHERE strategy = %s",
                (STRATEGY,)).fetchone()
            dims = conn.execute("SELECT atttypmod FROM pg_attribute WHERE attrelid = 'chunks'::regclass "
                                "AND attname = 'embedding'").fetchone()[0]
            versions = conn.execute("SELECT version(), extversion FROM pg_extension "
                                    "WHERE extname = 'vector'").fetchone()
        problems = []
        if rows != EXPECTED_ROWS:
            problems.append(f"{rows} strategy {STRATEGY} rows, expected {EXPECTED_ROWS}")
        if models != [EMBEDDING_MODEL]:
            problems.append(f"embedding models {models}, expected [{EMBEDDING_MODEL}]")
        if dims != DIMENSIONS:
            problems.append(f"{dims}-d vectors, expected {DIMENSIONS}")
        if problems:
            raise RuntimeError("Day 6 index does not match: " + "; ".join(problems))
        return {"strategy": STRATEGY, "rows": rows, "embedding_model": EMBEDDING_MODEL,
                "embedding_revision": EMBEDDING_REVISION, "dimensions": dims,
                "postgres": versions[0].split(",")[0], "pgvector": versions[1]}

    def all_chunks(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(f"SELECT {', '.join(_COLUMNS)} FROM chunks WHERE strategy = %s "
                                "ORDER BY chunk_id", (STRATEGY,)).fetchall()
        return [to_chunk(dict(zip(_COLUMNS, r))) for r in rows]

    def stored_vector(self, chunk_id: str) -> list[float]:
        with self.connect() as conn:
            text = conn.execute("SELECT embedding::text FROM chunks WHERE strategy = %s AND chunk_id = %s",
                                (STRATEGY, chunk_id)).fetchone()[0]
        return [float(x) for x in text.strip("[]").split(",")]

    def search(self, query_vector: list[float], top_k: int, year: int | None = None) -> list[dict[str, Any]]:
        """Exact cosine search over strategy B (no ANN index, as Day 6); score = cosine similarity."""
        if year is not None and year not in YEARS:
            raise ValueError(f"year filter must be one of {YEARS}, got {year!r}")
        where, params = "strategy = %s", [STRATEGY]
        if year is not None:
            where += " AND year = %s"
            params.append(year)
        vector = _vector_literal(query_vector)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT {', '.join(_COLUMNS)}, 1 - (embedding <=> %s::vector) AS score FROM chunks "
                f"WHERE {where} ORDER BY embedding <=> %s::vector, chunk_id LIMIT %s",
                [vector, *params, vector, top_k]).fetchall()
        hits = []
        for rank, r in enumerate(rows, 1):
            chunk = to_chunk(dict(zip(_COLUMNS, r[:-1])))
            hits.append({**chunk, "score": float(r[-1]), "rank": rank})
        return hits


class DenseSearch:
    """Dense retrieval on the Day 6 vector store, the lab's required method."""

    def __init__(self, index: Day6Index | None = None, embedder: QueryEmbedder | None = None) -> None:
        self.index = index or Day6Index()
        self._embedder = embedder

    @cached_property
    def embedder(self) -> QueryEmbedder:
        return self._embedder or QueryEmbedder()

    def search(self, query: str, top_k: int, year: int | None = None) -> list[dict[str, Any]]:
        return self.index.search(self.embedder.embed_query(query), top_k, year)


def compatibility_check(index: Day6Index, embedder: QueryEmbedder, chunk: dict[str, Any]) -> float:
    """Cosine between a stored vector and the same chunk re-embedded here; ~1.0 means same model."""
    stored = index.stored_vector(chunk["id"])
    fresh = embedder.embed_passage(chunk["text"])
    return sum(a * b for a, b in zip(stored, fresh))


def main() -> None:
    index = Day6Index()
    for key, value in index.check().items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
