[English](README.md) | [Türkçe](README.tr.md)

# Codex Bounded Orchestrator

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB.svg)](https://www.python.org/downloads/)

**A project-scoped Codex workflow for complex repository work: one accountable owner, one writer per scope, independent verification, and a finite review loop.**

Codex Bounded Orchestrator packages agent profiles, task contracts, review rules, and local integrity tooling into a safe-to-preview installer. Astra owns the outcome, Terra maps and verifies, Sol implements and diagnoses, and Luna is reserved for exact read-only lookups.

It is designed to make multi-agent work easier to inspect and stop. The repository configures guardrails; prompts alone are not a security boundary, and Codex clients may differ in how they apply settings.

> [!NOTE]
> This is an unofficial community project. It is not affiliated with or endorsed by OpenAI.

## Why use it?

- Keep one root owner responsible from task intake through final verification.
- Give each implementation scope to one writer at a time.
- Separate investigation, implementation, verification, and review.
- Freeze a candidate before independent review and detect later file changes.
- Track declared required work in a local metadata-only ledger before review.
- Add opt-in UI design or security review guidance without expanding authority.
- Cap retries, writer turns, repair cycles, and re-reviews.
- Preview installation and preserve existing project configuration by default.

## Architecture

![Codex Bounded Orchestrator role tree showing the owner, models, and responsibilities](docs/assets/codex-bounded-orchestrator-roles-tr.png)

The visual overview uses short Turkish labels; the diagram below shows the same core workflow in English.

```mermaid
flowchart TD
    U[User goal] --> O["Astra medium<br/>root owner"]
    O --> E["Terra medium<br/>explore and research<br/>read-only"]
    O --> I["Sol high<br/>implement<br/>single writer"]
    O --> V["Terra high<br/>verify<br/>evidence only"]
    O --> L["Local task ledger<br/>declared metadata only"]
    E --> O
    I --> V
    V --> F[Freeze candidate]
    F --> R["Astra medium<br/>independent review<br/>read-only"]
    R --> T{Root triage}
    T -->|pass| D[Final verification]
    T -->|material finding| B[One bounded repair]
    B --> V2[Narrow verification]
    V2 --> F2[Re-freeze]
    F2 --> R2[One narrow re-review]
    R2 --> D
```

Optional paths: Luna medium for `fast_lookup`, Sol high for `failure_analyst` and `qa_operator`, and Astra xhigh for one framed `advisor` decision. See the [full architecture](docs/architecture.md).

## Quick start

Requirements: Git, Python 3.11 or newer, a Codex client that supports project-scoped configuration and custom agents, and access to the configured models in your plan or workspace.

```bash
git clone https://github.com/metapak/codex-bounded-orchestrator.git
cd codex-bounded-orchestrator

# Preview every planned action first.
python3 scripts/install.py /absolute/path/to/your-project --profile astra --dry-run

# Install after reviewing the preview.
python3 scripts/install.py /absolute/path/to/your-project --profile astra
```

Start a fresh Codex session in the target project, then invoke:

```text
$bounded-orchestrator

Implement idempotency for invoice creation.
Map the request and persistence path first.
Do not push, merge, or deploy.
```

Run the [runtime smoke test](docs/runtime-smoke-test.md) before relying on the routing in real work.

## Platform entry points

These entry points are supplied by the repository. Runtime behavior still depends on your local Python, shell, Codex version, and model access.

| Platform | Supplied entry points | Guide |
|---|---|---|
| macOS | `setup.command`, `scripts/install.sh`, `scripts/install.py` | [macOS installation](INSTALL-MACOS.md) |
| Windows | `setup.cmd`, `setup.ps1`, `scripts/install.ps1`, `scripts/install.py` | [Windows installation](INSTALL-WINDOWS.md) |
| Linux | `scripts/install.sh`, `scripts/install.py` | Use the [quick start](#quick-start) and `--help` |

The installer uses only the Python standard library. The default `astra` profile uses GPT-6 Astra medium as root owner; `--profile sol` selects the supplied GPT-5.6 Sol high fallback profile while preserving the rest of the routing.

## What gets installed

- Explicit role registrations and one profile file per role under `.codex/agents/`.
- The `$bounded-orchestrator` skill and its task, review, and escalation contracts.
- `.codex/tools/candidate.py` for candidate hashes and Git identity.
- `.codex/tools/ledger.py` for ignored local task metadata and completion gates.
- Two opt-in expertise packs: UI design and security review.
- A marked, updateable block in the target project's `AGENTS.md`.
- A local install manifest and ignored backup directory for safe updates and uninstall.

If `.codex/config.toml` already exists, the default install preserves it and writes `.codex/bounded-orchestrator.config.example.toml` for manual merging. Conflicting managed files are skipped unless `--force` is supplied. `--force-config` separately opts into replacing root config after a local backup.

Useful commands:

```bash
# Replace conflicting managed role, skill, or tool files after backing them up.
python3 scripts/install.py /path/to/project --profile astra --force

# Remove only unmodified installer-owned files and the managed AGENTS.md block.
python3 scripts/install.py /path/to/project --uninstall

# Freeze and later verify the candidate from the installed project.
python3 .codex/tools/candidate.py freeze --label pre-review
python3 .codex/tools/candidate.py verify

# Track declared required work without storing prompts, source, or logs.
python3 .codex/tools/ledger.py start feature-123 --title "Short goal label"
python3 .codex/tools/ledger.py add implement --title "Implement the change"
python3 .codex/tools/ledger.py status
```

See the [task ledger guide](docs/task-ledger.md) and [expertise pack guide](docs/expertise-packs.md). The ledger can detect unresolved declared work, but it cannot prove that every necessary task was declared. Expertise packs are instructions, not enforcement or additional permission.

## Guardrails and their limits

| Control | How it is supplied | Practical limit |
|---|---|---|
| No recursive child delegation | Agent config disables child agents; role prompts also prohibit delegation | Depends on the Codex client honoring the loaded project config |
| One writer per scope | Owner and implementer task contracts | A procedural rule; it does not lock files at the operating-system level |
| Read-only reviewer | Reviewer sandbox default plus findings-only instructions | Live permissions can vary by client, trust state, and parent policy |
| Finite review loop | Skill state machine and explicit budgets | The root must follow the workflow; prompts do not enforce a global scheduler |
| Candidate integrity | Local tool records hashes and verifies the frozen file set | Detects changes; it does not prevent edits or prove code correctness |
| Declared-work gate | Local ledger validates task states and dependencies before review/completion | Finds unresolved declared work; it cannot discover work that was never declared |
| Opt-in expertise | Separate UI design and security review skill packs | Adds instructions only; it does not change permissions, roles, or enforcement |
| Safer installation | Code preserves conflicts, supports dry-run, backs up forced replacements, and tracks owned files | Review the preview and backups; it is not a substitute for version control |

The underlying Codex sandbox, operating-system permissions, repository protections, and human authorization remain the enforcement layers. After client upgrades, rerun the smoke test and report unobservable metadata as unknown.

## Learn more

- [Examples](docs/examples.md): feature work, cross-component debugging, high-risk changes, and root-only tasks
- [FAQ and troubleshooting](docs/faq.md)
- [Roadmap](docs/roadmap.md)
- [Architecture details](docs/architecture.md)
- [Runtime smoke test](docs/runtime-smoke-test.md)
- [Task ledger](docs/task-ledger.md) and [expertise packs](docs/expertise-packs.md)
- [v0.3.0 release notes](docs/release-v0.3.0.md) and [latest release](https://github.com/metapak/codex-bounded-orchestrator/releases/latest)
- [Source provenance](docs/provenance.md)

## Development

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 scripts/build_release.py --output-dir dist
```

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md), review the [security policy](SECURITY.md), and check the [changelog](CHANGELOG.md) before opening a pull request.

If this workflow makes your Codex work clearer or safer to review, a GitHub star helps other developers find it.

## License and attribution

Licensed under Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

This project is a ground-up redesign inspired by [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator), which is also distributed under Apache-2.0. See [NOTICE](NOTICE) and the [design differences](docs/from-astra-luna-orchestrator.md) for attribution and context.
