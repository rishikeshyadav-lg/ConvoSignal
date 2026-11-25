# 02: Recognize supported completion without feedback

**What to build:** An evaluator user can opt into the revised policy and evaluate
a complete, supported report, draft or recommendation as Satisfied with inferred
basis even when the user supplies no reaction. The complete path includes cited
evidence extraction, validation, the verdict and saved evaluation/report output.

**Blocked by:** 01 — Replay evaluations by their declared rule version.

**Status:** ready-for-human

**Implementation:** Complete; verified and available for review. Independent human validation remains pending.

- [x] A complete goal with supported essential requirements and no applicable
  negative history becomes inferred Satisfied without per-detail acknowledgment.
- [x] A convincing answer with unsupported essential figures and no acceptance
  remains Neutral; silence itself never supplies evidence of completion.
- [x] Complete grounded drafting/advisory deliverables can qualify without
  asserting that the user liked the wording or that future outcomes occurred.
- [x] Introduce only the typed evidence and prompt/contract changes necessary to
  support this behavior, with independently recorded versions and genuine old
  rule replay. Python owns labels and counts; model output supplies observations.
- [x] Saved records retain source citations, supported-completion reason,
  inferred basis, task outcome, correctness and unknown user reaction; no
  acceptance event, reading signal or session-end observation is fabricated.
- [x] Preserve null labels for operational errors and skips, bounded evidence
  repair, immutable sources and accepted classification policy.
- [x] Paired offline evaluation/replay tests cover supported versus unsupported
  completion, drafting/advisory output, recorded axes and persisted artifacts;
  package checks and existing compatibility tests pass.
