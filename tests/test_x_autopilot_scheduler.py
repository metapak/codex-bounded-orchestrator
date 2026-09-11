from __future__ import annotations

import tempfile
import threading
import time
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from x_autopilot.config import load_config
from x_autopilot.domain import RawResearchItem
from x_autopilot.publishing import PublishResult, PublishService
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

    def test_blocking_research_does_not_stall_concurrent_publication_workers(self):
        research_entered = threading.Event()
        release_research = threading.Event()
        post_sent = threading.Event()
        publish_calls: list[str] = []

        def blocking_research():
            research_entered.set()
            release_research.wait(2)
            return {"added": 1, "failures": []}

        class RecordingPublisher:
            def validate_credentials(self):
                return None

            def publish(self, text):
                publish_calls.append(text)
                post_sent.set()
                return PublishResult("123456")

        self.pipeline.research.side_effect = blocking_research
        raw = RawResearchItem("scheduler", "1", "Title", "https://example.com/scheduler", "Evidence")
        item_id, _ = self.repo.add_research(raw, raw.url, "scheduler-fingerprint")
        draft_id = self.repo.create_draft(text="due draft", category="tools", confidence=.8, factual_risk="low", verification_status="supported", research_item_id=item_id, provider="fake", model="m", prompt_version="v1", claims=[])
        approved = self.repo.set_draft_status(draft_id, "approved", 1)
        self.repo.schedule_draft(draft_id, "2020-01-01T00:00:00+00:00", approved.revision)
        service = PublishService(self.repo, RecordingPublisher(), enabled=True)
        config = replace(self.config, scheduler_tick_seconds=.01, publish_interval_seconds=.02, publish_enabled=True)
        schedulers = [Scheduler(config, self.repo, self.pipeline, service) for _ in range(2)]
        try:
            for scheduler in schedulers:
                scheduler.start()
            self.assertTrue(research_entered.wait(1), "research worker did not enter the blocking fixture")
            self.assertTrue(post_sent.wait(1), "publication was stalled behind research")
            time.sleep(.08)
            self.assertEqual(publish_calls, ["due draft"])
            self.assertTrue(all(scheduler.healthy() for scheduler in schedulers))
        finally:
            release_research.set()
            for scheduler in schedulers:
                scheduler.stop()
        for scheduler in schedulers:
            self.assertFalse(scheduler.thread and scheduler.thread.is_alive())
            self.assertFalse(scheduler._research_thread and scheduler._research_thread.is_alive())
            self.assertFalse(scheduler._publish_thread and scheduler._publish_thread.is_alive())

    def test_health_fails_when_publication_worker_dies(self):
        scheduler = self.scheduler(publish_enabled=True, scheduler_tick_seconds=.01, publish_interval_seconds=.02)
        self.publisher.publish_due.side_effect = SystemExit("fixture worker exit")
        previous_hook = threading.excepthook
        threading.excepthook = lambda _args: None
        try:
            scheduler.start()
            deadline = time.monotonic() + 1
            while scheduler._publish_thread is None or scheduler._publish_thread.is_alive():
                if time.monotonic() >= deadline:
                    self.fail("publication worker did not exit")
                time.sleep(.01)
            self.assertFalse(scheduler.healthy())
        finally:
            scheduler.stop()
            threading.excepthook = previous_hook


if __name__ == "__main__":
    unittest.main()
