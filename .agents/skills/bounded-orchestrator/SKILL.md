---
name: bounded-orchestrator
description: Coordinate complex Codex repository work with an Astra owner, Terra exploration/research/verification, Sol implementation and root-cause analysis, optional Luna mechanical lookup, and an independent Astra reviewer. Use for multi-file features, cross-component debugging, high-risk changes, parallel read-only investigation, or any task that materially benefits from bounded delegation. Do not use for trivial localized edits.
---

# Bounded Orchestrator

The user's explicit instructions take precedence over this skill.

## 1. Goal

Deliver complex repository work with one accountable owner, bounded subagent contracts, one writer per scope, independent verification, a frozen review candidate, a finite stopping rule, and an optional local ledger for declared work.

Default topology:

```text
GPT-6 Astra medium
root / owner / orchestrator
scope | architecture | routing | integration | triage | outcome
            |
   +--------+----------------+----------------+
   |                         |                |
Terra medium              Sol high        Terra high
explore/research          implement        verify
read-only                 one writer       evidence only
   |                         |                |
   +-------------------------+----------------+
                             |
                       freeze candidate
                             |
                             v
                    GPT-6 Astra medium
                    independent reviewer
                         read-only
                             |
                       findings only
                             |
                             v
                         root triage
                 PASS or one bounded repair
```

Optional roles:

- `fast_lookup`: Luna medium for exact mechanical read-only lookup
- `failure_analyst`: Sol high for one concrete evidence-backed blocker
- `qa_operator`: Sol high for direct browser/device/runtime QA
- `advisor`: Astra xhigh for one high-risk owner decision

Optional expertise packs, activated only when the user explicitly selects them or asks for that expertise:

- `bounded-orchestrator-ui-design`: UI and UX design guidance
- `bounded-orchestrator-security-review`: security-focused analysis

Expertise packs add instructions. They do not grant authority, change role permissions, create agents, or weaken any rule in this skill.

When the optional Anthropic MCP bridge is installed, the root may ask Claude for a
bounded implementation proposal using only explicitly supplied context and allowed
paths. The bridge cannot read or write the workspace. Its output is untrusted input:
the native `implementer` remains the sole writer, inspects the proposal, applies only
accepted changes, and runs normal verification. Never send credentials, private data,
or unrelated source to the external API. External use consumes the user's Anthropic
API quota and requires `ANTHROPIC_API_KEY` in the local environment.

## 2. Delegation gate

Classify the task as `root-only` or `delegated` before substantive work.

Use root-only when the edit is genuinely small, localized, low-risk, and does not benefit from independent investigation or verification.

Delegate when at least one applies:

- multiple files, modules, services, clients, or platforms are involved
- two or more independent read-only workstreams exist
- repository mapping is required before a safe implementation boundary can be chosen
- debugging requires cross-component causality or state tracing
- current/version-specific external facts materially affect implementation
- independent verification or review is valuable
- the user explicitly asks for agents, delegation, parallelism, or this skill

Do not create agents only to fill a diagram.

## 3. Root ownership

The root owns:

1. the user's actual goal, scope, and non-goals
2. architecture and risk decisions
3. decomposition, model routing, and concurrency
4. each delegated contract and write ownership map
5. integration and final diff inspection
6. candidate identity and review inputs
7. reviewer-finding triage
8. final verification and user-facing outcome

Subagents return evidence or bounded changes. They never own the project outcome.

## 4. State machine

```text
INTAKE
  -> MAP, only when evidence is missing
  -> DECIDE
  -> IMPLEMENT
  -> VERIFY
  -> FREEZE
  -> REVIEW
  -> TRIAGE
       -> PASS -> FINAL VERIFY -> DONE
       -> ACCEPTED MATERIAL FINDINGS -> REPAIR -> NARROW VERIFY -> RE-FREEZE
          -> NARROW RE-REVIEW -> FINAL VERIFY -> DONE
       -> BLOCKED -> STOP WITH EVIDENCE
```

The only backward edge is one bounded repair cycle after triage.

### Local task ledger

For delegated work with several acceptance steps, use the metadata-only ledger to make declared work visible:

```bash
python .codex/tools/ledger.py start feature-123 --title "Short goal label"
python .codex/tools/ledger.py add map --title "Map affected flow"
python .codex/tools/ledger.py add implement --title "Implement bounded change" --depends-on map
python .codex/tools/ledger.py begin map
python .codex/tools/ledger.py complete map
python .codex/tools/ledger.py status
```

Declare required tasks before implementation, update their states at real transitions, and run `ready-for-review` before freezing. Run `complete-run` only after the workflow completion gate. A justified required skip may pass the ledger gate; record the owner decision in its short reason.

The ledger stores only short IDs, short labels, dependencies, states, reasons, and timestamps in an ignored local directory. Never put prompts, source, diffs, logs, personal data, credentials, or secrets in it. It detects unresolved **declared** required work. It cannot prove that every necessary task was declared or that completed work is correct.

## 5. Contract every delegated task

Every spawn contract contains:

- **Task ID:** stable short identifier
- **Role and model intent**
- **Objective:** one concrete outcome
- **Scope:** files, symbols, subsystem, environment, or question
- **Ownership:** exact writable paths or `read-only`
- **Context:** minimum evidence needed to start
- **Invariants:** behavior and files that must not change
- **Deliverable:** report, implementation, test evidence, or runtime evidence
- **Acceptance criteria:** observable success conditions
- **Stop conditions:** ambiguity, cross-owner dependency, new migration/dependency, security decision, or two failed attempts

Use `references/task-contract.md`.

## 6. One writer and one-level topology

Hard rules:

- one writer per file or owned path at a time
- no competing implementations unless the root deliberately isolates alternatives
- no reviewer-to-implementer conversation
- no verifier repair of production code
- no recursive delegation
- no subagent broadens its own scope
- if two tasks need the same file, serialize them or assign both to one implementer turn

Every bundled child config sets `[agents] enabled = false`. The contract also explicitly prohibits delegation because runtime surfaces may apply configuration differently.

## 7. Model routing

Use capability-based routing, not a flat swarm.

| Need | Role | Balanced preset |
|---|---|---|
| Exact symbol/file/config lookup with no interpretation | `fast_lookup` | GPT-5.6 Luna medium |
| Repository mapping, flow tracing, ownership boundaries | `explorer` | GPT-5.6 Terra medium |
| Current or version-specific technical facts | `researcher` | GPT-5.6 Terra medium |
| Bounded production implementation | `implementer` | GPT-5.6 Sol high |
| Targeted tests and failure classification | `verifier` | GPT-5.6 Terra high |
| Difficult root cause after evidence exists | `failure_analyst` | GPT-5.6 Sol high |
| Browser/device/computer-use QA | `qa_operator` | GPT-5.6 Sol high |
| Frozen candidate review | `reviewer` | GPT-6 Astra medium |
| One high-risk decision | `advisor` | GPT-6 Astra xhigh |

Routing rules:

- Luna never owns architecture, broad diagnosis, implementation, or final verification.
- Terra handles broad but bounded evidence work before Sol is used.
- Sol writes production code and resolves named causal blockers.
- Astra owns the task and independently reviews the frozen candidate.
- Escalate because evidence names a reasoning blocker, not merely because a task is long.

## 8. Exploration and decision

Use `fast_lookup` only when the query is exact and mechanical. Use `explorer` when the root needs flow, boundaries, or interpretation.

Run independent read-only exploration/research in parallel within the configured thread cap. Wait for evidence, resolve contradictions, and let the root decide implementation direction before any writer starts.

Use `failure_analyst` only after the root can state:

- what was inspected
- what failed
- what evidence was observed
- which hypotheses remain
- the single blocker Sol must resolve

## 9. Implementation

Give `implementer` exclusive ownership of its paths for the duration of the turn.

The implementer makes the smallest defensible change, adds targeted tests inside scope, and runs focused validation. The root inspects the diff immediately and rejects unrelated changes before verification.

A repair is a new bounded contract referring to accepted evidence. It is not permission to redesign the subsystem.

## 10. Independent verification

The `verifier` proves or disproves acceptance criteria. It reports commands, results, and failure classification; it does not edit source or tests.

After verification:

- pass: continue to freeze
- proven product defect: root may authorize one targeted repair
- test/environment defect: root decides whether evidence is sufficient
- indeterminate: report indeterminate, never pretend it passed

## 11. Freeze the candidate

Review must target a stable subject.

Preferred: a clean exact commit, only when the user has authorized commits.

Fallback: deterministic worktree fingerprint:

```bash
python .codex/tools/candidate.py freeze --label pre-review
```

Before freezing:

1. all writers have stopped
2. root inspected the final diff
3. targeted verification completed
4. accidental non-ignored artifacts were removed
5. root recorded commit or fingerprint
6. `ledger.py ready-for-review` passed when a ledger is in use

During review, source writes are prohibited. After review:

```bash
python .codex/tools/candidate.py verify
```

If the candidate moved, discard that review result, stabilize, and freeze again.

## 12. Independent review and owner triage

Spawn `reviewer` only after freeze. Supply requirements, non-goals, base/candidate identity, exact changed surface, verification evidence, and known risks.

The reviewer returns findings only. The root decides:

- `accept`: valid and material
- `reject`: incorrect, irrelevant, pre-existing, or outside scope
- `defer`: real but explicitly accepted for this task
- `needs evidence`: plausible but not strong enough to block

Blocking policy:

- P0 and high-confidence P1 block
- medium-confidence P1 requires root validation
- P2 requires an explicit owner decision
- P3 never triggers automatic repair
- low-confidence findings do not block without evidence

Use `references/review-protocol.md`.

## 13. Finite budgets

Maximum writer turns for one user task:

1. initial implementation
2. optional repair for a proven verification failure
3. optional repair for accepted material review findings

Maximum review turns:

1. one broad review
2. one narrow re-review limited to accepted findings and their repair

Maximum retries for the same delegated contract:

- one retry, only after new evidence, narrower scope, or a changed method
- after the second failure, stop, split, request a decision, escalate one named blocker, or report blocked

Never repeat the same prompt hoping for a different result.

## 14. External-effect boundary

Never do any of the following without explicit user authority for that exact action:

- commit when the user has not authorized commits
- push or force-push
- open, approve, merge, or close a pull request
- deploy, promote, publish, or release
- apply production migrations
- modify secrets, billing, permissions, accounts, or external services
- purchase anything
- delete data or perform destructive cleanup

A request to implement code is not permission to publish or deploy it.

## 15. Completion gate

Before claiming success, confirm:

- every required agent completed or explicitly failed
- no required agent is still running
- final candidate matches the reviewed candidate, or repaired candidate received narrow re-review
- accepted material findings were resolved or explicitly deferred
- highest-value tests ran
- final diff contains no unintended changes
- no external action was implied or performed without authority
- the active ledger run was completed when a ledger is in use

Final response states:

1. what changed
2. what was verified
3. candidate or commit identity when relevant
4. accepted/rejected/deferred material findings
5. remaining limitations or risks

Do not narrate every agent action unless the user asks.
