
# Install on Windows

## Browser setup without typing commands

1. Extract the source or Windows ZIP completely. Install Python 3.11 or newer and Git if needed.
2. Double-click `launchers/Launch Bounded Orchestrator.vbs` and choose the target Git project folder in the folder picker.
3. In the local browser console, choose a work style and 1–10 planned helpers. Each helper can have its own duty, model, and reasoning level; duplicate duties are allowed. The chief is separate, and this team is not automatically started.
4. Select **Check changes**. Review the before/after choices, then select **Install** or **Save** to write only to the chosen project.
5. Use **Undo last change** if eligible, or **Close console** when finished. Restart Codex to use new settings.

The launcher uses local Python; it does not bundle a runtime. The console binds to `127.0.0.1` and does not send conversation text or credentials to the browser. Details: [local console](docs/local-console.md).

## Terminal alternative

Double-click `setup.cmd` to use the older guided terminal installer. It does not offer the per-slot browser team builder. It preserves an existing `.codex\config.toml` by default and shows its choices before writing.

## PowerShell path

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

Non-interactive:

```powershell
.\scripts\install.ps1 -Target "C:\path\to\project" -Preset balanced
```

Preview:

```powershell
.\scripts\install.ps1 -Target "C:\path\to\project" -Preset balanced -DryRun
```

For Claude proposals, set `ANTHROPIC_API_KEY` and select `anthropic`. For DeepSeek proposals, set `DEEPSEEK_API_KEY` and select `deepseek`. Keys are not written by the installer. See [docs/external-providers.md](docs/external-providers.md).

The terminal launcher detects `py -3`, `python`, or `python3`. Python 3.11 or newer is required by the installer, browser console, candidate fingerprint tool, and local task ledger.
After installation, restart Codex and run the read-only checklist in [docs/runtime-smoke-test.md](docs/runtime-smoke-test.md).
