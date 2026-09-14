from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USAGE = ROOT / ".codex/tools/usage_report.py"
LOCAL_EVAL = ROOT / ".codex/tools/local_eval.py"


class UsageAndEvalTests(unittest.TestCase):
    def test_usage_uses_only_token_record_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sessions = Path(temporary)
            records = [
                {"type": "message", "prompt": "must never appear", "usage": {"total_tokens": 999}},
                {"type": "token_usage_record", "model": "gpt-test", "role": "worker", "thread_id": "t1", "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}},
                {"type": "token_usage_record", "model": "gpt-test", "role": "worker", "thread_id": "t1", "usage": {"input_tokens": 14, "output_tokens": 5, "total_tokens": 19}},
            ]
            (sessions / "rollout.jsonl").write_text("".join(json.dumps(item) + "\n" for item in records))
            result = subprocess.run([sys.executable, str(USAGE), "--sessions", str(sessions), "--json"], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["totals"]["total_tokens"], 19)
            self.assertEqual(payload["records_observed"], 2)
            self.assertNotIn("must never appear", result.stdout)

    def test_usage_reads_realistic_outer_record_with_nested_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sessions = Path(temporary)
            record = {
                "timestamp": "2026-09-14T00:00:00Z",
                "type": "token_usage_record",
                "payload": {
                    "context": {"model": "gpt-nested", "role": "explorer", "thread_id": "thread-2"},
                    "usage": {"input_tokens": 11, "output_tokens": 3, "total_tokens": 14},
                    "prompt": "private prompt text",
                },
            }
            (sessions / "rollout.jsonl").write_text(json.dumps(record) + "\n")
            result = subprocess.run([sys.executable, str(USAGE), "--sessions", str(sessions), "--json"], text=True, capture_output=True, check=False)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["records_observed"], 1)
            self.assertEqual(payload["totals"]["total_tokens"], 14)
            self.assertEqual((payload["groups"][0]["model"], payload["groups"][0]["role"]), ("gpt-nested", "explorer"))
            self.assertNotIn("private prompt text", result.stdout)

    def test_local_eval_requires_argv_and_writes_ignored_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            manifest = repo / "eval.json"
            manifest.write_text(json.dumps({"label": "unit", "argv": [sys.executable, "-c", "print('ok')"], "timeout_seconds": 10}))
            result = subprocess.run([sys.executable, str(LOCAL_EVAL), "--root", str(repo), "--json", str(manifest)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["outcome"], "pass")
            summary = json.loads((repo / ".codex/.bounded-orchestrator/evals/unit.json").read_text())
            self.assertNotIn("sanitized_tail", summary)
            self.assertEqual(len(summary["output_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
