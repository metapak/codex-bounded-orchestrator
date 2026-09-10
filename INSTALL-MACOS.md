
# Install on macOS

## One-click path

1. Extract the release ZIP.
2. Double-click `setup.command`.
3. Drag the target project folder into Terminal and press Return.
4. Choose `balanced`, `quality`, `economy`, or `custom`. Custom asks for every role's model and effort.
5. Choose whether to add the optional read-only Claude API proposal role.
6. The safe defaults preserve conflicting files and existing `.codex/config.toml`.

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

For Claude proposals, export `ANTHROPIC_API_KEY` before launching Codex and add `--external-provider anthropic`. The key is inherited from the environment and is not written by the installer. See [docs/external-providers.md](docs/external-providers.md).

Python 3.11 or newer is required by the installer, candidate fingerprint tool, and local task ledger.
After installation, restart Codex and run the read-only checklist in [docs/runtime-smoke-test.md](docs/runtime-smoke-test.md).
