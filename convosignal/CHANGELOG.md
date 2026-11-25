# Changelog

## Unreleased

### Added

- Portable `acquire`, `batch-evaluate`, `replay` and `report` commands, plus an
  installed `convosignal` console entry point.
- Frozen-source/policy validation, atomic conversation checkpoints, single-writer
  protection and contract-bound resume that retains interrupted attempts.
- Typed report metadata and source-derived statistics, offline HTML inspection,
  editable Word documents, CSV/JSON exports and checksum manifests.
- Packaged report assets, clean-installed-wheel verification, Python 3.11/3.12 CI,
  and operational/reproduction documentation.

### Fixed

- JSONL readers now preserve Unicode line/paragraph separators inside captured
  source instead of treating them as record boundaries.

Classification rules, versioned prompts, existing CLI defaults and historical
results are unchanged. No public registry release or deployment has occurred.
Independent human accuracy validation remains pending.
