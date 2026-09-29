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
    def test_usage_uses_only_request_token_records(self) -> None:
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
            self.assertEqual(payload["totals"]["total_tokens"], 31)
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

    def test_real_request_shape_dedup_and_filters(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("usage", USAGE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            sessions = Path(temporary)
            records = [
                {"type":"session_meta", "payload":{"id":"sanitized-thread", "cwd":"/sample/project", "prompt":"SECRET"}},
                {"type":"turn_context", "payload":{"model":"gpt-test", "role":"implementer"}},
                {"timestamp":"2026-09-01T10:00:00Z", "type":"token_usage_record", "payload":{"usage":{"input_tokens":29000,"cached_input_tokens":20000,"output_tokens":268,"total_tokens":29268},"thread_token_usage":{"total_tokens":29268}}},
                {"timestamp":"2026-09-02T10:00:00Z", "type":"token_usage_record", "payload":{"usage":{"input_tokens":32000,"cached_input_tokens":21000,"output_tokens":426,"total_tokens":32426},"thread_token_usage":{"total_tokens":61694}}},
                {"timestamp":"2026-09-02T10:00:01Z", "type":"event_msg", "payload":{"type":"token_count", "info":{"total_token_usage":{"total_tokens":61694}}}},
            ]
            for filename in ("a.jsonl", "copy.jsonl"):
                (sessions/filename).write_text("".join(json.dumps(r)+"\n" for r in records))
            report = module.scan(sessions)
            self.assertEqual(report["totals"]["total_tokens"], 61694)
            self.assertEqual(report["totals"]["input_tokens"], 61000)
            self.assertEqual(report["records_observed"], 2)
            self.assertEqual(report["duplicates_skipped"], 3)
            self.assertNotIn("SECRET", json.dumps(report))
            filtered = module.scan(sessions, date_from="2026-09-02", project="/sample/project", thread="sanitized-thread")
            self.assertEqual(filtered["totals"]["total_tokens"], 32426)
            self.assertEqual(module.scan(sessions, project="missing")["status"], "unavailable")

    def test_legacy_cumulative_resets_and_equal_request_values(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("usage", USAGE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            sessions = Path(temporary)
            records = [{"timestamp":f"2026-09-01T10:00:0{i}Z", "type":"event_msg", "payload":{"type":"token_count", "info":{"total_token_usage":{"total_tokens":v}}}} for i,v in enumerate((12,19,4,9))]
            records += [{"type":"token_usage_record", "thread_id":"request-thread", "usage":{"total_tokens":12}}]*2
            (sessions/"a.jsonl").write_text("".join(json.dumps(r)+"\n" for r in records)+"invalid\n")
            report = module.scan(sessions)
            self.assertEqual(report["totals"]["total_tokens"], 52)
            self.assertEqual(report["counter_resets"], 1)
            self.assertEqual(report["malformed_lines_skipped"], 1)

    def test_legacy_cumulative_orders_by_time_across_files_before_filter(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("usage", USAGE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            sessions = Path(temporary)
            for filename, stamp, total in (("a.jsonl", "2026-09-02T00:00:00Z", 150), ("b.jsonl", "2026-09-01T00:00:00Z", 100)):
                records = [
                    {"type":"session_meta", "payload":{"id":"same-session"}},
                    {"timestamp":stamp, "type":"event_msg", "payload":{"type":"token_count", "info":{"total_token_usage":{"total_tokens":total}}}},
                ]
                (sessions/filename).write_text("".join(json.dumps(r)+"\n" for r in records))
            report = module.scan(sessions)
            self.assertEqual(report['totals']['total_tokens'], 150)
            self.assertEqual(report['counter_resets'], 0)
            self.assertEqual(module.scan(sessions, date_from='2026-09-02')['totals']['total_tokens'], 50)

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
