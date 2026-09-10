#!/usr/bin/env python3
"""Safely install Codex Bounded Orchestrator into an existing repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
START_MARKER = "<!-- codex-bounded-orchestrator:start -->"
END_MARKER = "<!-- codex-bounded-orchestrator:end -->"
MANIFEST_RELATIVE = Path(".codex/.bounded-orchestrator/install.json")
BACKUP_RELATIVE = Path(".codex/.bounded-orchestrator/backups")
CONFIG_EXAMPLE_RELATIVE = Path(".codex/bounded-orchestrator.config.example.toml")

MANAGED_RELATIVE_FILES = (
    Path(".codex/agents/fast-lookup.toml"),
    Path(".codex/agents/explorer.toml"),
    Path(".codex/agents/researcher.toml"),
    Path(".codex/agents/implementer.toml"),
    Path(".codex/agents/verifier.toml"),
    Path(".codex/agents/failure-analyst.toml"),
    Path(".codex/agents/qa-operator.toml"),
    Path(".codex/agents/reviewer.toml"),
    Path(".codex/agents/advisor.toml"),
    Path(".codex/tools/candidate.py"),
    Path(".codex/tools/ledger.py"),
    Path(".codex/.candidate/.gitignore"),
    Path(".codex/.bounded-orchestrator/.gitignore"),
    Path(".agents/skills/bounded-orchestrator/SKILL.md"),
    Path(".agents/skills/bounded-orchestrator/references/task-contract.md"),
    Path(".agents/skills/bounded-orchestrator/references/review-protocol.md"),
    Path(".agents/skills/bounded-orchestrator/references/escalation.md"),
    Path(".agents/skills/bounded-orchestrator-ui-design/SKILL.md"),
    Path(".agents/skills/bounded-orchestrator-security-review/SKILL.md"),
)


class InstallError(RuntimeError):
    """Expected installer failure."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def tool_version(root: Path) -> str:
    try:
        return (root / "VERSION").read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise InstallError("VERSION is missing from the installer repository.") from exc


def sha256_path(path: Path) -> str:
    if path.is_symlink():
        return hashlib.sha256(os.fsencode(os.readlink(path))).hexdigest()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def same_file(left: Path, right: Path) -> bool:
    if not left.exists() or not right.exists():
        return False
    if left.is_dir() or right.is_dir():
        return False
    return sha256_path(left) == sha256_path(right)


def load_manifest(target: Path) -> dict[str, Any]:
    path = target / MANIFEST_RELATIVE
    if not path.exists():
        return {
            "schema": SCHEMA_VERSION,
            "files": {},
            "agents_block": False,
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"Cannot read install manifest: {path}") from exc
    if data.get("schema") != SCHEMA_VERSION or not isinstance(data.get("files"), dict):
        raise InstallError(f"Unsupported install manifest: {path}")
    return data


def atomic_write_text(path: Path, text: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_copy(source: Path, destination: Path, dry_run: bool) -> None:
    if dry_run:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def timestamp_for_path() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backup_file(target_root: Path, path: Path, dry_run: bool) -> Path:
    try:
        relative = path.relative_to(target_root)
    except ValueError as exc:
        raise InstallError(f"Refusing to back up a path outside the target: {path}") from exc

    backup = target_root / BACKUP_RELATIVE / timestamp_for_path() / relative
    suffix = 1
    original = backup
    while backup.exists():
        backup = original.with_name(f"{original.name}.{suffix}")
        suffix += 1

    if not dry_run:
        backup.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            backup.symlink_to(os.readlink(path))
        else:
            shutil.copy2(path, backup)
    return backup


def validate_target(target: Path, root: Path) -> Path:
    target = target.expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise InstallError(f"Target must be an existing directory: {target}")
    if target == root:
        raise InstallError("Target repository must be different from the installer repository.")
    return target


def profile_source(root: Path, profile: str) -> Path:
    if profile == "astra":
        return root / ".codex/config.toml"
    if profile == "sol":
        return root / "presets/sol-owner.config.toml"
    raise InstallError(f"Unsupported profile: {profile}")


def ensure_source_files(root: Path, profile: str) -> None:
    required = [root / path for path in MANAGED_RELATIVE_FILES]
    required.extend(
        [
            profile_source(root, profile),
            root / "templates/AGENTS.block.md",
            root / "VERSION",
        ]
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise InstallError("Installer source is incomplete:\n  - " + "\n  - ".join(missing))


def previous_owned(manifest: dict[str, Any], relative: Path) -> bool:
    entry = manifest.get("files", {}).get(relative.as_posix(), {})
    return bool(entry.get("owned", False))


def remember_file(
    manifest: dict[str, Any], relative: Path, destination: Path, owned: bool
) -> None:
    manifest.setdefault("files", {})[relative.as_posix()] = {
        "sha256": sha256_path(destination),
        "owned": owned,
    }


def install_file(
    *,
    root: Path,
    target: Path,
    relative: Path,
    manifest: dict[str, Any],
    force: bool,
    dry_run: bool,
    messages: list[str],
) -> None:
    source = root / relative
    destination = target / relative

    if destination.exists() and destination.is_dir():
        messages.append(f"SKIP {relative}: destination is a directory")
        return

    if not destination.exists() and not destination.is_symlink():
        messages.append(f"INSTALL {relative}")
        atomic_copy(source, destination, dry_run)
        if not dry_run:
            remember_file(manifest, relative, destination, True)
        return

    if same_file(source, destination):
        owned = previous_owned(manifest, relative)
        messages.append(f"UNCHANGED {relative}")
        if not dry_run:
            remember_file(manifest, relative, destination, owned)
        return

    if not force:
        messages.append(f"SKIP {relative}: existing file differs; use --force to replace")
        return

    backup = backup_file(target, destination, dry_run)
    messages.append(f"BACKUP {relative} -> {backup.relative_to(target)}")
    messages.append(f"REPLACE {relative}")
    atomic_copy(source, destination, dry_run)
    if not dry_run:
        remember_file(manifest, relative, destination, True)


def install_config(
    *,
    root: Path,
    target: Path,
    profile: str,
    manifest: dict[str, Any],
    force_config: bool,
    dry_run: bool,
    messages: list[str],
) -> None:
    source = profile_source(root, profile)
    relative = Path(".codex/config.toml")
    destination = target / relative

    if destination.exists() and destination.is_dir():
        messages.append(f"SKIP {relative}: destination is a directory")
        return

    if not destination.exists() and not destination.is_symlink():
        messages.append(f"INSTALL {relative} ({profile} owner profile)")
        atomic_copy(source, destination, dry_run)
        if not dry_run:
            remember_file(manifest, relative, destination, True)
        return

    if same_file(source, destination):
        owned = previous_owned(manifest, relative)
        messages.append(f"UNCHANGED {relative}")
        if not dry_run:
            remember_file(manifest, relative, destination, owned)
        return

    if force_config:
        backup = backup_file(target, destination, dry_run)
        messages.append(f"BACKUP {relative} -> {backup.relative_to(target)}")
        messages.append(f"REPLACE {relative} ({profile} owner profile)")
        atomic_copy(source, destination, dry_run)
        if not dry_run:
            remember_file(manifest, relative, destination, True)
        return

    example = target / CONFIG_EXAMPLE_RELATIVE
    if example.exists() and example.is_dir():
        messages.append(
            f"SKIP {CONFIG_EXAMPLE_RELATIVE}: destination is a directory"
        )
        return

    example_was_absent = not example.exists() and not example.is_symlink()
    if example_was_absent or same_file(source, example):
        action = "WRITE" if example_was_absent else "UNCHANGED"
        messages.append(
            f"PRESERVE {relative}; {action} {CONFIG_EXAMPLE_RELATIVE} for manual merge"
        )
        if example_was_absent:
            atomic_copy(source, example, dry_run)
        if not dry_run:
            owned = True if example_was_absent else previous_owned(
                manifest, CONFIG_EXAMPLE_RELATIVE
            )
            remember_file(manifest, CONFIG_EXAMPLE_RELATIVE, example, owned)
        return

    text = example.read_text(encoding="utf-8", errors="replace")
    if "managed-by: codex-bounded-orchestrator" in text:
        backup = backup_file(target, example, dry_run)
        messages.append(
            f"BACKUP {CONFIG_EXAMPLE_RELATIVE} -> {backup.relative_to(target)}"
        )
        messages.append(
            f"PRESERVE {relative}; REFRESH {CONFIG_EXAMPLE_RELATIVE} for manual merge"
        )
        atomic_copy(source, example, dry_run)
        if not dry_run:
            remember_file(manifest, CONFIG_EXAMPLE_RELATIVE, example, True)
        return

    messages.append(
        f"PRESERVE {relative}; SKIP {CONFIG_EXAMPLE_RELATIVE} because it also differs"
    )


def normalize_block(raw: str) -> str:
    text = raw.strip()
    if not text.startswith(START_MARKER) or not text.endswith(END_MARKER):
        raise InstallError("templates/AGENTS.block.md is missing managed markers.")
    return text


def merge_agents_text(existing: str, block: str) -> str:
    start = existing.find(START_MARKER)
    end = existing.find(END_MARKER)

    if (start == -1) != (end == -1):
        raise InstallError("AGENTS.md contains only one bounded-orchestrator marker.")

    if start != -1:
        if end < start:
            raise InstallError("AGENTS.md managed markers are in the wrong order.")
        end += len(END_MARKER)
        merged = existing[:start].rstrip() + "\n\n" + block + existing[end:]
        return merged.strip() + "\n"

    if not existing.strip():
        return block + "\n"
    return existing.rstrip() + "\n\n" + block + "\n"


def install_agents_block(
    *,
    root: Path,
    target: Path,
    manifest: dict[str, Any],
    dry_run: bool,
    messages: list[str],
) -> None:
    path = target / "AGENTS.md"
    if path.exists() and path.is_dir():
        messages.append("SKIP AGENTS.md: destination is a directory")
        return
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    block = normalize_block((root / "templates/AGENTS.block.md").read_text(encoding="utf-8"))
    merged = merge_agents_text(existing, block)
    if existing == merged:
        messages.append("UNCHANGED AGENTS.md managed block")
    else:
        action = "UPDATE" if path.exists() else "CREATE"
        messages.append(f"{action} AGENTS.md managed block")
        atomic_write_text(path, merged, dry_run)
    if not dry_run:
        manifest["agents_block"] = True


def write_manifest(
    *,
    root: Path,
    target: Path,
    profile: str,
    manifest: dict[str, Any],
    dry_run: bool,
) -> None:
    manifest.update(
        {
            "schema": SCHEMA_VERSION,
            "tool_version": tool_version(root),
            "profile": profile,
            "installed_utc": utc_now(),
        }
    )
    if dry_run:
        return
    path = target / MANIFEST_RELATIVE
    atomic_write_text(
        path,
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        False,
    )


def remove_managed_block(target: Path, dry_run: bool, messages: list[str]) -> None:
    path = target / "AGENTS.md"
    if not path.exists() or path.is_dir():
        return
    existing = path.read_text(encoding="utf-8")
    start = existing.find(START_MARKER)
    end = existing.find(END_MARKER)
    if start == -1 and end == -1:
        return
    if start == -1 or end == -1 or end < start:
        messages.append("KEEP AGENTS.md: malformed managed markers")
        return
    end += len(END_MARKER)
    updated = (existing[:start].rstrip() + "\n\n" + existing[end:].lstrip()).strip()
    if updated:
        updated += "\n"
        messages.append("REMOVE AGENTS.md managed block")
        atomic_write_text(path, updated, dry_run)
    else:
        messages.append("REMOVE empty AGENTS.md")
        if not dry_run:
            path.unlink()


def prune_empty_directories(target: Path, relative_files: Iterable[Path]) -> None:
    candidates: set[Path] = set()
    for relative in relative_files:
        parent = (target / relative).parent
        while parent != target and target in parent.parents:
            candidates.add(parent)
            parent = parent.parent
    for directory in sorted(candidates, key=lambda item: len(item.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def uninstall(target: Path, dry_run: bool) -> int:
    messages: list[str] = []
    manifest_path = target / MANIFEST_RELATIVE
    manifest = load_manifest(target)
    files = manifest.get("files", {})

    for relative_text, entry in sorted(files.items(), reverse=True):
        relative = Path(relative_text)
        destination = target / relative
        if not entry.get("owned", False):
            messages.append(f"KEEP {relative}: pre-existing file was not owned")
            continue
        if not destination.exists() and not destination.is_symlink():
            continue
        if destination.is_dir():
            messages.append(f"KEEP {relative}: path became a directory")
            continue
        expected = entry.get("sha256")
        actual = sha256_path(destination)
        if expected != actual:
            messages.append(f"KEEP {relative}: modified after installation")
            continue
        messages.append(f"REMOVE {relative}")
        if not dry_run:
            destination.unlink()

    remove_managed_block(target, dry_run, messages)

    if manifest_path.exists():
        messages.append(f"REMOVE {MANIFEST_RELATIVE}")
        if not dry_run:
            manifest_path.unlink()

    if not dry_run:
        prune_empty_directories(target, [Path(item) for item in files])

    print("\n".join(messages) if messages else "Nothing managed was found.")
    return 0


def install(
    *,
    target: Path,
    profile: str,
    force: bool,
    force_config: bool,
    dry_run: bool,
) -> int:
    root = source_root()
    ensure_source_files(root, profile)
    target = validate_target(target, root)
    manifest = load_manifest(target)
    messages: list[str] = []

    runtime_ignore = Path(".codex/.bounded-orchestrator/.gitignore")
    runtime_destination = target / runtime_ignore
    runtime_source = root / runtime_ignore
    if (
        (runtime_destination.exists() or runtime_destination.is_symlink())
        and not same_file(runtime_source, runtime_destination)
    ):
        raise InstallError(
            "Reserved runtime path conflicts with this installer: "
            f"{runtime_destination}. Move or reconcile it before installation."
        )

    # Install the runtime ignore before any operation can create backups or a
    # manifest, so interrupted installs do not expose local state to Git.
    install_file(
        root=root,
        target=target,
        relative=runtime_ignore,
        manifest=manifest,
        force=False,
        dry_run=dry_run,
        messages=messages,
    )

    install_config(
        root=root,
        target=target,
        profile=profile,
        manifest=manifest,
        force_config=force_config,
        dry_run=dry_run,
        messages=messages,
    )

    for relative in MANAGED_RELATIVE_FILES:
        if relative == runtime_ignore:
            continue
        install_file(
            root=root,
            target=target,
            relative=relative,
            manifest=manifest,
            force=force,
            dry_run=dry_run,
            messages=messages,
        )

    install_agents_block(
        root=root,
        target=target,
        manifest=manifest,
        dry_run=dry_run,
        messages=messages,
    )
    write_manifest(
        root=root,
        target=target,
        profile=profile,
        manifest=manifest,
        dry_run=dry_run,
    )

    heading = "DRY RUN" if dry_run else "INSTALL COMPLETE"
    print(heading)
    print("\n".join(messages))
    print(f"Target: {target}")
    print(f"Profile: {profile}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install the bounded Codex multi-agent architecture into a repository."
    )
    parser.add_argument("target", type=Path, help="Existing target repository directory.")
    parser.add_argument(
        "--profile",
        choices=("astra", "sol"),
        default="astra",
        help="Root owner profile. Default: Astra medium.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Back up and replace conflicting managed agent, skill, or tool files.",
    )
    parser.add_argument(
        "--force-config",
        action="store_true",
        help="Back up and replace an existing .codex/config.toml.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove only files owned by this installer and the managed AGENTS.md block.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print("install error: Python 3.11 or newer is required.", file=sys.stderr)
        return 2

    args = build_parser().parse_args(argv)
    try:
        root = source_root()
        target = validate_target(args.target, root)
        if args.uninstall:
            return uninstall(target, args.dry_run)
        return install(
            target=target,
            profile=args.profile,
            force=args.force,
            force_config=args.force_config,
            dry_run=args.dry_run,
        )
    except (InstallError, OSError) as exc:
        print(f"install error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
