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
