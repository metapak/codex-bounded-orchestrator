"""Bounded directory discovery without executing or importing project code."""
import hashlib
import os
from pathlib import Path

IGNORED = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', '.next', '.cache', 'vendor'}
MARKERS = {'pyproject.toml', 'package.json', 'Cargo.toml', 'go.mod', 'requirements.txt', 'Makefile', '.git'}

def canonical(path):
    if not isinstance(path, str) or not path.strip() or '\x00' in path:
        raise ValueError('A directory path is required')
    target = Path(path).expanduser().resolve(strict=True)
    if not target.is_dir():
        raise ValueError('Project path must be a directory')
    return str(target)

def project(path):
    path = canonical(path)
    return {'id': hashlib.sha256(os.path.normcase(path).encode()).hexdigest()[:24], 'path': path, 'name': Path(path).name, 'is_git': (Path(path) / '.git').exists()}

def discover(roots, max_depth=3, max_directories=2000):
    found = {}
    count = 0
    for raw in roots:
        root = canonical(raw)
        for directory, children, files in os.walk(root, followlinks=False):
            count += 1
            if count > max_directories:
                raise ValueError('Discovery limit exceeded; choose a narrower root')
            resolved = Path(directory).resolve()
            if not resolved.is_relative_to(root):
                children[:] = []
                continue
            depth = len(Path(directory).relative_to(root).parts)
            children[:] = sorted(child for child in children if child not in IGNORED and not child.startswith('.') and not (Path(directory) / child).is_symlink()) if depth < max_depth else []
            names = set(files) | set(os.listdir(directory))
            if names & MARKERS:
                entry = project(directory)
                found[entry['id']] = entry
    return sorted(found.values(), key=lambda item: item['path'])


def pick_directory(timeout=120):
    """Open a fixed native folder dialog; no browser input enters a command."""
    import shutil
    import subprocess
    import sys
    if sys.platform == 'darwin':
        command = ['/usr/bin/osascript', '-e', 'POSIX path of (choose folder with prompt "Choose an Ustam project or discovery root")']
    elif os.name == 'nt':
        script = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Add-Type -AssemblyName System.Windows.Forms; $ustamPicker=New-Object System.Windows.Forms.FolderBrowserDialog; $ustamPicker.Description='Choose an Ustam project or discovery root'; if($ustamPicker.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){[Console]::WriteLine($ustamPicker.SelectedPath)}; $ustamPicker.Dispose()"
        command = ['powershell.exe', '-NoProfile', '-NonInteractive', '-STA', '-Command', script]
    else:
        executable = shutil.which('zenity')
        if not executable:
            raise ValueError('Native folder picker is unavailable; enter a folder path manually')
        command = [executable, '--file-selection', '--directory', '--title=Choose an Ustam project or discovery root']
    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError('Folder picker is unavailable or timed out; enter a folder path manually') from error
    if completed.returncode:
        if (sys.platform == 'darwin' and '-128' in completed.stderr) or (sys.platform != 'darwin' and completed.returncode == 1):
            return None
        raise ValueError('Folder picker could not open; enter a folder path manually')
    value = completed.stdout.strip()
    return canonical(value) if value else None
