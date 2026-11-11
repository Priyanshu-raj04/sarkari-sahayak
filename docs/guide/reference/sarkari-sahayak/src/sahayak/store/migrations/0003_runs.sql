-- Flight Recorder: every /v1/ask run, with the user's feedback and the Phoenix trace id.
CREATE TABLE IF NOT EXISTS runs (
    run_id      text PRIMARY KEY,
    question    text NOT NULL,
    answer      text NOT NULL,
    refused     boolean NOT NULL,
    degraded    boolean NOT NULL DEFAULT false,
    citations   jsonb NOT NULL DEFAULT '[]'::jsonb,   -- list of chunk_ids
    model       text,
    trace_id    text,
    latency_ms  int NOT NULL,
    feedback    smallint CHECK (feedback IN (-1, 0, 1)),
    note        text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS runs_feedback_idx ON runs (feedback) WHERE feedback = -1;
