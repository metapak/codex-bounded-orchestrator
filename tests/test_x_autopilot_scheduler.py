from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from x_autopilot.config import load_config
from x_autopilot.scheduler import Scheduler
from x_autopilot.storage import SQLiteRepository

ROOT = Path(__file__).resolve().parents[1]


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository(Path(self.temp.name) / "db.sqlite3")
        self.repo.initialize()
        self.config = load_config(ROOT / "config/x-autopilot.example.toml")
        self.pipeline = Mock()
        self.pipeline.research.return_value = {"added": 4, "failures": []}
        self.pipeline.generate.return_value = {"drafted": 4, "failures": []}
        self.publisher = Mock()
        self.publisher.publish_due.return_value = []

    def tearDown(self):
        self.temp.cleanup()

    def scheduler(self, **changes):
        return Scheduler(replace(self.config, **changes), self.repo, self.pipeline, self.publisher)

    def test_daily_batch_is_claimed_once_across_restarts_and_workers(self):
        now = datetime(2026, 9, 11, 6, 1, tzinfo=timezone.utc)
        self.scheduler().tick(now)
        self.scheduler().tick(now)
        self.pipeline.generate.assert_called_once_with()
        self.pipeline.research.assert_called_once_with()
        self.publisher.publish_due.assert_not_called()

    def test_no_generation_before_local_time_and_next_day_gets_one_batch(self):
        scheduler = self.scheduler()
        scheduler.tick(datetime(2026, 9, 11, 5, 59, tzinfo=timezone.utc))
        self.pipeline.generate.assert_not_called()
        scheduler.tick(datetime(2026, 9, 11, 6, 0, tzinfo=timezone.utc))
        scheduler.tick(datetime(2026, 9, 12, 6, 0, tzinfo=timezone.utc))
        self.assertEqual(self.pipeline.generate.call_count, 2)

    def test_failed_batch_is_not_replayed_after_restart(self):
        now = datetime(2026, 9, 11, 6, 0, tzinfo=timezone.utc)
        self.pipeline.generate.side_effect = RuntimeError("secret-must-not-escape")
        output = self.scheduler().tick(now)
        self.scheduler().tick(now)
        self.pipeline.generate.assert_called_once_with()
        self.assertNotIn("secret-must-not-escape", str(output))

    def test_enabled_publishing_only_calls_due_service_at_interval(self):
        scheduler = self.scheduler(publish_enabled=True)
        now = datetime(2026, 9, 11, 6, 0, tzinfo=timezone.utc)
        scheduler.tick(now)
        scheduler.tick(now)
        self.publisher.publish_due.assert_called_once_with(now=now.isoformat())

    def test_disabled_scheduler_does_nothing_and_naive_time_rejected(self):
        scheduler = self.scheduler(scheduler_enabled=False)
        self.assertEqual(scheduler.tick(), {"enabled": False})
        self.pipeline.research.assert_not_called()
        with self.assertRaises(ValueError):
            scheduler.tick(datetime(2026, 9, 11))


if __name__ == "__main__":
    unittest.main()
