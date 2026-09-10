#!/usr/bin/env python3
"""Track declared orchestration work as local metadata-only JSON.

The ledger records short task identifiers, short labels, dependencies, states, and
timestamps. Do not put prompts, source code, logs, credentials, or secrets in it.
Runtime files live under .codex/.bounded-orchestrator/runs/ and are ignored by Git.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
RUNTIME_RELATIVE = Path(".codex/.bounded-orchestrator")
RUNS_RELATIVE = RUNTIME_RELATIVE / "runs"
CURRENT_RELATIVE = RUNTIME_RELATIVE / "current.json"
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MAX_LABEL_LENGTH = 160
MAX_REASON_LENGTH = 240
TASK_STATES = {"pending", "in_progress", "complete", "blocked", "skipped"}


class LedgerError(RuntimeError):
    """Expected command or ledger validation failure."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def discover_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise LedgerError("Run this command inside a Git repository.")
    return Path(result.stdout.strip()).resolve()


def validate_id(value: str, kind: str) -> str:
    if not ID_PATTERN.fullmatch(value):
        raise LedgerError(
            f"Invalid {kind} ID {value!r}; use 1-64 letters, digits, '.', '_' or '-'."
        )
    return value


def validate_text(value: str, kind: str, maximum: int, *, allow_empty: bool = False) -> str:
    value = value.strip()
    if not value and not allow_empty:
        raise LedgerError(f"{kind} must not be empty.")
    if any(character in value for character in "\r\n\x00"):
        raise LedgerError(f"{kind} must be one line.")
    if len(value) > maximum:
        raise LedgerError(f"{kind} must be at most {maximum} characters.")
    return value


def ensure_runtime(root: Path) -> Path:
    runtime = root / RUNTIME_RELATIVE
    if runtime.is_symlink() or (runtime.exists() and not runtime.is_dir()):
        raise LedgerError("The reserved runtime path must be a real directory.")
    ignore = runtime / ".gitignore"
    if not ignore.is_file() or ignore.read_text(encoding="utf-8") != "*\n!.gitignore\n":
        raise LedgerError(
            "The reserved runtime ignore is missing or changed; reinstall before using the ledger."
        )
    runs = root / RUNS_RELATIVE
    if runs.is_symlink() or (runs.exists() and not runs.is_dir()):
        raise LedgerError("The ledger runs path must be a real directory.")
    runs.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(runtime, 0o700)
        os.chmod(runs, 0o700)
    except OSError:
        pass
    return runs


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        try:
            permission_setter = getattr(os, "fchmod", None)
            if permission_setter is not None:
                try:
                    permission_setter(descriptor, 0o600)
                except OSError:
                    pass
            data = (
                json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                if written == 0:
                    raise OSError("Could not write ledger temporary file.")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            # Close on every permission or write failure path. Windows refuses
            # to replace or remove a file while its descriptor is open.
            os.close(descriptor)
        os.replace(temporary, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            except OSError:
                pass
            finally:
                os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_json(path: Path, description: str) -> dict[str, Any]:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise LedgerError(f"Invalid {description} path: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LedgerError(f"{description} was not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise LedgerError(f"Cannot read {description}: {path}") from exc
    if not isinstance(value, dict):
        raise LedgerError(f"Invalid {description}: expected a JSON object.")
    return value


def current_run_id(root: Path) -> str:
    current = load_json(root / CURRENT_RELATIVE, "current run pointer")
    run_id = current.get("run_id")
    if not isinstance(run_id, str):
        raise LedgerError("Invalid current run pointer.")
    return validate_id(run_id, "run")


def run_path(root: Path, run_id: str) -> Path:
    return root / RUNS_RELATIVE / f"{validate_id(run_id, 'run')}.json"


def validate_run(run: dict[str, Any]) -> None:
    if run.get("schema") != SCHEMA_VERSION:
        raise LedgerError("Unsupported ledger schema.")
    validate_id(str(run.get("run_id", "")), "run")
    if run.get("status") not in {"active", "complete"}:
        raise LedgerError("Invalid run status.")
    tasks = run.get("tasks")
    if not isinstance(tasks, dict):
        raise LedgerError("Invalid ledger tasks collection.")
    for task_id, task in tasks.items():
        validate_id(task_id, "task")
        if not isinstance(task, dict) or task.get("status") not in TASK_STATES:
            raise LedgerError(f"Invalid task entry: {task_id}")
        if not isinstance(task.get("required"), bool):
            raise LedgerError(f"Task {task_id} has an invalid required flag.")
        dependencies = task.get("depends_on")
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) and item in tasks for item in dependencies
        ):
            raise LedgerError(f"Task {task_id} has invalid dependencies.")
        if task_id in dependencies:
            raise LedgerError(f"Task {task_id} cannot depend on itself.")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise LedgerError("Task dependency cycle detected.")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in tasks[task_id]["depends_on"]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        visit(task_id)


def load_run(root: Path, run_id: str | None = None) -> tuple[Path, dict[str, Any]]:
    selected = validate_id(run_id, "run") if run_id else current_run_id(root)
    path = run_path(root, selected)
    run = load_json(path, "run ledger")
    validate_run(run)
    return path, run


def save_run(path: Path, run: dict[str, Any]) -> None:
    validate_run(run)
    run["updated_at"] = utc_now()
    atomic_write_json(path, run)


def blockers(run: dict[str, Any]) -> list[str]:
    results: list[str] = []
    for task_id, task in run["tasks"].items():
        if not task["required"]:
            continue
        status = task["status"]
        if status in {"pending", "in_progress", "blocked"}:
            results.append(f"{task_id}: {status}")
        elif status == "skipped" and not task.get("reason"):
            results.append(f"{task_id}: skipped without justification")
    return results


def command_start(root: Path, args: argparse.Namespace) -> None:
    runs = ensure_runtime(root)
    run_id = validate_id(args.run_id, "run")
    title = validate_text(args.title, "Run title", MAX_LABEL_LENGTH)
    path = runs / f"{run_id}.json"
    if path.exists():
        raise LedgerError(f"Run already exists: {run_id}")
    now = utc_now()
    run = {
        "schema": SCHEMA_VERSION,
        "run_id": run_id,
        "title": title,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "tasks": {},
    }
    atomic_write_json(path, run)
    atomic_write_json(root / CURRENT_RELATIVE, {"schema": SCHEMA_VERSION, "run_id": run_id})
    print(f"Started run {run_id}: {title}")


def command_add(root: Path, args: argparse.Namespace) -> None:
    path, run = load_run(root, args.run)
    if run["status"] != "active":
        raise LedgerError("Cannot add tasks to a completed run.")
    task_id = validate_id(args.task_id, "task")
    if task_id in run["tasks"]:
        raise LedgerError(f"Task already exists: {task_id}")
    dependencies = list(dict.fromkeys(args.depends_on or []))
    for dependency in dependencies:
        validate_id(dependency, "dependency")
        if dependency not in run["tasks"]:
            raise LedgerError(f"Dependency does not exist: {dependency}")
    now = utc_now()
    run["tasks"][task_id] = {
        "title": validate_text(args.title, "Task title", MAX_LABEL_LENGTH),
        "required": not args.optional,
        "status": "pending",
        "depends_on": dependencies,
        "reason": None,
        "created_at": now,
        "updated_at": now,
    }
    save_run(path, run)
    print(f"Added task {task_id} ({'optional' if args.optional else 'required'}).")


def transition(root: Path, args: argparse.Namespace, target: str) -> None:
    path, run = load_run(root, args.run)
    if run["status"] != "active":
        raise LedgerError("Cannot change tasks in a completed run.")
    task_id = validate_id(args.task_id, "task")
    task = run["tasks"].get(task_id)
    if task is None:
        raise LedgerError(f"Task does not exist: {task_id}")
    allowed = {
        "in_progress": {"pending", "blocked"},
        "complete": {"in_progress"},
        "blocked": {"pending", "in_progress"},
        "skipped": {"pending", "blocked"},
    }
    if task["status"] not in allowed[target]:
        raise LedgerError(
            f"Cannot move {task_id} from {task['status']} to {target}."
        )
    if target == "in_progress":
        unresolved = [
            dependency
            for dependency in task["depends_on"]
            if run["tasks"][dependency]["status"] not in {"complete", "skipped"}
            or (
                run["tasks"][dependency]["status"] == "skipped"
                and not run["tasks"][dependency].get("reason")
            )
        ]
        if unresolved:
            raise LedgerError(
                f"Task {task_id} has unresolved dependencies: {', '.join(unresolved)}"
            )
    reason = getattr(args, "reason", None)
    if target == "blocked":
        reason = validate_text(reason, "Block reason", MAX_REASON_LENGTH)
    elif target == "skipped" and reason is not None:
        reason = validate_text(reason, "Skip reason", MAX_REASON_LENGTH, allow_empty=True)
    else:
        reason = None
    task["status"] = target
    task["reason"] = reason or None
    task["updated_at"] = utc_now()
    save_run(path, run)
    print(f"Task {task_id}: {target}")


def status_payload(run: dict[str, Any]) -> dict[str, Any]:
    pending_blockers = blockers(run)
    counts = {state: 0 for state in sorted(TASK_STATES)}
    for task in run["tasks"].values():
        counts[task["status"]] += 1
    return {
        "run": run,
        "counts": counts,
        "ready_for_review": run["status"] == "active" and not pending_blockers,
        "completion_blockers": pending_blockers,
    }


def command_status(root: Path, args: argparse.Namespace) -> None:
    _, run = load_run(root, args.run)
    payload = status_payload(run)
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return
    print(f"Run {run['run_id']} [{run['status']}]: {run['title']}")
    if not run["tasks"]:
        print("  No declared tasks.")
    for task_id, task in run["tasks"].items():
        required = "required" if task["required"] else "optional"
        dependencies = ", ".join(task["depends_on"]) or "none"
        line = f"  {task_id}: {task['status']} ({required}; depends on: {dependencies}) - {task['title']}"
        if task.get("reason"):
            line += f" [{task['reason']}]"
        print(line)
    if payload["completion_blockers"]:
        print("Ready for review: no")
        for item in payload["completion_blockers"]:
            print(f"  blocker: {item}")
    else:
        print("Ready for review: yes")


def command_ready(root: Path, args: argparse.Namespace) -> None:
    _, run = load_run(root, args.run)
    if run["status"] != "active":
        raise LedgerError("Run is already complete.")
    pending_blockers = blockers(run)
    if pending_blockers:
        raise LedgerError("Not ready for review: " + "; ".join(pending_blockers))
    print(f"Run {run['run_id']} is ready for review based on declared required tasks.")


def command_complete_run(root: Path, args: argparse.Namespace) -> None:
    path, run = load_run(root, args.run)
    if run["status"] != "active":
        raise LedgerError("Run is already complete.")
    pending_blockers = blockers(run)
    if pending_blockers:
        raise LedgerError("Cannot complete run: " + "; ".join(pending_blockers))
    run["status"] = "complete"
    run["completed_at"] = utc_now()
    save_run(path, run)
    print(f"Completed run {run['run_id']} based on declared required tasks.")


def command_clear(root: Path, args: argparse.Namespace) -> None:
    ensure_runtime(root)
    selected = validate_id(args.run, "run") if args.run else current_run_id(root)
    path = run_path(root, selected)
    if not path.exists():
        raise LedgerError(f"Run does not exist: {selected}")
    path.unlink()
    current_path = root / CURRENT_RELATIVE
    if current_path.exists():
        current = load_json(current_path, "current run pointer")
        if current.get("run_id") == selected:
            current_path.unlink()
    print(f"Cleared local ledger metadata for run {selected}.")


def add_run_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run", help="Run ID. Defaults to the current run.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        help="Git repository root. Defaults to discovery from the current directory.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Start and select a new run.")
    start.add_argument("run_id")
    start.add_argument("--title", required=True)
    start.set_defaults(handler=command_start)

    add = subparsers.add_parser("add", help="Declare a task in the selected run.")
    add.add_argument("task_id")
    add.add_argument("--title", required=True)
    add.add_argument("--depends-on", action="append", default=[])
    add.add_argument("--optional", action="store_true")
    add_run_option(add)
    add.set_defaults(handler=command_add)

    for name, target, help_text in (
        ("begin", "in_progress", "Begin a pending task or resume a blocked task."),
        ("complete", "complete", "Complete an in-progress task."),
        ("block", "blocked", "Block a pending or in-progress task."),
        ("skip", "skipped", "Skip a pending or blocked task."),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("task_id")
        add_run_option(command)
        if name == "block":
            command.add_argument("--reason", required=True)
        elif name == "skip":
            command.add_argument("--reason")
        command.set_defaults(
            handler=lambda root, args, selected=target: transition(root, args, selected)
        )

    status = subparsers.add_parser("status", help="Show human or JSON status.")
    add_run_option(status)
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=command_status)

    ready = subparsers.add_parser(
        "ready-for-review", help="Check declared required work before review."
    )
    add_run_option(ready)
    ready.set_defaults(handler=command_ready)

    complete_run = subparsers.add_parser(
        "complete-run", help="Mark a ready run complete."
    )
    add_run_option(complete_run)
    complete_run.set_defaults(handler=command_complete_run)

    clear = subparsers.add_parser("clear", help="Delete one run's local metadata.")
    add_run_option(clear)
    clear.set_defaults(handler=command_clear)
    return parser


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print("ledger error: Python 3.11 or newer is required.", file=sys.stderr)
        return 2
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = args.root.expanduser().resolve() if args.root else discover_root(Path.cwd())
        args.handler(root, args)
    except (LedgerError, OSError) as exc:
        print(f"ledger error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
