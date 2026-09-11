PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version(version) VALUES (1);
CREATE TABLE IF NOT EXISTS research_items (
 id INTEGER PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL, title TEXT NOT NULL,
 canonical_url TEXT NOT NULL, excerpt TEXT NOT NULL, fingerprint TEXT NOT NULL UNIQUE,
 author TEXT, published_at TEXT, discovered_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new',
 summary TEXT, category TEXT, confidence REAL, UNIQUE(source, external_id)
);
CREATE TABLE IF NOT EXISTS evidence_records (
 id INTEGER PRIMARY KEY, research_item_id INTEGER NOT NULL REFERENCES research_items(id),
 source_url TEXT NOT NULL, excerpt TEXT NOT NULL, content_hash TEXT NOT NULL,
 captured_at TEXT NOT NULL, evidence_type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
 id INTEGER PRIMARY KEY, text TEXT NOT NULL, category TEXT NOT NULL, status TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1, confidence REAL NOT NULL, factual_risk TEXT NOT NULL,
 verification_status TEXT NOT NULL, research_item_id INTEGER NOT NULL REFERENCES research_items(id),
 provider TEXT NOT NULL, model TEXT NOT NULL, prompt_version TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, rejection_reason TEXT
);
CREATE TABLE IF NOT EXISTS claims (
 id INTEGER PRIMARY KEY, draft_id INTEGER NOT NULL REFERENCES drafts(id), claim_index INTEGER NOT NULL,
 text TEXT NOT NULL, kind TEXT NOT NULL, evidence_ids TEXT NOT NULL, supported INTEGER, note TEXT
);
CREATE TABLE IF NOT EXISTS draft_revisions (
 id INTEGER PRIMARY KEY, draft_id INTEGER NOT NULL REFERENCES drafts(id), revision INTEGER NOT NULL,
 text TEXT NOT NULL, verification_status TEXT NOT NULL, changed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pipeline_runs (
 id INTEGER PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL,
 finished_at TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS model_calls (
 id INTEGER PRIMARY KEY, run_id INTEGER REFERENCES pipeline_runs(id), role TEXT NOT NULL,
 provider TEXT NOT NULL, model TEXT NOT NULL, response_id TEXT, input_tokens INTEGER,
 output_tokens INTEGER, prompt_version TEXT NOT NULL, created_at TEXT NOT NULL
);
