-- Core schema. Embedding dimension 384 = intfloat/multilingual-e5-small.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    doc_id        text PRIMARY KEY,                -- e.g. 'MD-KYC-2016-EN'
    title         text NOT NULL,
    lang          text NOT NULL CHECK (lang IN ('hi', 'en', 'mr')),
    doc_type      text NOT NULL,                   -- 'master_direction' | 'circular' | 'gr'
    source_url    text NOT NULL,
    issued_on     date,
    pair_doc_id   text,                            -- the same document in the other language
    sha256        text NOT NULL,                   -- of the downloaded file
    ingested_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id   text PRIMARY KEY,                   -- '<doc_id>#p<page>c<ordinal>'
    doc_id     text NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    page       int  NOT NULL,
    ordinal    int  NOT NULL,
    lang       text NOT NULL,
    text       text NOT NULL,
    embedding  vector(384)
);

CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks (doc_id);
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks
    USING hnsw (embedding vector_cosine_ops);
