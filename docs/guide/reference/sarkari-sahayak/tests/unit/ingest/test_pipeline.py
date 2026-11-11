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
