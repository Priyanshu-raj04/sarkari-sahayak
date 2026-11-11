from collections.abc import Sequence

from sahayak.agent.graph import build_graph, citations_valid
from sahayak.agent.prompts import REFUSAL
from sahayak.agent.schemas import DraftAnswer, EvidenceGrade, Rewrites
from sahayak.llm.gateway import LLMError
from sahayak.retrieve.types import Passage
from tests.fakes import FakeLLM, passage

KYC = passage("MD-KYC#p4c0", "केवाईसी हर दस साल में अद्यतन करना होगा।")


class StubSearch:
    def __init__(self, results: list[Passage]) -> None:
        self.results = results
        self.queries: list[list[str]] = []

    def search(self, queries: Sequence[str], k: int) -> list[Passage]:
        self.queries.append(list(queries))
        return self.results[:k]


def run(llm: FakeLLM, search: StubSearch, question: str) -> dict:
    return build_graph(llm, search).invoke({"question": question})


def test_answers_with_valid_citation_in_hindi() -> None:
    llm = FakeLLM(
        {
            Rewrites: [Rewrites(hindi="केवाईसी अद्यतन", english="KYC update periodicity")],
            EvidenceGrade: [EvidenceGrade(sufficient=True, relevant_chunk_ids=[KYC.chunk_id])],
            DraftAnswer: [
                DraftAnswer(answer="हर दस साल में [MD-KYC#p4c0]।", citations=["MD-KYC#p4c0"])
            ],
        }
    )
    search = StubSearch([KYC])
    out = run(llm, search, "केवाईसी कितने साल में अपडेट करनी है?")
    assert out["refused"] is False
    assert out["citations"] == ["MD-KYC#p4c0"]
    assert search.queries[0] == [
        "केवाईसी कितने साल में अपडेट करनी है?",
        "केवाईसी अद्यतन",
        "KYC update periodicity",
    ]
    assert "Hindi" in llm.calls[-1][0]  # answer prompt asks for Hindi


def test_english_question_gets_english_answer_prompt() -> None:
    llm = FakeLLM(
        {
            Rewrites: [Rewrites(hindi="h", english="e")],
            EvidenceGrade: [EvidenceGrade(sufficient=True)],
            DraftAnswer: [
                DraftAnswer(answer="Every ten years [MD-KYC#p4c0].", citations=["MD-KYC#p4c0"])
            ],
        }
    )
    run(llm, StubSearch([KYC]), "How often must KYC be updated?")
    assert "English" in llm.calls[-1][0]


def test_refuses_when_nothing_is_retrieved_after_retries() -> None:
    llm = FakeLLM({Rewrites: [Rewrites(hindi="h", english="e")] * 2})
    out = run(llm, StubSearch([]), "आज मौसम कैसा है?")
    assert out["refused"] is True
    assert out["answer"] == REFUSAL["hi"]
    assert out["refusal_reason"] == "insufficient_evidence"
    assert out["citations"] == []


def test_retries_rewrite_once_then_answers() -> None:
    llm = FakeLLM(
        {
            Rewrites: [Rewrites(hindi="h1", english="e1"), Rewrites(hindi="h2", english="e2")],
            EvidenceGrade: [EvidenceGrade(sufficient=False), EvidenceGrade(sufficient=True)],
            DraftAnswer: [DraftAnswer(answer="ok [MD-KYC#p4c0]", citations=["MD-KYC#p4c0"])],
        }
    )
    search = StubSearch([KYC])
    out = run(llm, search, "What about KYC?")
    assert out["refused"] is False
    assert len(search.queries) == 2


def test_refuses_when_answer_cites_unretrieved_chunk() -> None:
    llm = FakeLLM(
        {
            Rewrites: [Rewrites(hindi="h", english="e")],
            EvidenceGrade: [EvidenceGrade(sufficient=True)],
            DraftAnswer: [DraftAnswer(answer="Made up [MD-X#p1c0].", citations=["MD-X#p1c0"])],
        }
    )
    out = run(llm, StubSearch([KYC]), "What about KYC?")
    assert out["refused"] is True
    assert out["refusal_reason"] == "uncited_or_invalid_answer"
    assert out["answer"] == REFUSAL["en"]


def test_rewrite_failure_falls_back_to_original_question() -> None:
    llm = FakeLLM(
        {
            Rewrites: [LLMError("down")],
            EvidenceGrade: [EvidenceGrade(sufficient=True)],
            DraftAnswer: [DraftAnswer(answer="ok [MD-KYC#p4c0]", citations=["MD-KYC#p4c0"])],
        }
    )
    search = StubSearch([KYC])
    run(llm, search, "KYC?")
    assert search.queries[0] == ["KYC?"]


def test_citations_valid_rules() -> None:
    base = {"passages": [KYC], "answer": "x [MD-KYC#p4c0]", "citations": ["MD-KYC#p4c0"]}
    assert citations_valid(base)  # type: ignore[arg-type]
    assert not citations_valid({**base, "answer": "no citation"})  # type: ignore[arg-type]
    assert not citations_valid({**base, "citations": []})  # type: ignore[arg-type]
    assert not citations_valid({**base, "answer": ""})  # type: ignore[arg-type]
