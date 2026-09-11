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
        self._research_thread: threading.Thread | None = None
        self._publish_thread: threading.Thread | None = None
        self._research_heartbeat: float | None = None
        self._publish_heartbeat: float | None = None
        self._state_lock = threading.Lock()

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

    @staticmethod
    def _validated_time(now: datetime | None = None) -> datetime:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Scheduler time must include a UTC offset.")
        return now.astimezone(timezone.utc)

    def _tick_publish(self, utc: datetime, output: dict) -> None:
        epoch = int(utc.timestamp())
        publish_slot = epoch // self.config.publish_interval_seconds
        with self._state_lock:
            already_checked = publish_slot == self._last_publish_slot
            if not already_checked:
                self._last_publish_slot = publish_slot
        if self.config.publish_enabled and not already_checked:
            try:
                output["published"] = len(self.publisher.publish_due(now=utc.isoformat()))
            except Exception:
                self.last_error = "Publishing failed; inspect the review panel."
                LOG.error("Scheduled publishing failed; inspect the review panel.")
                output["publish_error"] = "publish_failed"

    def _tick_pipeline(self, utc: datetime, output: dict) -> None:
        epoch = int(utc.timestamp())
        self._run_slot("research", str(epoch // self.config.research_interval_seconds), self.pipeline.research, output)
        local = utc.astimezone(ZoneInfo(self.config.timezone))
        due_time = wall_time.fromisoformat(self.config.generation_time)
        if local.time() >= due_time and local.date().toordinal() % self.config.generation_every_days == 0:
            self._run_slot("generate", local.date().isoformat(), self.pipeline.generate, output)

    def tick(self, now: datetime | None = None) -> dict:
        utc = self._validated_time(now)
        self.last_tick = time.monotonic()
        if not self.config.scheduler_enabled:
            return {"enabled": False}
        output: dict = {"enabled": True}
        # The one-shot scheduler-tick command remains intentionally synchronous.
        self._tick_publish(utc, output)
        self._tick_pipeline(utc, output)
        self.last_tick = time.monotonic()
        return output

    def _research_loop(self) -> None:
        while not self.stop_event.is_set():
            self._research_heartbeat = time.monotonic()
            self.last_tick = self._research_heartbeat
            try:
                if self.config.scheduler_enabled:
                    self._tick_pipeline(self._validated_time(), {})
            except Exception:
                self.last_error = "Scheduler storage unavailable."
                LOG.error("Scheduled research tick failed; retrying on the next tick.")
            self._research_heartbeat = time.monotonic()
            self.last_tick = self._research_heartbeat
            self.stop_event.wait(self.config.scheduler_tick_seconds)

    def _publish_loop(self) -> None:
        while not self.stop_event.is_set():
            self._publish_heartbeat = time.monotonic()
            self.last_tick = self._publish_heartbeat
            try:
                if self.config.scheduler_enabled:
                    self._tick_publish(self._validated_time(), {})
            except Exception:
                self.last_error = "Publishing scheduler storage unavailable."
                LOG.error("Scheduled publishing tick failed; retrying on the next tick.")
            self._publish_heartbeat = time.monotonic()
            self.last_tick = self._publish_heartbeat
            self.stop_event.wait(self.config.scheduler_tick_seconds)

    @staticmethod
    def _join(thread: threading.Thread | None, deadline: float) -> None:
        if thread and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, deadline - time.monotonic()))

    def run_forever(self) -> None:
        self._research_thread = threading.Thread(target=self._research_loop, name="x-autopilot-research-scheduler", daemon=True)
        self._publish_thread = threading.Thread(target=self._publish_loop, name="x-autopilot-publish-scheduler", daemon=True)
        self._research_thread.start()
        self._publish_thread.start()
        try:
            while not self.stop_event.wait(0.25):
                pass
        finally:
            deadline = time.monotonic() + 5
            self._join(self._publish_thread, deadline)
            self._join(self._research_thread, deadline)

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run_forever, name="x-autopilot-scheduler", daemon=True)
        self.thread.start()

    def healthy(self) -> bool:
        # Research/model work may be slow; publication has its own tighter liveness budget.
        now = time.monotonic()
        research_budget = max(600, self.config.scheduler_tick_seconds * 3)
        publish_budget = max(5, self.config.scheduler_tick_seconds * 3)
        return bool(
            self.thread
            and self.thread.is_alive()
            and self._research_thread
            and self._research_thread.is_alive()
            and self._publish_thread
            and self._publish_thread.is_alive()
            and self._research_heartbeat is not None
            and now - self._research_heartbeat < research_budget
            and self._publish_heartbeat is not None
            and now - self._publish_heartbeat < publish_budget
        )

    def stop(self) -> None:
        self.stop_event.set()
        deadline = time.monotonic() + 5
        self._join(self.thread, deadline)
        self._join(self._publish_thread, deadline)
        self._join(self._research_thread, deadline)
