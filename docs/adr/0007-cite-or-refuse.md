# 7. Cite-or-refuse policy
Date: 2026-11-11 · Status: Accepted

## Context
Regulatory answers must not invent citations. Small models (3–4B) often invent chunk ids
or answer without evidence. Prompt-only instructions are insufficient under injection.

## Decision
LangGraph agent (`build_graph`) follows:

prepare → rewrite → retrieve → grade → (generate | rewrite≤2 | refuse) → **code** citation check.

- **Refuse** in the user’s language (`REFUSAL[hi|en]`) when evidence is insufficient after
  rewrite cap, or when `citations_valid` fails (empty answer, undeclared/unretrieved ids,
  declared ≠ inline `[chunk_id]`).
- **`citations_valid` is plain code**, never an LLM judgment.
- Passages/questions are treated as data; prompts say to ignore embedded instructions, but
  structural citation checks are the real defence.

## Consequences
- Invalid citations become refusals, not “almost answers”.
- Service layer (S4) can use `llm_failed` for degraded retrieval-only paths later.
- Unit tests cover answer, retry-then-answer, refuse-empty, refuse-bad-citation, rewrite-failure.
