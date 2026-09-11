ALTER TABLE research_items ADD COLUMN near_duplicate_key TEXT;
ALTER TABLE drafts ADD COLUMN approved_at TEXT;
ALTER TABLE drafts ADD COLUMN rejected_at TEXT;
ALTER TABLE drafts ADD COLUMN editor_notes TEXT;
ALTER TABLE drafts ADD COLUMN hook_type TEXT;
ALTER TABLE drafts ADD COLUMN post_structure TEXT;
ALTER TABLE drafts ADD COLUMN source_type TEXT;
INSERT OR IGNORE INTO schema_version(version) VALUES (2);
