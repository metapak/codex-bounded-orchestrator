from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / ".codex/tools/ledger.py"


class LedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary.name) / "repository"
        self.repository.mkdir()
        subprocess.run(
            ["git", "init", "-q", str(self.repository)], check=True, timeout=15
        )
        runtime = self.repository / ".codex/.bounded-orchestrator"
        runtime.mkdir(parents=True)
        (runtime / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", ".codex/.bounded-orchestrator/.gitignore"],
            cwd=self.repository,
            check=True,
            timeout=15,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Ledger Tests",
                "-c",
                "user.email=ledger-tests@example.invalid",
                "commit",
                "-qm",
                "test fixture",
            ],
            cwd=self.repository,
            check=True,
            timeout=15,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_ledger(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(LEDGER), "--root", str(self.repository), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
        )

    def start(self) -> None:
        result = self.run_ledger("start", "run-1", "--title", "Add safe feature")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_happy_path_dependencies_human_and_json_status(self) -> None:
        self.start()
        self.assertEqual(
            self.run_ledger("add", "map", "--title", "Map the flow").returncode,
            0,
        )
        self.assertEqual(
            self.run_ledger(
                "add",
                "implement",
                "--title",
                "Implement change",
                "--depends-on",
                "map",
            ).returncode,
            0,
        )
        blocked = self.run_ledger("begin", "implement")
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("unresolved dependencies", blocked.stderr)

        for command in (("begin", "map"), ("complete", "map"), ("begin", "implement"), ("complete", "implement")):
            result = self.run_ledger(*command)
            self.assertEqual(result.returncode, 0, result.stderr)

        human = self.run_ledger("status")
        self.assertIn("Ready for review: yes", human.stdout)
        machine = self.run_ledger("status", "--json")
        payload = json.loads(machine.stdout)
        self.assertTrue(payload["ready_for_review"])
        self.assertEqual(payload["counts"]["complete"], 2)
        self.assertEqual(self.run_ledger("ready-for-review").returncode, 0)
        self.assertEqual(self.run_ledger("complete-run").returncode, 0)

        completed = json.loads(self.run_ledger("status", "--json").stdout)
        self.assertEqual(completed["run"]["status"], "complete")
        self.assertIsNotNone(completed["run"]["completed_at"])

    def test_required_unresolved_states_and_unjustified_skip_block_completion(self) -> None:
        self.start()
        self.assertEqual(
            self.run_ledger("add", "required", "--title", "Required work").returncode,
            0,
        )
        for expected in ("pending", "in_progress", "blocked"):
            if expected == "in_progress":
                self.assertEqual(self.run_ledger("begin", "required").returncode, 0)
            elif expected == "blocked":
                self.assertEqual(
                    self.run_ledger(
                        "block", "required", "--reason", "Needs evidence"
                    ).returncode,
                    0,
                )
            result = self.run_ledger("complete-run")
            self.assertEqual(result.returncode, 2)
            self.assertIn(expected, result.stderr)

        self.assertEqual(self.run_ledger("skip", "required").returncode, 0)
        unjustified = self.run_ledger("ready-for-review")
        self.assertEqual(unjustified.returncode, 2)
        self.assertIn("without justification", unjustified.stderr)

    def test_blocked_task_can_resume(self) -> None:
        self.start()
        self.assertEqual(
            self.run_ledger("add", "task", "--title", "Recoverable task").returncode,
            0,
        )
        self.assertEqual(
            self.run_ledger("block", "task", "--reason", "Waiting for evidence").returncode,
            0,
        )
        self.assertEqual(self.run_ledger("begin", "task").returncode, 0)
        payload = json.loads(self.run_ledger("status", "--json").stdout)
        self.assertEqual(payload["run"]["tasks"]["task"]["status"], "in_progress")
        self.assertIsNone(payload["run"]["tasks"]["task"]["reason"])

    def test_justified_required_skip_and_unresolved_optional_task_allow_readiness(self) -> None:
        self.start()
        self.assertEqual(
            self.run_ledger("add", "required", "--title", "Required work").returncode,
            0,
        )
        self.assertEqual(
            self.run_ledger(
                "add", "optional", "--title", "Optional work", "--optional"
            ).returncode,
            0,
        )
        self.assertEqual(
            self.run_ledger("skip", "required", "--reason", "Out of scope").returncode,
            0,
        )
        self.assertEqual(self.run_ledger("ready-for-review").returncode, 0)
        self.assertEqual(self.run_ledger("complete-run").returncode, 0)

    def test_rejects_invalid_ids_duplicate_tasks_and_invalid_transitions(self) -> None:
        invalid = self.run_ledger("start", "../escape", "--title", "Bad")
        self.assertEqual(invalid.returncode, 2)
        self.start()
        add = self.run_ledger("add", "task", "--title", "One line")
        self.assertEqual(add.returncode, 0)
        self.assertEqual(self.run_ledger("add", "task", "--title", "Again").returncode, 2)
        self.assertEqual(self.run_ledger("complete", "task").returncode, 2)
        self.assertEqual(
            self.run_ledger(
                "add", "dependent", "--title", "Bad dependency", "--depends-on", "missing"
            ).returncode,
            2,
        )

    def test_runtime_files_are_restrictive_atomic_and_git_ignored(self) -> None:
        self.start()
        run_path = self.repository / ".codex/.bounded-orchestrator/runs/run-1.json"
        current_path = self.repository / ".codex/.bounded-orchestrator/current.json"
        self.assertTrue(run_path.is_file())
        self.assertTrue(current_path.is_file())
        if os.name != "nt":
            self.assertEqual(run_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(current_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(run_path.parent.stat().st_mode & 0o777, 0o700)
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.repository,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        )
        self.assertEqual(status.stdout, "")
        leftovers = list(run_path.parent.glob(".run-1.json.*"))
        self.assertEqual(leftovers, [])

        cleared = self.run_ledger("clear")
        self.assertEqual(cleared.returncode, 0, cleared.stderr)
        self.assertFalse(run_path.exists())
        self.assertFalse(current_path.exists())

    def test_refuses_runtime_without_exact_ignore(self) -> None:
        (self.repository / ".codex/.bounded-orchestrator/.gitignore").write_text(
            "runs/\n", encoding="utf-8"
        )
        result = self.run_ledger("start", "run-1", "--title", "No leak")
        self.assertEqual(result.returncode, 2)
        self.assertIn("runtime ignore", result.stderr)


if __name__ == "__main__":
    unittest.main()
