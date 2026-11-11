# Contributing

## Dev setup

```bash
uv sync --group dev                              # everyday: ruff, pytest, pyright
uv sync --group dev --extra ingest               # PDF/OCR ingest
uv sync --group dev --extra ingest --extra evals # + ranx harness (what CI uses)
uv sync --group dev --extra ingest --extra evals --extra ml  # + torch E5 (local bench)
```

**Why extras?** Heavy PDF libs live in `ingest`; `ranx`/HF helpers in `evals`; `sentence-transformers`
in `ml` (too heavy for default CI). CI runs `uv sync --group dev --extra ingest --extra evals`.
If you only sync `--group dev` locally, typecheck may fail on ingest imports.
## Branches

This repo currently pushes small conventional commits to `main` (see project handoff). Guide
branch names like `feat/s1-*` are optional.

## Commits / PR titles

[Conventional Commits](https://www.conventionalcommits.org/). Scopes for this repo: `ingest`,
`retrieval`, `agent`, `llm`, `mcp`, `api`, `ui`, `evals`, `infra`, `docs`.

Example: `feat(retrieval): add reciprocal rank fusion`

## Workflow

1. Open / link a milestone issue when useful.
2. TDD: failing test → implement → green → refactor.
3. `uv sync --group dev --extra ingest --extra evals && make check` before push.
4. Keep commits SSH-signed.

## Manual RBI PDFs (when WAF blocks download)

If `sahayak ingest` reports bot protection, Print→PDF from the browser and place the file at
`data/raw/<sha256(url)[:24]>.pdf` (or `.html` — same basename). Never commit PDFs.
