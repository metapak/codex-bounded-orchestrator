[English](release-v0.5.0.md) | [Türkçe](release-v0.5.0.tr.md)

# v0.5.0 release notes

Codex Bounded Orchestrator now keeps every native role on OpenAI GPT models. Prepared profiles are unchanged in intent, and custom native model IDs must use the forward-compatible `gpt-*` family. Other brands are explicit, optional API proposal tools.

The external provider selector defaults to none and now offers Anthropic Claude or DeepSeek. The new standard-library DeepSeek bridge uses the current `deepseek-flash` V4.1 Flash alias, accepts bounded supplied context, and cannot read or write the workspace. The native GPT implementer remains the sole writer.

The terminal installer now presents native profile, optional external API, and final review as three clear sections. macOS and Windows launchers explain actions and conflict behavior before prompting; Linux uses the same guided Python flow with `scripts/install.sh /path/to/project --interactive`. Output remains readable without color and survives restrictive console encodings.

No live paid provider call is made by validation. Provider compatibility is covered with mocked request tests; model access must still be confirmed in the user's own account.

Provider switching is config-aware. If the active config was modified by the user and must be preserved, the installer retains every owned bridge that config still references. The result reports requested and active providers separately and points to the pending manual-merge example.
