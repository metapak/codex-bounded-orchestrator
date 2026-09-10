#!/usr/bin/env python3
"""Safely install Codex Bounded Orchestrator into an existing repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
CONFIG_RELATIVE = Path(".codex/config.toml")
EXTERNAL_BRIDGE_RELATIVE = Path(".codex/tools/anthropic_mcp.py")

ROLE_FILES = {
    "fast_lookup": Path(".codex/agents/fast-lookup.toml"),
    "explorer": Path(".codex/agents/explorer.toml"),
    "researcher": Path(".codex/agents/researcher.toml"),
    "implementer": Path(".codex/agents/implementer.toml"),
    "verifier": Path(".codex/agents/verifier.toml"),
    "failure_analyst": Path(".codex/agents/failure-analyst.toml"),
    "qa_operator": Path(".codex/agents/qa-operator.toml"),
    "reviewer": Path(".codex/agents/reviewer.toml"),
    "advisor": Path(".codex/agents/advisor.toml"),
}
ALL_ROLES = ("owner", *ROLE_FILES)
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")

BALANCED_PROFILE = {
    "owner": ("gpt-6-astra", "medium"),
    "fast_lookup": ("gpt-5.6-luna", "medium"),
    "explorer": ("gpt-5.6-terra", "medium"),
    "researcher": ("gpt-5.6-terra", "medium"),
    "implementer": ("gpt-5.6-sol", "high"),
    "verifier": ("gpt-5.6-terra", "high"),
    "failure_analyst": ("gpt-5.6-sol", "high"),
    "qa_operator": ("gpt-5.6-sol", "high"),
    "reviewer": ("gpt-6-astra", "medium"),
    "advisor": ("gpt-6-astra", "xhigh"),
}
PRESETS = {
    "balanced": BALANCED_PROFILE,
    "quality": {
        **BALANCED_PROFILE,
        "owner": ("gpt-6-astra", "high"),
        "explorer": ("gpt-6-astra", "high"),
        "researcher": ("gpt-6-astra", "high"),
        "implementer": ("gpt-6-astra", "high"),
        "verifier": ("gpt-6-astra", "high"),
        "failure_analyst": ("gpt-6-astra", "high"),
        "qa_operator": ("gpt-6-astra", "high"),
        "reviewer": ("gpt-6-astra", "xhigh"),
        "advisor": ("gpt-6-astra", "max"),
    },
    "economy": {
        **BALANCED_PROFILE,
        "owner": ("gpt-5.6-terra", "medium"),
        "fast_lookup": ("gpt-5.6-luna", "low"),
        "explorer": ("gpt-5.6-luna", "medium"),
        "researcher": ("gpt-5.6-terra", "low"),
        "implementer": ("gpt-5.6-terra", "medium"),
        "verifier": ("gpt-5.6-terra", "medium"),
        "failure_analyst": ("gpt-5.6-terra", "medium"),
        "qa_operator": ("gpt-5.6-terra", "medium"),
        "reviewer": ("gpt-5.6-terra", "high"),
        "advisor": ("gpt-5.6-sol", "high"),
    },
    "custom": BALANCED_PROFILE,
}

MANAGED_RELATIVE_FILES = (
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

ALLOWED_MANIFEST_FILES = frozenset(
    (*MANAGED_RELATIVE_FILES, *ROLE_FILES.values(), CONFIG_RELATIVE,
     CONFIG_EXAMPLE_RELATIVE, EXTERNAL_BRIDGE_RELATIVE)
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


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def same_text(path: Path, text: str) -> bool:
    return path.is_file() and not path.is_symlink() and sha256_path(path) == sha256_text(text)


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


def ensure_source_files(root: Path) -> None:
    required = [root / path for path in (*MANAGED_RELATIVE_FILES, *ROLE_FILES.values())]
    required.extend(
        [
            root / CONFIG_RELATIVE,
            root / "presets/sol-owner.config.toml",
            root / EXTERNAL_BRIDGE_RELATIVE,
            root / "templates/AGENTS.block.md",
            root / "VERSION",
        ]
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise InstallError("Installer source is incomplete:\n  - " + "\n  - ".join(missing))


def parse_override(value: str, option: str) -> tuple[str, str]:
    if "=" not in value:
        raise InstallError(f"{option} must use ROLE=VALUE")
    role, selected = (part.strip() for part in value.split("=", 1))
    if role not in ALL_ROLES:
        raise InstallError(f"Unknown role {role!r} in {option}")
    if not selected:
        raise InstallError(f"Empty value for {role!r} in {option}")
    return role, selected


def resolve_profile(
    preset: str,
    legacy_profile: str | None,
    model_overrides: Iterable[str],
    effort_overrides: Iterable[str],
) -> dict[str, tuple[str, str]]:
    selected = {role: tuple(values) for role, values in PRESETS[preset].items()}
    if legacy_profile == "sol":
        selected["owner"] = ("gpt-5.6-sol", "high")
    elif legacy_profile == "astra":
        selected["owner"] = ("gpt-6-astra", "medium")
    for raw in model_overrides:
        role, model = parse_override(raw, "--role-model")
        selected[role] = (model, selected[role][1])
    for raw in effort_overrides:
        role, effort = parse_override(raw, "--role-effort")
        if effort not in EFFORTS:
            raise InstallError(
                f"Unsupported effort {effort!r}; choose one of: {', '.join(EFFORTS)}"
            )
        selected[role] = (selected[role][0], effort)
    return selected


def replace_toml_value(text: str, key: str, value: str) -> str:
    pattern = rf"(?m)^{re.escape(key)}\s*=\s*\"[^\"]*\"\s*$"
    updated, count = re.subn(pattern, f"{key} = {json.dumps(value)}", text, count=1)
    if count != 1:
        raise InstallError(f"Template is missing {key}")
    return updated


def render_role_config(root: Path, role: str, model: str, effort: str) -> str:
    text = (root / ROLE_FILES[role]).read_text(encoding="utf-8")
    text = replace_toml_value(text, "model", model)
    return replace_toml_value(text, "model_reasoning_effort", effort)


def render_root_config(
    root: Path,
    target: Path,
    settings: dict[str, tuple[str, str]],
    external_provider: str,
    external_model: str,
    external_effort: str,
) -> str:
    text = (root / CONFIG_RELATIVE).read_text(encoding="utf-8")
    text = replace_toml_value(text, "model", settings["owner"][0])
    text = replace_toml_value(text, "model_reasoning_effort", settings["owner"][1])
    text = replace_toml_value(text, "review_model", settings["reviewer"][0])
    text = replace_toml_value(text, "default_subagent_model", settings["explorer"][0])
    text = replace_toml_value(
        text, "default_subagent_reasoning_effort", settings["explorer"][1]
    )
    if external_provider == "anthropic":
        command = json.dumps(sys.executable)
        bridge = json.dumps(str((target / EXTERNAL_BRIDGE_RELATIVE).resolve()))
        text += (
            "\n# Optional read-only Anthropic bridge. The API key is inherited from "
            "ANTHROPIC_API_KEY and is never stored here.\n"
            "[mcp_servers.anthropic_claude]\n"
            f"command = {command}\n"
            f"args = [{bridge}, \"--model\", {json.dumps(external_model)}, "
            f"\"--effort\", {json.dumps(external_effort)}]\n"
            'env_vars = ["ANTHROPIC_API_KEY"]\n'
            "enabled = true\n"
            'enabled_tools = ["claude_implementation_proposal"]\n'
            "startup_timeout_sec = 10\n"
            "tool_timeout_sec = 180\n"
        )
    return text


def previous_owned(manifest: dict[str, Any], relative: Path) -> bool:
    entry = manifest.get("files", {}).get(relative.as_posix(), {})
    return bool(entry.get("owned", False))


def unchanged_owned(manifest: dict[str, Any], relative: Path, destination: Path) -> bool:
    entry = manifest.get("files", {}).get(relative.as_posix(), {})
    return bool(
        entry.get("owned", False)
        and isinstance(entry.get("sha256"), str)
        and (destination.exists() or destination.is_symlink())
        and not destination.is_dir()
        and sha256_path(destination) == entry["sha256"]
    )


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


def install_text_file(
    *,
    target: Path,
    relative: Path,
    text: str,
    manifest: dict[str, Any],
    force: bool,
    dry_run: bool,
    messages: list[str],
) -> None:
    destination = target / relative
    if destination.exists() and destination.is_dir():
        messages.append(f"SKIP {relative}: destination is a directory")
        return
    if not destination.exists() and not destination.is_symlink():
        messages.append(f"INSTALL {relative}")
        atomic_write_text(destination, text, dry_run)
        if not dry_run:
            remember_file(manifest, relative, destination, True)
        return
    if same_text(destination, text):
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
    atomic_write_text(destination, text, dry_run)
    if not dry_run:
        remember_file(manifest, relative, destination, True)


def install_config(
    *,
    target: Path,
    config_text: str,
    preset: str,
    manifest: dict[str, Any],
    force_config: bool,
    dry_run: bool,
    messages: list[str],
) -> None:
    relative = CONFIG_RELATIVE
    destination = target / relative

    if destination.exists() and destination.is_dir():
        messages.append(f"SKIP {relative}: destination is a directory")
        return

    if not destination.exists() and not destination.is_symlink():
        messages.append(f"INSTALL {relative} ({preset} preset)")
        atomic_write_text(destination, config_text, dry_run)
        if not dry_run:
            remember_file(manifest, relative, destination, True)
        return

    if same_text(destination, config_text):
        owned = previous_owned(manifest, relative)
        messages.append(f"UNCHANGED {relative}")
        if not dry_run:
            remember_file(manifest, relative, destination, owned)
        return

    if unchanged_owned(manifest, relative, destination):
        messages.append(f"UPDATE {relative} ({preset} preset; installer-owned)")
        atomic_write_text(destination, config_text, dry_run)
        if not dry_run:
            remember_file(manifest, relative, destination, True)
        return

    if force_config:
        backup = backup_file(target, destination, dry_run)
        messages.append(f"BACKUP {relative} -> {backup.relative_to(target)}")
        messages.append(f"REPLACE {relative} ({preset} preset)")
        atomic_write_text(destination, config_text, dry_run)
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
    if example_was_absent or same_text(example, config_text):
        action = "WRITE" if example_was_absent else "UNCHANGED"
        messages.append(
            f"PRESERVE {relative}; {action} {CONFIG_EXAMPLE_RELATIVE} for manual merge"
        )
        if example_was_absent:
            atomic_write_text(example, config_text, dry_run)
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
        atomic_write_text(example, config_text, dry_run)
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
    preset: str,
    settings: dict[str, tuple[str, str]],
    external_provider: str,
    external_model: str,
    external_effort: str,
    manifest: dict[str, Any],
    dry_run: bool,
) -> None:
    manifest.update(
        {
            "schema": SCHEMA_VERSION,
            "tool_version": tool_version(root),
            "profile": "sol" if settings["owner"] == ("gpt-5.6-sol", "high") else "astra",
            "preset": preset,
            "role_settings": {
                role: {"model": model, "effort": effort}
                for role, (model, effort) in settings.items()
            },
            "external_provider": external_provider,
            "external_model": external_model if external_provider != "none" else None,
            "external_effort": external_effort if external_provider != "none" else None,
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


def safe_manifest_relative(value: str) -> Path | None:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or relative not in ALLOWED_MANIFEST_FILES:
        return None
    return relative


def uninstall(target: Path, dry_run: bool) -> int:
    messages: list[str] = []
    manifest_path = target / MANIFEST_RELATIVE
    manifest = load_manifest(target)
    files = manifest.get("files", {})

    for relative_text, entry in sorted(files.items(), reverse=True):
        relative = safe_manifest_relative(relative_text)
        if relative is None:
            messages.append(f"KEEP invalid manifest path: {relative_text}")
            continue
        if not isinstance(entry, dict):
            messages.append(f"KEEP {relative}: invalid manifest entry")
            continue
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
        prune_empty_directories(
            target,
            [relative for item in files if (relative := safe_manifest_relative(item))],
        )

    print("\n".join(messages) if messages else "Nothing managed was found.")
    return 0


def install(
    *,
    target: Path,
    preset: str,
    settings: dict[str, tuple[str, str]],
    external_provider: str,
    external_model: str,
    external_effort: str,
    force: bool,
    force_config: bool,
    dry_run: bool,
) -> int:
    root = source_root()
    ensure_source_files(root)
    target = validate_target(target, root)
    manifest = load_manifest(target)
    messages: list[str] = []
    config_text = render_root_config(
        root, target, settings, external_provider, external_model, external_effort
    )

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
        target=target,
        config_text=config_text,
        preset=preset,
        manifest=manifest,
        force_config=force_config,
        dry_run=dry_run,
        messages=messages,
    )

    for role, relative in ROLE_FILES.items():
        model, effort = settings[role]
        install_text_file(
            target=target,
            relative=relative,
            text=render_role_config(root, role, model, effort),
            manifest=manifest,
            force=force,
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

    if external_provider == "anthropic":
        install_file(
            root=root,
            target=target,
            relative=EXTERNAL_BRIDGE_RELATIVE,
            manifest=manifest,
            force=force,
            dry_run=dry_run,
            messages=messages,
        )
        if "ANTHROPIC_API_KEY" not in os.environ:
            messages.append(
                "NOTE ANTHROPIC_API_KEY is not set; export it before using the Claude tool"
            )
    else:
        bridge = target / EXTERNAL_BRIDGE_RELATIVE
        if unchanged_owned(manifest, EXTERNAL_BRIDGE_RELATIVE, bridge):
            messages.append(f"REMOVE {EXTERNAL_BRIDGE_RELATIVE} (external provider disabled)")
            if not dry_run:
                bridge.unlink()
                manifest.get("files", {}).pop(EXTERNAL_BRIDGE_RELATIVE.as_posix(), None)

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
        preset=preset,
        settings=settings,
        external_provider=external_provider,
        external_model=external_model,
        external_effort=external_effort,
        manifest=manifest,
        dry_run=dry_run,
    )

    heading = "DRY RUN" if dry_run else "INSTALL COMPLETE"
    print(heading)
    print("\n".join(messages))
    print(f"Target: {target}")
    print(f"Preset: {preset}")
    print(f"External provider: {external_provider}")
    return 0


def prompt_choice(prompt: str, choices: dict[str, str], default: str) -> str:
    while True:
        answer = input(prompt).strip() or default
        if answer in choices:
            return choices[answer]
        print("Geçersiz seçim / Invalid choice.")


def interactive_options(
    preset: str | None,
    model_overrides: list[str],
    effort_overrides: list[str],
    external_provider: str | None,
    external_model: str,
    external_effort: str,
) -> tuple[str, list[str], list[str], str, str, str]:
    print("\nKurulum profili / Installation profile:")
    print("  1) Dengeli / Balanced (önerilen / recommended)")
    print("  2) Yüksek kalite / Quality")
    print("  3) Ekonomik / Economy")
    print("  4) Özel / Custom")
    if preset is None:
        preset = prompt_choice("Seçim / Select [1]: ", {
            "1": "balanced", "2": "quality", "3": "economy", "4": "custom"
        }, "1")
    if preset == "custom":
        defaults = resolve_profile("balanced", None, model_overrides, effort_overrides)
        print("\nHer rol için model ve efor seçin. Boş bırakırsanız önerilen değer kullanılır.")
        print("Choose a model and effort per role. Press Return to keep the default.")
        for role in ALL_ROLES:
            model, effort = defaults[role]
            selected_model = input(f"  {role} model [{model}]: ").strip() or model
            while True:
                selected_effort = input(f"  {role} effort [{effort}]: ").strip() or effort
                if selected_effort in EFFORTS:
                    break
                print("  Geçersiz efor / Invalid effort: " + ", ".join(EFFORTS))
            model_overrides.append(f"{role}={selected_model}")
            effort_overrides.append(f"{role}={selected_effort}")

    if external_provider is None:
        answer = input(
            "\nClaude API üzerinden salt okunur öneri rolü eklensin mi? "
            "/ Add read-only Claude API proposal role? [y/N]: "
        ).strip().lower()
        external_provider = "anthropic" if answer in {"y", "yes", "e", "evet"} else "none"
    if external_provider == "anthropic":
        print("\nClaude modeli / Claude model:")
        print("  1) claude-sonnet-5 (dengeli / balanced)")
        print("  2) claude-opus-5 (yüksek kalite / quality)")
        print("  3) Özel model kimliği / Custom model ID")
        choice = prompt_choice("Seçim / Select [1]: ", {"1": "sonnet", "2": "opus", "3": "custom"}, "1")
        if choice == "sonnet":
            external_model = "claude-sonnet-5"
        elif choice == "opus":
            external_model = "claude-opus-5"
        else:
            external_model = input(f"Model ID [{external_model}]: ").strip() or external_model
        while True:
            value = input(f"Claude effort [{external_effort}]: ").strip() or external_effort
            if value in {"low", "medium", "high", "xhigh", "max"}:
                external_effort = value
                break
            print("Geçersiz efor / Invalid effort: low, medium, high, xhigh, max")
    return (
        preset, model_overrides, effort_overrides, external_provider,
        external_model, external_effort,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install the bounded Codex multi-agent architecture into a repository."
    )
    parser.add_argument("target", type=Path, help="Existing target repository directory.")
    parser.add_argument(
        "--profile",
        choices=("astra", "sol"),
        default=None,
        help="Legacy root-owner switch kept for compatibility (astra or sol).",
    )
    parser.add_argument(
        "--preset",
        choices=tuple(PRESETS),
        default=None,
        help="Prepared routing preset. Non-interactive default: balanced.",
    )
    parser.add_argument(
        "--role-model",
        action="append",
        default=[],
        metavar="ROLE=MODEL",
        help="Override a role model; repeat for multiple roles.",
    )
    parser.add_argument(
        "--role-effort",
        action="append",
        default=[],
        metavar="ROLE=EFFORT",
        help="Override a role effort; repeat for multiple roles.",
    )
    parser.add_argument(
        "--external-provider",
        choices=("none", "anthropic"),
        default=None,
        help="Optionally configure the read-only Anthropic MCP bridge.",
    )
    parser.add_argument("--external-model", default="claude-sonnet-5")
    parser.add_argument(
        "--external-effort",
        choices=("low", "medium", "high", "xhigh", "max"),
        default="high",
    )
    parser.add_argument("--interactive", action="store_true")
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
        preset = args.preset
        external_provider = args.external_provider
        model_overrides = list(args.role_model)
        effort_overrides = list(args.role_effort)
        external_model = args.external_model
        external_effort = args.external_effort
        if args.interactive:
            (
                preset,
                model_overrides,
                effort_overrides,
                external_provider,
                external_model,
                external_effort,
            ) = interactive_options(
                preset,
                model_overrides,
                effort_overrides,
                external_provider,
                external_model,
                external_effort,
            )
        preset = preset or "balanced"
        external_provider = external_provider or "none"
        settings = resolve_profile(
            preset, args.profile, model_overrides, effort_overrides
        )
        return install(
            target=target,
            preset=preset,
            settings=settings,
            external_provider=external_provider,
            external_model=external_model,
            external_effort=external_effort,
            force=args.force,
            force_config=args.force_config,
            dry_run=args.dry_run,
        )
    except (InstallError, OSError) as exc:
        print(f"install error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
