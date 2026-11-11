# Agent live-smoke notes

Checked: **2026-11-11**. Model: `ollama_chat/qwen3:4b-instruct` via local Ollama (`localhost:11434`).
`PROMPT_VERSION`: `2026-11-10.1`.

## Smoke (`tests/e2e/test_live_ollama.py`)

Question: “How often must KYC be updated for low-risk customers?” with one English KYC passage (`MD-T#p1c0`).
Pass criterion (SoT): `refused` **or** `citations == ["MD-T#p1c0"]` — never cite an unretrieved id.

| Run | Result | Approx wall time |
|---|---|---|
| 1 | pass | ~19 s |
| 2 | pass | ~11 s |
| 3 | pass | ~11 s |
| 4 | pass | ~12 s |
| 5 | pass | ~11 s |

**Measured: 5/5 passes** (DoD requires ≥4/5). No prompt retune needed this session.

## Cassette (Step 5)

Tried pytest-recording VCR against LiteLLM→Ollama; capture of provider HTTP is unreliable for this stack.
**Fallback used:** gateway hash-cassette (`tests/cassettes/llm/`) — see `sahayak.llm.cassette`. Replay does not need Ollama.
