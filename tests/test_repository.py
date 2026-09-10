from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import py_compile
import subprocess
import sys
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
        for platform, expected_errors in (("win32", 0), ("linux", 5), ("darwin", 5)):
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

    def test_windows_launchers_keep_safe_defaults(self) -> None:
        setup_ps1 = (ROOT / "setup.ps1").read_text(encoding="utf-8")
        install_ps1 = (ROOT / "scripts/install.ps1").read_text(encoding="utf-8")
        setup_cmd = (ROOT / "setup.cmd").read_text(encoding="utf-8")
        self.assertIn('[string]$Profile = "astra"', setup_ps1)
        self.assertIn('[string]$Profile = "astra"', install_ps1)
        self.assertIn("-ExecutionPolicy Bypass", setup_cmd)
        self.assertNotIn("force-config", setup_cmd.lower())


if __name__ == "__main__":
    unittest.main()
