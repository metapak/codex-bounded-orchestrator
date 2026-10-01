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
  --external-model claude-sonnet-5-5 \
  --external-effort high
```

The browser console and guided installer offer `claude-fable-5-1`, `claude-opus-5-5`, `claude-sonnet-5-5`, and `claude-haiku-4-5-20251001`. The first three use supported `low`, `medium`, `high`, `xhigh`, or `max` effort. Haiku 4.5 has no separate effort setting: its bridge omits `output_config` when `auto` is selected. These IDs and the effort boundary follow [Anthropic's model list](https://platform.claude.com/docs/en/models/overview) and [effort guide](https://platform.claude.com/docs/en/build-with-claude/effort). Account access is not checked. The CLI still accepts a custom `claude-*` ID, but its availability and effort support must be checked against provider documentation.

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

The browser choice is `deepseek-flash`. DeepSeek's [V4.1 Flash announcement](https://deepseek.com/en/news/deepseek-v4-1-flash/) identifies that alias. The browser offers the distinct Responses API reasoning levels `none`, `low`, `high`, and `max`; the API accepts some other CLI bridge values as aliases, as its [Responses API reference](https://api-docs.deepseek.com/api/create-response/) explains. A custom `deepseek-*` model ID can be supplied through the CLI, but availability must be checked against the provider and account.

## Boundary and data handling

Each bridge accepts a task, explicitly supplied context, constraints, and a non-empty allowlist of repository-relative paths. It has no workspace path parameter, does not read files, and does not apply changes. The native GPT implementer remains the sole writer and must review any proposal before applying it.

Do not include credentials, personal data, proprietary source outside the agreed scope, or unrelated files in supplied context. The selected context is sent to the provider. API use is subject to that provider's access, quota, data terms, and billing.

The installer adds the selected provider's bridge and MCP entry. When it updates the active config, switching providers or returning to `none` removes an unchanged installer-owned bridge that is no longer selected. If a user-modified `.codex/config.toml` is preserved for manual merging, every installer-owned bridge still referenced by that active config is retained. The result distinguishes the requested provider from the active provider and shows the generated example path. `--force-config` remains the explicit backup-and-replace option.

The test suite exercises each local MCP handshake and mocked HTTP request. It makes no live paid API call and claims no live-provider compatibility beyond the documented request format.
