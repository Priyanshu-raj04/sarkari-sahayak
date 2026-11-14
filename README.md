# Sarkari Sahayak — सरकारी सहायक

Bilingual (Hindi/English) agentic-RAG MCP server over RBI regulations. Every answer cites retrieved passages — or the system refuses.

🚧 **Under active development** (S4 MCP + REST closed; next: S5 UI / optional MIRACL benches).

## Roadmap

- [x] S0 Bootstrap (repo skeleton, CI, docs)
- [x] S1 Ingestion
- [x] S2 Retrieval + benchmarks
- [x] S3 Agent (cite-or-refuse)
- [x] S4 MCP + REST (`SahayakService`, rate limit, `/v1/ask`, `/mcp`; Cursor + Claude screenshots in `docs/img/`)
- [ ] S5 UI + Flight Recorder
- [ ] S6 Ship v1.0
- [ ] S7 v1.1 Supersession + Marathi

## Quick start

```bash
# Day-to-day (lint, unit tests, typecheck without PDF deps)
uv sync --group dev

# S1 ingest / PDF+OCR (CI installs this for pyright)
uv sync --group dev --extra ingest

# S2 harness unit tests (ranx) — also what CI uses with ingest
uv sync --group dev --extra ingest --extra evals

# Local E5 / FlagEmbedding for ingest + bench-quick (not in default CI)
uv sync --group dev --extra ingest --extra evals --extra ml

make check
uv run sahayak version
```

`make check` and GitHub Actions install **ingest** + **evals** so `pymupdf` and `ranx` resolve. Real embeddings need `--extra ml` locally. See `CONTRIBUTING.md`.

### Benchmarks (local)

```bash
make up
uv sync --group dev --extra ingest --extra evals --extra ml
make bench-quick   # IndicQA-hi → docs/results/retrieval.json + .md
```

On Apple Silicon, E5 uses MPS when available (`PYTORCH_ENABLE_MPS_FALLBACK=1` if needed).

### Serve (REST + MCP)

```bash
make up
ollama serve   # if not already running
uv run sahayak serve          # http://127.0.0.1:8000
curl -s http://127.0.0.1:8000/health
# Cursor: .cursor/mcp.json → http://127.0.0.1:8000/mcp
# Claude Desktop: stdio via python -m sahayak.mcp_server (see docs/guide/sahayak/S4-mcp-server.md)
```

Client proof screenshots: `docs/img/s4-cursor-mcp-tools.png`, `s4-cursor-cited-answer.png`, `s4-claude-desktop-mcp.png`.

### Agent live smoke (local Ollama)

```bash
ollama serve   # if not already running
ollama pull qwen3:4b-instruct
uv run pytest -m llm -q   # excluded from default CI / make check
```

See `docs/results/agent-notes.md` for measured pass rates.

See `docs/guide/` for the full implementation guide and `AGENTS.md` for contributor rules.
