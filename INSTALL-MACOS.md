
# Install on macOS

## Four steps on Mac

Have Codex, [Git](https://git-scm.com/downloads), and [Python 3.11 or newer](https://www.python.org/downloads/) installed. Python is not included.

1. **Download:** [Get the current ZIP](https://github.com/metapak/codex-bounded-orchestrator/archive/refs/heads/main.zip) and open the extracted folder.
2. **Open:** Open `launchers` and double-click **Bounded Orchestrator.app**.
3. **Follow the two folder steps:** If macOS cannot find the extracted package because it moved the app for security, the first dialog explains how to find that package in Downloads. Choose its outer folder containing `launchers` and `scripts`, such as `codex-bounded-orchestrator-main 2`. If you choose another folder, the launcher explains the mistake and lets you retry. The next dialog explains that you should choose the Git project where you work with Codex; setup will save settings there.
4. **Install:** In the browser, keep the suggested team or change it. Click **Check changes**, then **Install**. Restart Codex in that project.

For later changes, reopen the app and click **Save**; no uninstall is needed. An already-open Codex session may need to be reopened before it uses the changes. If macOS blocks the unsigned app, Control-click it and choose **Open**. Keep the app inside the extracted folder: it needs the neighboring `launch_dashboard.py` and `scripts` files. If no folder picker appears, check whether macOS is still showing a security prompt for the app. If the browser cannot open, the launcher shows an alert with the local address to open manually. See the [local console guide](docs/local-console.md) for more help.

<details>
<summary>Terminal alternative</summary>

Double-click `setup.command` to use the older guided terminal installer. It does not offer the per-slot browser team builder. It preserves an existing `.codex/config.toml` by default and shows its choices before writing.

```bash
chmod +x setup.command scripts/install.sh
./setup.command
```

If you already know the target path, this also opens the interactive profile, model, and effort selector:

```bash
./setup.command /absolute/path/to/project
```

When explicit options are present, `setup.command` passes them through unchanged. For example, the following remains non-interactive:

```bash
./setup.command /absolute/path/to/project --preset economy --dry-run
```

Non-interactive:

```bash
./scripts/install.sh /absolute/path/to/project --preset balanced
```

Preview:

```bash
./scripts/install.sh /absolute/path/to/project --preset balanced --dry-run
```

For Claude proposals, export `ANTHROPIC_API_KEY` and select `anthropic`. For DeepSeek proposals, export `DEEPSEEK_API_KEY` and select `deepseek`. Keys are inherited from the environment and are not written by the installer. See [docs/external-providers.md](docs/external-providers.md).

Python 3.11 or newer is required by the installer, browser console, candidate fingerprint tool, and local task ledger.
After installation, restart Codex and run the read-only checklist in [docs/runtime-smoke-test.md](docs/runtime-smoke-test.md).

</details>
