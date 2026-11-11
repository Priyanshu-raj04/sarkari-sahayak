"""Live smoke against local Ollama (excluded from default CI via `-m "not llm"`)."""

from collections.abc import Sequence

import pytest

from sahayak.agent.graph import build_graph
from sahayak.config import get_settings
from sahayak.llm.gateway import LiteLLMGateway
from sahayak.retrieve.types import Passage
from tests.fakes import passage

pytestmark = [pytest.mark.llm, pytest.mark.e2e]


class OnePassage:
    def search(self, queries: Sequence[str], k: int) -> list[Passage]:
        return [
            passage(
                "MD-T#p1c0",
                "Regulated entities shall carry out periodic updation of KYC "
                "at least once every ten years for low risk customers.",
                lang="en",
            )
        ]


def test_real_model_answers_with_valid_citation_or_refuses() -> None:
    settings = get_settings()
    graph = build_graph(
        LiteLLMGateway(
            models=[settings.agent_model],
            api_base=settings.ollama_base_url,
        ),
        OnePassage(),
    )
    out = graph.invoke({"question": "How often must KYC be updated for low-risk customers?"})
    # A small model may legitimately refuse; what it must never do is cite something unretrieved.
    assert out["refused"] or out["citations"] == ["MD-T#p1c0"]
