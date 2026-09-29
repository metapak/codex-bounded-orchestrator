[English](examples.md) | [Türkçe](examples.tr.md)

# Examples

Invoke `$bounded-orchestrator` in a target project after installation. State the outcome and boundaries; the chief assigns every execution step to a bounded specialist.

## Feature across multiple files

```text
$bounded-orchestrator

Add idempotency to invoice creation across the API and persistence layers.
Preserve the public API. Map the path first, give implementation to one writer,
verify duplicate requests, then review one frozen candidate. Do not deploy.
```

## Cross-component bug

```text
$bounded-orchestrator

Find and fix why a saved notification preference resets after sign-in.
Trace client, API, and storage state before choosing the repair scope.
Reproduce the failure and verify the fix. Do not change the schema.
```

## High-risk decision

```text
$bounded-orchestrator

Assess the safest retry boundary for payment capture.
Use the advisor only for the named architecture decision. Return evidence,
tradeoffs, and a recommendation; do not modify code or external systems.
```

Small, localized edits also go to one suitable specialist. The chief stays with user communication and coordination; additional specialists are used only when their independent work adds value.
