# 08: Explain old/new results on frozen sources

**What to build:** An evaluator user can compare saved old/new policy results
for the same frozen conversations and understand which labels changed, their
evidence and reasons, and the distinction between exploratory comparison and
independent reviewer validation.

**Blocked by:** 02 — Recognize supported completion without feedback;
07 — Assess reviewer agreement without label leakage.

**Status:** ready-for-human

**Implementation:** Complete; verified and available for review. Independent human validation remains pending.

- [x] Join results by stable conversation identity and verified source content,
  preserving genuine per-run hashes instead of rewriting subset checksums.
- [x] Detect missing or changed sources/policy, duplicates and incomplete result
  sets rather than presenting them as a clean like-for-like comparison.
- [x] Report old/new labels, transitions, reasons, bases, per-goal results,
  Neutral reasons, skips/errors and reconciled denominators.
- [x] Preserve original predictions and show actual rule, prompt and contract
  versions. Disclose fresh extraction and model variation separately from
  deterministic replay of compatible common evidence.
- [x] Include independent validation status using the review workflow; absent
  annotations remain pending. A changed distribution, or zero Satisfied, neither
  proves accuracy improvement nor constitutes a positive-label quota failure.
- [x] Store sensitive evidence privately and provide a reviewable aggregate
  report with traceable local artifacts and no label-driven retries.
- [x] Offline saved-artifact tests cover changed labels, unchanged labels,
  mismatches, operational coverage, version provenance and no-review pending
  status. Package/compatibility checks pass.
