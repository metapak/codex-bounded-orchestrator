[English](profiles.md) | [Türkçe](profiles.tr.md)

# Routing profiles

Profile names describe routing intent and expected relative resource use; they are not benchmarked quality, cost, or speed guarantees. Actual availability and usage depend on the user's Codex plan and workspace.

| Role | Balanced | Quality | Economy |
|---|---|---|---|
| owner | Astra medium | Astra high | Terra medium |
| fast lookup | Luna medium | Luna medium | Luna low |
| explorer | Terra medium | Astra high | Luna medium |
| researcher | Terra medium | Astra high | Terra low |
| implementer | Sol high | Astra high | Terra medium |
| verifier | Terra high | Astra high | Terra medium |
| failure analyst | Sol high | Astra high | Terra medium |
| QA operator | Sol high | Astra high | Terra medium |
| reviewer | Astra medium | Astra xhigh | Terra high |
| advisor | Astra xhigh | Astra max | Sol high |

`custom` starts from Balanced and asks for every role's exact model ID and effort. Native Codex roles accept OpenAI `gpt-*` model IDs only; Claude and DeepSeek are available through the explicit external proposal-provider flow. This prefix rule avoids a brittle exact allowlist while keeping future GPT model IDs usable. Non-interactive installs can repeat `--role-model ROLE=MODEL` and `--role-effort ROLE=EFFORT`. The installer cannot confirm that a chosen GPT model is enabled in the user's account.
