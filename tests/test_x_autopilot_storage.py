from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from x_autopilot.domain import DraftStatus, EvidenceError, InvalidTransitionError, RawResearchItem, StaleRevisionError, VerificationStatus
from x_autopilot.normalize import canonicalize_url, fingerprint
from x_autopilot.ports import ModelResponse
from x_autopilot.storage import SQLiteRepository


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository(Path(self.temporary.name) / "db.sqlite3")
        self.repo.initialize()
        raw = RawResearchItem("test", "1", "Hello", "https://EXAMPLE.com/a/?utm_source=x", "Evidence text")
        url = canonicalize_url(raw.url)
        self.item_id, _ = self.repo.add_research(raw, url, fingerprint(raw, url))
        self.evidence_id = self.repo.add_evidence(self.item_id, url, raw.excerpt)

    def tearDown(self):
        self.temporary.cleanup()

    def create_draft(self, text: str = "Taslak", verification: str = "supported") -> int:
        return self.repo.create_draft(text=text, category="tools", confidence=.8, factual_risk="low", verification_status=verification, research_item_id=self.item_id, provider="fake", model="m", prompt_version="v1", claims=[])

    def test_deduplication_and_evidence_preservation(self):
        raw = RawResearchItem("other", "2", "Hello", "https://example.com/a", "Evidence text")
        url = canonicalize_url(raw.url)
        item_id, created = self.repo.add_research(raw, url, fingerprint(raw, url))
        self.assertFalse(created)
        self.assertEqual(item_id, self.item_id)
        self.assertEqual(self.repo.get_evidence(self.evidence_id).excerpt, "Evidence text")

    def test_every_editorial_mutation_increments_revision_and_clears_approval(self):
        draft_id = self.create_draft()
        approved = self.repo.set_draft_status(draft_id, "approved", 1)
        self.assertEqual((approved.status, approved.revision), (DraftStatus.APPROVED, 2))
        scheduled = self.repo.schedule_draft(draft_id, "2030-01-01T15:00:00+03:00", approved.revision)
        self.assertEqual((scheduled.status, scheduled.revision, scheduled.scheduled_at), (DraftStatus.SCHEDULED, 3, "2030-01-01T12:00:00+00:00"))
        edited = self.repo.edit_draft(draft_id, "Yeni olgusal metin", scheduled.revision)
        self.assertEqual((edited.verification_status, edited.status, edited.revision), (VerificationStatus.UNVERIFIED, DraftStatus.PENDING, 4))
        self.assertIsNone(edited.approved_at)
        self.assertIsNone(edited.scheduled_at)
        verified = self.repo.replace_claims_and_verification(draft_id, [], "supported", edited.revision)
        self.assertEqual((verified.status, verified.revision), (DraftStatus.PENDING, 5))
        with self.assertRaises(StaleRevisionError):
            self.repo.set_draft_status(draft_id, "approved", edited.revision)

    def test_generic_status_setter_cannot_bypass_approval_or_publish_transitions(self):
        draft_id = self.create_draft()
        with self.assertRaises(InvalidTransitionError):
            self.repo.set_draft_status(draft_id, "scheduled", 1)
        with self.assertRaises(InvalidTransitionError):
            self.repo.schedule_draft(draft_id, "2030-01-01T00:00:00+00:00", 1)
        unsupported_id = self.create_draft("Unsupported", "unsupported")
        with self.assertRaises(EvidenceError):
            self.repo.set_draft_status(unsupported_id, "approved", 1)
        with self.assertRaises(ValueError):
            self.repo.schedule_draft(draft_id, "2030-01-01T00:00:00", 1)

    def test_revision_guard_is_atomic_under_concurrent_approval(self):
        draft_id = self.create_draft()
        barrier = threading.Barrier(2)
        results: list[str] = []

        def approve():
            barrier.wait()
            try:
                self.repo.set_draft_status(draft_id, "approved", 1)
                results.append("approved")
            except StaleRevisionError:
                results.append("stale")

        threads = [threading.Thread(target=approve) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
        self.assertEqual(sorted(results), ["approved", "stale"])
        self.assertEqual(self.repo.get_draft(draft_id).revision, 2)

    def test_job_slot_claim_is_durable_and_unique(self):
        self.assertTrue(self.repo.claim_job_slot("publish", "2030-01-01T12:00Z"))
        self.assertFalse(self.repo.claim_job_slot("publish", "2030-01-01T12:00Z"))
        self.repo.finish_job_slot("publish", "2030-01-01T12:00Z", "completed")

    def test_model_call_cost_accounting_round_trips(self):
        run_id = self.repo.create_run("cost")
        response = ModelResponse({}, "fake", "m", input_tokens=10, output_tokens=2, cached_input_tokens=7, cache_write_tokens=3, estimated_cost_usd=.0012, cost_provenance="pricing-v1")
        self.repo.record_model_call(run_id, "sol", response, "v1")
        row = self.repo.list_model_calls(run_id)[0]
        self.assertEqual((row["cached_input_tokens"], row["cache_write_tokens"], row["estimated_cost_usd"], row["cost_provenance"]), (7, 3, .0012, "pricing-v1"))
        self.assertTrue(self.repo.healthcheck())

    def test_version_three_database_is_migrated_without_data_loss(self):
        old_path = Path(self.temporary.name) / "old.sqlite3"
        connection = sqlite3.connect(old_path)
        try:
            for migration in sorted((Path(__file__).parents[1] / "x_autopilot/migrations").glob("00[1-3]_*.sql")):
                connection.executescript(migration.read_text(encoding="utf-8"))
            connection.execute("INSERT INTO research_items(source,external_id,title,canonical_url,excerpt,fingerprint,discovered_at) VALUES(?,?,?,?,?,?,?)", ("old", "1", "Old", "https://example.com", "e", "fp", "2029-01-01T00:00:00+00:00"))
            connection.commit()
        finally:
            connection.close()
        repository = SQLiteRepository(old_path)
        repository.initialize()
        connection = sqlite3.connect(old_path)
        try:
            version = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
            draft_columns = {row[1] for row in connection.execute("PRAGMA table_info(drafts)")}
            model_columns = {row[1] for row in connection.execute("PRAGMA table_info(model_calls)")}
            title = connection.execute("SELECT title FROM research_items").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(version, 4)
        self.assertIn("publish_attempted_at", draft_columns)
        self.assertIn("cost_provenance", model_columns)
        self.assertEqual(title, "Old")


if __name__ == "__main__":
    unittest.main()
