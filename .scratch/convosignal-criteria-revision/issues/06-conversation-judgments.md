# 06: Judge complete conversations with scoped overall feedback

**What to build:** An evaluator user receives an overall conversation judgment
that respects every independently evaluated goal, clear overall acceptance and
explicit user priority, with all supporting goal outcomes retained.

**Blocked by:** 03 — Respect essential scope and honest inability;
04 — Preserve feedback, contradictions and scoped recovery;
05 — Evaluate goals using relevant captured history.

**Status:** ready-for-human

**Implementation:** Complete; verified and available for review. Independent human validation remains pending.

- [x] Uniform evaluated goal labels carry through; mixed labels without valid
  overall feedback or decisive user priority yield Neutral with mixed-goal reason.
- [x] Clearly scoped overall acceptance can cover its named delivered goals
  without extending praise about one result to unrelated work.
- [x] Overall feedback cannot erase a known essential contradiction within its
  scope. Explicit decisive priority is honored without deleting other outcomes.
- [x] Do not majority-vote, infer importance from message order/length, or invent
  goal weights. Retain separate direct/inferred bases and all goal diagnostics.
- [x] Exercise the actual revised goal workflow with successful reporting,
  honest inability, recovery and relevant-context cases in multi-goal sessions,
  rather than testing only preassigned goal labels.
- [x] Errors and skips retain their operational semantics and null labels;
  persisted conversation/goal summaries reconcile with source counts.
- [x] Public workflow and scoped replay tests cover mixed/uniform goals,
  overall acceptance, explicit priority and contradictions; required package
  checks remain green.
