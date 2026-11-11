from types import SimpleNamespace
from typing import Any

import litellm
import pytest
from pydantic import BaseModel

from sahayak.llm.gateway import LiteLLMGateway, LLMError, extract_json


class Verdict(BaseModel):
    supported: bool
    reason: str


def reply(text: str) -> SimpleNamespace:
    msg = SimpleNamespace(content=text)
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)


class ScriptedCompletion:
    def __init__(self, script: list[object]) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        assert isinstance(item, str)
        return reply(item)


@pytest.mark.parametrize(
    "text",
    [
        '{"supported": true, "reason": "ok"}',
        '```json\n{"supported": true, "reason": "ok"}\n```',
        '<think>hmm</think>\nSure! {"supported": true, "reason": "ok"} trailing',
    ],
)
def test_extract_json_tolerates_wrappers(text: str) -> None:
    assert extract_json(text) == {"supported": True, "reason": "ok"}


def test_extract_json_raises_without_object() -> None:
    with pytest.raises(ValueError, match="no JSON"):
        extract_json("नहीं पता")


def test_returns_validated_model_and_records_usage() -> None:
    fake = ScriptedCompletion(['{"supported": false, "reason": "नहीं"}'])
    gw = LiteLLMGateway(models=["m1"], completion=fake)
    out = gw.complete_json(system="s", user="u", schema=Verdict)
    assert out == Verdict(supported=False, reason="नहीं")
    assert gw.last_model == "m1"
    assert gw.usage == [{"model": "m1", "prompt_tokens": 10, "completion_tokens": 5}]
    assert "matching this schema" in fake.calls[0]["messages"][0]["content"]


def test_invalid_json_triggers_one_repair_turn() -> None:
    fake = ScriptedCompletion(['{"supported": "maybe"}', '{"supported": true, "reason": "fixed"}'])
    out = LiteLLMGateway(models=["m1"], completion=fake).complete_json(
        system="s", user="u", schema=Verdict
    )
    assert out.reason == "fixed"
    assert fake.calls[1]["messages"][-1]["content"].startswith("Invalid:")


def test_provider_error_falls_back_to_next_model() -> None:
    fake = ScriptedCompletion([ConnectionError("down"), '{"supported": true, "reason": "ok"}'])
    gw = LiteLLMGateway(models=["groq/x", "gemini/y"], completion=fake)
    gw.complete_json(system="s", user="u", schema=Verdict)
    assert gw.last_model == "gemini/y"
    assert [c["model"] for c in fake.calls] == ["groq/x", "gemini/y"]


def test_all_models_failing_raises_llm_error_with_reasons() -> None:
    fake = ScriptedCompletion([ConnectionError("a"), "not json", "still not json"])
    gw = LiteLLMGateway(models=["m1", "m2"], completion=fake)
    with pytest.raises(LLMError, match=r"m1: ConnectionError.*m2: invalid JSON"):
        gw.complete_json(system="s", user="u", schema=Verdict)


def test_works_with_real_litellm_mock_response() -> None:
    def mocked(**kwargs: Any) -> Any:
        return litellm.completion(**kwargs, mock_response='{"supported": true, "reason": "m"}')

    gw = LiteLLMGateway(models=["ollama_chat/qwen3:4b-instruct"], completion=mocked)
    assert gw.complete_json(system="s", user="u", schema=Verdict).supported is True
