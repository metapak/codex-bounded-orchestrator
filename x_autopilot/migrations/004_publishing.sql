ALTER TABLE drafts ADD COLUMN scheduled_at TEXT;
ALTER TABLE drafts ADD COLUMN publish_attempted_at TEXT;
ALTER TABLE drafts ADD COLUMN published_at TEXT;
ALTER TABLE drafts ADD COLUMN x_post_id TEXT;
ALTER TABLE drafts ADD COLUMN publish_error TEXT;
ALTER TABLE model_calls ADD COLUMN cached_input_tokens INTEGER;
ALTER TABLE model_calls ADD COLUMN cache_write_tokens INTEGER;
ALTER TABLE model_calls ADD COLUMN estimated_cost_usd REAL;
ALTER TABLE model_calls ADD COLUMN cost_provenance TEXT;
CREATE TABLE publish_claims (
 content_hash TEXT PRIMARY KEY,
 draft_id INTEGER NOT NULL UNIQUE REFERENCES drafts(id),
 claimed_at TEXT NOT NULL
);
CREATE TABLE job_slots (
 job_name TEXT NOT NULL,
 slot TEXT NOT NULL,
 status TEXT NOT NULL,
 claimed_at TEXT NOT NULL,
 finished_at TEXT,
 PRIMARY KEY(job_name, slot)
);
CREATE INDEX drafts_due_idx ON drafts(status, scheduled_at);
INSERT OR IGNORE INTO schema_version(version) VALUES (4);
