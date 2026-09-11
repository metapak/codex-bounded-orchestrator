CREATE TABLE research_claims (
 id INTEGER PRIMARY KEY,
 research_item_id INTEGER NOT NULL REFERENCES research_items(id),
 claim_index INTEGER NOT NULL,
 text TEXT NOT NULL,
 kind TEXT NOT NULL,
 evidence_ids TEXT NOT NULL,
 UNIQUE(research_item_id, claim_index)
);
INSERT OR IGNORE INTO schema_version(version) VALUES (3);
