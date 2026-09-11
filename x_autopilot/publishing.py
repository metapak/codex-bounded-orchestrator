"""Human-approved, at-most-once publishing through X's official API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

import requests
from requests_oauthlib import OAuth1

from .domain import ConfigurationError, Draft, InvalidTransitionError, PublishAmbiguousError, PublishError, StaleRevisionError, utc_now
from .ports import Repository

X_CREATE_POST_URL = "https://api.x.com/2/tweets"
_CREDENTIAL_NAMES = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
_KNOWN_FAILURE = "X rejected the publish request."
_UNKNOWN_FAILURE = "X publish request outcome is unknown; reconcile manually before any further action."


@dataclass(frozen=True)
class PublishResult:
    post_id: str


class Publisher(Protocol):
    def validate_credentials(self) -> None: ...

    def publish(self, text: str) -> PublishResult: ...


class XPublisher:
    """OAuth 1.0a client for POST /2/tweets; one request and no retries."""

    def __init__(self, *, environ: Mapping[str, str] | None = None, session: Any | None = None, timeout_seconds: float = 15.0) -> None:
        self._environ = os.environ if environ is None else environ
        self._session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def validate_credentials(self) -> None:
        if any(not self._environ.get(name) for name in _CREDENTIAL_NAMES):
            raise ConfigurationError("X publishing credentials are incomplete.")

    def publish(self, text: str) -> PublishResult:
        self.validate_credentials()
        auth = OAuth1(
            self._environ["X_API_KEY"],
            self._environ["X_API_SECRET"],
            self._environ["X_ACCESS_TOKEN"],
            self._environ["X_ACCESS_TOKEN_SECRET"],
        )
        try:
            response = self._session.post(
                X_CREATE_POST_URL,
                json={"text": text},
                auth=auth,
                timeout=self.timeout_seconds,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise PublishAmbiguousError(_UNKNOWN_FAILURE) from exc
        if response.status_code != 201:
            if 200 <= response.status_code < 300:
                raise PublishAmbiguousError(_UNKNOWN_FAILURE)
            if response.status_code >= 500:
                raise PublishAmbiguousError(_UNKNOWN_FAILURE)
            raise PublishError(_KNOWN_FAILURE)
        try:
            post_id = response.json()["data"]["id"]
        except (KeyError, TypeError, ValueError) as exc:
            raise PublishAmbiguousError(_UNKNOWN_FAILURE) from exc
        if not isinstance(post_id, str) or not post_id.strip().isdigit():
            raise PublishAmbiguousError(_UNKNOWN_FAILURE)
        return PublishResult(post_id=post_id.strip())


class PublishService:
    def __init__(self, repository: Repository, publisher: Publisher, enabled: bool = False) -> None:
        self.repository = repository
        self.publisher = publisher
        self.enabled = enabled

    def _validate(self) -> None:
        if not self.enabled:
            raise ConfigurationError("X publishing is disabled.")
        self.publisher.validate_credentials()

    def _publish_claimed(self, draft: Draft) -> Draft:
        try:
            result = self.publisher.publish(draft.text)
        except PublishAmbiguousError:
            return self.repository.finish_publish(draft.id, error=_UNKNOWN_FAILURE, ambiguous=True)
        except PublishError:
            return self.repository.finish_publish(draft.id, error=_KNOWN_FAILURE)
        except Exception:
            return self.repository.finish_publish(draft.id, error=_UNKNOWN_FAILURE, ambiguous=True)
        return self.repository.finish_publish(draft.id, post_id=result.post_id)

    def publish_now(self, draft_id: int, revision: int) -> Draft:
        self._validate()
        claimed = self.repository.claim_publish(draft_id, revision)
        if claimed is None:
            current = self.repository.get_draft(draft_id)
            if current is not None and current.status.value == "publish_failed":
                return current
            raise InvalidTransitionError("Draft is not eligible for publishing.")
        return self._publish_claimed(claimed)

    def publish_due(self, now: str | None = None) -> list[Draft]:
        self._validate()
        effective_now = now or utc_now()
        results: list[Draft] = []
        for due in self.repository.list_due_drafts(effective_now):
            try:
                claimed = self.repository.claim_publish(due.id, due.revision, scheduled_only=True, now=effective_now)
            except StaleRevisionError:
                continue
            if claimed is not None:
                results.append(self._publish_claimed(claimed))
        return results
