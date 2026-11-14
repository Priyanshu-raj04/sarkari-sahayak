"""Application service: the one place where retrieval, the agent and budgets meet.

Both the REST API and the MCP server call this — never the graph or the DB directly.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel, Field

from sahayak.agent.graph import build_graph
from sahayak.agent.prompts import GRADE_SYSTEM, format_passages
from sahayak.agent.schemas import EvidenceGrade
from sahayak.api.ratelimit import DailyBudget
from sahayak.llm.gateway import LLMClient
from sahayak.retrieve.types import Passage, PassageStore


class SearchPort(Protocol):
    def search(self, queries: Sequence[str], k: int) -> list[Passage]: ...


class BudgetExceededError(RuntimeError):
    """The global daily LLM budget is used up."""


class Verdict(BaseModel):
    supported: bool
    evidence_chunk_ids: list[str] = Field(default_factory=list)


class AskResult(BaseModel):
    run_id: str
    answer: str
    citations: list[Passage]
    refused: bool
    refusal_reason: str | None = None
    degraded: bool = False  # all LLMs failed → retrieval-only result
    latency_ms: int


@dataclass
class SahayakService:
    retriever: SearchPort
    store: PassageStore
    llm: LLMClient
    budget: DailyBudget
    top_k: int = 6
    _graph: object = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._graph = build_graph(self.llm, self.retriever, k=self.top_k)

    def search(self, query: str, k: int) -> list[Passage]:
        return self.retriever.search([query], k)

    def get_passage(self, chunk_id: str) -> Passage | None:
        return self.store.get_many([chunk_id]).get(chunk_id)

    def verify_claim(self, claim: str, chunk_ids: list[str]) -> Verdict:
        self._spend()
        found = self.store.get_many(chunk_ids)
        if not found:
            return Verdict(supported=False)
        grade = self.llm.complete_json(
            system=GRADE_SYSTEM,
            user=f"Claim: {claim}\n\nPassages:\n"
            + format_passages([(p.chunk_id, p.text) for p in found.values()]),
            schema=EvidenceGrade,
        )
        ids = [c for c in grade.relevant_chunk_ids if c in found]
        return Verdict(supported=grade.sufficient, evidence_chunk_ids=ids)

    def ask(self, question: str) -> AskResult:
        self._spend()
        started = time.perf_counter()
        state = self._graph.invoke({"question": question})  # type: ignore[attr-defined]
        passages: list[Passage] = state.get("passages", [])
        by_id = {p.chunk_id: p for p in passages}
        degraded = bool(state.get("refused") and state.get("llm_failed") and passages)
        citation_ids = state.get("citations", [])
        return AskResult(
            run_id=uuid.uuid4().hex,
            answer=state["answer"],
            citations=passages if degraded else [by_id[c] for c in citation_ids if c in by_id],
            refused=bool(state.get("refused")),
            refusal_reason=state.get("refusal_reason"),
            degraded=degraded,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    def _spend(self) -> None:
        if not self.budget.try_spend():
            raise BudgetExceededError
