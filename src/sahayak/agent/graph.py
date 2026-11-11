"""The cite-or-refuse LangGraph agent.

prepare → rewrite → retrieve → grade ─┬─ sufficient ─→ generate → check_citations ─┬─ ok ─→ END
                ↑                     ├─ retry (attempts < max) ─→ rewrite          └─ bad → refuse
                └─────────────────────┴─ give up ──────────────────→ refuse → END
"""

from collections.abc import Sequence
from typing import Literal, Protocol, Required, TypedDict

import regex
import structlog
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from sahayak.agent.prompts import (
    ANSWER_SYSTEM,
    GRADE_SYSTEM,
    REFUSAL,
    REWRITE_SYSTEM,
    format_passages,
)
from sahayak.agent.schemas import DraftAnswer, EvidenceGrade, Rewrites
from sahayak.llm.gateway import LLMClient, LLMError
from sahayak.retrieve.types import Passage
from sahayak.text.normalize import detect_script, normalize_text

log = structlog.get_logger()
_CITATION_RE = regex.compile(r"\[([^\[\]\s]+#p\d+c\d+)\]")


class SearchPort(Protocol):
    def search(self, queries: Sequence[str], k: int) -> list[Passage]: ...


class _Fields(TypedDict, total=False):
    answer_lang: Literal["hi", "en"]
    queries: list[str]
    passages: list[Passage]
    attempts: int
    evidence_ok: bool
    answer: str
    citations: list[str]
    refused: bool
    refusal_reason: str
    llm_failed: bool


class AgentState(_Fields, total=False):
    """Full graph state; `question` is the only required input."""

    question: Required[str]


class AgentUpdate(_Fields, total=False):
    """What a node returns: any subset of the state keys."""

    question: str


def build_graph(
    llm: LLMClient, retriever: SearchPort, *, k: int = 6, max_attempts: int = 2
) -> CompiledStateGraph:
    def prepare(state: AgentState) -> AgentUpdate:
        q = normalize_text(state["question"])
        lang: Literal["hi", "en"] = "en" if detect_script(q) == "en" else "hi"
        return {"question": q, "answer_lang": lang, "queries": [q], "attempts": 0}

    def rewrite(state: AgentState) -> AgentUpdate:
        attempts = state.get("attempts", 0) + 1
        try:
            rw = llm.complete_json(system=REWRITE_SYSTEM, user=state["question"], schema=Rewrites)
            queries = list(dict.fromkeys([state["question"], rw.hindi, rw.english]))
        except LLMError:
            log.warning("rewrite_failed_using_original")
            queries = [state["question"]]
        return {"queries": [q for q in queries if q.strip()], "attempts": attempts}

    def retrieve(state: AgentState) -> AgentUpdate:
        return {"passages": retriever.search(state.get("queries", [state["question"]]), k)}

    def grade(state: AgentState) -> AgentUpdate:
        passages = state.get("passages", [])
        if not passages:
            return {"evidence_ok": False}
        try:
            verdict = llm.complete_json(
                system=GRADE_SYSTEM,
                user=f"Question: {state['question']}\n\nPassages:\n"
                + format_passages([(p.chunk_id, p.text) for p in passages]),
                schema=EvidenceGrade,
            )
        except LLMError:
            log.warning("grade_failed")
            return {"evidence_ok": False, "llm_failed": True}
        return {"evidence_ok": verdict.sufficient}

    def route_after_grade(state: AgentState) -> Literal["generate", "rewrite", "refuse"]:
        if state.get("evidence_ok"):
            return "generate"
        return "rewrite" if state.get("attempts", 0) < max_attempts else "refuse"

    def generate(state: AgentState) -> AgentUpdate:
        language = "Hindi (Devanagari)" if state.get("answer_lang") == "hi" else "English"
        try:
            draft = llm.complete_json(
                system=ANSWER_SYSTEM.format(language=language),
                user=f"Question: {state['question']}\n\nPassages:\n"
                + format_passages([(p.chunk_id, p.text) for p in state.get("passages", [])]),
                schema=DraftAnswer,
            )
        except LLMError:
            return {"answer": "", "citations": [], "llm_failed": True}
        return {"answer": draft.answer, "citations": draft.citations}

    def route_after_generate(state: AgentState) -> Literal["ok", "refuse"]:
        return "ok" if citations_valid(state) else "refuse"

    def refuse(state: AgentState) -> AgentUpdate:
        reason = "uncited_or_invalid_answer" if state.get("answer") else "insufficient_evidence"
        return {
            "answer": REFUSAL[state.get("answer_lang", "hi")],
            "citations": [],
            "refused": True,
            "refusal_reason": reason,
        }

    def finish(state: AgentState) -> AgentUpdate:
        return {"refused": False}

    g = StateGraph(AgentState)
    for name, fn in [
        ("prepare", prepare),
        ("rewrite", rewrite),
        ("retrieve", retrieve),
        ("grade", grade),
        ("generate", generate),
        ("refuse", refuse),
        ("finish", finish),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "prepare")
    g.add_edge("prepare", "rewrite")
    g.add_edge("rewrite", "retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges(
        "grade",
        route_after_grade,
        {"generate": "generate", "rewrite": "rewrite", "refuse": "refuse"},
    )
    g.add_conditional_edges("generate", route_after_generate, {"ok": "finish", "refuse": "refuse"})
    g.add_edge("finish", END)
    g.add_edge("refuse", END)
    return g.compile()


def citations_valid(state: AgentState) -> bool:
    """Every cited id was retrieved, the answer cites at least one, and declared == inline ids."""
    answer = state.get("answer", "")
    if not answer:
        return False
    retrieved = {p.chunk_id for p in state.get("passages", [])}
    inline = set(_CITATION_RE.findall(answer))
    declared = set(state.get("citations", []))
    return bool(inline) and inline <= retrieved and declared == inline
