from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/build_release.py"
PREFIX = "codex-bounded-orchestrator/"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


class ReleaseBuilderTests(unittest.TestCase):
    def test_runtime_paths_are_excluded(self) -> None:
        import importlib.util
        spec=importlib.util.spec_from_file_location("release_builder",BUILDER); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertTrue(module.should_skip(Path("config/x-autopilot.toml")))
        self.assertTrue(module.should_skip(Path("var/research.sqlite3")))
        self.assertFalse(module.should_skip(Path(".env.example")))

    def test_builds_source_macos_and_windows_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = subprocess.run(
                [sys.executable, str(BUILDER), "--output-dir", str(output)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            source = output / f"codex-bounded-orchestrator-v{VERSION}-source.zip"
            macos = output / f"codex-bounded-orchestrator-v{VERSION}-macos.zip"
            windows = output / f"codex-bounded-orchestrator-v{VERSION}-windows.zip"
            for path in (source, macos, windows):
                self.assertTrue(path.is_file())

            with zipfile.ZipFile(source) as archive:
                names = set(archive.namelist())
                self.assertIn(PREFIX + ".codex/config.toml", names)
                self.assertIn(PREFIX + ".codex/tools/ledger.py", names)
                self.assertIn(PREFIX + ".codex/tools/anthropic_mcp.py", names)
                self.assertIn(
                    PREFIX
                    + ".agents/skills/bounded-orchestrator-ui-design/SKILL.md",
                    names,
                )
                self.assertIn(
                    PREFIX
                    + ".agents/skills/bounded-orchestrator-security-review/SKILL.md",
                    names,
                )
                self.assertIn(PREFIX + "setup.command", names)
                self.assertIn(PREFIX + "setup.cmd", names)
                self.assertIn(PREFIX + "x_autopilot/__main__.py", names)
                self.assertIn(PREFIX + "x_autopilot/migrations/001_initial.sql", names)
                self.assertIn(PREFIX + "x_autopilot/migrations/002_editorial_metadata.sql", names)
                self.assertIn(PREFIX + "x_autopilot/migrations/003_research_claims.sql", names)
                self.assertIn(PREFIX + "docs/x-autopilot.md", names)
                self.assertIn(PREFIX + "docs/x-autopilot.tr.md", names)
                self.assertIn(PREFIX + ".env.example", names)
                self.assertFalse(any("/.git/" in name for name in names))
                self.assertFalse(any(name.endswith(".pyc") for name in names))
                self.assertFalse(any(name.startswith(PREFIX + "var/") for name in names))
                self.assertFalse(any(name.endswith((".sqlite", ".sqlite3", ".db")) for name in names))

            with zipfile.ZipFile(macos) as archive:
                self.assertIn(PREFIX + "START-HERE-MACOS.txt", archive.namelist())
                info = archive.getinfo(PREFIX + "setup.command")
                mode = (info.external_attr >> 16) & 0o777
                self.assertEqual(mode, 0o755)

            with zipfile.ZipFile(windows) as archive:
                self.assertIn(PREFIX + "START-HERE-WINDOWS.txt", archive.namelist())
                for name in ("setup.ps1", "setup.cmd", "scripts/install.ps1"):
                    data = archive.read(PREFIX + name)
                    self.assertIn(b"\r\n", data)
                    self.assertNotIn(b"\n", data.replace(b"\r\n", b""))


if __name__ == "__main__":
    unittest.main()
