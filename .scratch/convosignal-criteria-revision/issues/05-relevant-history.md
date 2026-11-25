# 05: Evaluate goals using relevant captured history

**What to build:** An evaluator user can judge a self-contained goal when its
request, answer and supporting evidence are captured, even if an unrelated
earlier exchange is missing, while relevant omissions remain explicit limits.

**Blocked by:** 02 — Recognize supported completion without feedback.

**Status:** ready-for-human

**Implementation:** Complete; verified and available for review. Independent human validation remains pending.

- [x] Goal-relevant context support is explicit and source-cited; a whole-session
  incompleteness flag alone does not invalidate every self-contained goal.
- [x] Missing history that could alter scope, correctness or applicable recovery
  yields Neutral rather than an assumed success or failure.
- [x] Preserve global source diagnostics even where a sufficiently captured
  individual goal can be evaluated.
- [x] Failed downloads and invalid evaluator evidence remain operational errors
  with null labels; they are not reclassified as harmless missing history.
- [x] No reading, session-closure or silence-duration evidence is invented.
  Later evidence affects a later snapshot without rewriting historical outputs.
- [x] Public workflow/replay tests pair unrelated omissions with relevant missing
  antecedents and actual read failures, checking saved citations, statuses,
  reasons and unchanged old-policy behavior. Package checks pass.
