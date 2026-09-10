# Codex Bounded Orchestrator v0.2.0

A project-scoped Codex workflow with one accountable owner, explicit task ownership,
separate verification, and a finite review process.

## Included

- Nine registered agent roles: Terra exploration/research/verification, Sol
  implementation/diagnosis/QA, Astra review/advice, and optional Luna lookup.
- Astra medium owner by default, with a Sol owner preset.
- Python standard-library installer, macOS and Windows launchers, conflict
  preservation, local backups for explicit replacement, and conservative uninstall.
- Candidate fingerprint tool to check that reviewed files have not changed.
- English and Turkish entry points, examples, troubleshooting, and roadmap.
- Apache-2.0 license and retained upstream attribution.

## Downloads

Choose the macOS or Windows ZIP for the corresponding start instructions.
The source ZIP contains the project for manual installation and development.
Extract the archive fully; use Git and Python 3.11 or newer. Follow the included
README and preview the installation before applying it to a separate project.
`SHA256SUMS.txt` records SHA-256 hashes for the release assets.

## Verification and limits

The recovered source passes 22 local automated tests on macOS with Python 3.14.7.
The repository includes CI for Ubuntu, macOS, and Windows with Python 3.11.
Check the workflow run for this release commit for the actual hosted results.
These checks do not establish an end-to-end live Codex model session or graphical
installer execution. Model access and client behavior must be checked with the
included runtime smoke test. Instruction-level review and ownership rules are
not a security sandbox, cost cap, or guarantee of correct output.

## Provenance

This is the first public publication of the prepared v0.2.0 source, recovered
from its verified macOS archive. Original Git history was unavailable and is not
reconstructed. Publication documentation and packaging differ from the original
archive; see `docs/provenance.md`. Release asset checksums are newly generated.

## Türkçe

Tek sorumlu yönetici, açık görev sahipliği, ayrı doğrulama ve sınırlı inceleme
süreci sunan, proje bazlı Codex kurulumu. macOS veya Windows ZIP dosyasını açıp
`README.tr.md` ile başlayın. Git ve Python 3.11+ gereklidir.

Yerel macOS ortamında 22 otomatik test geçti. Canlı Codex model yönlendirmesi
ve grafik arayüzden kurulum bu sonuçlara dahil değildir. Destek sınırlarını ve
kurulum önizlemesini okuyun. Apache-2.0 lisansı ve kaynak atıfları korunmuştur.
