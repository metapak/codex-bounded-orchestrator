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
    def test_translocated_app_uses_selected_extracted_folder(self) -> None:
        source = (ROOT / "launchers/Bounded Orchestrator.app/Contents/MacOS/launch").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            executable = temporary / "AppTranslocation/random/d/Bounded Orchestrator.app/Contents/MacOS/launch"
            executable.parent.mkdir(parents=True)
            distribution = temporary / "codex-bounded-orchestrator-main 2"
            (distribution / "launchers").mkdir(parents=True)
            (distribution / "scripts").mkdir()
            (distribution / "scripts/dashboard.py").write_text("", encoding="utf-8")
            (distribution / "launchers/launch_dashboard.py").write_text(
                "print('selected distribution launched')\n", encoding="utf-8"
            )
            picker = temporary / "picker"
            picker.write_text(f"#!/bin/sh\nprintf '%s\\n' {shlex.quote(str(distribution))}\n", encoding="utf-8")
            picker.chmod(0o755)
            executable.write_text(source.replace("/usr/bin/osascript", shlex.quote(str(picker))), encoding="utf-8")
            executable.chmod(0o755)
            result = subprocess.run([str(executable)], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("selected distribution launched", result.stdout)

            alert_marker = temporary / "alert-shown"
            picker.write_text(
                "#!/bin/sh\n"
                f"case \"$2\" in *'display alert'*) touch {shlex.quote(str(alert_marker))} ;; "
                f"*) printf '%s\\n' {shlex.quote(str(temporary / 'wrong folder'))} ;; esac\n",
                encoding="utf-8",
            )
            wrong = subprocess.run([str(executable)], capture_output=True, text=True, check=False)
            self.assertEqual(wrong.returncode, 1)
            self.assertTrue(alert_marker.is_file())

            alert_marker.unlink()
            picker.write_text(
                "#!/bin/sh\n"
                f"case \"$2\" in *'display alert'*) touch {shlex.quote(str(alert_marker))} ;; "
                "*) echo 'User canceled. (-128)' >&2; exit 1 ;; esac\n",
                encoding="utf-8",
            )
            canceled = subprocess.run([str(executable)], capture_output=True, text=True, check=False)
            self.assertEqual(canceled.returncode, 0)
            self.assertTrue(alert_marker.is_file())

    def test_app_is_visible_and_picker_does_not_activate_background_script(self) -> None:
        plist = ROOT / "launchers/Bounded Orchestrator.app/Contents/Info.plist"
        self.assertFalse(plistlib.loads(plist.read_bytes())["LSUIElement"])
        chosen = subprocess.CompletedProcess([], 0, stdout="/tmp/project folder/\n", stderr="")
        with patch.object(launcher.sys, "platform", "darwin"), patch.object(
            launcher.subprocess, "run", return_value=chosen
        ) as run:
            self.assertEqual(launcher.choose_project(), Path("/tmp/project folder/"))
        self.assertIn("choose folder", run.call_args.args[0][2])
        self.assertNotIn("activate", run.call_args.args[0][2])

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
