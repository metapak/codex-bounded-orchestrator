# Ustam local hub

Download Ustam → Open → Select apps → Add projects.

For Windows/Linux, choose the native ZIP for your system from the release assets, extract it completely, and open Ustam.exe on Windows or Ustam on Linux. Published Mac downloads still have unresolved first-launch issues; use the source build route below. The native download includes its Python runtime. Keep the Windows/Linux executable with the other extracted files. The Mac app contains its worker and assets; it opens the hub directly without choosing a package or project folder first.

Select Codex, Claude Code, OpenCode, or any combination. Add your project folders inside the local browser page. Select projects, review the proposed changes, then apply them. Installed provider command-line tools and their login/model access are separate requirements. Ustam does not bundle those tools or provide an account. API-backed models may require their own credentials and incur charges when actually used. Offline setup and preview do not require a paid model call.

The hub keeps local preferences and registered projects in your user state directory. Projects receive configuration only after an explicit apply. Each provider runs through its own bundled, pinned engine; the engine manifest verifies the exact assets and SHA-256 hashes. Usage is locally recorded history and is not a billing balance.

These builds are unsigned and are not notarized: signing credentials are unavailable. macOS Gatekeeper may block a downloaded app; do not treat this package as a signed or notarized release. Check the release's published checksum and source before using an unsigned build. Follow macOS's security settings for software you decide to trust. Managed computers may require administrator approval. A local build passing tests does not prove a downloaded app will pass Gatekeeper.

For advanced source use, Python 3.11+ is required: run `python -m ustam`. The older provider-specific console and terminal installers remain available for compatibility. Native downloads are additional assets and do not replace the source CLI distributions.

To build locally, install PyInstaller in a separate Python environment, run `python scripts/build_ustam_engines.py` with the pinned sibling repositories available, then `python scripts/build_ustam_app.py`. CI uses `--skip-engine-build` to verify and package the checked-in immutable engine closure; it cannot silently replace it from an unrelated checkout. Build on each target OS/architecture. The windowed launcher starts a separate console worker; adapters relaunch that worker with `--adapter`, preserving JSON stdio. Windows subprocesses are hidden.

The native app version lives in `ustam/VERSION`; pinned provider engine versions and the existing source CLI release version are separate. This beta has actual local runtime evidence on Mac arm64. Windows, Linux, and Mac Intel builds still require CI build and runtime verification.

External prerequisites for a signed distribution: a Developer ID Application identity, an exported P12 certificate and password stored as protected secrets; notarization also requires an Apple account, app-specific password, and team ID. The current CI neither requests nor uses these credentials and produces unsigned packages. Never add certificates or credentials to the repository.

The macOS beta.1 package changed Info.plist after the app was sealed, invalidating its integrity signature and causing the “damaged” warning. beta.2 seals the fully assembled app and verifies its signature after ZIP extraction. The beta.2 downloaded app still has unresolved launch issues; updating to it does not establish a working Mac installation. An ad-hoc integrity seal is not Apple Developer ID signing or notarization; Gatekeeper trust assessment remains separate and may still block the app.

The unpublished macOS beta.3 candidate repairs the missing resource seal in the worker Python framework. Package checks verify each framework root and every native Mach-O individually before ZIP creation and after extraction, rather than relying only on the outer app signature. Apple Developer ID signing and notarization are still absent. If macOS permits it, first launch may require your approval through System Settings → Privacy & Security → Open Anyway. If that option is unavailable, do not bypass the block by disabling security settings or removing quarantine.

A local source build was opened successfully on the development Mac, and the user confirmed seeing the page. This local copy had no quarantine attribute naturally; none was removed. The downloaded quarantine-marked test copy remained blocked and macOS did not offer Open Anyway. This is evidence for local installation on that Mac, not successful distribution of a prebuilt Mac package.

For a local Mac build, use Python 3.11+ and an isolated build environment from this source checkout: `python3 -m venv .venv-build`, `.venv-build/bin/python -m pip install pyinstaller==6.22.3`, then `.venv-build/bin/python scripts/build_ustam_app.py --skip-engine-build`. Open the resulting `dist/ustam-*/Ustam.app`. The build verifies pinned engines and all native code before and after archiving. Once built, the app includes Python. The source version 1.0.0-beta.3 is a development candidate; no beta.3 public release or native download is available.
