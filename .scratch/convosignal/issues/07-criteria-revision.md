# 07 — Criteria revision and frozen-sample comparison

Status: ready-for-agent
Blocked by: None for implementation; independent validation requires human annotations.
Milestone: C4 criteria revision; independent accuracy validation remains separate.

All 18 business decisions are agreed and published in the
[ready-for-agent specification](../../convosignal-criteria-revision/spec.md).
The [consolidated plan](../../../convosignal/docs/criteria-revision-plan.md)
preserves the interview history. Implement
a separately versioned rule path allowing supported completion without feedback
to establish inferred satisfaction. Preserve feedback, correctness, honest
inability, essential scope, rejection/recovery and mixed-goal distinctions.

Acceptance:

- Preserve genuine version 2 replay and unchanged historical predictions.
- Cite support for all material interpretations; Python owns final labels.
- Pass paired cases for all 18 decisions and compatibility checks.
- Pass package lint/format/types/tests and required root checks, including
  Databricks dev bundle validation.
- Compare on the same frozen 100-session source with unchanged accepted
  taxonomy/policy. Save new private artifacts with transitions, bases, reasons,
  versions and coverage; disclose fresh extraction and model variability.
- Do not target a Satisfied percentage or claim accuracy from changed counts.
- Prepare blind independent review. Keep C4 validation pending until conversation
  precision against reviewer labels reaches 90% for each predicted non-Neutral
  class with at least 30 reviewed predictions per class. Report recall, confusion,
  Neutral share, coverage, sample sizes and uncertainty alongside it.
- Do not fabricate acceptance, reading, session closure or independent reviews.
  Reviewer agreement does not establish the original user's actual feelings.

No implementation or new evaluation began during the planning interview.

## Comments

- The user explicitly requested to-spec synthesis and publication without another
  interview. The full specification is ready-for-agent. Runtime implementation
  and a revised pilot run remain separate work.
