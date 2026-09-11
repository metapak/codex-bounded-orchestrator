"""Review use cases shared by HTTP and other interfaces."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .domain import Draft, InvalidTransitionError, StaleRevisionError
from .ports import Repository


class ReviewService:
    _ATTEMPTED_STATES = {"publishing", "published", "publish_failed", "publish_unknown"}

    def __init__(self, repository: Repository, publisher: object | None = None) -> None:
        self.repository = repository
        self.publisher = publisher

    def _draft_for_change(self, draft_id: int, revision: int) -> Draft:
        draft = self.repository.get_draft(draft_id)
        if draft is None:
            raise KeyError(draft_id)
        if draft.revision != revision:
            raise StaleRevisionError("Draft başka bir istek tarafından değiştirildi.")
        status = getattr(draft.status, "value", str(draft.status))
        if status in self._ATTEMPTED_STATES or getattr(draft, "publish_attempted_at", None):
            raise InvalidTransitionError("Yayın denemesi başlamış draft artık değiştirilemez.")
        return draft

    def edit(self, draft_id: int, text: str, revision: int) -> Draft:
        self._draft_for_change(draft_id, revision)
        return self.repository.edit_draft(draft_id, text, revision)

    def approve(self, draft_id: int, revision: int) -> Draft:
        self._draft_for_change(draft_id, revision)
        return self.repository.set_draft_status(draft_id, "approved", revision)

    def reject(self, draft_id: int, revision: int, reason: str | None = None) -> Draft:
        self._draft_for_change(draft_id, revision)
        return self.repository.set_draft_status(draft_id, "rejected", revision, reason)

    def schedule(self, draft_id: int, local_value: str, revision: int, timezone_name: str) -> Draft:
        draft = self._draft_for_change(draft_id, revision)
        if getattr(draft.status, "value", str(draft.status)) != "approved":
            raise InvalidTransitionError("Yalnızca onaylı draft zamanlanabilir.")
        scheduled_at = local_datetime_to_iso(local_value, timezone_name)
        schedule_draft = getattr(self.repository, "schedule_draft", None)
        if not callable(schedule_draft):
            raise InvalidTransitionError("Repository zamanlama işlemini desteklemiyor.")
        return schedule_draft(draft_id, scheduled_at=scheduled_at, expected_revision=revision)

    def publish_now(self, draft_id: int, revision: int) -> Any:
        draft = self._draft_for_change(draft_id, revision)
        if getattr(draft.status, "value", str(draft.status)) != "approved":
            raise InvalidTransitionError("Yalnızca onaylı draft hemen yayınlanabilir.")
        if self.publisher is None:
            raise InvalidTransitionError("Yayın servisi yapılandırılmamış.")
        publish_now = getattr(self.publisher, "publish_now", None)
        if not callable(publish_now):
            raise InvalidTransitionError("Yayın servisi publish_now işlemini desteklemiyor.")
        return publish_now(draft_id, revision)


def local_datetime_to_iso(value: str, timezone_name: str) -> str:
    """Interpret a datetime-local value in an IANA zone and reject DST gaps/folds."""
    try:
        naive = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Zamanlama tarihi geçersiz.") from exc
    if naive.tzinfo is not None:
        raise ValueError("Zamanlama tarihi yerel tarih ve saat olmalıdır.")
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Yapılandırılmış saat dilimi geçersiz.") from exc

    candidates: list[datetime] = []
    for fold in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=fold)
        round_trip = aware.astimezone(timezone.utc).astimezone(zone)
        if round_trip.replace(tzinfo=None) == naive and round_trip.fold == fold:
            candidates.append(aware)
    offsets = {candidate.utcoffset() for candidate in candidates}
    if not candidates:
        raise ValueError("Bu yerel saat, yaz/kış saati geçişinde mevcut değil.")
    if len(offsets) > 1:
        raise ValueError("Bu yerel saat, yaz/kış saati geçişinde belirsiz.")
    return candidates[0].replace(microsecond=0).isoformat()
