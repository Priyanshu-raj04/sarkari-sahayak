import numpy as np
import pytest

from sahayak.store.migrate import has_extension, migrate
from sahayak.store.repo import (
    ChunkRow,
    DocumentRow,
    ParadeBM25Retriever,
    PgDenseRetriever,
    PgRepository,
)

pytestmark = pytest.mark.integration

DOC = DocumentRow(
    doc_id="MD-TEST-HI",
    title="परीक्षण निर्देश",
    lang="hi",
    doc_type="master_direction",
    source_url="https://example.test/md",
    sha256="0" * 64,
)


def unit(*xs: float) -> np.ndarray:
    v = np.zeros(384, dtype=np.float32)
    v[: len(xs)] = xs
    return v / np.linalg.norm(v)


def seed(repo: PgRepository) -> None:
    repo.upsert_document(DOC)
    repo.replace_chunks(
        DOC.doc_id,
        [
            ChunkRow(
                "MD-TEST-HI#p1c0", DOC.doc_id, 1, 0, "hi", "केवाईसी नियम हर दस साल में", unit(1, 0)
            ),
            ChunkRow("MD-TEST-HI#p1c1", DOC.doc_id, 1, 1, "hi", "ब्याज दर निर्देश", unit(0, 1)),
        ],
    )
    repo.commit()


def test_migrate_is_idempotent(conn) -> None:  # type: ignore[no-untyped-def]
    assert migrate(conn) == []


def test_get_many_joins_document_metadata(conn) -> None:  # type: ignore[no-untyped-def]
    repo = PgRepository(conn)
    seed(repo)
    got = repo.get_many(["MD-TEST-HI#p1c0", "missing"])
    assert list(got) == ["MD-TEST-HI#p1c0"]
    assert got["MD-TEST-HI#p1c0"].title == "परीक्षण निर्देश"
    assert repo.get_many([]) == {}


def test_replace_chunks_is_atomic_replacement(conn) -> None:  # type: ignore[no-untyped-def]
    repo = PgRepository(conn)
    seed(repo)
    repo.replace_chunks(DOC.doc_id, [ChunkRow("MD-TEST-HI#p2c0", DOC.doc_id, 2, 0, "hi", "नया")])
    repo.commit()
    assert [cid for cid, _ in repo.iter_chunks()] == ["MD-TEST-HI#p2c0"]


@pytest.mark.parametrize("exact", [True, False])
def test_dense_retriever_orders_by_cosine(conn, exact: bool) -> None:  # type: ignore[no-untyped-def]
    repo = PgRepository(conn)
    seed(repo)
    dense = PgDenseRetriever(conn, lambda q: unit(0.9, 0.1), exact=exact)
    assert dense.search("q", 2) == ["MD-TEST-HI#p1c0", "MD-TEST-HI#p1c1"]


def test_paradedb_bm25_with_icu_tokenizer(conn) -> None:  # type: ignore[no-untyped-def]
    if not has_extension(conn, "pg_search"):
        pytest.skip("pg_search not installed (plain Postgres)")
    repo = PgRepository(conn)
    seed(repo)
    assert ParadeBM25Retriever(conn).search("केवाईसी", 5) == ["MD-TEST-HI#p1c0"]
