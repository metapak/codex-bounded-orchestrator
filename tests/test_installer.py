from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/install.py"
START_MARKER = "<!-- codex-bounded-orchestrator:start -->"
MANIFEST = Path(".codex/.bounded-orchestrator/install.json")

EXPECTED_ROLES = {
    "fast_lookup": ("fast-lookup.toml", "gpt-5.6-luna", "medium", "read-only"),
    "explorer": ("explorer.toml", "gpt-5.6-terra", "medium", "read-only"),
    "researcher": ("researcher.toml", "gpt-5.6-terra", "medium", "read-only"),
    "implementer": (
        "implementer.toml",
        "gpt-5.6-sol",
        "high",
        "workspace-write",
    ),
    "verifier": ("verifier.toml", "gpt-5.6-terra", "high", "workspace-write"),
    "failure_analyst": (
        "failure-analyst.toml",
        "gpt-5.6-sol",
        "high",
        "read-only",
    ),
    "qa_operator": (
        "qa-operator.toml",
        "gpt-5.6-sol",
        "high",
        "workspace-write",
    ),
    "reviewer": ("reviewer.toml", "gpt-6-astra", "medium", "read-only"),
    "advisor": ("advisor.toml", "gpt-6-astra", "xhigh", "read-only"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.target = Path(self.temporary.name) / "target repository"
        self.target.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_installer(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(INSTALLER), str(self.target), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )

    def test_fresh_astra_install_has_exact_routing(self) -> None:
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)

        config_path = self.target / ".codex/config.toml"
        config = read_toml(config_path)
        self.assertEqual(config["model"], "gpt-6-astra")
        self.assertEqual(config["model_reasoning_effort"], "medium")
        self.assertEqual(config["review_model"], "gpt-6-astra")
        self.assertEqual(config["agents"]["default_subagent_model"], "gpt-5.6-terra")
        self.assertEqual(config["agents"]["max_depth"], 1)

        registered_roles = {
            name for name, value in config["agents"].items() if isinstance(value, dict)
        }
        self.assertEqual(registered_roles, set(EXPECTED_ROLES))

        for role_name, (filename, model, effort, sandbox) in EXPECTED_ROLES.items():
            registration = config["agents"][role_name]
            self.assertEqual(registration["config_file"], f"./agents/{filename}")
            role = read_toml(self.target / ".codex/agents" / filename)
            self.assertEqual(role["name"], role_name)
            self.assertEqual(role["model"], model)
            self.assertEqual(role["model_reasoning_effort"], effort)
            self.assertEqual(role["sandbox_mode"], sandbox)
            self.assertIs(role["agents"]["enabled"], False)

        self.assertTrue(
            (self.target / ".agents/skills/bounded-orchestrator/SKILL.md").is_file()
        )
        self.assertTrue((self.target / ".codex/tools/candidate.py").is_file())
        self.assertIn(START_MARKER, (self.target / "AGENTS.md").read_text())

        manifest = json.loads((self.target / MANIFEST).read_text())
        self.assertEqual(manifest["profile"], "astra")
        self.assertEqual(manifest["tool_version"], "0.2.0")
        self.assertTrue(manifest["files"][".codex/config.toml"]["owned"])

    def test_sol_fallback_profile_keeps_terra_sol_astra_routing(self) -> None:
        result = self.run_installer("--profile", "sol")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = read_toml(self.target / ".codex/config.toml")
        self.assertEqual(config["model"], "gpt-5.6-sol")
        self.assertEqual(config["model_reasoning_effort"], "high")
        self.assertEqual(config["agents"]["default_subagent_model"], "gpt-5.6-terra")
        self.assertEqual(
            read_toml(self.target / ".codex/agents/reviewer.toml")["model"],
            "gpt-6-astra",
        )
        self.assertEqual(
            read_toml(self.target / ".codex/agents/fast-lookup.toml")["model"],
            "gpt-5.6-luna",
        )

    def test_install_is_idempotent_and_preserves_existing_agents_text(self) -> None:
        (self.target / "AGENTS.md").write_text(
            "# Existing instructions\n", encoding="utf-8"
        )
        first = self.run_installer()
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_installer()
        self.assertEqual(second.returncode, 0, second.stderr)
        text = (self.target / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Existing instructions"))
        self.assertEqual(text.count(START_MARKER), 1)

    def test_existing_config_is_preserved_and_example_is_written(self) -> None:
        codex = self.target / ".codex"
        codex.mkdir()
        existing = (
            'model = "custom-model"\n'
            "[mcp_servers.example]\n"
            'url = "https://example.com"\n'
        )
        config = codex / "config.toml"
        config.write_text(existing, encoding="utf-8")
        before = digest(config)

        result = self.run_installer("--profile", "sol")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(digest(config), before)
        example = codex / "bounded-orchestrator.config.example.toml"
        self.assertTrue(example.is_file())
        parsed = read_toml(example)
        self.assertEqual(parsed["model"], "gpt-5.6-sol")
        self.assertEqual(parsed["agents"]["default_subagent_model"], "gpt-5.6-terra")
        self.assertEqual(
            parsed["agents"]["reviewer"]["config_file"],
            "./agents/reviewer.toml",
        )
        manifest = json.loads((self.target / MANIFEST).read_text())
        self.assertTrue(
            manifest["files"][".codex/bounded-orchestrator.config.example.toml"][
                "owned"
            ]
        )

    def test_force_config_creates_ignored_backup_and_replaces(self) -> None:
        codex = self.target / ".codex"
        codex.mkdir()
        config = codex / "config.toml"
        config.write_text('model = "custom"\n', encoding="utf-8")

        result = self.run_installer("--profile", "sol", "--force-config")
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = read_toml(config)
        self.assertEqual(parsed["model"], "gpt-5.6-sol")
        self.assertEqual(parsed["model_reasoning_effort"], "high")
        backups = list(
            (self.target / ".codex/.bounded-orchestrator/backups").rglob(
                "config.toml"
            )
        )
        self.assertEqual(len(backups), 1)
        self.assertIn('model = "custom"', backups[0].read_text())

    def test_conflicting_agent_is_preserved_without_force(self) -> None:
        path = self.target / ".codex/agents/reviewer.toml"
        path.parent.mkdir(parents=True)
        path.write_text("custom reviewer\n", encoding="utf-8")
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(path.read_text(), "custom reviewer\n")
        self.assertIn(f"SKIP {Path('.codex/agents/reviewer.toml')}", result.stdout)

    def test_force_replaces_conflicting_agent_with_backup(self) -> None:
        path = self.target / ".codex/agents/reviewer.toml"
        path.parent.mkdir(parents=True)
        path.write_text("custom reviewer\n", encoding="utf-8")
        result = self.run_installer("--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = read_toml(path)
        self.assertEqual(parsed["name"], "reviewer")
        self.assertEqual(parsed["model_reasoning_effort"], "medium")
        backups = list(
            (self.target / ".codex/.bounded-orchestrator/backups").rglob(
                "reviewer.toml"
            )
        )
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "custom reviewer\n")

    def test_uninstall_removes_owned_files_and_block(self) -> None:
        (self.target / "AGENTS.md").write_text("# Keep me\n", encoding="utf-8")
        self.assertEqual(self.run_installer().returncode, 0)
        result = self.run_installer("--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.target / ".codex/config.toml").exists())
        self.assertFalse((self.target / ".codex/agents/reviewer.toml").exists())
        self.assertFalse((self.target / ".codex/agents/fast-lookup.toml").exists())
        self.assertEqual((self.target / "AGENTS.md").read_text(), "# Keep me\n")
        self.assertFalse((self.target / MANIFEST).exists())

    def test_uninstall_keeps_modified_managed_file(self) -> None:
        self.assertEqual(self.run_installer().returncode, 0)
        path = self.target / ".codex/agents/reviewer.toml"
        path.write_text(path.read_text() + "# local edit\n", encoding="utf-8")
        result = self.run_installer("--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(path.exists())
        self.assertIn("modified after installation", result.stdout)

    def test_dry_run_writes_nothing(self) -> None:
        result = self.run_installer("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.target.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
