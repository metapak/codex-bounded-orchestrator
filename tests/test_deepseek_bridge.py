from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / ".codex/tools/deepseek_mcp.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("deepseek_mcp", BRIDGE)
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


class DeepSeekBridgeTests(unittest.TestCase):
    def test_mocked_response_request_uses_effort_and_env_key(self) -> None:
        bridge = load_bridge()
        captured = {}

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data)
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return FakeResponse({"output_text": "--- a/app.py"})

        arguments = {
            "task": "Fix the bug",
            "context": "app.py contains supplied source",
            "allowed_paths": ["app.py"],
            "constraints": "No dependencies",
        }
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-only-key"}, clear=True), patch.object(
            bridge.urllib.request, "urlopen", side_effect=fake_urlopen
        ):
            response = bridge.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "tools/call",
                    "params": {
                        "name": "deepseek_implementation_proposal",
                        "arguments": arguments,
                    },
                },
                default_model="deepseek-flash",
                default_effort="max",
                endpoint=bridge.DEFAULT_ENDPOINT,
            )
        self.assertEqual(response["result"]["content"][0]["text"], "--- a/app.py")
        self.assertEqual(captured["body"]["model"], "deepseek-flash")
        self.assertEqual(captured["body"]["reasoning"], {"effort": "max"})
        self.assertIn("app.py", captured["body"]["input"])
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-only-key")

    def test_rejects_unsafe_paths_wrong_model_and_missing_key(self) -> None:
        bridge = load_bridge()
        with self.assertRaises(bridge.BridgeError):
            bridge.validate_allowed_paths(["../secret.txt"])
        with self.assertRaises(bridge.BridgeError):
            bridge.validate_model("claude-sonnet-5")
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(bridge.BridgeError):
            bridge.call_deepseek(
                {"task": "x", "context": "y", "allowed_paths": ["a.py"]},
                default_model="deepseek-flash",
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
        self.assertEqual(tool["name"], "deepseek_implementation_proposal")
        self.assertIn("never applies", tool["description"])


if __name__ == "__main__":
    unittest.main()
