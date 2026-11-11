# AGENTS.md — Sarkari Sahayak

## What this is
A bilingual (Hindi/English) agentic-RAG MCP server over RBI Master Directions. Every answer must cite
chunk ids from retrieved passages, or the system must refuse. See docs/guide/sahayak/00-story-and-architecture.md.

## Golden rules
1. TDD: write/adjust a failing test first, then the minimum code to pass, then refactor.
2. Never call a real LLM or the network in unit tests. Use FakeLLM / cassettes / fixtures.
3. Python 3.13, type hints everywhere, pyright must pass. Pydantic models at every boundary.
4. Tokenize Hindi with the `regex` package `[\p{L}\p{M}\p{N}]+` — never `re`'s `\w` (it splits Devanagari).
5. All config through `sahayak.config.Settings`; no os.environ reads elsewhere.
6. Small functions, pure where possible; I/O at the edges (adapters), logic in the core.
7. Don't add dependencies without asking; never bump litellm/fastmcp/mcp casually.
8. Conventional commit messages. Don't commit data/, .env, PDFs, model files.

## Commands
make up | make check | make test-int | make test-e2e | uv run sahayak --help
