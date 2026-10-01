from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import plistlib
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("launch_dashboard", ROOT / "launchers/launch_dashboard.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class MacLauncherTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX app launcher is not used on Windows")
    def test_translocated_app_retries_wrong_folder_then_uses_selected_distribution(self) -> None:
        source = (ROOT / "launchers/Bounded Orchestrator.app/Contents/MacOS/launch").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            executable = temporary / "AppTranslocation/random/d/Bounded Orchestrator.app/Contents/MacOS/launch"
            executable.parent.mkdir(parents=True)
            distribution = temporary / "codex-bounded-orchestrator-main 2"
            (distribution / "launchers").mkdir(parents=True)
            (distribution / "scripts").mkdir()
            (distribution / "scripts/dashboard.py").write_text("", encoding="utf-8")
            project = temporary / "my Git project"
            project.mkdir()
            picker = temporary / "picker"
            dashboard_source = (ROOT / "launchers/launch_dashboard.py").read_text(encoding="utf-8")
            (distribution / "launchers/launch_dashboard.py").write_text(
                dashboard_source.replace("/usr/bin/osascript", str(picker)).replace(
                    "return run_mac_console(entry, project)",
                    "print(f'selected target: {project}'); return 0",
                ),
                encoding="utf-8",
            )
            picker_calls = temporary / "picker-calls"
            picker.write_text(
                "#!/bin/sh\n"
                f"case \"$2\" in *'2/2 Çalışacağınız Git projesini seçin'*) printf '%s\\n' {shlex.quote(str(project))}; exit 0 ;; esac\n"
                f"case \"$2\" in *'display dialog'*) exit 0 ;; *'display alert'*) exit 0 ;; esac\n"
                f"printf 'call\\n' >> {shlex.quote(str(picker_calls))}\n"
                f"if [ $(wc -l < {shlex.quote(str(picker_calls))}) -eq 1 ]; then\n"
                f"  printf '%s\\n' {shlex.quote(str(temporary / 'Git project'))}\n"
                "else\n"
                f"  printf '%s\\n' {shlex.quote(str(distribution))}\n"
                "fi\n",
                encoding="utf-8",
            )
            picker.chmod(0o755)
            executable.write_text(source.replace("/usr/bin/osascript", shlex.quote(str(picker))), encoding="utf-8")
            executable.chmod(0o755)
            result = subprocess.run([str(executable)], capture_output=True, text=True, check=False, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"selected target: {project.resolve()}", result.stdout)
            self.assertEqual(picker_calls.read_text(encoding="utf-8").count("call"), 2)

    @unittest.skipIf(os.name == "nt", "POSIX app launcher is not used on Windows")
    def test_translocated_app_wrong_folder_then_cancel_exits_cleanly(self) -> None:
        source = (ROOT / "launchers/Bounded Orchestrator.app/Contents/MacOS/launch").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            executable = temporary / "AppTranslocation/random/d/Bounded Orchestrator.app/Contents/MacOS/launch"
            executable.parent.mkdir(parents=True)
            picker = temporary / "picker"
            picker_calls = temporary / "picker-calls"
            alert_marker = temporary / "alert-shown"
            picker.write_text(
                "#!/bin/sh\n"
                f"case \"$2\" in *'display dialog'*) exit 0 ;; *'display alert'*) printf '%s\\n' \"$2\" >> {shlex.quote(str(alert_marker))}; exit 0 ;; esac\n"
                f"printf 'call\\n' >> {shlex.quote(str(picker_calls))}\n"
                f"if [ $(wc -l < {shlex.quote(str(picker_calls))}) -eq 1 ]; then\n"
                f"  printf '%s\\n' {shlex.quote(str(temporary / 'wrong folder'))}\n"
                "else\n"
                "  echo 'User canceled. (-128)' >&2; exit 1\n"
                "fi\n",
                encoding="utf-8",
            )
            picker.chmod(0o755)
            executable.write_text(source.replace("/usr/bin/osascript", shlex.quote(str(picker))), encoding="utf-8")
            executable.chmod(0o755)
            canceled = subprocess.run([str(executable)], capture_output=True, text=True, check=False, timeout=10)
            self.assertEqual(canceled.returncode, 0)
            self.assertEqual(picker_calls.read_text(encoding="utf-8").count("call"), 2)
            alerts = alert_marker.read_text(encoding="utf-8")
            self.assertIn("Yanlış klasör", alerts)
            self.assertIn("Kurulum iptal edildi", alerts)

    @unittest.skipIf(os.name == "nt", "POSIX app launcher is not used on Windows")
    def test_translocated_app_intro_cancel_skips_folder_picker(self) -> None:
        source = (ROOT / "launchers/Bounded Orchestrator.app/Contents/MacOS/launch").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            executable = temporary / "AppTranslocation/random/d/Bounded Orchestrator.app/Contents/MacOS/launch"
            executable.parent.mkdir(parents=True)
            picker = temporary / "picker"
            picker.write_text(
                "#!/bin/sh\n"
                "case \"$2\" in *'display dialog'*) echo 'User canceled. (-128)' >&2; exit 1 ;; esac\n"
                "exit 9\n",
                encoding="utf-8",
            )
            picker.chmod(0o755)
            executable.write_text(source.replace("/usr/bin/osascript", shlex.quote(str(picker))), encoding="utf-8")
            executable.chmod(0o755)
            canceled = subprocess.run([str(executable)], capture_output=True, text=True, check=False, timeout=10)
            self.assertEqual(canceled.returncode, 0)

    def test_app_is_visible_and_picker_does_not_activate_background_script(self) -> None:
        plist = ROOT / "launchers/Bounded Orchestrator.app/Contents/Info.plist"
        self.assertFalse(plistlib.loads(plist.read_bytes())["LSUIElement"])
        chosen = subprocess.CompletedProcess([], 0, stdout="/tmp/project folder/\n", stderr="")
        with patch.object(launcher.sys, "platform", "darwin"), patch.object(
            launcher.subprocess, "run", return_value=chosen
        ) as run:
            self.assertEqual(launcher.choose_project(), Path("/tmp/project folder/"))
        self.assertIn("2/2 Çalışacağınız Git projesini seçin", run.call_args.args[0][2])
        self.assertIn("Kurulum ayarları bu projeye yazılacak", run.call_args.args[0][2])
        self.assertIn("Değişiklikleri kontrol edin", run.call_args.args[0][2])
        self.assertNotIn("activate", run.call_args.args[0][2])

    def test_project_guide_cancel_skips_project_picker(self) -> None:
        canceled = subprocess.CompletedProcess([], 1, stdout="", stderr="User canceled. (-128)")
        with patch.object(launcher.sys, "platform", "darwin"), patch.object(
            launcher.subprocess, "run", return_value=canceled
        ) as run, patch.object(launcher, "alert") as alert:
            self.assertIsNone(launcher.choose_project())
        self.assertEqual(run.call_count, 1)
        alert.assert_not_called()

    def test_selected_project_reaches_mac_console(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "scripts/dashboard.py"
            entry.parent.mkdir()
            entry.write_text("", encoding="utf-8")
            project = root / "my Git project"
            project.mkdir()
            with patch.object(launcher, "ROOT", root), patch.object(launcher.sys, "argv", ["launch_dashboard.py"]), patch.object(
                launcher.sys, "platform", "darwin"
            ), patch.object(launcher, "choose_project", return_value=project), patch.object(
                launcher, "run_mac_console", return_value=0
            ) as console:
                self.assertEqual(launcher.main(), 0)
            console.assert_called_once_with(entry, project.resolve())

    def test_opens_browser_after_server_reports_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            entry = Path(directory) / "server.py"
            entry.write_text(
                "import time\nprint('Codex yerel konsol: http://127.0.0.1:43210', flush=True)\ntime.sleep(0.2)\n",
                encoding="utf-8",
            )
            with patch.object(launcher.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as opened:
                self.assertEqual(launcher.run_mac_console(entry, Path(directory)), 0)
            self.assertEqual(opened.call_args.args[0], ["/usr/bin/open", "http://127.0.0.1:43210"])

    def test_reports_server_start_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            entry = Path(directory) / "server.py"
            entry.write_text("raise RuntimeError('startup failed')\n", encoding="utf-8")
            with patch.object(launcher, "alert") as alert:
                self.assertEqual(launcher.run_mac_console(entry, Path(directory)), 1)
            self.assertIn("startup failed", alert.call_args.args[1])

    def test_reports_browser_failure_with_local_address(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            entry = Path(directory) / "server.py"
            failure = subprocess.CompletedProcess([], 1, stderr="Launch Services error")
            server = Mock()
            server.poll.return_value = None
            server.wait.return_value = 0

            def start_server(*_args, **kwargs):
                kwargs["stdout"].write("Codex yerel konsol: http://127.0.0.1:43210\n")
                kwargs["stdout"].flush()
                return server

            def inspect_alert(_title: str, message: str) -> None:
                self.assertIn("http://127.0.0.1:43210", message)
                server.terminate.assert_not_called()
                server.wait.assert_not_called()

            with patch.object(launcher.subprocess, "Popen", side_effect=start_server), patch.object(
                launcher.subprocess, "run", return_value=failure
            ), patch.object(
                launcher, "alert", side_effect=inspect_alert
            ) as alert:
                self.assertEqual(launcher.run_mac_console(entry, Path(directory)), 1)
            self.assertIn("Open http://127.0.0.1:43210", alert.call_args.args[1])
            server.wait.assert_called_once()


if __name__ == "__main__":
    unittest.main()
