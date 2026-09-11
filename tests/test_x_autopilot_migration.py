import hashlib
import os
import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from x_autopilot.domain import RawResearchItem
from x_autopilot.migration import import_sqlite_to_postgres
from x_autopilot.storage import SQLiteRepository


@unittest.skipUnless(os.environ.get("XAP_TEST_DATABASE_URL"), "Isolated PostgreSQL test URL not configured")
class MigrationTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        from psycopg import sql
        self.base_url = os.environ["XAP_TEST_DATABASE_URL"]
        self.schema = "xap_import_" + uuid.uuid4().hex
        with psycopg.connect(self.base_url) as connection:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        parts = urlsplit(self.base_url)
        query = dict(parse_qsl(parts.query))
        query["options"] = "-csearch_path=" + self.schema
        self.url = urlunsplit(parts._replace(query=urlencode(query)))
        self.temp = tempfile.TemporaryDirectory()
        self.source = Path(self.temp.name) / "source.sqlite3"
        # Genuine Phase 1 version 3 source, not an already migrated fixture.
        with closing(sqlite3.connect(self.source)) as connection, connection:
            migrations = Path(__file__).resolve().parents[1] / "x_autopilot/migrations"
            for version in ("001", "002", "003"):
                connection.executescript(next(migrations.glob(version + "_*.sql")).read_text())
            connection.execute("INSERT INTO research_items(id,source,external_id,title,canonical_url,excerpt,fingerprint,discovered_at) VALUES(7,'fixture','1','Source','https://example.com','Evidence','unique','2026-09-11T00:00:00+00:00')")

    def tearDown(self):
        import psycopg
        from psycopg import sql
        with psycopg.connect(self.base_url) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))
        self.temp.cleanup()

    def test_import_preserves_ids_source_bytes_and_repairs_sequences(self):
        from x_autopilot.postgres import PostgresRepository
        before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        counts = import_sqlite_to_postgres(self.source, self.url)
        repo = PostgresRepository(self.url)
        self.assertEqual(counts["research_items"], 1)
        self.assertEqual(repo.get_research(7).title, "Source")
        raw = RawResearchItem("fixture", "2", "Next", "https://example.com/2", "Next evidence")
        new_id, created = repo.add_research(raw, raw.url, "unique2")
        self.assertTrue(created)
        self.assertGreater(new_id, 7)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), before)

    def test_nonempty_target_is_rejected_without_overwrite(self):
        from x_autopilot.postgres import PostgresRepository
        import_sqlite_to_postgres(self.source, self.url)
        with self.assertRaises(ValueError):
            import_sqlite_to_postgres(self.source, self.url)
        self.assertEqual(len(PostgresRepository(self.url).list_research()), 1)

    def test_import_failure_rolls_back_all_copied_rows(self):
        from x_autopilot.postgres import PostgresRepository
        with closing(sqlite3.connect(self.source)) as connection, connection:
            connection.execute("INSERT INTO evidence_records(id,research_item_id,source_url,excerpt,content_hash,captured_at,evidence_type) VALUES(1,999,'https://example.com','Broken','hash','now','source_excerpt')")
        with self.assertRaises(Exception):
            import_sqlite_to_postgres(self.source, self.url)
        self.assertEqual(PostgresRepository(self.url).list_research(), [])


if __name__ == "__main__":
    unittest.main()
