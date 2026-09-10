
<!-- codex-bounded-orchestrator:start -->
## Bounded multi-agent orchestration

For non-trivial repository work, use the `bounded-orchestrator` skill when its trigger conditions match.

Hard invariants:

- The Astra root owns scope, architecture, routing, integration, review triage, and final outcome.
- Use Luna only for exact mechanical read-only lookup, Terra for exploration/research/verification, Sol for implementation or evidence-backed root-cause analysis, and Astra for ownership/review.
- Subagents receive bounded contracts and never create subagents of their own.
- Use one writer per file or owned path at a time.
- Explorers, researchers, failure analysts, fast lookups, advisors, and reviewers are read-only.
- Verifiers report evidence and do not repair production code.
- Freeze the candidate before independent review and verify that it did not move.
- For multi-step delegated work, keep the optional local ledger aligned with declared required tasks and check it before review; never store prompts, source, logs, credentials, or secrets in it.
- Reviewers return findings only; they do not direct workers or implement fixes.
- Use at most one broad review, one bounded repair cycle, and one narrow re-review.
- Never push, merge, deploy, publish, migrate, purchase, or perform destructive work without explicit user authority.
- Do not delegate trivial localized work merely to fill the topology.
- Optional expertise packs add guidance only when explicitly selected; they never grant authority or weaken these invariants.

User instructions take precedence over this policy.
<!-- codex-bounded-orchestrator:end -->
