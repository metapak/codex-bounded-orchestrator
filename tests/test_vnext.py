from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class VNextTests(unittest.TestCase):
    def test_quota_saver_and_managed_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            result = subprocess.run([sys.executable, str(ROOT / "scripts/install.py"), str(target), "--preset", "quota-saver"], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            with (target / ".codex/config.toml").open("rb") as handle:
                config = tomllib.load(handle)
            self.assertEqual((config["model"], config["model_reasoning_effort"]), ("gpt-6-astra", "low"))
            self.assertTrue((target / ".codex/tools/usage_report.py").is_file())
            self.assertTrue((target / ".codex/tools/local_eval.py").is_file())

    def test_retry_is_bounded_and_eval_can_gate_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            runtime = repo / ".codex/.bounded-orchestrator"
            runtime.mkdir(parents=True)
            (runtime / ".gitignore").write_text("*\n!.gitignore\n")
            tool = ROOT / ".codex/tools/ledger.py"
            def run(*args):
                return subprocess.run([sys.executable, str(tool), "--root", str(repo), *args], text=True, capture_output=True, check=False)
            self.assertEqual(run("start", "r1", "--title", "Work").returncode, 0)
            self.assertEqual(run("add", "t1", "--title", "Repair", "--owner-role", "implementer").returncode, 0)
            for command in (("begin", "t1"), ("interrupt", "t1", "--reason", "Stopped"), ("retry", "t1", "--evidence", "Checked"), ("begin", "t1"), ("interrupt", "t1", "--reason", "Stopped again")):
                self.assertEqual(run(*command).returncode, 0)
            self.assertEqual(run("retry", "t1", "--evidence", "Again").returncode, 2)
            payload = json.loads(run("status", "--json").stdout)
            self.assertEqual(payload["run"]["tasks"]["t1"]["attempt_count"], 2)

    def test_local_eval_pass_is_bound_to_exact_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            runtime = repo / ".codex/.bounded-orchestrator"
            runtime.mkdir(parents=True)
            (runtime / ".gitignore").write_text("*\n!.gitignore\n")
            (repo / "tracked.txt").write_text("before\n")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"], cwd=repo, check=True)
            manifest = repo / "eval.json"
            manifest.write_text(json.dumps({"label": "focused", "argv": [sys.executable, "-c", "pass"], "timeout_seconds": 10}))
            local_eval = ROOT / ".codex/tools/local_eval.py"
            ledger = ROOT / ".codex/tools/ledger.py"
            self.assertEqual(subprocess.run([sys.executable, str(local_eval), "--root", str(repo), str(manifest)], capture_output=True).returncode, 0)
            def run(*args):
                return subprocess.run([sys.executable, str(ledger), "--root", str(repo), *args], text=True, capture_output=True, check=False)
            self.assertEqual(run("start", "eval-run", "--title", "Evaluate").returncode, 0)
            self.assertEqual(run("require-eval", "--label", "focused").returncode, 0)
            self.assertEqual(run("ready-for-review").returncode, 0)
            (repo / "tracked.txt").write_text("after\n")
            stale = run("ready-for-review")
            self.assertEqual(stale.returncode, 2)
            self.assertIn("stale candidate", stale.stderr)

    def test_waiting_user_resume_preserves_attempt_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            runtime = repo / ".codex/.bounded-orchestrator"
            runtime.mkdir(parents=True)
            (runtime / ".gitignore").write_text("*\n!.gitignore\n")
            tool = ROOT / ".codex/tools/ledger.py"
            def run(*args): return subprocess.run([sys.executable, str(tool), "--root", str(repo), *args], text=True, capture_output=True, check=False)
            self.assertEqual(run("start", "r1", "--title", "Waits").returncode, 0)
            self.assertEqual(run("add", "pending", "--title", "Pending wait").returncode, 0)
            self.assertEqual(run("wait-user", "pending", "--reason", "Need answer").returncode, 0)
            self.assertEqual(run("resume", "pending", "--evidence", "Answer received").returncode, 0)
            self.assertEqual(run("begin", "pending").returncode, 0)
            self.assertEqual(run("complete", "pending").returncode, 0)
            self.assertEqual(run("add", "active", "--title", "Active wait").returncode, 0)
            self.assertEqual(run("begin", "active").returncode, 0)
            self.assertEqual(run("wait-user", "active", "--reason", "Need choice").returncode, 0)
            self.assertEqual(run("resume", "active", "--evidence", "Choice received").returncode, 0)
            self.assertEqual(run("complete", "active").returncode, 0)
            tasks = json.loads(run("status", "--json").stdout)["run"]["tasks"]
            self.assertEqual(tasks["pending"]["attempt_count"], 1)
            self.assertEqual(tasks["active"]["attempt_count"], 1)
            self.assertEqual(tasks["active"]["attempts"][0]["attempt_id"], "a01")

    def test_eval_command_that_changes_candidate_cannot_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "tracked.txt").write_text("before\n")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"], cwd=repo, check=True)
            manifest = repo / "eval.json"
            manifest.write_text(json.dumps({"label": "mutates", "argv": [sys.executable, "-c", "from pathlib import Path; Path('tracked.txt').write_text('after\\n')"], "timeout_seconds": 10}))
            result = subprocess.run([sys.executable, str(ROOT / ".codex/tools/local_eval.py"), "--root", str(repo), "--json", str(manifest)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)["outcome"], "candidate_changed")


if __name__ == "__main__":
    unittest.main()
