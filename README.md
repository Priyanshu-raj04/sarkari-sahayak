# Sarkari Sahayak — सरकारी सहायक

Bilingual (Hindi/English) agentic-RAG MCP server over RBI regulations. Every answer cites retrieved passages — or the system refuses.

🚧 **Under active development** (Phase 0 bootstrap complete; feature milestones next).

## Roadmap

- [x] S0 Bootstrap (repo skeleton, CI, docs)
- [ ] S1 Ingestion
- [ ] S2 Retrieval + benchmarks
- [ ] S3 Agent (cite-or-refuse)
- [ ] S4 MCP server
- [ ] S5 UI + Flight Recorder
- [ ] S6 Ship v1.0
- [ ] S7 v1.1 Supersession + Marathi

## Quick start

```bash
uv sync --group dev
make check
uv run sahayak version
```

See `docs/guide/` for the full implementation guide and `AGENTS.md` for contributor rules.
