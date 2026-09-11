from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import requests

from x_autopilot.domain import ConfigurationError, DraftStatus, InvalidTransitionError, PublishAmbiguousError, PublishError, RawResearchItem
from x_autopilot.normalize import canonicalize_url, fingerprint
from x_autopilot.publishing import PublishResult, PublishService, XPublisher
from x_autopilot.storage import SQLiteRepository


class FakePublisher:
    def __init__(self, result: PublishResult | BaseException = PublishResult("12345")) -> None:
        self.result = result
        self.validations = 0
        self.calls: list[str] = []

    def validate_credentials(self) -> None:
        self.validations += 1

    def publish(self, text: str) -> PublishResult:
        self.calls.append(text)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class FakeResponse:
    def __init__(self, status_code: int, payload=None) -> None:
        self.status_code = status_code
        self.payload = payload

    def json(self):
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


class FakeSession:
    def __init__(self, response: FakeResponse | BaseException) -> None:
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository(Path(self.temporary.name) / "db.sqlite3")
        self.repo.initialize()
        raw = RawResearchItem("test", "1", "Hello", "https://example.com/a", "Evidence")
        url = canonicalize_url(raw.url)
        self.item_id, _ = self.repo.add_research(raw, url, fingerprint(raw, url))

    def tearDown(self):
        self.temporary.cleanup()

    def approved(self, text: str = "Taslak"):
        draft_id = self.repo.create_draft(text=text, category="tools", confidence=.8, factual_risk="low", verification_status="supported", research_item_id=self.item_id, provider="fake", model="m", prompt_version="v1", claims=[])
        return self.repo.set_draft_status(draft_id, "approved", 1)

    def test_success_claims_before_one_post_and_persists_id(self):
        approved = self.approved()
        publisher = FakePublisher()
        published = PublishService(self.repo, publisher, enabled=True).publish_now(approved.id, approved.revision)
        self.assertEqual((published.status, published.revision, published.x_post_id), (DraftStatus.PUBLISHED, 4, "12345"))
        self.assertIsNotNone(published.publish_attempted_at)
        self.assertIsNotNone(published.published_at)
        self.assertEqual(publisher.calls, ["Taslak"])
        with self.assertRaises(InvalidTransitionError):
            self.repo.edit_draft(published.id, "changed", published.revision)

    def test_disabled_and_missing_credentials_fail_before_claim(self):
        approved = self.approved()
        fake = FakePublisher()
        with self.assertRaises(ConfigurationError):
            PublishService(self.repo, fake).publish_now(approved.id, approved.revision)
        self.assertEqual(fake.validations, 0)
        session = FakeSession(FakeResponse(201, {"data": {"id": "999"}}))
        with self.assertRaises(ConfigurationError):
            PublishService(self.repo, XPublisher(environ={}, session=session), enabled=True).publish_now(approved.id, approved.revision)
        current = self.repo.get_draft(approved.id)
        self.assertEqual(current.status, DraftStatus.APPROVED)
        self.assertIsNone(current.publish_attempted_at)
        self.assertEqual(session.calls, [])

    def test_scheduled_publish_only_runs_when_due(self):
        approved = self.approved()
        scheduled = self.repo.schedule_draft(approved.id, "2030-01-01T12:00:00+00:00", approved.revision)
        publisher = FakePublisher()
        service = PublishService(self.repo, publisher, enabled=True)
        with self.assertRaises(InvalidTransitionError):
            service.publish_now(scheduled.id, scheduled.revision)
        self.assertEqual(self.repo.get_draft(scheduled.id).status, DraftStatus.SCHEDULED)
        self.assertEqual(service.publish_due("2030-01-01T11:59:59+00:00"), [])
        results = service.publish_due("2030-01-01T12:00:00+00:00")
        self.assertEqual([item.status for item in results], [DraftStatus.PUBLISHED])
        self.assertEqual(publisher.calls, ["Taslak"])
        self.assertEqual(scheduled.revision, 3)

    def test_ambiguous_timeout_is_never_retried(self):
        approved = self.approved()
        publisher = FakePublisher(PublishAmbiguousError("secret details"))
        result = PublishService(self.repo, publisher, enabled=True).publish_now(approved.id, approved.revision)
        self.assertEqual(result.status, DraftStatus.PUBLISH_UNKNOWN)
        self.assertNotIn("secret", result.publish_error)
        self.assertEqual(len(publisher.calls), 1)
        with self.assertRaises(InvalidTransitionError):
            PublishService(self.repo, publisher, enabled=True).publish_now(result.id, result.revision)
        self.assertEqual(len(publisher.calls), 1)

    def test_process_crash_window_stays_publishing(self):
        approved = self.approved()
        publisher = FakePublisher(SystemExit("crash"))
        with self.assertRaises(SystemExit):
            PublishService(self.repo, publisher, enabled=True).publish_now(approved.id, approved.revision)
        current = self.repo.get_draft(approved.id)
        self.assertEqual(current.status, DraftStatus.PUBLISHING)
        self.assertIsNotNone(current.publish_attempted_at)
        with self.assertRaises(InvalidTransitionError):
            PublishService(self.repo, FakePublisher(), enabled=True).publish_now(current.id, current.revision)

    def test_duplicate_text_across_drafts_is_claimed_once(self):
        first = self.approved("same text")
        second = self.approved("same text")
        publisher = FakePublisher()
        service = PublishService(self.repo, publisher, enabled=True)
        self.assertEqual(service.publish_now(first.id, first.revision).status, DraftStatus.PUBLISHED)
        duplicate = service.publish_now(second.id, second.revision)
        self.assertEqual(duplicate.status, DraftStatus.PUBLISH_FAILED)
        self.assertIn("Duplicate", duplicate.publish_error)
        self.assertEqual(publisher.calls, ["same text"])

    def test_official_x_request_uses_oauth1_no_redirect_and_no_retry(self):
        credentials = {"X_API_KEY": "key", "X_API_SECRET": "secret", "X_ACCESS_TOKEN": "token", "X_ACCESS_TOKEN_SECRET": "token-secret"}
        session = FakeSession(FakeResponse(201, {"data": {"id": "987654321"}}))
        result = XPublisher(environ=credentials, session=session, timeout_seconds=7).publish("hello")
        self.assertEqual(result.post_id, "987654321")
        self.assertEqual(len(session.calls), 1)
        url, kwargs = session.calls[0]
        self.assertEqual(url, "https://api.x.com/2/tweets")
        self.assertEqual(kwargs["json"], {"text": "hello"})
        self.assertEqual(kwargs["timeout"], 7)
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["auth"].client.client_key, "key")

    def test_x_5xx_and_invalid_success_are_ambiguous(self):
        credentials = {"X_API_KEY": "key", "X_API_SECRET": "secret", "X_ACCESS_TOKEN": "token", "X_ACCESS_TOKEN_SECRET": "token-secret"}
        for response in (FakeResponse(503, {"credential": "secret"}), FakeResponse(201, {"data": {"id": "not-digits"}})):
            with self.assertRaises(PublishAmbiguousError):
                XPublisher(environ=credentials, session=FakeSession(response)).publish("hello")
        with self.assertRaises(PublishAmbiguousError):
            XPublisher(environ=credentials, session=FakeSession(requests.Timeout("secret"))).publish("hello")
        with self.assertRaises(PublishError):
            XPublisher(environ=credentials, session=FakeSession(FakeResponse(403, {"secret": "leak"}))).publish("hello")


if __name__ == "__main__":
    unittest.main()
