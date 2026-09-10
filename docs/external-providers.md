[English](external-providers.md) | [Türkçe](external-providers.tr.md)

# Optional Anthropic API bridge

Codex supports MCP tools, so this project can optionally expose Anthropic's Messages API as a local stdio MCP tool. This is an API-backed tool integration, not a native Claude subagent inside Codex.

## Install

Set the key only in the environment that launches Codex:

```bash
export ANTHROPIC_API_KEY="your-key"
python3 scripts/install.py /path/to/project \
  --preset balanced \
  --external-provider anthropic \
  --external-model claude-sonnet-5 \
  --external-effort high
```

The installer adds `.codex/tools/anthropic_mcp.py` and an `anthropic_claude` MCP server entry only when selected. Existing `.codex/config.toml` files are preserved unless they are still unmodified installer-owned files or `--force-config` is used. In a conflict, merge the generated example manually.

## Boundary

The tool accepts a task, supplied context, constraints, and a non-empty allowlist of repository-relative paths. It sends those values to Anthropic and requests a unified-diff proposal. It has no workspace path parameter, does not read files, and does not apply changes. The native implementer remains the only writer and must review any proposal before applying it.

Do not include credentials, personal data, proprietary source outside the agreed scope, or unrelated files in the supplied context. API use is subject to the user's Anthropic account, model access, quota, and billing.

## Models and effort

As verified on 2026-09-10, the prepared choices use the current pinned Claude API IDs `claude-sonnet-5` and `claude-opus-5`. Anthropic's [effort documentation](https://platform.claude.com/docs/en/build-with-claude/effort) lists both models as supporting `low`, `medium`, `high`, `xhigh`, and `max`; the bridge sends the selected value as `output_config.effort`. A custom model ID may be installed, but availability and effort support must be checked against Anthropic's current [model overview](https://platform.claude.com/docs/en/about-claude/models/overview) and [Messages API reference](https://platform.claude.com/docs/en/api/messages/create), plus the user's account.

The repository test suite exercises the complete local MCP handshake and a mocked Messages API HTTP request. It does not claim a live paid API call in CI.
