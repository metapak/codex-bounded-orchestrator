[English](usage-and-local-eval.md) | [Türkçe](usage-and-local-eval.tr.md)

# Usage reporting and optional local evaluation

## Locally observed Codex usage

```bash
python3 .codex/tools/usage_report.py
python3 .codex/tools/usage_report.py --json
```

The reporter scans `~/.codex/sessions` read-only and aggregates only observed `token_usage_record.usage` counter deltas. It never prints prompt or source content. Model, role, and thread are shown only when those fields are present on the usage record. The totals are local observations; they are not quota percentages, bills, or cost estimates.

## Explicit local evaluation

Copy `.codex/bounded-orchestrator.eval.example.json` to a project-local manifest and edit its explicit `argv` array. Nothing runs automatically.

```bash
python3 .codex/tools/local_eval.py .codex/local-eval.json
python3 .codex/tools/ledger.py require-eval --label focused-tests
python3 .codex/tools/ledger.py ready-for-review
```

The runner does not use a shell, runs in the project root, enforces a bounded timeout, and writes an ignored summary. By default the summary stores an output digest, not command output. This is a project-specific check, not a universal quality benchmark. Once opted in for a run, a passing summary is required before review.
The pass summary is bound to a privacy-safe fingerprint of HEAD plus relevant tracked and untracked worktree content. Any later candidate change makes that pass stale; ignored evaluation summaries are excluded so saving the result does not invalidate itself.

The ledger also records stable attempt and event IDs. `interrupt`, `wait-user`, and `needs-repair` preserve the last short evidence; `retry --evidence ...` permits one bounded retry and routes repair back to the named owner role.
