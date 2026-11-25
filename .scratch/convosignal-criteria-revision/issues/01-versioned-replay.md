# 01: Replay evaluations by their declared rule version

**What to build:** An evaluator user can replay archived evidence through its
declared rule policy and select the supported policy for a new evaluation,
without newer work silently changing historical judgments. This is the narrow
prefactoring needed before adding the revised policy, not a new framework.

**Blocked by:** None (can start immediately).

**Status:** ready-for-human

**Implementation:** Complete; verified and available for review. Independent human validation remains pending.

- [x] Public replay dispatches version 2 evidence to genuine version 2 behavior,
  preserving labels, reasons, bases, recovery, goal results and error semantics.
- [x] New evaluations and saved artifacts consistently identify the selected
  supported rule policy independently of prompt and contract versions.
- [x] Unsupported versions fail visibly; do not fall back to another policy or
  advertise the revised policy as available before it has an implementation.
- [x] Keep existing behavior available during incremental delivery and preserve
  existing serialized evidence compatibility and source/policy checksums.
- [x] Demonstrate archived evidence round-tripping through the public boundary,
  including mixed goals, recovery and errors, without a network or model call.
- [x] Add workflow/replay regression tests and keep existing lint, types, tests
  and schema checks green without unrelated rewrites or new dependencies.
