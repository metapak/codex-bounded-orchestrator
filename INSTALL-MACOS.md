
# Install on macOS

## Browser setup without typing commands

1. [Download the current `main` ZIP](https://github.com/metapak/codex-bounded-orchestrator/archive/refs/heads/main.zip) and extract it completely. Older release ZIPs may lack the GUI launcher. Install [Python 3.11+](https://www.python.org/downloads/) and [Git](https://git-scm.com/downloads) with their graphical installers if needed.
2. Open `launchers/Bounded Orchestrator.app` and choose the target Git project folder in the native picker.
3. In the local browser console, choose a work style and 1–10 planned helpers. Each helper can have its own duty, model, and reasoning level; duplicate duties are allowed. The chief is separate, and this team is not automatically started.
4. Select **Check changes**. Review the before/after choices, then select **Install** or **Save** to write only to the chosen project.
5. Use **Undo last change** if eligible, or **Close console** when finished. Restart Codex to use new settings.

If macOS blocks the unsigned app, right-click it and choose **Open**. The app needs local Python; it does not bundle a runtime. The console binds to `127.0.0.1` and does not send conversation text or credentials to the browser. Details: [local console](docs/local-console.md).

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
