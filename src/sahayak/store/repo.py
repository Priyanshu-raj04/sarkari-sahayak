"""Postgres repository + pgvector / ParadeDB retrievers."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from sahayak.retrieve.types import Passage


class QueryEmbedder(Protocol):
    def __call__(self, query: str, /) -> np.ndarray: ...


@dataclass(frozen=True, slots=True)
class DocumentRow:
    doc_id: str
    title: str
    lang: str
    doc_type: str
    source_url: str
    sha256: str
    issued_on: date | None = None
    pair_doc_id: str | None = None


@dataclass(frozen=True, slots=True)
class ChunkRow:
    chunk_id: str
    doc_id: str
    page: int
    ordinal: int
    lang: str
    text: str
    embedding: np.ndarray | None = None


def connect(url: str) -> psycopg.Connection:
    conn = psycopg.connect(url)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    register_vector(conn)
    return conn


class PgRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def upsert_document(self, d: DocumentRow) -> None:
        self.conn.execute(
            """INSERT INTO documents (doc_id, title, lang, doc_type, source_url, issued_on,
                                      pair_doc_id, sha256)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (doc_id) DO UPDATE SET title = EXCLUDED.title,
                 source_url = EXCLUDED.source_url, issued_on = EXCLUDED.issued_on,
                 pair_doc_id = EXCLUDED.pair_doc_id, sha256 = EXCLUDED.sha256,
                 ingested_at = now()""",
            (
                d.doc_id,
                d.title,
                d.lang,
                d.doc_type,
                d.source_url,
                d.issued_on,
                d.pair_doc_id,
                d.sha256,
            ),
        )

    def replace_chunks(self, doc_id: str, chunks: Sequence[ChunkRow]) -> None:
        """Re-ingesting a document replaces all of its chunks atomically."""
        with self.conn.transaction():
            self.conn.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
            with self.conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO chunks (chunk_id, doc_id, page, ordinal, lang, text, embedding) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    [
                        (c.chunk_id, c.doc_id, c.page, c.ordinal, c.lang, c.text, c.embedding)
                        for c in chunks
                    ],
                )

    def get_many(self, chunk_ids: list[str]) -> dict[str, Passage]:
        if not chunk_ids:
            return {}
        with self.conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(
                """SELECT c.chunk_id, c.doc_id, c.lang, c.page, c.text, d.title, d.source_url
                   FROM chunks c JOIN documents d USING (doc_id)
                   WHERE c.chunk_id = ANY(%s)""",
                (chunk_ids,),
            ).fetchall()
        return {r["chunk_id"]: Passage(**r) for r in rows}

    def iter_chunks(self, batch: int = 1000) -> Iterator[tuple[str, str]]:
        """(chunk_id, text) for building the in-memory BM25 index (hosted profile)."""
        with self.conn.cursor(name="all_chunks") as cur:
            cur.itersize = batch
            cur.execute("SELECT chunk_id, text FROM chunks ORDER BY chunk_id")
            yield from cur

    def commit(self) -> None:
        self.conn.commit()


class PgDenseRetriever:
    name = "dense"

    def __init__(
        self, conn: psycopg.Connection, embed_query: QueryEmbedder, *, exact: bool = False
    ) -> None:
        self.conn, self.embed_query, self.exact = conn, embed_query, exact

    def search(self, query: str, k: int) -> list[str]:
        vec = self.embed_query(query)
        with self.conn.transaction():
            if self.exact:  # benchmarks: brute-force scan, no ANN approximation
                self.conn.execute("SET LOCAL enable_indexscan = off")
            rows = self.conn.execute(
                "SELECT chunk_id FROM chunks WHERE embedding IS NOT NULL "
                "ORDER BY embedding <=> %s LIMIT %s",
                (vec, k),
            ).fetchall()
        return [r[0] for r in rows]


class ParadeBM25Retriever:
    name = "bm25"

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def search(self, query: str, k: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT chunk_id FROM chunks WHERE text ||| %s "
            "ORDER BY pdb.score(chunk_id) DESC, chunk_id LIMIT %s",
            (query, k),
        ).fetchall()
        return [r[0] for r in rows]
