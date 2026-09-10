# Source provenance and publication changes

Version 0.2.0 was recovered from the prepared macOS distribution archive.
Its SHA-256 was verified before publication:

```text
76135c8037e158639f0c3b470286040698669c0da02604547bab39b6a006a4bf
```

The original source ZIP and Git bundle were unavailable. This repository therefore
starts a new publication history; it does not claim to preserve the original
v0.1.0/v0.2.0 commits or their tags.

Publication changes: expanded English and Turkish documentation, community
contribution templates, roadmap, examples, and explicit verification limits.
The generated macOS start note was removed from the source tree because the
release builder creates the appropriate start note for each platform. Installer,
agent profiles, candidate tool, and orchestration policy originate from the
recovered package. New release archives have new checksums.

## Upstream inspiration

The supplied project credits [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator).
The upstream repository was inspected on 2026-09-10 at commit
`f1de1b8729c8ccfb7978321b4764c58bd34c8493`: it declares Apache-2.0,
contains the standard Apache license, and has no root NOTICE file. The supplied
[LICENSE](../LICENSE) matches that license verbatim. The supplied
[NOTICE](../NOTICE) is retained, including author and inspiration attribution.
No upstream endorsement or transfer of trademark rights is implied.

See [architectural differences](from-astra-luna-orchestrator.md).
