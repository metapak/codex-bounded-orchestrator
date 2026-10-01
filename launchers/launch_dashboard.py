#!/usr/bin/env python3
"""Open the local setup console from a double-click launcher."""

from __future__ import annotations

import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import time


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
    if os.environ.get("BO_LANG") == "tr":
        script = (
            'display dialog "Şimdi Codex ile üzerinde çalıştığınız kendi proje klasörünüzü seçin. Bu, kodlarınızın bulunduğu Git klasörüdür." & return & return & '
            '"Kurulum ayarları bu projeye yazılacak. Sonra tarayıcı açılacak: önerilen ekibi inceleyin, değişiklikleri kontrol edin ve Kur düğmesine basın." '
            'buttons {"Vazgeç", "Devam"} default button "Devam" cancel button "Vazgeç" with title "2/2 · Codex projeniz"\n'
            'POSIX path of (choose folder with prompt "2/2 · Codex projenizin klasörünü seçin" default location (path to home folder))'
        )
    else:
        script = (
            'display dialog "Now choose the Git project where you work with Codex." & return & return & '
            '"Setup settings will be saved in this project. Then the browser opens: review the suggested team, check changes, and click Install." '
            'buttons {"Cancel", "Continue"} default button "Continue" cancel button "Cancel" with title "2/2 · Your Codex project"\n'
            'POSIX path of (choose folder with prompt "2/2 · Select your Codex project folder" default location (path to home folder))'
        )
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", script], capture_output=True, text=True, check=False
    )
    if result.returncode:
        if "-128" not in result.stderr:
            alert("Could not choose a folder", result.stderr.strip() or "Please try again.")
        return None
    return Path(result.stdout.removesuffix("\n"))


def run_mac_console(entry: Path, project: Path) -> int:
    """Wait for the local server before asking Launch Services to show it."""
    with tempfile.TemporaryDirectory() as directory:
        log_path = Path(directory) / "console.log"
        with log_path.open("w", encoding="utf-8") as log:
            server = subprocess.Popen(
                [sys.executable, str(entry), str(project), "--port", "0", "--no-browser"],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        deadline = time.monotonic() + 15
        origin = None
        while time.monotonic() < deadline and server.poll() is None:
            match = re.search(r"Codex yerel konsol: (http://127\.0\.0\.1:\d+)", log_path.read_text(encoding="utf-8"))
            if match:
                origin = match.group(1)
                break
            time.sleep(0.1)
        if origin is None:
            if server.poll() is None:
                server.terminate()
            server.wait(timeout=5)
            detail = log_path.read_text(encoding="utf-8")[-1800:].strip()
            alert("Setup console could not start", detail or "The local server did not become ready.")
            return 1
        opened = subprocess.run(["/usr/bin/open", origin], capture_output=True, text=True, check=False)
        if opened.returncode:
            detail = opened.stderr.strip()
            alert("Browser could not open", f"Open {origin} in your browser. {detail}".strip())
            server.wait()
            return 1
        result = server.wait()
        if result:
            detail = log_path.read_text(encoding="utf-8")[-1800:].strip()
            alert("Setup console stopped", detail or "The local server stopped unexpectedly.")
        return result


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
        if sys.platform == "darwin":
            return run_mac_console(entry, project)
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
