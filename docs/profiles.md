[English](profiles.md) | [Türkçe](profiles.tr.md)

# Routing profiles

Profile names describe routing intent and expected relative resource use; they are not benchmarked quality, cost, or speed guarantees. Actual availability and usage depend on the user's Codex plan and workspace.

| Role | balanced | quality | economy | quota-saver | custom | focused |
|---|---|---|---|---|---|---|
| owner | 6-astra medium | 6-astra high | 5.6-terra medium | 6-astra low | 6-astra medium | 6-sol medium |
| fast_lookup | 5.6-luna medium | 5.6-luna medium | 5.6-luna low | 5.6-luna low | 5.6-luna medium | 6-luna high |
| explorer | 5.6-terra medium | 6-astra high | 5.6-luna medium | 5.6-terra low | 5.6-terra medium | 6-luna high |
| researcher | 5.6-terra medium | 6-astra high | 5.6-terra low | 5.6-terra low | 5.6-terra medium | 6-sol medium |
| implementer | 5.6-sol high | 6-astra high | 5.6-terra medium | 5.6-sol medium | 5.6-sol high | 6-sol medium |
| verifier | 5.6-terra high | 6-astra high | 5.6-terra medium | 5.6-terra medium | 5.6-terra high | 6-sol medium |
| failure_analyst | 5.6-sol high | 6-astra high | 5.6-terra medium | 5.6-sol medium | 5.6-sol high | 6-sol medium |
| qa_operator | 5.6-sol high | 6-astra high | 5.6-terra medium | 5.6-sol medium | 5.6-sol high | 6-sol medium |
| reviewer | 6-astra medium | 6-astra xhigh | 5.6-terra high | 6-astra low | 6-astra medium | 6-sol medium |
| advisor | 6-astra xhigh | 6-astra max | 5.6-sol high | 6-astra low | 6-astra xhigh | 6-sol medium |

`custom` starts from Balanced and asks for every role's exact model ID and effort. Native Codex roles accept OpenAI `gpt-*` model IDs only; Claude and DeepSeek are available through the explicit external proposal-provider flow. This prefix rule avoids a brittle exact allowlist while keeping future GPT model IDs usable. Non-interactive installs can repeat `--role-model ROLE=MODEL` and `--role-effort ROLE=EFFORT`. The installer cannot confirm that a chosen GPT model is enabled in the user's account.


`focused` uses Sol medium for the owner, Luna high for narrow lookup/exploration and Sol medium for other bounded specialists. It recommends no Astra role. It is the new-console default; existing CLI presets remain unchanged. [Local console](local-console.md)


The profiles change role models and reasoning effort; they do not change the planned helper count or the separate concurrency cap. **Economy** moves the owner and most specialists toward Terra and lowers effort for some roles. **Quota saver** keeps Astra as the owner and mostly reduces reasoning effort across the existing mix. **Focused** uses Sol for the owner and most specialists and Luna for lookup/exploration; it recommends no Astra role. **Quality** moves most roles to Astra with deeper reasoning. These are routing choices, not measured token savings or guaranteed cost/quality outcomes. The console shows exact before/after role selections before saving.
