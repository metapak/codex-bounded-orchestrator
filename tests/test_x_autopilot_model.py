from __future__ import annotations

import io
import json
import os
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from x_autopilot.config import AppConfig, ModelRoute
from x_autopilot.costs import LUNA_PRICE_PROVENANCE, LunaCostRates, estimate_luna_cost_usd
from x_autopilot.domain import ConfigurationError, ProviderError, ProviderUnavailableError, StructuredOutputError
from x_autopilot.model import FakeModelProvider, ModelGateway, OpenAIResponsesProvider
from x_autopilot.ports import ModelRequest


SCHEMA = {"type": "object", "additionalProperties": False, "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}


def app_config(routes):
    return AppConfig(Path(":memory:"), "127.0.0.1", 0, .5, 8, 4, "tr", (), routes, {})


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *args):
        return json.dumps(self.payload).encode()


class ModelTests(unittest.TestCase):
    def test_gateway_allows_luna_only_and_validates_output(self):
        fake = FakeModelProvider({"test": {"ok": True}})
        config = app_config({
            "luna": ModelRoute("fake", "configured-luna"),
            "sol": ModelRoute("fake", "configured-sol"),
            "astra": ModelRoute("fake", "configured-astra"),
        })
        response = ModelGateway(config, {"fake": fake}).run("luna", ModelRequest("test", "instructions", {}, "result", SCHEMA, "v1"))
        self.assertEqual(response.model, "configured-luna")
        for role in ("sol", "astra"):
            with self.assertRaises(ConfigurationError):
                ModelGateway(config, {"fake": fake}).run(role, ModelRequest("test", "", {}, "result", SCHEMA, "v1"))
        invalid = FakeModelProvider({"test": {"wrong": True}})
        with self.assertRaises(StructuredOutputError):
            ModelGateway(config, {"fake": invalid}).run("luna", ModelRequest("test", "", {}, "result", SCHEMA, "v1"))

    def test_openai_gateway_requires_exact_luna_model(self):
        provider = FakeModelProvider({"test": {"ok": True}})
        provider.name = "openai"
        config = app_config({"luna": ModelRoute("openai", "gpt-5.6-sol")})
        with self.assertRaises(ConfigurationError):
            ModelGateway(config, {"openai": provider}).run("luna", ModelRequest("test", "", {}, "result", SCHEMA, "v1"))

    def test_gateway_retries_transient_error_but_not_unavailable_model(self):
        class Provider:
            name = "flaky"

            def __init__(self, error):
                self.calls = 0
                self.error = error

            def generate(self, *args, **kwargs):
                self.calls += 1
                if self.calls < 2:
                    raise self.error("failure")
                return FakeModelProvider({"test": {"ok": True}}).generate(args[0], model=kwargs["model"], reasoning_effort="low", max_output_tokens=1, timeout_seconds=1)

        config = app_config({"luna": ModelRoute("flaky", "m", retries=1)})
        transient = Provider(ProviderError)
        ModelGateway(config, {"flaky": transient}).run("luna", ModelRequest("test", "", {}, "r", SCHEMA, "v1"))
        self.assertEqual(transient.calls, 2)
        unavailable = Provider(ProviderUnavailableError)
        with self.assertRaises(ProviderUnavailableError):
            ModelGateway(config, {"flaky": unavailable}).run("luna", ModelRequest("test", "", {}, "r", SCHEMA, "v1"))
        self.assertEqual(unavailable.calls, 1)

    def test_openai_provider_parses_cache_usage_and_estimates_cost_once(self):
        captured = {}

        def opener(request, timeout):
            captured["body"] = json.loads(request.data)
            captured["headers"] = dict(request.header_items())
            return Response({
                "id": "resp_1",
                "output_text": "{\"ok\":true}",
                "usage": {
                    "input_tokens": 1364,
                    "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 1361},
                    "output_tokens": 1376,
                    "output_tokens_details": {"reasoning_tokens": 54},
                },
            })

        provider = OpenAIResponsesProvider(opener=opener)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}, clear=True):
            result = provider.generate(ModelRequest("test", "safe", {}, "result", SCHEMA, "v1"), model="gpt-5.6-luna", reasoning_effort="low", max_output_tokens=50, timeout_seconds=4)
        self.assertEqual(result.cached_input_tokens, 0)
        self.assertEqual(result.cache_write_tokens, 1361)
        self.assertAlmostEqual(result.estimated_cost_usd, 0.00199205)
        self.assertEqual(result.cost_provenance, LUNA_PRICE_PROVENANCE)
        self.assertFalse(captured["body"]["store"])
        self.assertIn("Bearer test-secret", captured["headers"].values())

    def test_cost_rates_are_explicit_and_injectable(self):
        rates = LunaCostRates(1, 2, 3, 4, "fixture rates")
        cost = estimate_luna_cost_usd(input_tokens=10, cached_input_tokens=2, cache_write_tokens=3, output_tokens=5, rates=rates)
        self.assertEqual(cost, (5 * 1 + 2 * 2 + 3 * 3 + 5 * 4) / 1_000_000)
        self.assertEqual(rates.provenance, "fixture rates")
        clamped = estimate_luna_cost_usd(input_tokens=10, cached_input_tokens=8, cache_write_tokens=8, output_tokens=0, rates=rates)
        self.assertEqual(clamped, (8 * 2 + 2 * 3) / 1_000_000)

    def test_http_error_does_not_expose_response_body_or_secret(self):
        for status, error_type in ((400, ProviderUnavailableError), (500, ProviderError)):
            with self.subTest(status=status):
                body = io.BytesIO(b"secret response body")

                def opener(request, timeout):
                    raise urllib.error.HTTPError(request.full_url, status, "bad", {}, body)

                provider = OpenAIResponsesProvider(opener=opener)
                with patch.dict(os.environ, {"OPENAI_API_KEY": "top-secret"}, clear=True):
                    with self.assertRaises(error_type) as raised:
                        provider.generate(ModelRequest("test", "", {}, "result", SCHEMA, "v1"), model="gpt-5.6-luna", reasoning_effort="low", max_output_tokens=10, timeout_seconds=1)
                message = str(raised.exception)
                self.assertTrue(body.closed)
                self.assertNotIn("secret response body", message)
                self.assertNotIn("top-secret", message)


if __name__ == "__main__":
    unittest.main()
