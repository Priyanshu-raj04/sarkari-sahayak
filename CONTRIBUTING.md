# Contributing

## Branches

`<type>/<milestone>-<slug>` — example: `feat/s2-rrf-fusion`

## Commits / PR titles

[Conventional Commits](https://www.conventionalcommits.org/). Scopes for this repo: `ingest`, `retrieval`, `agent`, `llm`, `mcp`, `api`, `ui`, `evals`, `infra`, `docs`.

Example: `feat(retrieval): add reciprocal rank fusion`

## Workflow

1. Open / link a milestone issue.
2. Branch from `main`.
3. TDD: failing test → implement → green → refactor.
4. `make check` locally (added in Phase-0 skeleton).
5. Open a PR; squash-merge only.

## Signing

Commits are SSH-signed. After Phase-0 CI lands, `main` will require PRs + the `check` status.
