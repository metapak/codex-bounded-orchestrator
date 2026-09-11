from __future__ import annotations

import os
import threading
import unittest
import uuid
from urllib.parse import urlencode

try:
    import psycopg
    from psycopg import sql
except ImportError:  # pragma: no cover - optional adapter dependency
    psycopg = None
    sql = None

from x_autopilot.domain import DraftStatus, RawResearchItem


class PostgresRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_url = os.environ.get("XAP_TEST_DATABASE_URL")
        if not cls.base_url or psycopg is None:
            raise unittest.SkipTest("XAP_TEST_DATABASE_URL and psycopg are required for live PostgreSQL tests.")
        cls.schema = f"xap_{uuid.uuid4().hex}"
        with psycopg.connect(cls.base_url, autocommit=True) as db:
            db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema)))
        separator = "&" if "?" in cls.base_url else "?"
        cls.schema_url = cls.base_url + separator + urlencode({"options": f"-csearch_path={cls.schema}"})
        from x_autopilot.postgres import PostgresRepository
        cls.repo = PostgresRepository(cls.schema_url)
        errors = []

        def initialize():
            try:
                cls.repo.initialize()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=initialize) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        if errors:
            raise errors[0]

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "base_url", None) and psycopg is not None and getattr(cls, "schema", None):
            with psycopg.connect(cls.base_url, autocommit=True) as db:
                db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(cls.schema)))

    def approved(self, text: str):
        suffix = uuid.uuid4().hex
        raw = RawResearchItem("pg", suffix, "Title", f"https://example.com/{suffix}", "Evidence")
        item_id, _ = self.repo.add_research(raw, raw.url, suffix)
        draft_id = self.repo.create_draft(text=text, category="tools", confidence=.8, factual_risk="low", verification_status="supported", research_item_id=item_id, provider="fake", model="m", prompt_version="v1", claims=[])
        return self.repo.set_draft_status(draft_id, "approved", 1)

    def test_schema_and_editorial_publish_round_trip(self):
        self.assertTrue(self.repo.healthcheck())
        with self.repo._db() as db:
            self.assertEqual(db.execute("SELECT MAX(version) AS version FROM schema_version").fetchone()["version"], 4)
        approved = self.approved("postgres round trip")
        scheduled = self.repo.schedule_draft(approved.id, "2030-01-01T15:00:00+03:00", approved.revision)
        self.assertEqual((scheduled.status, scheduled.scheduled_at, scheduled.revision), (DraftStatus.SCHEDULED, "2030-01-01T12:00:00+00:00", 3))
        claimed = self.repo.claim_publish(scheduled.id, scheduled.revision, scheduled_only=True, now="2030-01-01T12:00:00+00:00")
        self.assertEqual(claimed.status, DraftStatus.PUBLISHING)
        published = self.repo.finish_publish(claimed.id, post_id="123")
        self.assertEqual((published.status, published.x_post_id, published.revision), (DraftStatus.PUBLISHED, "123", 5))

    def test_concurrent_duplicate_content_and_job_slot_claims(self):
        content = "same pg content " + uuid.uuid4().hex
        drafts = [self.approved(content), self.approved(content)]
        barrier = threading.Barrier(2)
        claims = []

        def claim(draft):
            barrier.wait()
            claims.append(self.repo.claim_publish(draft.id, draft.revision))

        threads = [threading.Thread(target=claim, args=(draft,)) for draft in drafts]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        self.assertEqual(sum(claim is not None for claim in claims), 1)
        statuses = {self.repo.get_draft(draft.id).status for draft in drafts}
        self.assertEqual(statuses, {DraftStatus.PUBLISHING, DraftStatus.PUBLISH_FAILED})

        slot = uuid.uuid4().hex
        barrier = threading.Barrier(2)
        results = []

        def claim_slot():
            barrier.wait()
            results.append(self.repo.claim_job_slot("publish", slot))

        threads = [threading.Thread(target=claim_slot) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        self.assertEqual(sorted(results), [False, True])


if __name__ == "__main__":
    unittest.main()
