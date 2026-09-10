# Runtime smoke test

Run this after installation and after material Codex client upgrades. Static TOML validation proves the intended routing; only a live session can prove which role/model/sandbox the current client actually applied.

## 1. Confirm the installed files

From the target repository:

```bash
python .codex/tools/candidate.py --help
```

Open `.codex/config.toml` and confirm the selected root profile. The default should be:

```toml
model = "gpt-6-astra"
model_reasoning_effort = "medium"
```

## 2. Start a fresh Codex session

Open the target repository as a trusted project, restart the client if the configuration was just installed, and use this prompt:

```text
$bounded-orchestrator

Run a read-only orchestration smoke test. Do not edit any file, create a commit,
push, deploy, or perform external actions.

1. Confirm the root owner model and reasoning effort visible to this session.
2. Spawn explorer for one bounded read-only task: list the repository root and
   identify the primary language from tracked files only.
3. Spawn reviewer for a separate read-only task: inspect no code and return
   exactly "SMOKE_REVIEW_PASS" plus the role/model/effort/sandbox metadata that
   the client exposes.
4. Do not spawn implementer, verifier, QA, or advisor.
5. Report the actual role names, models, reasoning efforts, and sandboxes used.
6. Report any field the client does not expose as "not observable" rather than
   inferring it.
```

## 3. Pass criteria

- The root uses the selected Astra medium profile, or the explicitly selected Sol high fallback.
- `explorer` and `reviewer` are discoverable by their registered names.
- The explorer performs no write.
- The reviewer performs no write and returns findings only.
- No child creates another child.
- Any unobservable runtime metadata is reported honestly.

`fast_lookup` is optional. Some plans or client surfaces may not expose Luna as a child model. When that role is unavailable, use the Terra `explorer` for the same exact read-only query; do not weaken the core workflow or silently substitute Luna for implementation.

## 4. Failure handling

If a named role is missing or its pinned model is ignored:

1. Stop before production implementation.
2. Confirm the project is trusted and the client was restarted.
3. Confirm the role is explicitly registered in `.codex/config.toml` and its `config_file` path exists.
4. Check the client version and model access for the current plan/workspace.
5. Use the default Terra path only for read-only evidence work until the runtime behavior is understood.

A static configuration that looks correct is not proof that a particular client build honored every per-role override.
