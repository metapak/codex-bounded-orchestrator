[English](task-ledger.md) | [Türkçe](task-ledger.tr.md)

# Local task ledger

The v0.3.0 ledger keeps a small, local record of work the owner declared for one orchestration run. It helps the owner see required tasks that are still pending, in progress, blocked, or skipped without a reason before review and completion.

It deliberately stores metadata only: short run and task IDs, short labels, dependencies, required/optional flags, states, short reasons, and timestamps. Never put prompts, source code, diffs, logs, personal data, credentials, or secrets in labels or reasons.

## Basic flow

Run the commands from the target Git repository:

```bash
python3 .codex/tools/ledger.py start invoice-idempotency --title "Invoice idempotency"

python3 .codex/tools/ledger.py add map --title "Map request and persistence flow"
python3 .codex/tools/ledger.py add implement --title "Implement bounded change" --depends-on map
python3 .codex/tools/ledger.py add verify --title "Run independent verification" --depends-on implement

python3 .codex/tools/ledger.py begin map
python3 .codex/tools/ledger.py complete map
python3 .codex/tools/ledger.py status
```

Continue transitions with `begin` and `complete`. Use `block TASK --reason "short reason"` when evidence names a blocker. Use `skip TASK --reason "short owner decision"` only when skipping is justified. Add `--optional` to `add` for a task that should not block the run.

Before freezing a candidate:

```bash
python3 .codex/tools/ledger.py ready-for-review
```

After the full bounded workflow completion gate passes:

```bash
python3 .codex/tools/ledger.py complete-run
```

Use `status --json` for machine-readable output. Add `--run RUN_ID` to target a run other than the current one. `clear --run RUN_ID` deletes only that run's local ledger metadata.

## Valid transitions

| Command | From | To |
|---|---|---|
| `begin` | `pending`, `blocked` | `in_progress` |
| `complete` | `in_progress` | `complete` |
| `block` | `pending`, `in_progress` | `blocked` |
| `skip` | `pending`, `blocked` | `skipped` |

A task can begin only after its dependencies are complete or have a recorded skip reason. Required tasks in `pending`, `in_progress`, or `blocked` state prevent readiness and completion. A required skipped task also blocks when it has no reason. Unresolved optional tasks remain visible but do not block the gate.

## Storage and limits

Runtime state is written atomically under `.codex/.bounded-orchestrator/runs/`. The installer places an exact `.gitignore` in the parent runtime directory before installing the tool. On systems with POSIX permissions, directories are restricted to the current user and JSON files use mode `0600`.

The ledger is a workflow aid, not a scheduler or security boundary. It validates declared IDs, dependencies, transitions, and completion conditions. It cannot discover an omitted task, confirm that a status update is truthful, prove code correctness, or replace tests and review.
