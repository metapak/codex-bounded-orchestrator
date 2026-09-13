
# Install on macOS

## One-click path

1. Extract the release ZIP.
2. Double-click `setup.command`.
3. Drag the target project folder into Terminal and press Return.
4. Choose `balanced`, `quality`, `economy`, or `custom`. Custom accepts OpenAI `gpt-*` models for native roles.
5. Keep the external provider at `none`, or explicitly choose a read-only Claude or DeepSeek API proposal tool.
6. Review the final native brand, role, provider, model, and effort summary.
7. The safe defaults preserve conflicting files and existing `.codex/config.toml`.

If macOS blocks the file, right-click `setup.command`, choose **Open**, then confirm.

## Terminal path

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

Python 3.11 or newer is required by the installer, candidate fingerprint tool, and local task ledger.
After installation, restart Codex and run the read-only checklist in [docs/runtime-smoke-test.md](docs/runtime-smoke-test.md).
