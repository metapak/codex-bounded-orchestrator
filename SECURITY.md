# Security policy

## Supported versions

Security fixes are applied to the current release line.

| Version | Supported |
|---|---|
| 0.2.x | Yes |
| Earlier versions | No |

## Report a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/metapak/codex-bounded-orchestrator/security/advisories/new). Include the affected version, platform, reproduction steps, impact, and any suggested mitigation. Please do not publish exploit details in a public issue before a fix is available.

Do not include live credentials, tokens, private keys, personal data, production data, or secrets in the report. Replace sensitive values with safe examples.

## Scope and boundaries

Useful reports include vulnerabilities in:

- installer path validation, backup, overwrite, or uninstall behavior
- candidate manifest integrity or unintended source-content capture
- release archive construction or path traversal
- checked-in configuration that unexpectedly broadens write or delegation permissions
- documentation that directs users toward an unsafe destructive action

This repository supplies project configuration, role instructions, and local tools. It does not replace Codex sandboxing, operating-system permissions, repository review, or human authorization. In particular:

- Live parent permission choices can override child sandbox defaults.
- Prompt instructions are procedural guardrails, not an access-control system.
- The candidate tool stores file hashes and Git metadata, not source contents; it detects changes but does not prevent them or prove correctness.
- Installer backups and manifests are local and ignored by the supplied Git rules.
- Push, merge, deployment, release, migration, billing, account, and destructive operations require explicit user authority under the supplied workflow.

If you are unsure whether a report is a security issue, use the private reporting channel and describe the concrete failure mode.
