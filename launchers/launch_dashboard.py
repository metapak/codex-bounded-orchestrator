#!/usr/bin/env python3
"""Open the local setup console from a double-click launcher."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent


def alert(title: str, message: str) -> None:
    if sys.platform == "darwin":
        script = (
            "on run argv\n"
            "display alert (item 1 of argv) message (item 2 of argv) as warning\n"
            "end run"
        )
        subprocess.run(["/usr/bin/osascript", "-e", script, title, message], check=False)
    elif os.name == "nt":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, 0x30)
    else:
        print(f"{title}: {message}", file=sys.stderr)


def choose_project() -> Path | None:
    if sys.platform != "darwin":
        alert("Choose a project", "Open this launcher with a project folder selected.")
        return None
    script = (
        'tell current application to activate\n'
        'POSIX path of (choose folder with prompt "Choose the project folder to configure")'
    )
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", script], capture_output=True, text=True, check=False
    )
    if result.returncode:
        if "-128" not in result.stderr:
            alert("Could not choose a folder", result.stderr.strip() or "Please try again.")
        return None
    return Path(result.stdout.removesuffix("\n"))


def main() -> int:
    if len(sys.argv) > 2:
        alert("Invalid launch", "Open the launcher again and choose one project folder.")
        return 2
    entry = ROOT / "scripts" / "dashboard.py"
    if not entry.is_file():
        entry = ROOT / "scripts" / "configure.py"
    if not entry.is_file():
        alert("Setup console unavailable", "The launcher must stay inside its distribution folder.")
        return 1
    if sys.version_info < (3, 11):
        alert("Python update needed", "Install Python 3.11 or newer, then open this launcher again.")
        return 1
    project = Path(sys.argv[1]) if len(sys.argv) == 2 else choose_project()
    if project is None:
        return 0
    project = project.expanduser().resolve()
    if not project.is_dir():
        alert("Project folder unavailable", "Choose an existing local project folder.")
        return 1
    try:
        with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as log:
            result = subprocess.run(
                [sys.executable, str(entry), str(project), "--port", "0"],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
            if result.returncode:
                log.seek(0)
                detail = log.read()[-1800:].strip()
                alert(
                    "Setup console could not start",
                    detail or "Check that this distribution and project folder are valid.",
                )
            return result.returncode
    except OSError as exc:
        alert("Setup console could not start", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
