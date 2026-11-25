# 01 — Contracts and deterministic rules

Status: ready-for-human
Blocked by: None.
Implementation: Complete; available for review.
Milestone: C0

Read the [spec](../../../convosignal/docs/Prod-Spec.md) and architecture via the
[issue index](../spec.md). Propose exact dependency bounds, scaffold the isolated
package after approval, define versioned schemas and implement pure goal and
conversation rules. No model calls are needed for this issue.

Acceptance: the complete behavioral matrix passes; paired fixtures independently
assert requirements, feedback, correctness, recovery and verdict. Apparent repair
without acceptance produces Neutral, and identical evidence replays identically.

## Comments

- 2026-11-24: Planned; no implementation performed.

- 2026-11-24: Core dataclasses, chronological rule replay and eight tests implemented
  without dependencies. Full schemas and remaining acceptance coverage pending;
  issue remains open.

- 2026-11-24: C0 completed with dependency authorization, validated schemas and
  50 passing behavioral/contract tests; quality and packaging checks pass.
