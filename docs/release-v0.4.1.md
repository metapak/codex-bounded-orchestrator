[English](release-v0.4.1.md) | [Türkçe](release-v0.4.1.tr.md)

# v0.4.1 release notes

v0.4.1 fixes the interactive installer on Windows consoles whose active encoding cannot represent every Turkish character.

- Installer startup configures standard output and standard error to retain the terminal's active encoding while replacing only unsupported characters.
- UTF-8 terminals continue to display the original Turkish text.
- Restrictive encodings such as cp1252 display safe replacement characters instead of raising `UnicodeEncodeError` and stopping installation.
- A regression test runs the interactive dry-run flow with strict cp1252 output streams.

All v0.4.0 profile selection, custom role routing, optional Claude API bridge, secret handling, and bounded-workflow behavior remain unchanged.
