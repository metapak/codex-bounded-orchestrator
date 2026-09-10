[English](faq.md) | [Türkçe](faq.tr.md)

# FAQ and troubleshooting

## Does this guarantee that each model and sandbox will be used?

No. The repository supplies intended project config and role instructions. Client version, product surface, trust state, plan access, and parent permissions can affect live behavior. Run the [runtime smoke test](runtime-smoke-test.md) and treat unobservable metadata as unknown.

## Why did installation create a config example?

An existing `.codex/config.toml` is preserved by default. The installer writes `.codex/bounded-orchestrator.config.example.toml` so you can review and merge it manually. Use `--force-config` only when you intend to back up and replace the root config.

## Why was an agent or tool file skipped?

The destination differs from the supplied file. Review the difference first. `--force` backs up and replaces conflicting managed role, skill, and tool files; it does not replace root config unless `--force-config` is also used.

## Does candidate freeze prevent changes?

No. It records hashes and Git identity, then `verify` detects whether the frozen candidate changed. It does not lock files, prove correctness, or replace tests and review.

## Can the task ledger prove that no work was forgotten?

No. It flags unresolved required tasks that were declared. The owner must still declare the right work, inspect the result, run tests, and complete independent review. Keep prompts, source, logs, personal data, credentials, and secrets out of ledger labels and reasons.

## Do expertise packs grant extra permissions?

No. They are opt-in instruction sets. They do not create agents, change sandboxes, provide credentials, or authorize external actions.

## Why did uninstall keep a file?

Uninstall removes only files recorded as installer-owned and unchanged since installation. It keeps pre-existing or modified files to avoid deleting user work. It also removes only the marked bounded-orchestrator block from `AGENTS.md`.

## When should I use the Sol-owner profile?

Use `--profile sol` when the supplied Astra root-owner model is unavailable or when you explicitly prefer Sol high as root. The other supplied role routes remain in place. Confirm actual model availability in your Codex plan or workspace.

## Can Claude replace a native Codex subagent?

The optional bridge exposes Claude as an API-backed MCP proposal tool, not a native Codex subagent. It cannot inspect or edit the repository. Codex must supply bounded context, and the native implementer reviews and applies accepted changes.

## Why does the Claude tool say the API key is missing?

Set `ANTHROPIC_API_KEY` in the same shell or application environment that starts Codex, then restart Codex. Do not add the key to `.codex/config.toml`, the repository, or an installer argument.
