from __future__ import annotations

import importlib.util
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("launch_dashboard", ROOT / "launchers/launch_dashboard.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class MacLauncherTests(unittest.TestCase):
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
            entry.write_text(
                "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
                "class Handler(BaseHTTPRequestHandler):\n"
                "    def do_GET(self):\n"
                "        self.send_response(200)\n"
                "        self.end_headers()\n"
                "        self.wfile.write(b'live')\n"
                "server = HTTPServer(('127.0.0.1', 0), Handler)\n"
                "print('Codex yerel konsol: http://127.0.0.1:' + str(server.server_port), flush=True)\n"
                "server.handle_request()\n",
                encoding="utf-8",
            )
            failure = subprocess.CompletedProcess([], 1, stderr="Launch Services error")
            def inspect_alert(_title: str, message: str) -> None:
                address = message.split(" ")[1]
                with urlopen(address, timeout=2) as response:
                    self.assertEqual(response.read(), b"live")

            with patch.object(launcher.subprocess, "run", return_value=failure), patch.object(
                launcher, "alert", side_effect=inspect_alert
            ) as alert:
                self.assertEqual(launcher.run_mac_console(entry, Path(directory)), 1)
            self.assertIn("Open http://127.0.0.1:", alert.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
