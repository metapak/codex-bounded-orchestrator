
# Install on Windows

## One-click path

1. Extract the release ZIP completely.
2. Double-click `setup.cmd`.
3. Paste the target repository folder path and press Enter.
4. Keep the default `Astra owner` profile unless Astra is unavailable in your Codex workspace.
5. The safe defaults preserve conflicting files and existing `.codex\config.toml`.

## PowerShell path

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

Non-interactive:

```powershell
.\scripts\install.ps1 -Target "C:\path\to\project" -Profile astra
```

Preview:

```powershell
.\scripts\install.ps1 -Target "C:\path\to\project" -Profile astra -DryRun
```

The launcher detects `py -3`, `python`, or `python3`. Python 3.11 or newer is required by the installer, candidate fingerprint tool, and local task ledger.
After installation, restart Codex and run the read-only checklist in [docs/runtime-smoke-test.md](docs/runtime-smoke-test.md).
