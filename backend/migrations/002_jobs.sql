CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    available BIGINT NOT NULL,
    created BIGINT NOT NULL,
    error TEXT
);
CREATE INDEX job_queue ON jobs (state,available);
