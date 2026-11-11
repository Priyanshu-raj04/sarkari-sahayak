# 6. LiteLLM pinned + own gateway
Date: 2026-11-11 · Status: Accepted

## Context
We need a provider-agnostic chat completion path (Ollama locally; Groq/Gemini hosted later)
with JSON schema validation and fallbacks. Calling providers ad hoc from graph nodes would
scatter retries and make FakeLLM injection hard.

LiteLLM had **verified 2026 supply-chain incidents** on PyPI/Docker (malicious publishes
of `1.82.7`/`1.82.8` in March and `1.107.0` on 2026-10-21; see
[LiteLLM March advisory](https://docs.litellm.ai/blog/security-update-march-2026) and
[Oct 21 advisory](https://docs.litellm.ai/blog/security-incident-oct-21-2026) /
[Microsoft analysis](https://www.microsoft.com/en-us/security/blog/2026/10/23/inside-the-litellm-1-107-0-supply-chain-compromise-credential-theft-through-python-startup-hooks/)).
We must pin a known-good version and keep our own thin gateway rather than sprawling
direct SDK usage.

## Decision
- Pin **`litellm==1.108.3`** in `pyproject.toml` (post-1.107.0; do not bump casually — see `AGENTS.md`).
- All LLM traffic goes through **`LiteLLMGateway`** (`complete_json` + `extract_json`, one
  repair turn, ordered model fallbacks, injectable `completion=` for tests).
- Local default model: `ollama_chat/qwen3:4b-instruct` with `api_base` from settings.
- CI never calls live providers; unit tests use ScriptedCompletion / FakeLLM / mock_response.

## Consequences
- Graph depends only on the `LLMClient` protocol.
- Dependency upgrades of litellm require explicit review against advisory history.
- Hash-cassette fallback (`sahayak.llm.cassette`) records/replays when VCR cannot capture
  LiteLLM↔Ollama HTTP.
