-- ParadeDB only (local + benchmarks). Skipped automatically where pg_search is unavailable (Neon).
CREATE EXTENSION IF NOT EXISTS pg_search;
CREATE INDEX IF NOT EXISTS chunks_bm25 ON chunks
    USING paradedb (chunk_id, (text::pdb.icu), doc_id, lang);
