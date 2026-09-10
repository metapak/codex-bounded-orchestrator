from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import py_compile
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RepositoryTests(unittest.TestCase):
    def test_static_validation(self) -> None:
        path = ROOT / "scripts/validate.py"
        spec = importlib.util.spec_from_file_location("bounded_validate", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = module.main()
        self.assertEqual(result, 0)
        self.assertIn("Repository validation passed", output.getvalue())

    def test_wrapper_modes_respect_platform_semantics(self) -> None:
        spec = importlib.util.spec_from_file_location("bounded_validate_modes", ROOT / "scripts/validate.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for platform, expected_errors in (("win32", 0), ("linux", 7), ("darwin", 7)):
            with self.subTest(platform=platform):
                errors = []
                with patch.object(module.sys, "platform", platform), patch.object(
                    module.Path, "stat", return_value=Mock(st_mode=0)
                ):
                    module.validate_wrapper_modes(errors)
                self.assertEqual(len(errors), expected_errors)

    def test_python_files_compile(self) -> None:
        files = [
            ROOT / ".codex/tools/candidate.py",
            ROOT / ".codex/tools/ledger.py",
            ROOT / ".codex/tools/anthropic_mcp.py",
            ROOT / "scripts/install.py",
            ROOT / "scripts/validate.py",
            ROOT / "scripts/build_release.py",
        ]
        for path in files:
            py_compile.compile(str(path), doraise=True)

    @unittest.skipIf(os.name == "nt", "POSIX shell parser is not required on Windows")
    def test_shell_launchers_parse(self) -> None:
        for path in (ROOT / "scripts/install.sh", ROOT / "setup.command"):
            result = subprocess.run(
                ["sh", "-n", str(path)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipIf(os.name == "nt", "POSIX launcher behavior is not required on Windows")
    def test_setup_command_single_target_is_interactive_but_options_pass_through(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "target repository"
            target.mkdir()
            interactive = subprocess.run(
                [str(ROOT / "setup.command"), str(target)],
                cwd=ROOT,
                input="1\nn\n",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(interactive.returncode, 0, interactive.stderr)
            self.assertIn("Kurulum profili / Installation profile", interactive.stdout)
            self.assertTrue((target / ".codex/config.toml").is_file())

        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "advanced target"
            target.mkdir()
            direct = subprocess.run(
                [
                    str(ROOT / "setup.command"),
                    str(target),
                    "--preset",
                    "economy",
                    "--dry-run",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(direct.returncode, 0, direct.stderr)
            self.assertNotIn("Kurulum profili / Installation profile", direct.stdout)
            self.assertEqual(list(target.iterdir()), [])

    def test_windows_launchers_keep_safe_defaults(self) -> None:
        setup_ps1 = (ROOT / "setup.ps1").read_text(encoding="utf-8")
        install_ps1 = (ROOT / "scripts/install.ps1").read_text(encoding="utf-8")
        setup_cmd = (ROOT / "setup.cmd").read_text(encoding="utf-8")
        self.assertIn('ValidateSet("balanced", "quality", "economy", "custom")', setup_ps1)
        self.assertIn('ValidateSet("balanced", "quality", "economy", "custom")', install_ps1)
        self.assertIn("--interactive", (ROOT / "setup.command").read_text(encoding="utf-8"))
        self.assertIn("-ExecutionPolicy Bypass", setup_cmd)
        self.assertNotIn("force-config", setup_cmd.lower())

    def test_versioned_docs_and_language_pairs_exist(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(version, "0.4.1")
        for stem in ("task-ledger", "expertise-packs", "external-providers", "profiles", f"release-v{version}"):
            self.assertTrue((ROOT / "docs" / f"{stem}.md").is_file())
            self.assertTrue((ROOT / "docs" / f"{stem}.tr.md").is_file())


if __name__ == "__main__":
    unittest.main()
