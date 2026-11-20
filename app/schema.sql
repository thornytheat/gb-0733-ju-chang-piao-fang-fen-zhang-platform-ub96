CREATE TABLE IF NOT EXISTS publications (
    book TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    book TEXT NOT NULL REFERENCES publications(book),
    payload TEXT NOT NULL,
    sequence INTEGER NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS run_inputs (
    run_id TEXT NOT NULL REFERENCES runs(id),
    source TEXT NOT NULL,
    data BLOB NOT NULL,
    PRIMARY KEY (run_id, source)
);
CREATE INDEX IF NOT EXISTS run_head ON runs(book, sequence DESC);
