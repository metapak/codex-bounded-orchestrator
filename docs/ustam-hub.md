# Ustam local hub

Download Ustam → Open → Select apps → Add projects.

Choose the native ZIP for your operating system and architecture from the release assets, extract it completely, and open Ustam.app on macOS, Ustam.exe on Windows, or Ustam on Linux. The native download includes its Python runtime. Keep the Windows/Linux executable with the other extracted files. The Mac app contains its worker and assets; it opens the hub directly without choosing a package or project folder first.

Select Codex, Claude Code, OpenCode, or any combination. Add your project folders inside the local browser page. Select projects, review the proposed changes, then apply them. Installed provider command-line tools and their login/model access are separate requirements. Ustam does not bundle those tools or provide an account. API-backed models may require their own credentials and incur charges when actually used. Offline setup and preview do not require a paid model call.

The hub keeps local preferences and registered projects in your user state directory. Projects receive configuration only after an explicit apply. Each provider runs through its own bundled, pinned engine; the engine manifest verifies the exact assets and SHA-256 hashes. Usage is locally recorded history and is not a billing balance.

These builds are unsigned and are not notarized: signing credentials are unavailable. macOS Gatekeeper may block a downloaded app; do not treat this package as a signed or notarized release. Check the release's published checksum and source before using an unsigned build. Follow macOS's security settings for software you decide to trust. Managed computers may require administrator approval. A local build passing tests does not prove a downloaded app will pass Gatekeeper.

For advanced source use, Python 3.11+ is required: run `python -m ustam`. The older provider-specific console and terminal installers remain available for compatibility. Native downloads are additional assets and do not replace the source CLI distributions.

To build locally, install PyInstaller in a separate Python environment, run `python scripts/build_ustam_engines.py` with the pinned sibling repositories available, then `python scripts/build_ustam_app.py`. CI uses `--skip-engine-build` to verify and package the checked-in immutable engine closure; it cannot silently replace it from an unrelated checkout. Build on each target OS/architecture. The windowed launcher starts a separate console worker; adapters relaunch that worker with `--adapter`, preserving JSON stdio. Windows subprocesses are hidden.

The native app version lives in `ustam/VERSION`; pinned provider engine versions and the existing source CLI release version are separate. This beta has actual local runtime evidence on Mac arm64. Windows, Linux, and Mac Intel builds still require CI build and runtime verification.

External prerequisites for a signed distribution: a Developer ID Application identity, an exported P12 certificate and password stored as protected secrets; notarization also requires an Apple account, app-specific password, and team ID. The current CI neither requests nor uses these credentials and produces unsigned packages. Never add certificates or credentials to the repository.
