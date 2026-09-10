from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / ".codex/tools/candidate.py"
IGNORE = ROOT / ".codex/.candidate/.gitignore"


class CandidateToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test User")
        self.git("config", "user.email", "test@example.com")
        runtime = self.repo / ".codex/.candidate"
        runtime.mkdir(parents=True)
        shutil.copy2(IGNORE, runtime / ".gitignore")
        (self.repo / "app.txt").write_text("one\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "initial")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def tool(self, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(TOOL), "--repo", str(self.repo), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def test_freeze_and_verify_clean_candidate(self) -> None:
        frozen = self.tool("freeze", "--label", "unit", "--json")
        self.assertEqual(frozen.returncode, 0, frozen.stderr)
        data = json.loads(frozen.stdout)
        self.assertEqual(data["status"], "FROZEN")
        self.assertTrue(data["clean"])
        self.assertEqual(len(data["fingerprint"]), 64)

        status = self.git("status", "--porcelain").stdout
        self.assertEqual(status, "", "candidate state must not dirty the worktree")

        verified = self.tool("verify", "--json")
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertEqual(json.loads(verified.stdout)["status"], "VERIFIED")

    def test_tracked_change_after_freeze_is_detected(self) -> None:
        self.assertEqual(self.tool("freeze").returncode, 0)
        (self.repo / "app.txt").write_text("two\n", encoding="utf-8")
        verified = self.tool("verify", "--json")
        self.assertEqual(verified.returncode, 1)
        data = json.loads(verified.stdout)
        self.assertEqual(data["status"], "MISMATCH")
        self.assertTrue(data["mismatches"])

    def test_dirty_candidate_can_be_frozen_and_verified(self) -> None:
        (self.repo / "app.txt").write_text("dirty candidate\n", encoding="utf-8")
        frozen = self.tool("freeze", "--json")
        self.assertEqual(frozen.returncode, 0, frozen.stderr)
        self.assertFalse(json.loads(frozen.stdout)["clean"])
        self.assertEqual(self.tool("verify").returncode, 0)

    def test_untracked_content_change_is_detected(self) -> None:
        path = self.repo / "new file.txt"
        path.write_text("alpha\n", encoding="utf-8")
        self.assertEqual(self.tool("freeze").returncode, 0)
        path.write_text("beta\n", encoding="utf-8")
        self.assertEqual(self.tool("verify").returncode, 1)

    def test_require_clean_rejects_dirty_worktree(self) -> None:
        (self.repo / "app.txt").write_text("dirty\n", encoding="utf-8")
        result = self.tool("freeze", "--require-clean")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not clean", result.stderr)

    def test_clear_removes_state(self) -> None:
        self.assertEqual(self.tool("freeze").returncode, 0)
        self.assertEqual(self.tool("clear").returncode, 0)
        result = self.tool("show")
        self.assertEqual(result.returncode, 2)
        self.assertIn("No frozen candidate", result.stderr)

    def test_unborn_repository_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(
                ["git", "init", "-b", "main"],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            runtime = repo / ".codex/.candidate"
            runtime.mkdir(parents=True)
            shutil.copy2(IGNORE, runtime / ".gitignore")
            result = subprocess.run(
                [sys.executable, str(TOOL), "--repo", str(repo), "freeze", "--json"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["head"], "UNBORN")


if __name__ == "__main__":
    unittest.main()
