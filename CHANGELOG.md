# Changelog

All notable changes to the public project are documented here. This repository begins a new publication history from the recovered v0.2.0 source archive; see [source provenance](docs/provenance.md).

## [0.3.0] - 2026-09-10

### Added

- A standard-library local task ledger with validated IDs, dependencies, state transitions, human and JSON status, and review/completion gates.
- Atomic, restrictive storage for metadata-only run state under the existing ignored runtime directory.
- Opt-in UI design and security review expertise packs that preserve the base authority and bounded-workflow rules.
- English and Turkish guides for the ledger, expertise packs, and v0.3.0 release.

### Changed

- The base skill and managed `AGENTS.md` block now describe ledger use and expertise-pack boundaries.
- Install, uninstall, validation, and release packaging include the ledger and both expertise packs.
- Release tests derive artifact names from `VERSION`.
- Ledger atomic writes explicitly close temporary file descriptors before replacement for Windows compatibility.

### Limits

- The ledger detects unresolved declared work; it cannot prove that all necessary work was declared or that completed work is correct.
- Expertise packs provide instructions, not enforcement, permissions, credentials, or external-action authority.

## [0.2.0] - 2026-09-10

### Added

- Project-scoped Astra-owner and Sol-owner profiles.
- Explicit profiles for explorer, researcher, implementer, verifier, failure analyst, QA operator, reviewer, advisor, and optional fast lookup roles.
- A bounded orchestration skill with task contracts, one-writer ownership, candidate freezing, independent review, and finite repair/re-review budgets.
- A dependency-free candidate hash and Git identity tool.
- A safe installer with dry-run, conflict preservation, local backups for forced replacement, repeatable installation, and ownership-aware uninstall.
- Supplied launchers for macOS, Windows, and POSIX shells, plus release archive construction.
- English-first and Turkish documentation, examples, FAQ, roadmap, contribution guidance, security reporting, and GitHub templates.

### Routing

- GPT-6 Astra medium owns scope, architecture, routing, integration, triage, and final outcome by default.
- GPT-5.6 Terra medium handles repository exploration and technical research.
- GPT-5.6 Sol high is the single writer for bounded implementation scopes and the read-only failure analyst after evidence identifies a blocker.
- GPT-5.6 Terra high independently verifies acceptance criteria.
- GPT-6 Astra medium reviews one frozen candidate and returns findings only.
- GPT-5.6 Luna medium remains an optional exact, read-only lookup path.

### Attribution

- Preserved Apache-2.0 licensing and attribution to [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator) in [LICENSE](LICENSE), [NOTICE](NOTICE), and the [design comparison](docs/from-astra-luna-orchestrator.md).

[0.2.0]: https://github.com/metapak/codex-bounded-orchestrator/releases/tag/v0.2.0
[0.3.0]: https://github.com/metapak/codex-bounded-orchestrator/releases/tag/v0.3.0

### Publication validation repair / Yayın doğrulama düzeltmesi

- Windows skips the POSIX-only filesystem executable-bit check; regression coverage preserves macOS/Linux checks and ZIP mode checks.
- Windows, yalnızca POSIX dosya sistemine ait çalıştırma izni kontrolünü atlar; macOS/Linux ve ZIP izin kontrolleri korunur.
