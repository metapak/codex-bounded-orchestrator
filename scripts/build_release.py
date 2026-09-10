#!/usr/bin/env python3
"""Build deterministic source, macOS, and Windows release ZIP files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
PROJECT_NAME = "codex-bounded-orchestrator"
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
EXECUTABLE_PATHS = {
    "setup.command",
    "scripts/install.sh",
    "scripts/install.py",
    "scripts/validate.py",
    "scripts/build_release.py",
    ".codex/tools/candidate.py",
    ".codex/tools/ledger.py",
    ".codex/tools/anthropic_mcp.py",
}
SKIP_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".DS_Store",
    "Thumbs.db",
}
SKIP_SUFFIXES = {".pyc", ".pyo", ".zip", ".bundle"}
WINDOWS_CRLF_SUFFIXES = {".ps1", ".cmd"}
REQUIRED_SOURCE_FILES = {
    ".codex/tools/anthropic_mcp.py",
    "docs/external-providers.md",
    "docs/external-providers.tr.md",
    "docs/release-v0.4.0.md",
    "docs/release-v0.4.0.tr.md",
    "docs/release-v0.4.1.md",
    "docs/release-v0.4.1.tr.md",
    "docs/profiles.md",
    "docs/profiles.tr.md",
    "tests/test_anthropic_bridge.py",
}

MAC_START = """Codex Bounded Orchestrator {version} - macOS\n\n1. Extract this ZIP completely.\n2. Double-click setup.command.\n3. Drag the target Git repository folder into Terminal.\n4. Choose balanced, quality, economy, or custom.\n5. Optionally configure the read-only Claude API proposal role.\n\nDetailed instructions: INSTALL-MACOS.md\n"""

WINDOWS_START = """Codex Bounded Orchestrator {version} - Windows\r\n\r\n1. Extract this ZIP completely.\r\n2. Double-click setup.cmd.\r\n3. Paste the target Git repository folder path.\r\n4. Choose balanced, quality, economy, or custom.\r\n5. Optionally configure the read-only Claude API proposal role.\r\n\r\nDetailed instructions: INSTALL-WINDOWS.md\r\n"""


class ReleaseError(RuntimeError):
    """Expected release-build failure."""


def version() -> str:
    value = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not value:
        raise ReleaseError("VERSION is empty.")
    return value


def should_skip(relative: Path) -> bool:
    if any(part in SKIP_NAMES for part in relative.parts):
        return True
    if relative.name == ".env" or relative.name.startswith(".env."):
        return True
    if relative.suffix.lower() in SKIP_SUFFIXES:
        return True
    if relative.as_posix().startswith(".codex/.bounded-orchestrator/backups/"):
        return True
    return False


def git_tracked_files() -> list[Path] | None:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        return None
    return [
        Path(os.fsdecode(item))
        for item in result.stdout.split(b"\0")
        if item
    ]


def source_files() -> list[Path]:
    tracked = git_tracked_files()
    if tracked is not None:
        candidates = tracked + [Path(item) for item in REQUIRED_SOURCE_FILES]
    else:
        candidates = [
            path.relative_to(ROOT)
            for path in ROOT.rglob("*")
            if path.is_file() and not path.is_symlink()
        ]

    files = [
        relative
        for relative in candidates
        if (ROOT / relative).is_file() and not should_skip(relative)
    ]
    return sorted(set(files), key=lambda item: item.as_posix())


def zip_info(archive_name: str, executable: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(archive_name, ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    mode = 0o755 if executable else 0o644
    info.external_attr = (mode & 0xFFFF) << 16
    return info


def normalized_bytes(path: Path, platform: str) -> bytes:
    data = path.read_bytes()
    if platform == "windows" and path.suffix.lower() in WINDOWS_CRLF_SUFFIXES:
        data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return data


def write_zip(
    destination: Path,
    files: Iterable[Path],
    platform: str,
    extra_files: dict[str, bytes] | None = None,
) -> None:
    prefix = f"{PROJECT_NAME}/"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in files:
            archive_name = prefix + relative.as_posix()
            archive.writestr(
                zip_info(archive_name, relative.as_posix() in EXECUTABLE_PATHS),
                normalized_bytes(ROOT / relative, platform),
            )
        for name, data in sorted((extra_files or {}).items()):
            archive.writestr(zip_info(prefix + name), data)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str | None:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def build(output_dir: Path) -> dict[str, object]:
    current_version = version()
    files = source_files()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    artifacts = {
        "source": output_dir / f"{PROJECT_NAME}-v{current_version}-source.zip",
        "macos": output_dir / f"{PROJECT_NAME}-v{current_version}-macos.zip",
        "windows": output_dir / f"{PROJECT_NAME}-v{current_version}-windows.zip",
    }

    write_zip(artifacts["source"], files, "source")
    write_zip(
        artifacts["macos"],
        files,
        "macos",
        {
            "START-HERE-MACOS.txt": MAC_START.format(version=current_version).encode(
                "utf-8"
            )
        },
    )
    write_zip(
        artifacts["windows"],
        files,
        "windows",
        {
            "START-HERE-WINDOWS.txt": WINDOWS_START.format(
                version=current_version
            ).encode("utf-8")
        },
    )

    return {
        "project": PROJECT_NAME,
        "version": current_version,
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "commit": git_commit(),
        "source_file_count": len(files),
        "artifacts": {
            key: {
                "path": str(path),
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
            for key, path in artifacts.items()
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "dist",
        help="Directory for release ZIP files. Default: ./dist",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable build metadata.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print("release error: Python 3.11 or newer is required.", file=sys.stderr)
        return 2

    args = build_parser().parse_args(argv)
    try:
        metadata = build(args.output_dir)
    except (OSError, ReleaseError) as exc:
        print(f"release error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(metadata, indent=2, sort_keys=True))
    else:
        print(f"Built Codex Bounded Orchestrator v{metadata['version']}:")
        for item in metadata["artifacts"].values():
            print(f"  {item['path']}  sha256={item['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
