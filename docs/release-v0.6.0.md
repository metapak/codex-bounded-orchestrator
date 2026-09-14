[English](release-v0.6.0.md) | [Türkçe](release-v0.6.0.tr.md)

# v0.6.0 release notes

- Adds a read-only local Codex token/model usage report based only on observed usage-record deltas.
- Adds the optional `quota-saver` native GPT profile without changing the balanced default.
- Adds an explicit, shell-free local evaluation runner and an opt-in ledger gate.
- Migrates ledger data non-destructively to stable attempt/event history, richer interruption states, one bounded retry, derived status, and owner route-back metadata.

The usage report does not claim quota percentage, price, or completeness. Local evaluation stays off until explicitly invoked and selected for a run.
