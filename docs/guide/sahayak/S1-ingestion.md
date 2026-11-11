# S1 — Ingestion: from RBI PDFs to chunks in Postgres

**Goal:** a reproducible pipeline that turns a committed manifest of RBI documents into normalised, chunked, embedded rows in ParadeDB, with Hindi text handled correctly (including legacy-font PDFs).
**Time:** ~10–12 h. **Branches:** `feat/s1-corpus-spike`, `feat/s1-text`, `feat/s1-store`, `feat/s1-ingest`.

## Issue text (paste into GitHub)

> **S1: Ingestion pipeline**
> Acceptance criteria
> - [ ] `docs/data-sources.md` records how RBI publishes Master Directions in EN/HI, the robots.txt rules, and the 20–40 document pairs chosen
> - [ ] `data_manifest/rbi_manifest.csv` committed (no PDFs in git)
> - [ ] `sahayak db migrate` creates `documents`, `chunks` (+ BM25 index on ParadeDB)
> - [ ] `sahayak ingest` is idempotent (re-running replaces chunks, no duplicates)
> - [ ] Hindi tokenisation keeps matras; legacy-font pages are OCR'd; script mismatches are reported
> - [ ] Unit + integration tests green; coverage gates pass

## Concept primers

> 📘 **Unicode normalisation (NFC).** The same Hindi letter can be stored as one code point or as a base letter + a combining mark. PDFs, keyboards and OCR disagree. NFC picks one canonical form so `==`, BM25 and embeddings see the same text. Surprise found while verifying: Devanagari nukta letters such as क़ (U+0958) are *composition exclusions*, so NFC turns the precomposed form into क + ़. Our test pins that down.

> 📘 **Why not `re` `\w`?** Python's `re` treats Devanagari vowel signs (matras, category `Mn`/`Mc`) as non-word characters, so `re.findall(r"\w+", "किताबें")` returns fragments. The third-party `regex` module supports Unicode properties: `[\p{L}\p{M}\p{N}]+` keeps letters + marks + digits together.

> 📘 **Legacy fonts (Kruti Dev etc.).** Many Indian government PDFs were typed in fonts that draw Devanagari glyphs on *Latin* code points. The page looks Hindi, but the text layer is gibberish like `dsokbZlh`. You can detect it (font names; or a Hindi document whose text has almost no Devanagari) and fall back to OCR (Tesseract `hin+eng`). Converter libraries (e.g. `krutiextract`) exist, but OCR is more general.

> 📘 **Chunking.** Retrieval works on passages, not whole PDFs. We pack whole sentences (split on `.?!` **and the Devanagari danda `।` / double danda `॥`**) up to ~900 characters, with a one-sentence overlap so a fact split across a boundary is still findable. Chunk ids `<doc_id>#p<page>c<n>` are stable, which makes citations meaningful and tests exact.

> 📘 **Migrations.** Schema changes are numbered SQL files applied once each and recorded in `schema_migrations`. The BM25 migration is skipped automatically when the `pg_search` extension isn't available (Neon), so the same code runs in both places.

## Step 1 — Corpus discovery spike (no code) ⚠️

Time-box: 2 h. Output: `docs/data-sources.md` + a first `data_manifest/rbi_manifest.csv`.

1. On **rbi.org.in**, find the Master Directions listing (Notifications → Master Directions) ⚠️ the exact URL/page structure must be checked by you; RBI's site layout changes.
2. Check the **Hindi** site (rbi.org.in has a हिंदी version). For 20–40 Master Directions relevant to fintech/NBFC/banking (KYC, Digital Lending, Fraud Risk Management, Outsourcing of IT Services, Interest Rate on Deposits, Prepaid Payment Instruments, …) record the EN and HI document URLs. Prefer documents that exist in **both** languages: the pair gives you free cross-lingual eval data.
3. Open `https://www.rbi.org.in/robots.txt` and the site's terms/disclaimer. Write down what they say about automated access ⚠️. If anything forbids scripted downloading, download the 40–80 files **manually** and keep the downloader for cache/hash only.
4. For 3 Hindi PDFs, check the text layer: open in Preview, select text, paste into a text editor. Devanagari → Unicode ✅; Latin gibberish → legacy font → OCR path. Record which.
5. Write the manifest (columns below). Use doc ids like `MD-KYC-2016-EN` / `MD-KYC-2016-HI` and fill `pair_doc_id` both ways.

```csv
doc_id,title,lang,doc_type,url,issued_on,pair_doc_id,sha256
MD-KYC-2016-EN,Master Direction - Know Your Customer (KYC) Direction 2016,en,master_direction,https://…,2016-02-25,MD-KYC-2016-HI,
MD-KYC-2016-HI,मास्टर निदेश - अपने ग्राहक को जानिए (केवाईसी) निदेश 2016,hi,master_direction,https://…,2016-02-25,MD-KYC-2016-EN,
```

Copyright note: RBI documents are public regulatory text, but their reuse terms are **not verified** here ⚠️. We never commit or re-host the PDFs; the repo contains only URLs + hashes, and the demo shows short cited excerpts with a link back to rbi.org.in.

## Step 2 — Text utilities (TDD)

Write the tests first, watch them fail, then implement.

`tests/unit/text/test_normalize.py` ✅

```python
import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sahayak.text.normalize import detect_script, normalize_text, tokenize


def test_stdlib_re_breaks_devanagari_which_is_why_we_use_regex() -> None:
    assert re.findall(r"\w+", "किताबें") != ["किताबें"]  # documents the pitfall


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("किताबें पढ़ो", ["किताबें", "पढ़ो"]),
        ("KYC-नियम 2016", ["kyc", "नियम", "2016"]),
        ("  Re-KYC   norms  ", ["re", "kyc", "norms"]),
    ],
)
def test_tokenize_keeps_matras_and_lowercases_latin(text: str, expected: list[str]) -> None:
    assert tokenize(text) == expected


def test_normalize_removes_zero_width_and_collapses_space() -> None:
    assert normalize_text("के\N{ZERO WIDTH JOINER}वाईसी \n\n नियम") == "केवाईसी नियम"


def test_nfc_decomposes_nukta_letters_so_both_pdf_forms_match() -> None:
    # QA is a Unicode *composition exclusion*: NFC turns it into KA + NUKTA.
    precomposed = "\N{DEVANAGARI LETTER QA}"
    decomposed = "\N{DEVANAGARI LETTER KA}\N{DEVANAGARI SIGN NUKTA}"
    assert normalize_text(precomposed) == normalize_text(decomposed) == decomposed


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("केवाईसी नियम क्या हैं?", "hi"),
        ("What are the KYC norms?", "en"),
        ("KYC ke liye documents kaunse", "en"),  # romanised Hinglish looks Latin
        ("KYC norms और नियम", "mixed"),
        ("12345 ???", "unknown"),
    ],
)
def test_detect_script(text: str, lang: str) -> None:
    assert detect_script(text) == lang


@given(st.text())
def test_normalize_is_idempotent(text: str) -> None:
    once = normalize_text(text)
    assert normalize_text(once) == once
```

`src/sahayak/text/normalize.py` ✅

```python
"""Unicode normalisation, script detection and tokenisation for Hindi/Marathi/English."""

import unicodedata
from typing import Literal

import regex

Lang = Literal["hi", "en", "mixed", "unknown"]

# Letters + combining marks (matras, virama, nukta) + digits.
# NOTE: stdlib `re`'s \w would split Devanagari words.
_TOKEN_RE = regex.compile(r"[\p{L}\p{M}\p{N}]+")
_DEVANAGARI_RE = regex.compile(r"\p{Script=Devanagari}")
_LATIN_RE = regex.compile(r"\p{Script=Latin}")
_ZERO_WIDTH_RE = regex.compile(
    "[\N{ZERO WIDTH SPACE}\N{ZERO WIDTH NON-JOINER}\N{ZERO WIDTH JOINER}"
    "\N{WORD JOINER}\N{ZERO WIDTH NO-BREAK SPACE}]"
)
_SPACE_RE = regex.compile(r"\s+")


def normalize_text(text: str) -> str:
    """NFC-normalise, drop zero-width characters, collapse whitespace."""
    text = unicodedata.normalize("NFC", text)
    text = _ZERO_WIDTH_RE.sub("", text)
    return _SPACE_RE.sub(" ", text).strip()


def tokenize(text: str) -> list[str]:
    """Lower-cased word tokens that keep Devanagari matras attached."""
    return [t.lower() for t in _TOKEN_RE.findall(normalize_text(text))]


def detect_script(text: str, threshold: float = 0.8) -> Lang:
    """Classify by the share of Devanagari vs Latin letters."""
    deva = len(_DEVANAGARI_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    total = deva + latin
    if total == 0:
        return "unknown"
    if deva / total >= threshold:
        return "hi"
    if latin / total >= threshold:
        return "en"
    return "mixed"
```

Note the `\N{...}` escapes: named characters are safer than raw invisible characters in source code (an editor or tool can silently drop a zero-width joiner; it can't drop a name).

`tests/unit/text/test_chunking.py` ✅

```python
import pytest
from hypothesis import given
from hypothesis import strategies as st

from sahayak.text.chunking import chunk_page, split_sentences


def test_split_sentences_handles_danda_and_latin_punctuation() -> None:
    text = "यह पहला वाक्य है। यह दूसरा है॥ Third one. Fourth?"
    assert split_sentences(text) == ["यह पहला वाक्य है।", "यह दूसरा है॥", "Third one.", "Fourth?"]


def test_chunk_ids_are_stable_and_ordered() -> None:
    text = "वाक्य एक। वाक्य दो। वाक्य तीन।"
    chunks = chunk_page("MD-KYC-2016", 3, text, max_chars=20, overlap_sentences=0)
    assert [c.chunk_id for c in chunks] == [f"MD-KYC-2016#p3c{i}" for i in range(len(chunks))]
    assert chunk_page("MD-KYC-2016", 3, text, max_chars=20, overlap_sentences=0) == chunks


def test_overlap_carries_last_sentence_forward() -> None:
    chunks = chunk_page("D", 1, "Aaaa. Bbbb. Cccc.", max_chars=11, overlap_sentences=1)
    assert [c.text for c in chunks] == ["Aaaa. Bbbb.", "Bbbb. Cccc."]


def test_oversized_sentence_becomes_its_own_chunk() -> None:
    long = "क" * 50 + "।"
    chunks = chunk_page("D", 1, f"छोटा। {long} छोटा।", max_chars=20, overlap_sentences=0)
    assert any(c.text == long for c in chunks)


def test_rejects_non_positive_max_chars() -> None:
    with pytest.raises(ValueError, match="max_chars"):
        chunk_page("D", 1, "x.", max_chars=0)


@given(st.lists(st.text(alphabet="कखगabc ", min_size=1, max_size=30), min_size=1, max_size=20))
def test_chunking_never_loses_words(parts: list[str]) -> None:
    text = "। ".join(parts) + "।"
    words_in = set(text.replace("।", " ").split())
    chunks = chunk_page("D", 1, text, max_chars=60, overlap_sentences=0)
    words_out = set(" ".join(c.text for c in chunks).replace("।", " ").split())
    assert words_in == words_out
```

> ✋ **Try it yourself first.** You have the failing tests above. Spend 30–45 minutes making them pass on your own before reading the reference implementation below. Then compare: what did you do differently, and why?

`src/sahayak/text/chunking.py` ✅

```python
"""Split documents into overlapping, paragraph-aware chunks with stable ids."""

from dataclasses import dataclass

import regex

from sahayak.text.normalize import normalize_text

# Sentence ends: Latin . ? ! and the Devanagari danda (।) / double danda (॥).
_SENTENCE_END_RE = regex.compile(r"(?<=[.?!\N{DEVANAGARI DANDA}\N{DEVANAGARI DOUBLE DANDA}])\s+")


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str  # "<doc_id>#p<page>c<ordinal>" — stable across re-ingestion
    doc_id: str
    page: int
    ordinal: int
    text: str


def split_sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_END_RE.split(normalize_text(text)) if s]


def chunk_page(
    doc_id: str, page: int, text: str, *, max_chars: int = 900, overlap_sentences: int = 1
) -> list[Chunk]:
    """Greedy sentence packing up to `max_chars`, carrying `overlap_sentences` forward."""
    if max_chars <= 0:
        msg = "max_chars must be positive"
        raise ValueError(msg)
    sentences = split_sentences(text)
    chunks: list[Chunk] = []
    current: list[str] = []
    for sentence in sentences:
        candidate = " ".join([*current, sentence])
        if current and len(candidate) > max_chars:
            chunks.append(_make(doc_id, page, len(chunks), current))
            current = current[-overlap_sentences:] if overlap_sentences else []
        current.append(sentence)
    if current:
        chunks.append(_make(doc_id, page, len(chunks), current))
    return chunks


def _make(doc_id: str, page: int, ordinal: int, sentences: list[str]) -> Chunk:
    return Chunk(
        chunk_id=f"{doc_id}#p{page}c{ordinal}",
        doc_id=doc_id,
        page=page,
        ordinal=ordinal,
        text=" ".join(sentences),
    )
```

> 🧪 The last test is a **property test** (Hypothesis): for random Hindi/Latin text, chunking never loses a word. Property tests find edge cases you wouldn't think to write.

Commit: `feat(ingest): add Unicode normalisation, tokenizer and sentence-aware chunker`.

## Step 3 — Schema, migrations and repository

`src/sahayak/store/migrations/0001_core.sql` ✅

```sql
-- Core schema. Embedding dimension 384 = intfloat/multilingual-e5-small.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    doc_id        text PRIMARY KEY,                -- e.g. 'MD-KYC-2016-EN'
    title         text NOT NULL,
    lang          text NOT NULL CHECK (lang IN ('hi', 'en', 'mr')),
    doc_type      text NOT NULL,                   -- 'master_direction' | 'circular' | 'gr'
    source_url    text NOT NULL,
    issued_on     date,
    pair_doc_id   text,                            -- the same document in the other language
    sha256        text NOT NULL,                   -- of the downloaded file
    ingested_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id   text PRIMARY KEY,                   -- '<doc_id>#p<page>c<ordinal>'
    doc_id     text NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    page       int  NOT NULL,
    ordinal    int  NOT NULL,
    lang       text NOT NULL,
    text       text NOT NULL,
    embedding  vector(384)
);

CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks (doc_id);
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks
    USING hnsw (embedding vector_cosine_ops);
```

`src/sahayak/store/migrations/0002_bm25_paradedb.sql` ✅

```sql
-- ParadeDB only (local + benchmarks). Skipped automatically where pg_search is unavailable (Neon).
CREATE EXTENSION IF NOT EXISTS pg_search;
CREATE INDEX IF NOT EXISTS chunks_bm25 ON chunks
    USING paradedb (chunk_id, (text::pdb.icu), doc_id, lang);
```

ParadeDB syntax was checked against its current docs 📚: the access method is `paradedb` (`USING bm25` remains as an alias), the `key_field` option is deprecated and ignored, a column is tokenised with ICU via `(text::pdb.icu)`, queries use `|||` and `pdb.score(id)`.

`src/sahayak/store/migrate.py` ✅

```python
"""Tiny forward-only migration runner (ordered *.sql files, tracked in schema_migrations)."""

from importlib.resources import files

import psycopg
import structlog

log = structlog.get_logger()
OPTIONAL_PREFIX = "bm25"  # migrations whose name contains this need the pg_search extension


def has_extension(conn: psycopg.Connection, name: str) -> bool:
    row = conn.execute("SELECT 1 FROM pg_available_extensions WHERE name = %s", (name,)).fetchone()
    return row is not None


def migrate(conn: psycopg.Connection) -> list[str]:
    """Apply pending migrations in one transaction each. Returns the names applied."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    conn.commit()
    done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations").fetchall()}
    scripts = sorted(
        (p for p in files("sahayak.store.migrations").iterdir() if p.name.endswith(".sql")),
        key=lambda p: p.name,
    )
    applied: list[str] = []
    for script in scripts:
        if script.name in done:
            continue
        if OPTIONAL_PREFIX in script.name and not has_extension(conn, "pg_search"):
            log.info("migration_skipped_no_pg_search", name=script.name)
            continue
        with conn.transaction():
            conn.execute(script.read_text(encoding="utf-8"))  # type: ignore[arg-type]
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (script.name,))
        applied.append(script.name)
    return applied
```

`src/sahayak/store/repo.py` ✅

```python
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
```

> 📘 **HNSW vs exact search.** `hnsw` is an *approximate* nearest-neighbour index: fast, but it can miss a few true neighbours. For benchmark numbers we want the truth, so `PgDenseRetriever(exact=True)` disables index scans inside the transaction (`SET LOCAL enable_indexscan = off`) and Postgres does a full scan. In S2 you'll report both and their difference ("ANN recall").

Integration tests (need `make up`):

`tests/integration/conftest.py` ✅

```python
import os
from collections.abc import Iterator

import psycopg
import pytest

from sahayak.store.migrate import migrate
from sahayak.store.repo import connect


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    """A migrated database with empty tables. Needs `make up` (or the CI service container)."""
    url = os.environ.get("TEST_DATABASE_URL", "postgresql://sahayak:sahayak@localhost:5432/sahayak")
    try:
        c = connect(url)
    except psycopg.OperationalError:
        if os.environ.get("CI"):  # never silently skip in CI
            raise
        pytest.skip("Postgres not reachable — run `make up`")
    migrate(c)
    c.execute("TRUNCATE documents CASCADE")
    c.commit()
    yield c
    c.close()
```

`tests/integration/test_repo.py` ✅

```python
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
```

Verified on 2026-11-09 against real PostgreSQL + pgvector (embedded server): 5 passed, the ParadeDB BM25 test correctly **skipped** on plain Postgres ✅. On your Mac (ParadeDB) all six must pass — the BM25 test is the first proof that the ICU tokenizer handles Hindi ⚠️.

Add the `db` command group to the CLI (see the final `cli.py` in Step 5), then:

```bash
make up
uv run sahayak db migrate        # applied: 0001_core.sql, 0002_bm25_paradedb.sql
uv run sahayak db migrate        # applied: nothing (up to date)
make test-int
```

## Step 4 — Download, extract, manifest

`tests/unit/ingest/test_download_manifest.py` ✅

```python
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from pydantic import HttpUrl

from sahayak.ingest.download import DisallowedError, PoliteDownloader
from sahayak.ingest.manifest import ManifestRow, read_manifest, sha256_file, write_manifest


class Clock:
    def __init__(self) -> None:
        self.t = 0.0
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.t += s


@respx.mock
def test_downloads_respecting_robots_rate_limit_and_cache(tmp_path: Path) -> None:
    respx.get("https://rbi.test/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /private/\n")
    )
    pdf = respx.get("https://rbi.test/docs/md.pdf").mock(
        return_value=httpx.Response(200, content=b"%PDF-1.7")
    )
    clock = Clock()
    dl = PoliteDownloader(tmp_path, client=httpx.Client(), sleep=clock.sleep, clock=clock.now)
    path = dl.fetch("https://rbi.test/docs/md.pdf")
    assert path.read_bytes() == b"%PDF-1.7"
    assert path.suffix == ".pdf"
    assert clock.slept == [3.0]  # robots.txt request, then waited before the PDF
    assert dl.fetch("https://rbi.test/docs/md.pdf") == path  # cached: no new request
    assert pdf.call_count == 1
    with pytest.raises(DisallowedError):
        dl.fetch("https://rbi.test/private/x.pdf")


@respx.mock
def test_missing_robots_allows_and_http_errors_raise(tmp_path: Path) -> None:
    respx.get("https://x.test/robots.txt").mock(return_value=httpx.Response(404))
    respx.get("https://x.test/a").mock(return_value=httpx.Response(500))
    dl = PoliteDownloader(tmp_path, client=httpx.Client(), min_interval_s=0)
    with pytest.raises(httpx.HTTPStatusError):
        dl.fetch("https://x.test/a")


def test_manifest_roundtrip_and_hash(tmp_path: Path) -> None:
    rows = [
        ManifestRow(
            doc_id="MD-KYC-2016-EN",
            title="Master Direction - KYC",
            lang="en",
            doc_type="master_direction",
            url=HttpUrl("https://rbi.test/md.pdf"),
            issued_on=date(2016, 2, 25),
            pair_doc_id="MD-KYC-2016-HI",
        ),
    ]
    path = tmp_path / "m.csv"
    write_manifest(path, rows)
    assert read_manifest(path) == rows
    (tmp_path / "f").write_bytes(b"abc")
    assert sha256_file(tmp_path / "f").startswith("ba7816bf")
```

`src/sahayak/ingest/manifest.py` ✅

```python
"""The corpus manifest: one row per source document. Committed to git (the PDFs are not)."""

import csv
import hashlib
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, HttpUrl

FIELDS = ["doc_id", "title", "lang", "doc_type", "url", "issued_on", "pair_doc_id", "sha256"]


class ManifestRow(BaseModel):
    doc_id: str
    title: str
    lang: Literal["hi", "en", "mr"]
    doc_type: Literal["master_direction", "circular", "gr"]
    url: HttpUrl
    issued_on: date | None = None
    pair_doc_id: str | None = None
    sha256: str | None = None  # filled after download


def read_manifest(path: Path) -> list[ManifestRow]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [
            ManifestRow.model_validate({k: (v or None) for k, v in row.items()})
            for row in csv.DictReader(fh)
        ]


def write_manifest(path: Path, rows: list[ManifestRow]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: ("" if v is None else str(v)) for k, v in r.model_dump().items()})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()
```

`src/sahayak/ingest/download.py` ✅

```python
"""Polite downloader: honours robots.txt, identifies itself, rate-limits, caches by URL."""

import hashlib
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import structlog

log = structlog.get_logger()
USER_AGENT = "sarkari-sahayak-research/0.1 (+https://github.com/Priyanshu-raj04/sarkari-sahayak)"


class DisallowedError(RuntimeError):
    """robots.txt forbids this URL."""


class PoliteDownloader:
    def __init__(
        self,
        cache_dir: Path,
        client: httpx.Client | None = None,
        min_interval_s: float = 3.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cache_dir = cache_dir
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True
        )
        self.min_interval_s, self.sleep, self.clock = min_interval_s, sleep, clock
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request: float | None = None

    def fetch(self, url: str) -> Path:
        target = self.cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:24] + _suffix(url))
        if target.exists():
            return target
        if not self._allowed(url):
            raise DisallowedError(url)
        self._wait()
        resp = self.client.get(url)
        resp.raise_for_status()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        target.write_bytes(resp.content)
        log.info("downloaded", url=url, bytes=len(resp.content))
        return target

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self._robots:
            parser = RobotFileParser()
            self._wait()
            resp = self.client.get(f"{root}/robots.txt")
            parser.parse(resp.text.splitlines() if resp.status_code == 200 else [])
            self._robots[root] = parser
        return self._robots[root].can_fetch(USER_AGENT, url)

    def _wait(self) -> None:
        now = self.clock()
        if self._last_request is not None:
            remaining = self.min_interval_s - (now - self._last_request)
            if remaining > 0:
                self.sleep(remaining)
        self._last_request = self.clock()


def _suffix(url: str) -> str:
    path = urlsplit(url).path.lower()
    return ".pdf" if path.endswith(".pdf") else ".html"
```

> Why the `sleep`/`clock` parameters? So the test can prove the 3-second politeness delay without actually sleeping. Injecting time is the standard trick for testing anything time-based.

`tests/unit/ingest/test_pdf.py` ✅

```python
from pathlib import Path

import pymupdf

from sahayak.ingest.pdf import extract_pages

LONG_EN = "Regulated entities shall update KYC records periodically as per this Direction."


def make_pdf(tmp_path: Path, pages: list[str]) -> Path:
    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_text((72, 72), text)  # built-in Helvetica (Latin only)
    path = tmp_path / "t.pdf"
    doc.save(path)
    return path


def fake_ocr(page: pymupdf.Page) -> str:
    return f"OCR page {page.number + 1}"  # type: ignore[operator]


def test_text_layer_used_for_english_pages(tmp_path: Path) -> None:
    pages = extract_pages(make_pdf(tmp_path, [LONG_EN]), expect_hindi=False, ocr=fake_ocr)
    assert pages[0].method == "text"
    assert "KYC records" in pages[0].text


def test_empty_page_goes_to_ocr(tmp_path: Path) -> None:
    pages = extract_pages(make_pdf(tmp_path, [LONG_EN, ""]), expect_hindi=False, ocr=fake_ocr)
    assert [p.method for p in pages] == ["text", "ocr"]
    assert pages[1].text == "OCR page 2"


def test_hindi_doc_with_latin_only_text_layer_goes_to_ocr(tmp_path: Path) -> None:
    # Simulates a legacy-font PDF: Devanagari shown on screen, Latin gibberish in the text layer.
    gibberish = "dsokbZlh fu;eksa dk ikyu lHkh cSadksa ds fy, vfuok;Z gSA"
    pages = extract_pages(make_pdf(tmp_path, [gibberish]), expect_hindi=True, ocr=fake_ocr)
    assert pages[0].method == "ocr"
```

`src/sahayak/ingest/pdf.py` ✅

```python
"""PDF → page texts. Detects legacy (non-Unicode) Devanagari fonts and falls back to OCR."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import regex

# Kruti Dev / Chanakya etc. encode Devanagari glyphs on Latin code points, so the "text" looks like
# Latin gibberish ("dsokbZlh"). These fonts are recognisable by name.
LEGACY_FONT_RE = regex.compile(r"kruti|chanakya|devlys|walkman|agra|shusha", regex.IGNORECASE)
_DEVANAGARI = regex.compile(r"\p{Script=Devanagari}")
_LATIN = regex.compile(r"\p{Script=Latin}")

OcrFn = Callable[[pymupdf.Page], str]


@dataclass(frozen=True, slots=True)
class PageText:
    page: int  # 1-based
    text: str
    method: str  # "text" | "ocr"


def needs_ocr(page: pymupdf.Page, expect_hindi: bool) -> bool:
    text = str(page.get_text("text"))
    if len(text.strip()) < 30:  # scanned image page
        return True
    fonts = " ".join(f[3] for f in page.get_fonts())  # f[3] = base font name
    if LEGACY_FONT_RE.search(fonts):
        return True
    if expect_hindi:  # a Hindi document whose text layer has no Devanagari is mis-encoded
        deva, latin = len(_DEVANAGARI.findall(text)), len(_LATIN.findall(text))
        return deva < 0.2 * max(1, deva + latin)
    return False


def tesseract_ocr(page: pymupdf.Page, langs: str = "hin+eng", dpi: int = 300) -> str:
    import pytesseract  # noqa: PLC0415 - optional (extra "ingest")
    from PIL import Image  # noqa: PLC0415

    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return pytesseract.image_to_string(img, lang=langs)


def extract_pages(path: Path, *, expect_hindi: bool, ocr: OcrFn = tesseract_ocr) -> list[PageText]:
    out: list[PageText] = []
    with pymupdf.open(path) as doc:
        for i in range(doc.page_count):
            page = doc[i]
            if needs_ocr(page, expect_hindi):
                out.append(PageText(i + 1, ocr(page), "ocr"))
            else:
                out.append(PageText(i + 1, str(page.get_text("text")), "text"))
    return out
```

⚠️ Verify the OCR path for real on one scanned/legacy Hindi PDF on your Mac: `tesseract --list-langs` must show `hin`; OCR at 300 dpi takes a few seconds per page on the M1. If OCR quality is poor, try `dpi=400` and record the choice in an ADR.

## Step 5 — The pipeline + CLI

`tests/unit/ingest/test_pipeline.py` ✅

```python
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from pydantic import HttpUrl

from sahayak.ingest.manifest import ManifestRow
from sahayak.ingest.pdf import PageText
from sahayak.ingest.pipeline import IngestPipeline
from sahayak.store.repo import ChunkRow, DocumentRow

ROW = ManifestRow(
    doc_id="MD-T-HI",
    title="परीक्षण",
    lang="hi",
    doc_type="master_direction",
    url=HttpUrl("https://rbi.test/t.pdf"),
)


class FakeFetcher:
    def __init__(self, tmp: Path) -> None:
        self.path = tmp / "t.pdf"
        self.path.write_bytes(b"pdf")

    def fetch(self, url: str) -> Path:
        return self.path


class FakeEmbedder:
    def embed_passages(self, texts: Sequence[str]) -> np.ndarray:
        return np.ones((len(texts), 384), dtype=np.float32)


class MemWriter:
    def __init__(self) -> None:
        self.docs: list[DocumentRow] = []
        self.chunks: dict[str, list[ChunkRow]] = {}
        self.commits = 0

    def upsert_document(self, d: DocumentRow) -> None:
        self.docs.append(d)

    def replace_chunks(self, doc_id: str, chunks: Sequence[ChunkRow]) -> None:
        self.chunks[doc_id] = list(chunks)

    def commit(self) -> None:
        self.commits += 1


def test_ingest_writes_document_and_embedded_chunks(tmp_path: Path) -> None:
    pages = [PageText(1, "पहला अनुच्छेद। दूसरा अनुच्छेद।", "text"), PageText(2, "तीसरा।", "ocr")]
    writer = MemWriter()
    pipe = IngestPipeline(FakeFetcher(tmp_path), lambda p, hi: pages, FakeEmbedder(), writer)
    report = pipe.ingest(ROW)
    assert (report.pages, report.ocr_pages, report.chunks) == (2, 1, 2)
    assert report.script_mismatch is False
    assert len(writer.docs[0].sha256) == 64  # computed from the downloaded file
    assert [c.chunk_id for c in writer.chunks["MD-T-HI"]] == ["MD-T-HI#p1c0", "MD-T-HI#p2c0"]
    assert writer.commits == 1


def test_flags_hindi_doc_whose_text_is_latin(tmp_path: Path) -> None:
    pages = [PageText(1, "dsokbZlh fu;eksa dk ikyu", "text")]
    pipe = IngestPipeline(FakeFetcher(tmp_path), lambda p, hi: pages, FakeEmbedder(), MemWriter())
    assert pipe.ingest(ROW).script_mismatch is True
```

`src/sahayak/ingest/pipeline.py` ✅

```python
"""manifest row → download → extract (OCR if needed) → chunk → embed → store."""

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import structlog

from sahayak.ingest.manifest import ManifestRow, sha256_file
from sahayak.ingest.pdf import PageText
from sahayak.store.repo import ChunkRow, DocumentRow
from sahayak.text.chunking import chunk_page
from sahayak.text.normalize import detect_script

log = structlog.get_logger()


class Fetcher(Protocol):
    def fetch(self, url: str) -> Path: ...


class PassageEmbedder(Protocol):
    def embed_passages(self, texts: Sequence[str]) -> np.ndarray: ...


class Writer(Protocol):
    def upsert_document(self, d: DocumentRow) -> None: ...
    def replace_chunks(self, doc_id: str, chunks: Sequence[ChunkRow]) -> None: ...
    def commit(self) -> None: ...


Extractor = Callable[[Path, bool], list[PageText]]


@dataclass(frozen=True, slots=True)
class IngestReport:
    doc_id: str
    pages: int
    ocr_pages: int
    chunks: int
    script_mismatch: bool  # lang says 'hi' but extracted text is mostly Latin (or vice versa)


@dataclass
class IngestPipeline:
    fetcher: Fetcher
    extract: Extractor
    embedder: PassageEmbedder
    writer: Writer
    max_chars: int = 900

    def ingest(self, row: ManifestRow) -> IngestReport:
        path = self.fetcher.fetch(str(row.url))
        pages = self.extract(path, row.lang != "en")
        chunks = [
            c
            for p in pages
            for c in chunk_page(row.doc_id, p.page, p.text, max_chars=self.max_chars)
        ]
        vectors = self.embedder.embed_passages([c.text for c in chunks]) if chunks else []
        self.writer.upsert_document(
            DocumentRow(
                doc_id=row.doc_id,
                title=row.title,
                lang=row.lang,
                doc_type=row.doc_type,
                source_url=str(row.url),
                sha256=sha256_file(path),
                issued_on=row.issued_on,
                pair_doc_id=row.pair_doc_id,
            )
        )
        self.writer.replace_chunks(
            row.doc_id,
            [
                ChunkRow(c.chunk_id, row.doc_id, c.page, c.ordinal, row.lang, c.text, v)
                for c, v in zip(chunks, vectors, strict=True)
            ],
        )
        self.writer.commit()
        sample = " ".join(p.text for p in pages)[:5000]
        script = detect_script(sample)
        mismatch = (row.lang == "hi" and script == "en") or (row.lang == "en" and script == "hi")
        report = IngestReport(
            row.doc_id, len(pages), sum(p.method == "ocr" for p in pages), len(chunks), mismatch
        )
        log.info("ingested", **asdict(report))
        return report
```

The embedder is defined in S2 (`E5Embedder`). For S1 you can either implement S2-Step 1 first (it's 30 lines) or temporarily pass a fake embedder; the pipeline only depends on the `PassageEmbedder` protocol.

Final CLI (this is the v1.0 file; at S1 you only need `version`, `db migrate` and `ingest`. Add `serve` in S4 and `golden` in S5):

`src/sahayak/cli.py` ✅

```python
"""`sahayak` command-line entry point. Heavy imports stay inside commands (fast `--help`)."""

from datetime import date
from pathlib import Path
from typing import Annotated, Literal

import typer

from sahayak import __version__

app = typer.Typer(no_args_is_help=True, help="Sarkari Sahayak CLI")
db_app = typer.Typer(no_args_is_help=True, help="Database commands")
golden_app = typer.Typer(no_args_is_help=True, help="Flight Recorder golden set")
app.add_typer(db_app, name="db")
app.add_typer(golden_app, name="golden")

GOLDEN = Path("evals/golden/golden.jsonl")


@app.callback()
def main() -> None:
    """Sarkari Sahayak: ingest, index, benchmark and serve."""


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@db_app.command("migrate")
def db_migrate() -> None:
    """Apply pending SQL migrations."""
    from sahayak.config import get_settings  # noqa: PLC0415
    from sahayak.store.migrate import migrate  # noqa: PLC0415
    from sahayak.store.repo import connect  # noqa: PLC0415

    applied = migrate(connect(get_settings().database_url))
    typer.echo(f"applied: {', '.join(applied) or 'nothing (up to date)'}")


@app.command()
def ingest(
    manifest: Annotated[Path, typer.Option(exists=True)] = Path("data_manifest/rbi_manifest.csv"),
    cache: Annotated[Path, typer.Option()] = Path("data/raw"),
    only: Annotated[str | None, typer.Option(help="ingest a single doc_id")] = None,
) -> None:
    """Download, extract, chunk, embed and store every document in the manifest."""
    from sahayak.config import get_settings  # noqa: PLC0415
    from sahayak.embed.e5 import E5Embedder  # noqa: PLC0415
    from sahayak.ingest.download import PoliteDownloader  # noqa: PLC0415
    from sahayak.ingest.manifest import read_manifest  # noqa: PLC0415
    from sahayak.ingest.pdf import extract_pages  # noqa: PLC0415
    from sahayak.ingest.pipeline import IngestPipeline  # noqa: PLC0415
    from sahayak.store.repo import PgRepository, connect  # noqa: PLC0415

    settings = get_settings()
    pipeline = IngestPipeline(
        fetcher=PoliteDownloader(cache),
        extract=lambda p, hi: extract_pages(p, expect_hindi=hi),
        embedder=E5Embedder.load(settings.embed_model),
        writer=PgRepository(connect(settings.database_url)),
    )
    for row in read_manifest(manifest):
        if only and row.doc_id != only:
            continue
        report = pipeline.ingest(row)
        flag = "  ⚠️ script mismatch" if report.script_mismatch else ""
        typer.echo(
            f"{row.doc_id}: {report.pages} pages ({report.ocr_pages} OCR), "
            f"{report.chunks} chunks{flag}"
        )


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the REST + MCP server."""
    import uvicorn  # noqa: PLC0415

    from sahayak.api.app import build_app  # noqa: PLC0415
    from sahayak.bootstrap import build_service  # noqa: PLC0415
    from sahayak.config import Profile, get_settings  # noqa: PLC0415
    from sahayak.logging import configure_logging  # noqa: PLC0415

    settings = get_settings()
    configure_logging(settings.log_level, json=settings.log_json)
    app_ = build_app(
        build_service(settings),
        per_minute=settings.rate_limit_per_minute,
        trust_proxy=settings.profile is Profile.HOSTED,  # Render sets X-Forwarded-For
    )
    uvicorn.run(app_, host=host, port=port)


@golden_app.command("add")
def golden_add(
    run_id: str,
    expect: Annotated[str, typer.Option(help="answer | refuse")],
    failure_mode: Annotated[str, typer.Option()],
    must_cite: Annotated[
        list[str] | None, typer.Option(help="doc_id(s) that must be cited")
    ] = None,
    path: Path = GOLDEN,
) -> None:
    """Promote a flagged run into the golden regression set."""
    from sahayak.config import get_settings  # noqa: PLC0415
    from sahayak.flight.golden import GoldenCase, append_case, load_cases, next_id  # noqa: PLC0415
    from sahayak.flight.runs import RunStore  # noqa: PLC0415
    from sahayak.store.repo import connect  # noqa: PLC0415
    from sahayak.text.normalize import detect_script  # noqa: PLC0415

    run = RunStore(connect(get_settings().database_url)).get(run_id)
    if run is None:
        raise typer.BadParameter(f"unknown run_id {run_id}")
    script = detect_script(run["question"])
    lang: Literal["hi", "en", "hinglish"] = (
        "hi" if script == "hi" else "en" if script == "en" else "hinglish"
    )
    if expect not in ("answer", "refuse"):
        raise typer.BadParameter("expect must be 'answer' or 'refuse'")
    path.parent.mkdir(parents=True, exist_ok=True)
    case = GoldenCase(
        id=next_id(load_cases(path)),
        question=run["question"],
        lang=lang,
        expect=expect,  # type: ignore[arg-type]
        must_cite_doc_ids=must_cite or [],
        source_run_id=run_id,
        failure_mode=failure_mode,
        added_on=date.today(),
    )
    append_case(path, case)
    typer.echo(f"added {case.id} from run {run_id}")
```

`tests/unit/test_cli.py` ✅

```python
from typer.testing import CliRunner

from sahayak import __version__
from sahayak.cli import app


def test_version_command_prints_package_version() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_help_lists_all_commands() -> None:
    out = CliRunner().invoke(app, ["--help"]).stdout
    for cmd in ("db", "golden", "ingest", "serve", "version"):
        assert cmd in out
```

Run it:

```bash
uv sync --extra ingest --extra ml --group dev
uv run sahayak ingest --only MD-KYC-2016-EN      # one document first
uv run sahayak ingest                            # the rest (cached downloads)
docker compose exec db psql -U sahayak -c "select lang, count(*) from chunks group by 1;"
```

Makefile additions:

```makefile
ingest:  ## Download + ingest the manifest
	uv run sahayak ingest
```

## Definition of Done

- [ ] Manifest + data-sources doc committed; no PDFs in git (`git ls-files | grep -i pdf` is empty)
- [ ] `make check` and `make test-int` green; coverage gates pass
- [ ] Ingest log shows OCR pages and **zero unexplained script mismatches**
- [ ] ADR-0002 "ParadeDB locally, Neon (pgvector) hosted" written
- [ ] Spot check: `select text from chunks where lang='hi' limit 3;` reads as proper Hindi

## Cursor prompt (S1)

> Context: `AGENTS.md`, `docs/guide/sahayak/00-story-and-architecture.md`, `docs/guide/sahayak/S1-ingestion.md`.
> Implement S1 Step 2 only. First create `tests/unit/text/test_normalize.py` and `test_chunking.py` exactly as in the guide and run them to show they fail. Then implement `src/sahayak/text/normalize.py` and `chunking.py` until they pass. Do not touch other files. Show `make check` output.
