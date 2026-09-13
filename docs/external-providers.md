[English](external-providers.md) | [Türkçe](external-providers.tr.md)

# Optional external API proposal providers

Codex uses OpenAI GPT models for every native role. The installer defaults to no external provider. Anthropic and DeepSeek are optional API-backed MCP tools that return bounded implementation proposals; they are not native Codex subagents.

## Guided setup

The interactive installer presents three explicit choices:

1. None (default)
2. Anthropic Claude proposal
3. DeepSeek proposal

It then shows the provider, model, effort, and proposal-only boundary in the final review. Selecting a provider does not store an API key.

## Anthropic

Set the key only in the environment that launches Codex:

```bash
export ANTHROPIC_API_KEY="your-key"
python3 scripts/install.py /path/to/project \
  --preset balanced \
  --external-provider anthropic \
  --external-model claude-sonnet-5 \
  --external-effort high
```

Prepared choices are `claude-sonnet-5` and `claude-opus-5`. Anthropic efforts are `low`, `medium`, `high`, `xhigh`, and `max`. A custom `claude-*` model ID can be supplied, but availability and effort support depend on the user's account and current Anthropic documentation.

## DeepSeek

Set the key only in the environment that launches Codex:

```bash
export DEEPSEEK_API_KEY="your-key"
python3 scripts/install.py /path/to/project \
  --preset balanced \
  --external-provider deepseek \
  --external-model deepseek-flash \
  --external-effort high
```

The prepared choice is `deepseek-flash`. DeepSeek's September 10, 2026 [V4.1 Flash announcement](https://deepseek.com/en/news/deepseek-v4-1-flash/) identifies that alias for the current API model and says older V4 Flash aliases temporarily route to it. Supported bridge effort values follow DeepSeek's Responses API shape: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`. A custom `deepseek-*` model ID can be supplied, but availability must be checked against current provider documentation and the user's account.

## Boundary and data handling

Each bridge accepts a task, explicitly supplied context, constraints, and a non-empty allowlist of repository-relative paths. It has no workspace path parameter, does not read files, and does not apply changes. The native GPT implementer remains the sole writer and must review any proposal before applying it.

Do not include credentials, personal data, proprietary source outside the agreed scope, or unrelated files in supplied context. The selected context is sent to the provider. API use is subject to that provider's access, quota, data terms, and billing.

The installer adds the selected provider's bridge and MCP entry. When it updates the active config, switching providers or returning to `none` removes an unchanged installer-owned bridge that is no longer selected. If a user-modified `.codex/config.toml` is preserved for manual merging, every installer-owned bridge still referenced by that active config is retained. The result distinguishes the requested provider from the active provider and shows the generated example path. `--force-config` remains the explicit backup-and-replace option.

The test suite exercises each local MCP handshake and mocked HTTP request. It makes no live paid API call and claims no live-provider compatibility beyond the documented request format.
