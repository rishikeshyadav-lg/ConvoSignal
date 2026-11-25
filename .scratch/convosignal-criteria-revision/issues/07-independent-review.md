# 07: Assess reviewer agreement without label leakage

**What to build:** An evaluation owner can prepare blind review material from
saved predictions and source snapshots, then compare independently frozen human
annotations and obtain an auditable pass, fail or pending validation assessment.

**Blocked by:** None (can start immediately).

**Status:** ready-for-human

**Implementation:** Complete; verified and available for review. Independent human validation remains pending.

- [x] Review packets contain necessary source context and stable identifiers,
  with blank annotations and no predicted labels exposed to reviewers.
- [x] Preserve snapshot binding and reject duplicate/mismatched reviews or
  model-generated annotations presented as independent human judgments.
- [x] At the conversation level, assess each non-Neutral predicted class
  separately: precision must reach 90%, with at least 30 independently reviewed
  predictions in that class. Missing reviews/classes keep validation pending.
- [x] Report confusion matrix, recall, Neutral share, operational/review coverage,
  sample sizes, uncertainty and available direct/inferred breakdowns.
- [x] Disclose class-targeted sampling and prevent misleading unweighted recall
  or population-rate claims where review sampling is not representative.
- [x] Keep functional tooling completion separate from actual independent
  validation; do not fabricate annotations, contact users or claim measured
  original-user feelings from reviewer agreement.
- [x] Tests through the existing saved-comparison/review boundary cover both
  class gates, threshold and sample-size boundaries, undefined metrics,
  uncertainty edge cases, sampling disclosure and prediction-free packets.
  Synthetic fixtures remain explicitly synthetic; package checks pass.
