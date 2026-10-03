<!-- opencode-bounded-orchestrator:start -->
## Ustam

For every execution task, including small source lookups, use the `bounded-orchestrator` skill. The primary `owner` only speaks with the user, plans, delegates, reads concise worker reports, decides, and redelegates. It never reads or changes source, researches, builds, tests, freezes candidates, operates the ledger, or reviews work itself. If delegation is unavailable, report the blocker; do not execute as fallback. Specialists do the assigned work; only a helper based on `implementer` writes implementation within an explicit scope. Named helper slots may share the same duty while remaining separate agents. Verification and review use a frozen candidate, review loops are finite, and unfinished work is recorded in the local schema-2 ledger. Project-specific local evaluation is optional and must be explicitly configured.
<!-- opencode-bounded-orchestrator:end -->
