# 03 — Complete offline workflow

Status: ready-for-human
Blocked by: None; 01 and 02 completed.
Milestone: C2

Connect fake evidence extraction, citation/schema validation, rule derivation and
reporting. Implement CLI commands and one-snapshot pipeline, local outputs,
README, schemas and synthetic demo. See the [specification index](../spec.md).

Acceptance: fresh-install demo runs with network disabled; all three labels plus
skipped/error scenarios appear; excluded-only inputs make no evaluator call;
counts reconcile, citations resolve, invalid evidence fails visibly, and partial
failures retain completed goals but have null overall verdicts.

## Comments

- 2026-11-24: Functional demonstration is separate from real-world accuracy.

- 2026-11-24: Functional implementation and verification complete. See ConvoSignal
  milestones for test/build/connectivity evidence; C4 human validation is separate.
