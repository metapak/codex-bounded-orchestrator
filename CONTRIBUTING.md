# Contributing

Thanks for helping make bounded multi-agent work more useful and easier to inspect. Bug reports, documentation improvements, platform fixes, and focused design proposals are welcome.

## Before you start

For a small fix, open a focused pull request. For a material change to routing, authority, installer behavior, role permissions, or review budgets, open an issue first so the safety and compatibility effects can be discussed before implementation.

Security vulnerabilities belong in a [private report](https://github.com/metapak/codex-bounded-orchestrator/security/advisories/new), not a public issue. See [SECURITY.md](SECURITY.md).

## Development setup

The runtime tools use Python's standard library and require Python 3.11 or newer.

```bash
git clone https://github.com/metapak/codex-bounded-orchestrator.git
cd codex-bounded-orchestrator
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
```

Use an expendable temporary repository when manually exercising installation, force, backup, or uninstall paths. Do not point development tests at a repository containing work you cannot restore.

## Architectural invariants

A contribution must preserve these rules unless an accepted design discussion explicitly changes them:

- one accountable root owner
- one writer per file or owned path at a time
- no recursive child delegation
- candidate freeze before independent review
- a reviewer that is read-only by default and returns findings only
- root-owned finding triage
- finite implementation, retry, repair, and review budgets
- explicit user authority for push, merge, deploy, publishing, migration, billing, account changes, secrets, and destructive actions

Treat role prompts and project config as guardrails. Do not describe them as a security boundary or claim they override the live Codex sandbox, parent permissions, operating-system permissions, or repository protections.

## Making a change

1. Keep the change focused on one problem.
2. Follow existing patterns and avoid new dependencies unless the benefit and maintenance cost are clear.
3. Add targeted tests for behavior changes in the installer, candidate tool, task ledger, release builder, or validation rules.
4. Update both `README.md` and `README.tr.md` when user-visible behavior changes. Update paired English and Turkish files under `docs/` together.
5. Update `CHANGELOG.md` when the change is notable to users.
6. Run the validation commands below.

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
```

For release-related changes, also run:

```bash
python3 scripts/build_release.py --output-dir dist
```

## Pull requests

Describe the concrete trigger and resulting behavior. Include:

- the problem and intended outcome
- files, roles, or platforms affected
- commands run and their results
- compatibility assumptions and observed environment
- any effect on safety, authority, or trust boundaries

Keep generated archives out of the pull request unless a maintainer explicitly requests them. Passing static validation establishes repository consistency; it does not prove that a particular Codex client honored every runtime role, model, effort, or sandbox setting.

## License

By submitting a contribution, you agree that it may be distributed under the repository's [Apache-2.0 license](LICENSE). Preserve applicable notices and the attribution in [NOTICE](NOTICE), including the link to [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator).
