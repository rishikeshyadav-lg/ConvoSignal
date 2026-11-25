# 05 — Independent evaluation

Status: needs-info

Agreed revision gate: conversation-level precision against independent reviewer
labels must reach at least 90% for each predicted non-Neutral class, with at least
30 reviewed predictions per class, plus confusion/recall, Neutral share, coverage,
sample sizes and uncertainty reporting. This gate is pending actual annotations;
it is not a claim about users' feelings. See the
[consolidated plan](../../../convosignal/docs/criteria-revision-plan.md).
Blocked by: independent reviewer labels and complete acceptance/recovery examples.
Milestone: C4

Define private review JSONL keyed to snapshot/conversation/goal IDs. Gather
attributable examples covering every class and recovery, preserve provenance,
resolve reviewer disagreements and freeze a holdout. Implement compare on saved
predictions and labels. See the [specification index](../spec.md).

Acceptance: report per-class precision/recall, confusion matrix, unknown/mixed
shares, sample sizes and coverage. Undefined metrics are null. Technical failures
stay out of outcome metrics and remain in coverage. Reviewed labels never enter
prompts. Agree quality thresholds before examining holdout results; do not claim
accuracy or improvement from synthetic tests.

## Comments

- 2026-11-24: Human review is a real dependency; automated labels are not ground truth.

- 2026-11-24: Comparison/review tooling and synthetic calculation tests complete.
  Independent real-conversation annotations and reviewer input remain unavailable;
  empirical acceptance checks are not passed or waived.

- 2026-11-24: Operational real-data pilot completed on 12 frozen attributed
  sessions / 40 user messages. Baseline had 8 evaluated, 1 skipped, 3 errors;
  targeted retries yield 11 evaluated, 1 skipped, 0 errors, preserving all valid
  baseline verdicts. Private report and 11-entry blank independent-review packet
  are under convosignal/private/real-pilot-20261124/. Eight Dissatisfied judgments
  infer unmet tasks rather than observed complaints. Conditional scope and missing
  data need adjudication; no accuracy claim or C4 gate completion is supported.

- 2026-11-24: Expanded to 100 attributed sessions / 173 user messages, including
  88 sessions beyond the original 12. Unchanged rules/taxonomy/prompt yield
  93 evaluated (0 Satisfied, 40 Dissatisfied, 53 Neutral), 7 skips and 0 errors.
  All 93 source/replay audits pass and blank human review forms are prepared.
  Of 40 Dissatisfied conversations, 39 use inferred failures only. One partial
  productive-use signal remains Neutral under the all-requirement scope gate;
  independently assess possible undercounting before tuning. The taxonomy leaves
  83 messages unclassified, all retained. Private evidence/report is in
  convosignal/private/real-pilot-100-20261124/. C4 remains needs-info.
