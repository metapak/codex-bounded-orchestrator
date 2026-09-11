"""Durable periodic work; a claimed generation slot is never replayed after a crash."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, time as wall_time, timezone
from zoneinfo import ZoneInfo

from .config import AppConfig
from .ports import Repository

LOG = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, config: AppConfig, repository: Repository, pipeline, publisher):
        self.config = config
        self.repository = repository
        self.pipeline = pipeline
        self.publisher = publisher
        self.last_tick: float | None = None
        self.last_error: str | None = None
        self._last_publish_slot: int | None = None
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def _run_slot(self, name: str, slot: str, callback, output: dict) -> None:
        if not self.repository.claim_job_slot(name, slot):
            return
        try:
            result = callback()
            # Pipeline failures are structured values, not necessarily exceptions.
            failed = isinstance(result, dict) and bool(result.get("failures"))
            self.repository.finish_job_slot(name, slot, "failed" if failed else "completed")
            output[name] = result
            if failed:
                self.last_error = f"{name} failed; inspect the recorded run."
        except Exception:
            self.last_error = f"{name} failed; the claimed slot will not be retried."
            self.repository.finish_job_slot(name, slot, "failed")
            # Exception details may contain connection credentials. Never interpolate them.
            LOG.error("Scheduled %s failed; manual inspection required.", name)
            output[name] = {"error": "scheduled_job_failed"}

    def tick(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Scheduler time must include a UTC offset.")
        self.last_tick = time.monotonic()
        if not self.config.scheduler_enabled:
            return {"enabled": False}
        output: dict = {"enabled": True}
        utc = now.astimezone(timezone.utc)
        epoch = int(utc.timestamp())
        # Publication does not wait behind a fresh research/model run.
        publish_slot = epoch // self.config.publish_interval_seconds
        if self.config.publish_enabled and publish_slot != self._last_publish_slot:
            self._last_publish_slot = publish_slot
            try:
                output["published"] = len(self.publisher.publish_due(now=utc.isoformat()))
            except Exception:
                self.last_error = "Publishing failed; inspect the review panel."
                LOG.error("Scheduled publishing failed; inspect the review panel.")
                output["publish_error"] = "publish_failed"
        self._run_slot("research", str(epoch // self.config.research_interval_seconds), self.pipeline.research, output)
        local = utc.astimezone(ZoneInfo(self.config.timezone))
        due_time = wall_time.fromisoformat(self.config.generation_time)
        if local.time() >= due_time and local.date().toordinal() % self.config.generation_every_days == 0:
            self._run_slot("generate", local.date().isoformat(), self.pipeline.generate, output)
        self.last_tick = time.monotonic()
        return output

    def run_forever(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.tick()
            except Exception:
                self.last_error = "Scheduler storage unavailable."
                LOG.error("Scheduler tick failed; retrying on the next tick.")
            self.stop_event.wait(self.config.scheduler_tick_seconds)

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self.run_forever, name="x-autopilot-scheduler", daemon=True)
        self.thread.start()

    def healthy(self) -> bool:
        # Source timeouts plus two bounded model calls can consume several minutes.
        budget = max(600, self.config.scheduler_tick_seconds * 3)
        return bool(self.thread and self.thread.is_alive() and self.last_tick is not None and time.monotonic() - self.last_tick < budget)

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
