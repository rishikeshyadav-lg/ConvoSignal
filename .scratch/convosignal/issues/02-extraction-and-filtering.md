# 02 — Extraction and safe filtering

Status: ready-for-human
Blocked by: None; 01 completed.
Implementation: Complete; available for review.
Milestone: C1

Implement offline trace/conversation normalization, proposal sampling/validation,
coverage, explicit acceptance, hashes and faithful longest-marker classification.
Implement exact standalone exclusion examples, conservative mixed-request routing
and retention of feedback/context. See the [specification index](../spec.md).

Acceptance: all original-brief Stage 1 tests pass, including duplicate traffic,
blanks, malformed shapes, tie ordering, checksum changes, policy overrides,
unclassified tasks, partial extraction failure and zero-question diagnostics.

## Comments

- 2026-11-24: Planned; depends on versioned contracts from 01.

- 2026-11-24: C1 completed; 112 network-blocked synthetic tests pass across
  Python 3.11 and 3.12. CLI integration/model calls remain later milestones.
