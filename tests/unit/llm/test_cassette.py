import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel

from sahayak.llm.cassette import wrap_completion
from sahayak.llm.gateway import LiteLLMGateway


class Verdict(BaseModel):
    supported: bool
    reason: str


def _reply(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2),
    )


def test_hash_cassette_record_and_replay(tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []

    def live(**kwargs: Any) -> SimpleNamespace:
        calls.append(kwargs)
        return _reply('{"supported": true, "reason": "ok"}')

    recorded = wrap_completion(live, cassette_dir=tmp_path, mode="record")
    gw = LiteLLMGateway(models=["m1"], completion=recorded)
    assert gw.complete_json(system="s", user="u", schema=Verdict).supported is True
    assert len(calls) == 1
    assert list(tmp_path.glob("*.json"))

    replayed = wrap_completion(live, cassette_dir=tmp_path, mode="replay")
    gw2 = LiteLLMGateway(models=["m1"], completion=replayed)
    out = gw2.complete_json(system="s", user="u", schema=Verdict)
    assert out.supported is True
    assert len(calls) == 1  # live not called again
    blob = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert "supported" in blob["content"]
