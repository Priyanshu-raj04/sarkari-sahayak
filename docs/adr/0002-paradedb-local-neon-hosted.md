# 2. ParadeDB locally, Neon (pgvector) hosted
Date: 2026-11-11 · Status: Accepted

## Context
We need BM25 + dense vector search over Hindi/English regulatory chunks. Neon removed
`pg_search` (ParadeDB) for new projects; local Mac demos still want in-database BM25 with
an ICU tokenizer that handles Devanagari.

## Decision
- **Local / CI / benchmarks:** ParadeDB in Docker (`pgvector` + `pg_search`). Migration
  `0002_bm25_paradedb.sql` builds a `paradedb` BM25 index over `chunks.text` with
  `(text::pdb.icu)`.
- **Hosted (Render + Neon):** plain Postgres with `pgvector` only. Skip the BM25 migration
  when `pg_search` is unavailable; build an in-process **bm25s** index from rows at startup
  (S2/S6). Same application schema (`documents`, `chunks`).

## Consequences
- One migration runner with an optional `bm25` name prefix.
- Hybrid retrieval must select BM25 backend by profile (ParadeDB SQL vs bm25s).
- Local DoD includes the ParadeDB ICU BM25 integration test.
