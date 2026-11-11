"""Retrieval data types and ports (interfaces)."""

from typing import Protocol

from pydantic import BaseModel, Field


class Passage(BaseModel):
    chunk_id: str
    doc_id: str
    lang: str
    page: int
    text: str
    title: str = ""
    source_url: str = ""
    score: float = 0.0
    scores: dict[str, float] = Field(
        default_factory=dict
    )  # per-retriever ranks/scores for debugging


class Retriever(Protocol):
    name: str

    def search(self, query: str, k: int) -> list[str]:
        """Return chunk ids, best first."""
        ...


class PassageStore(Protocol):
    def get_many(self, chunk_ids: list[str]) -> dict[str, Passage]: ...


class Reranker(Protocol):
    def score(self, query: str, texts: list[str]) -> list[float]: ...
