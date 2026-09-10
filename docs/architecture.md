
# Architecture rationale

## Design goal

Improve difficult repository work without creating a harder coordination problem. The architecture optimizes for accountability, boundedness, model-fit, and evidence rather than maximum agent count.

## Control plane: Astra medium

The root is the control plane and owns interpretation, scope, architecture, routing, write ownership, integration, candidate identity, finding triage, and final outcome.

Medium reasoning is the default design choice for root decisions about scope, evidence, and stopping. The optional `advisor` requests xhigh for a framed high-risk decision. These settings are a workflow preset; no cost, latency, or quality advantage has been established by comparative benchmarks.

## Execution plane: Luna, Terra, and Sol by job shape

- **Luna:** optional exact mechanical read-only lookup. It is never the default implementer or diagnostician.
- **Terra:** exploration, external technical research, targeted verification, and failure classification.
- **Sol:** production implementation, difficult root-cause analysis, and direct runtime QA.
- **Astra:** ownership and independent frozen-candidate review.

This assigns distinct responsibilities to each role. Whether the routing improves outcomes depends on the task and the models available to the user.

## Why the verifier is not a repair agent

A verifier that silently repairs code converts failed evidence into an unreviewed implementation path. The Terra verifier may run tests and create disposable artifacts, but it cannot edit source or tests. Evidence returns to the owner, which decides whether a Sol repair is justified.

## Why the candidate is frozen

A review is meaningful only when it has a stable subject. Prefer a clean exact commit when authorized. Otherwise `candidate.py` fingerprints commit/branch identity, staged and unstaged diffs, status, and untracked non-ignored files. Review is accepted only if the fingerprint still matches afterward.

## Why the reviewer cannot implement

Implementation tries to satisfy the contract. Review tries to falsify confidence in a frozen candidate. Combining them makes it unclear which candidate was reviewed. The Astra reviewer therefore returns findings only; the owner triages; a bounded Sol repair receives narrow re-verification and re-review.

## Why loops have a ceiling

Completion needs a stopping rule:

- at most three writer turns across initial work and two evidence-backed repairs
- one broad review
- one narrow re-review
- one retry of an unchanged delegated objective, only after new evidence or narrower scope

When the ceiling is reached, the owner returns a truthful blocked state.

## Role discovery and recursion controls

Every role is both stored under `.codex/agents/` and explicitly registered through `agents.<name>.config_file`. Each child role sets `[agents] enabled = false`, and its instructions prohibit delegation. The duplication is intentional because Codex surfaces and versions may apply configuration layers differently.

## Safety is layered

- TOML pins intended model, effort, role, and sandbox defaults.
- The skill defines authority, ownership, and finite state transitions.
- The candidate tool detects mutation.
- The local task ledger reports unresolved declared required work.
- The installer preserves existing configuration and backs up forced replacements.
- Final diff inspection remains mandatory.
- External effects require exact user authority.

Agent sandbox settings are workflow defaults, not a substitute for live platform permissions or human review. One-writer ownership, finite review budgets, and communication boundaries are instruction-level rules. The candidate tool detects changes when invoked; it does not lock files or automatically block a merge. The task ledger catches unresolved work only when that work was declared; it cannot discover missing tasks or prove correctness. Expertise packs add opt-in instructions and do not grant permissions or enforce behavior. The verifier has workspace-write configuration to run checks; its prohibition on editing source is an instruction, not a read-only sandbox.

## Optional external proposal model

When explicitly installed, a local stdio MCP server may call Anthropic's Messages API for a bounded patch proposal. It receives only context selected by the root and has no workspace access. This keeps the topology one level deep: Claude is a tool-backed proposal source, not a recursively delegating Codex agent. The native implementer remains the single writer and normal verification, freeze, and review steps still apply.
