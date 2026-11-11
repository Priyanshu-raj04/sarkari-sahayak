"""Replay a recorded LiteLLM hash-cassette without calling Ollama (CI-safe)."""

from pathlib import Path

import litellm
import pytest
from pydantic import BaseModel

from sahayak.llm.cassette import wrap_completion
from sahayak.llm.gateway import LiteLLMGateway

pytestmark = [pytest.mark.e2e]

CASSETTE_DIR = Path(__file__).resolve().parents[1] / "cassettes" / "llm"


class Verdict(BaseModel):
    supported: bool
    reason: str


@pytest.mark.skipif(not any(CASSETTE_DIR.glob("*.json")), reason="no hash cassettes recorded")
def test_hash_cassette_replays_without_network() -> None:
    def forbidden(**kwargs: object) -> object:
        raise AssertionError("live completion must not run in replay")

    # Prefer replay; if key missing, do not fall through to live.
    completion = wrap_completion(forbidden, cassette_dir=CASSETTE_DIR, mode="replay")
    # Rebuild the same prompt shape used when recording (gateway adds schema hint).
    gw = LiteLLMGateway(models=["ollama_chat/qwen3:4b-instruct"], completion=completion)
    out = gw.complete_json(
        system="You check a trivial claim.",
        user='Is "ten years" supported for KYC low-risk updation? Return JSON.',
        schema=Verdict,
    )
    assert isinstance(out.supported, bool)
    assert out.reason
    _ = litellm  # keep import for parity with record path tooling
