
# Repository instructions

This repository defines a public, project-scoped Codex orchestration setup.

When modifying it:

- preserve the bounded-owner architecture and one-level topology
- keep the macOS and Windows installation paths behaviorally equivalent
- update English and Turkish documentation together
- run `python scripts/validate.py` and `python -m unittest discover -s tests -v`
- do not weaken candidate freezing, one-writer ownership, independent verification, read-only review, or finite loop limits
- do not publish, tag, release, or push without explicit user authority
