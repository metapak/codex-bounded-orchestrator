
# What changed from the inspiration project

This repository is a ground-up redesign inspired by `donvito/codex-astra-luna-orchestrator`.

The inspiration project established a useful base: a strong root, bounded subagents, and an independent reviewer. Version 0.2 changes the model routing and tightens runtime registration.

| Area | Version 0.2 behavior |
|---|---|
| Owner | GPT-6 Astra medium owns scope, architecture, routing, triage, and outcome |
| Mechanical lookup | Optional Luna medium, exact and read-only only |
| Exploration/research | Terra medium |
| Verification | Terra high, evidence only, no repair |
| Implementation | Sol high, one writer per owned scope |
| Failure analysis | Sol high after evidence names a blocker |
| Review | Astra medium, frozen candidate, read-only findings only |
| High-risk advice | Astra xhigh for one framed decision |
| Role loading | Every role explicitly uses `agents.<name>.config_file` plus directory files |
| Child topology | Every child profile disables further agents and prohibits delegation |
| Loop control | Fixed retry, writer, review, and re-review budgets |
| External actions | Push, merge, deployment, release, migration, and destructive actions need explicit authority |
| Installation | Safe macOS and Windows launchers preserve existing files by default |

## Migration

Preview first:

```bash
python scripts/install.py /path/to/project --profile astra --dry-run
```

Then install:

```bash
python scripts/install.py /path/to/project --profile astra
```

Conflicting managed files are preserved unless `--force` is supplied. Existing `.codex/config.toml` remains untouched unless `--force-config` is explicitly supplied; a merge example is written instead.

The version 0.2 roles are:

- `fast_lookup`
- `explorer`
- `researcher`
- `implementer`
- `verifier`
- `failure_analyst`
- `qa_operator`
- `reviewer`
- `advisor`

The skill remains `$bounded-orchestrator`.
