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
