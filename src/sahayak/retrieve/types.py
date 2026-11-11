"""Shared retrieval types. Full hybrid retrieval arrives in S2."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Passage:
    chunk_id: str
    doc_id: str
    lang: str
    page: int
    text: str
    title: str
    source_url: str
