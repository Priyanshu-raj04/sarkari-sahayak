"""Structured outputs the LLM must return (validated with Pydantic)."""

from pydantic import BaseModel, Field


class Rewrites(BaseModel):
    hindi: str = Field(description="The question rewritten as a clear Hindi search query")
    english: str = Field(description="The question rewritten as a clear English search query")


class EvidenceGrade(BaseModel):
    sufficient: bool = Field(description="True only if the passages fully answer the question")
    relevant_chunk_ids: list[str] = Field(default_factory=list)


class DraftAnswer(BaseModel):
    answer: str = Field(
        description="Answer in the user's language with [chunk_id] after each claim"
    )
    citations: list[str] = Field(description="chunk_ids used, each must appear in the answer text")
