from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / ".codex/tools/anthropic_mcp.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("anthropic_mcp", BRIDGE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class AnthropicBridgeTests(unittest.TestCase):
    def test_mocked_messages_request_uses_output_config_and_env_key(self) -> None:
        bridge = load_bridge()
        captured = {}

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data)
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return FakeResponse({"content": [{"type": "text", "text": "--- a/app.py"}]})

        arguments = {
            "task": "Fix the bug",
            "context": "app.py contains supplied source",
            "allowed_paths": ["app.py"],
            "constraints": "No dependencies",
        }
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-only-key"}, clear=True), patch.object(
            bridge.urllib.request, "urlopen", side_effect=fake_urlopen
        ):
            response = bridge.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "tools/call",
                    "params": {
                        "name": "claude_implementation_proposal",
                        "arguments": arguments,
                    },
                },
                default_model="claude-sonnet-5",
                default_effort="medium",
                endpoint=bridge.DEFAULT_ENDPOINT,
            )
        self.assertEqual(response["result"]["content"][0]["text"], "--- a/app.py")
        self.assertEqual(captured["body"]["model"], "claude-sonnet-5")
        self.assertEqual(captured["body"]["output_config"], {"effort": "medium"})
        self.assertIn("app.py", captured["body"]["messages"][0]["content"])
        self.assertEqual(captured["headers"]["X-api-key"], "test-only-key")

    def test_bridge_rejects_unsafe_paths_and_missing_key(self) -> None:
        bridge = load_bridge()
        with self.assertRaises(bridge.BridgeError):
            bridge.validate_allowed_paths(["../secret.txt"])
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(bridge.BridgeError):
            bridge.call_anthropic(
                {"task": "x", "context": "y", "allowed_paths": ["a.py"]},
                default_model="claude-sonnet-5",
                default_effort="high",
            )

    def test_stdio_mcp_initialize_and_tools_list(self) -> None:
        requests = "\n".join(
            json.dumps(item)
            for item in (
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
        ) + "\n"
        result = subprocess.run(
            [sys.executable, str(BRIDGE)],
            input=requests,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(responses[0]["result"]["protocolVersion"], "2025-06-18")
        tool = responses[1]["result"]["tools"][0]
        self.assertEqual(tool["name"], "claude_implementation_proposal")
        self.assertIn("never applies", tool["description"])


if __name__ == "__main__":
    unittest.main()
