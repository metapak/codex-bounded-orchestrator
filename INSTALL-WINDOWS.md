
# Install on Windows

## One-click path

1. Extract the release ZIP completely.
2. Double-click `setup.cmd`.
3. Paste the target repository folder path and press Enter.
4. Choose `balanced`, `quality`, `economy`, or `custom`. Custom asks for every role's model and effort.
5. Choose whether to add the optional read-only Claude API proposal role.
6. The safe defaults preserve conflicting files and existing `.codex\config.toml`.

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

For Claude proposals, set `ANTHROPIC_API_KEY` in the environment that starts Codex and add `-ExternalProvider anthropic`. The key is not written by the installer. See [docs/external-providers.md](docs/external-providers.md).

The launcher detects `py -3`, `python`, or `python3`. Python 3.11 or newer is required by the installer, candidate fingerprint tool, and local task ledger.
After installation, restart Codex and run the read-only checklist in [docs/runtime-smoke-test.md](docs/runtime-smoke-test.md).
