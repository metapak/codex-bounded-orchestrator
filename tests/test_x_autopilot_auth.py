from __future__ import annotations

import base64
import http.client
import os
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from x_autopilot.auth import ReviewAuth, load_review_auth
from x_autopilot.web import create_server


class CountingRepository:
    def __init__(self) -> None:
        self.reads = 0
        self.fail_reads = False

    def list_research(self):
        self.reads += 1
        if self.fail_reads:
            raise RuntimeError("postgresql://user:secret@database.example/internal")
        return []

    def get_draft(self, draft_id):
        raise RuntimeError("postgresql://user:secret@database.example/internal")


class ReviewAuthTests(unittest.TestCase):
    def test_basic_auth_parsing_is_exact(self):
        auth = ReviewAuth("editor", "a-secure-password-long-enough")
        valid = base64.b64encode(b"editor:a-secure-password-long-enough").decode()
        wrong = base64.b64encode(b"editor:a-secure-password-long-enough-extra").decode()
        self.assertTrue(auth.matches(f"Basic {valid}"))
        self.assertFalse(auth.matches(f"Basic {wrong}"))
        self.assertFalse(auth.matches(f"Basic {valid} extra"))
        self.assertFalse(auth.matches("Bearer token"))

    def test_remote_configuration_fails_closed(self):
        config = SimpleNamespace(
            public_url="https://review.example.com",
            review_username_env="TEST_REVIEW_USERNAME",
            review_password_env="TEST_REVIEW_PASSWORD",
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "kullanıcı adı"):
                load_review_auth("0.0.0.0", config)
        with patch.dict(os.environ, {"TEST_REVIEW_USERNAME": "editor", "TEST_REVIEW_PASSWORD": "short"}, clear=True):
            with self.assertRaisesRegex(ValueError, "20"):
                load_review_auth("0.0.0.0", config)
        insecure = SimpleNamespace(
            public_url="http://review.example.com",
            review_username_env="TEST_REVIEW_USERNAME",
            review_password_env="TEST_REVIEW_PASSWORD",
        )
        with patch.dict(os.environ, {"TEST_REVIEW_USERNAME": "editor", "TEST_REVIEW_PASSWORD": "a-secure-password-long-enough"}, clear=True):
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                load_review_auth("0.0.0.0", insecure)

    def test_remote_auth_precedes_reads_and_health_is_exempt(self):
        repository = CountingRepository()
        config = SimpleNamespace(
            public_url="https://review.example.com",
            review_username_env="TEST_REVIEW_USERNAME",
            review_password_env="TEST_REVIEW_PASSWORD",
            timezone="Europe/Istanbul",
        )
        environment = {"TEST_REVIEW_USERNAME": "editor", "TEST_REVIEW_PASSWORD": "a-secure-password-long-enough"}
        with patch.dict(os.environ, environment, clear=True):
            server = create_server(repository, "0.0.0.0", 0, csrf_token="test-token", config=config, readiness=lambda: False)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, headers, _ = self._request(server.server_port, "GET", "/")
            self.assertEqual(status, 401)
            self.assertIn("Basic", headers["WWW-Authenticate"])
            self.assertEqual(repository.reads, 0)

            status, _, body = self._request(server.server_port, "GET", "/health")
            self.assertEqual(status, 200)
            self.assertEqual(body, '{"status": "ok"}')
            status, _, body = self._request(server.server_port, "GET", "/ready")
            self.assertEqual(status, 503)
            self.assertEqual(body, '{"status": "unavailable"}')

            token = base64.b64encode(b"editor:a-secure-password-long-enough").decode()
            authorization = {"Authorization": f"Basic {token}"}
            status, headers, body = self._request(server.server_port, "GET", "/", headers=authorization)
            self.assertEqual(status, 200)
            self.assertEqual(repository.reads, 1)
            self.assertIn("Secure", headers["Set-Cookie"])
            self.assertEqual(headers["Referrer-Policy"], "strict-origin-when-cross-origin")

            post_headers = {
                **authorization,
                "Content-Type": "application/x-www-form-urlencoded",
                "Cookie": "xap_csrf=test-token",
                "Origin": "https://attacker.example",
            }
            status, _, _ = self._request(server.server_port, "POST", "/draft/1/approve", "csrf=test-token&revision=1", post_headers)
            self.assertEqual(status, 403)
            self.assertEqual(repository.reads, 1)

            large = "x" * (64 * 1024 + 1)
            status, _, _ = self._request(server.server_port, "POST", "/draft/1/approve", large, authorization)
            self.assertEqual(status, 413)
            self.assertEqual(repository.reads, 1)

            repository.fail_reads = True
            status, _, body = self._request(server.server_port, "GET", "/", headers=authorization)
            self.assertEqual(status, 503)
            self.assertNotIn("secret", body)
            same_origin_headers = {
                **authorization,
                "Content-Type": "application/x-www-form-urlencoded",
                "Cookie": "xap_csrf=test-token",
                "Origin": "https://review.example.com",
            }
            status, _, body = self._request(server.server_port, "POST", "/draft/1/approve", "csrf=test-token&revision=1", same_origin_headers)
            self.assertEqual(status, 503)
            self.assertNotIn("secret", body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)

    @staticmethod
    def _request(port, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        data = response.read().decode()
        result = response.status, dict(response.getheaders()), data
        connection.close()
        return result


if __name__ == "__main__":
    unittest.main()
