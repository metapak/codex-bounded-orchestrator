
# Install on macOS

## One-click path

1. Extract the release ZIP.
2. Double-click `setup.command`.
3. Drag the target project folder into Terminal and press Return.
4. Keep the default `Astra owner` profile unless Astra is unavailable in your Codex workspace.
5. The safe defaults preserve conflicting files and existing `.codex/config.toml`.

If macOS blocks the file, right-click `setup.command`, choose **Open**, then confirm.

## Terminal path

```bash
chmod +x setup.command scripts/install.sh
./setup.command
```

Non-interactive:

```bash
./scripts/install.sh /absolute/path/to/project --profile astra
```

Preview:

```bash
./scripts/install.sh /absolute/path/to/project --profile astra --dry-run
```

Python 3.11 or newer is required by the installer and candidate fingerprint tool.
After installation, restart Codex and run the read-only checklist in [docs/runtime-smoke-test.md](docs/runtime-smoke-test.md).
