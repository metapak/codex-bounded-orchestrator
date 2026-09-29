
# Install on Windows

## Four steps on Windows

Have Codex, [Git](https://git-scm.com/downloads), and [Python 3.11 or newer](https://www.python.org/downloads/) installed. Python is not included.

1. **Download:** [Get the current ZIP](https://github.com/metapak/codex-bounded-orchestrator/archive/refs/heads/main.zip) and open the extracted folder.
2. **Open:** Open `launchers` and double-click **Launch Bounded Orchestrator.vbs**.
3. **Choose a project:** Pick the Git project folder where you use Codex.
4. **Install:** In the browser, keep the suggested team or change it. Click **Check changes**, then **Install**. Restart Codex in that project.

For later changes, reopen the launcher and click **Save**; no uninstall is needed. An already-open Codex session may need to be reopened before it uses the changes. Double-click behavior has not been tested on every Windows setup. See the [local console guide](docs/local-console.md) for more help.

<details>
<summary>Terminal alternative</summary>

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

</details>
