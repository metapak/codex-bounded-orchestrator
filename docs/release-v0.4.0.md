[English](release-v0.4.0.md) | [Türkçe](release-v0.4.0.tr.md)

# v0.4.0 release notes

v0.4.0 adds a Turkish-friendly one-click profile selector and an optional Anthropic API proposal role.

- Choose `balanced`, `quality`, `economy`, or `custom` during setup.
- In `custom`, choose the model and effort for every role.
- Automate the same choices with `--preset`, `--role-model`, and `--role-effort`.
- Optionally install a dependency-free local MCP bridge for Claude patch proposals.
- Keep `ANTHROPIC_API_KEY` in the environment; it is never copied into config or the manifest.
- Preserve the native single-writer rule: the bridge cannot read or write the workspace.
- Reject uninstall manifest paths outside the fixed managed-file allowlist.

The external bridge is covered by a local MCP handshake test and a mocked Anthropic Messages API HTTP test. No live paid API call was made as part of repository validation.
