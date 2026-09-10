[English](release-v0.3.0.md) | [Türkçe](release-v0.3.0.tr.md)

# v0.3.0 release notes

v0.3.0 adds visibility for declared work and two optional expertise lenses while preserving the v0.2.0 authority model.

The new `.codex/tools/ledger.py` records short local task metadata, validates dependencies and state transitions, reports human-readable or JSON status, and blocks review/completion when declared required work remains unresolved. Files are atomically written inside the ignored runtime directory with restrictive permissions where supported. Temporary descriptors are explicitly closed before replacement for Windows compatibility. The ledger never needs prompt, source, diff, log, personal-data, credential, or secret content.

The UI design and security review packs are installed as separate opt-in skills. They add focused questions and checks while preserving one owner, one writer per scope, independent verification, frozen review candidates, finite loops, and exact authority for external actions.

The installer and uninstaller track the new files using the existing conflict-preserving ownership manifest. Static validation and release archives now require them. Artifact version expectations in tests come from `VERSION`.

Known limit: the ledger can find unresolved work only among tasks that were declared. It does not prove completeness or correctness. Expertise packs are instructions and do not add enforcement or permission.
