# 09: Demonstrate the revision on the frozen 100 sessions

**What to build:** The evaluation owner can inspect a complete, reproducible
comparison of the revised criteria against the original 100-session predictions,
with an audited private report and explicit functional/validation status.

**Blocked by:** 06 — Judge complete conversations with scoped overall feedback;
08 — Explain old/new results on frozen sources.

**Status:** ready-for-human

**Implementation:** Complete; verified and available for review. Independent human validation remains pending.

- [x] Use the preserved final frozen 100-session source and unchanged accepted
  taxonomy/filter policy. Preserve all original predictions and write revised
  outputs separately; do not silently select new sessions or exclusions.
- [x] Evaluate with declared versions and consistent recorded budgets. Keep
  bounded structural repair and provider diagnostics; do not retry for a label,
  discard source turns or weaken validation to force complete coverage.
- [x] Produce the comparison report, source/replay audit, versions, citations,
  raw evidence attempts, per-goal results and reconciled coverage. Operational
  failures remain visible rather than being forced to zero or scored Neutral.
- [x] Verify saved evidence matches authoritative source turns and deterministic
  replay reproduces the new saved decisions under the declared policy.
- [x] Provide a blank independent-review packet and report the actual validation
  state. Human annotations are not an implementation prerequisite; absent human
  evidence cannot pass the independent gate.
- [x] Report findings without a required Satisfied share or claims of improved
  accuracy, measured user feelings or a newly untouched holdout.
- [x] Complete package lint/format/types/tests, compatibility/build checks,
  required Account360 regression checks and Databricks dev bundle validation.
  Confirm sensitive pilot data stay out of version control and distributions.
- [x] Update feature delivery documentation with measured results, remaining
  limitations and independent validation status, without altering parent issues.
