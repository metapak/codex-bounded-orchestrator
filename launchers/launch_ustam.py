#!/usr/bin/env python3
"""Native launcher for the bundled loopback hub; no project picker."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile


def worker_path(executable=None):
    executable = Path(executable or sys.executable).resolve()
    if sys.platform == 'darwin':
        return executable.parent.parent / 'Resources' / 'worker' / 'UstamWorker'
    return executable.parent / 'worker' / ('UstamWorker.exe' if os.name == 'nt' else 'UstamWorker')


def console_python(executable=None):
    executable = Path(executable or sys.executable)
    # Source compatibility can be started with pythonw by WScript. Its
    # adapter children require the console interpreter, hidden at creation.
    return str(executable.with_name('python.exe') if executable.name.lower() == 'pythonw.exe' else executable)


def hidden_process_options():
    if os.name != 'nt':
        return {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {'startupinfo': startup, 'creationflags': subprocess.CREATE_NO_WINDOW}


def alert(message):
    if sys.platform == 'darwin':
        subprocess.run(['/usr/bin/osascript', '-e', 'on run argv\ndisplay alert "Ustam" message (item 1 of argv) as warning\nend run', message], check=False)
    elif os.name == 'nt':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, 'Ustam', 0x30)
    else:
        print(message, file=sys.stderr)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    frozen = getattr(sys, 'frozen', False)
    command = [str(worker_path()), *argv] if frozen else [console_python(), '-m', 'ustam', *argv]
    if frozen and not Path(command[0]).is_file():
        alert('Ustam runtime is missing. Extract the complete native download and open Ustam again.')
        return 1
    # Keep a bounded diagnostic on disk, never pipe server output to a windowed
    # executable: PyInstaller windowed builds may have sys.stdout=None.
    with tempfile.TemporaryFile() as log:
        try:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT, cwd=None if frozen else Path(__file__).resolve().parents[1],
                                       **hidden_process_options())
            result = process.wait()
        except OSError as exc:
            alert(str(exc))
            return 1
        if result:
            log.seek(0)
            detail = log.read().decode('utf-8', 'replace')[-1800:]
            alert('Ustam could not start.\n' + detail)
        return result

if __name__ == '__main__':
    raise SystemExit(main())
