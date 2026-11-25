# Product Spec — ConvoSignal

## Repository ownership — 2026-11-24

The owner clarified that all ConvoSignal code and production-quality workflow
changes belong in `https://github.com/rishikeshyadav-lg/ConvoSignal`, independently
of the campaign-agent repository. Preserve the existing CLI, policies, and package
layout when publishing. Private pilot data and generated reports remain local.

## Portable workflow hardening — 2026-11-24

The owner requested production-quality reuse of the evaluator and report
workflow. Promote reusable code out of private pilot scripts into the installed
package. Add explicit snapshot acquisition, checkpointed/resumable evaluation,
offline source-bound replay and portable HTML/DOCX report generation. Inputs,
outputs, model settings and owner-supplied report metadata are explicit; no
campaign IDs, user paths, credentials or private datasets ship in distributions.
Keep rules 2/default and opt-in rules 3, prompts, and historical outputs intact.
Fresh LLM extraction is not guaranteed to reproduce labels; saved-evidence replay
must reproduce evaluated verdicts or fail. Errors/skips remain separate.

Reports include all selected samples, captured answers, goal reasons, source
coverage and honest missing metadata. Counts derive from saved source/results;
user/date counts require captured header metadata. HTML must work offline and
render source as text. Word exports retain source text and internal navigation.
New outputs never silently replace existing paths. Resume rejects changed
source, policy, model, budgets, rules or incompatible evaluator code. Incomplete
attempts are retained; completed error cases are not automatically retried.
The functional gate includes offline behavioral tests, strict types, package
build/install smoke checks and clean-checkout instructions/CI. Independent human
accuracy validation remains a separate, pending gate. No production deployment.

Last updated: 2026-11-24
Status: Functional software delivered. Independent real-conversation validation
remains pending; synthetic tests and connectivity probes do not establish accuracy.

Revision: the user approved all six rounds of the
[criteria interview](criteria-revision-plan.md). Under opt-in version 3,
unsupported figures without feedback remain Neutral; honest inability alone is
not inferred dissatisfaction; supported completion can justify inferred
satisfaction while the user's reaction remains unknown. The implementation
preserves version 2 rules and historical pilot results.
Explicit essential scope must still be fulfilled; unrelated missing history need
not prevent evaluating a self-contained goal; verified repair after rejection
remains Neutral until acceptance/use confirms recovery. See the
[accepted design direction](../../docs/adr/0001-distinguish-inferred-satisfaction-from-user-feedback.md).
Explicit acceptance without a known contradiction may establish Satisfied while
correctness remains unverified. Mixed independent outcomes remain Neutral without
applicable overall feedback or priority. Proven essential failure can still yield
inferred Dissatisfied without a complaint. The historical rules below describe
the preserved version 2 implementation; the linked revision spec describes version 3.
Known essential contradictions preserve Neutral / conflicting_evidence despite
praise. Grounded writing/advisory deliverables may be complete without proof of
user taste or future outcomes. Genuine user-approved scope changes supersede
the old scope; frustration or giving up is not a scope waiver.
Courtesy alone is not direct acceptance. Clearly scoped overall acceptance can
cover multiple goals, while recovery confirmation must cover each previously
rejected material issue. The revision will first be compared against the original
100-session predictions on the same frozen source, without a Satisfied quota.
Independent conversation-level review requires at least 90% precision for each
predicted non-Neutral class with at least 30 reviews per class, plus transparent
coverage, confusion/recall and uncertainty reporting. Absent human labels keep
that gate pending. The user requested publication of the
[ready-for-agent spec](../../.scratch/convosignal-criteria-revision/spec.md);
the revision is now implemented with explicit version 3 selection. The published
spec governs this opt-in behavior; version 2 remains the default and the historical
rules below continue to document genuine version 2 replay. Independent human
validation has not passed.

## Outcome and authority

Build a self-contained Python CLI that classifies and safely filters agent
questions, then evaluates retained goals and conversations as Satisfied,
Dissatisfied, or Neutral with inspectable evidence.

The [original brief](original-brief.md) defines the complete minimum deliverable.
This spec refines its satisfaction rules using the subsequent user discussion.
Where they differ, this spec takes precedence: a concrete apparent repair without
later acceptance yields Neutral / recovery_unconfirmed rather than automatically
preserving Dissatisfied. No other brief requirement is waived.

## Scope

- Isolated project in convosignal/, selected by the user on 2026-11-24.
- One configurable MLflow reader and one Databricks chat-model adapter.
- Reviewed taxonomy/filter policy; literal phrase classification and safe routing.
- Ordered conversations, goal evidence, deterministic verdicts and local reports.
- Offline fixtures/fake LLM, JSON schemas, CLI, README and independent comparison.

No UI, service, scheduler, source writes, warehouse queries, schema changes,
embeddings, agent-evals dependency or deployment. User-supplied experiment IDs,
workspace hosts and profiles remain runtime configuration, never package defaults.

## Stage 1 contract

Implement the original brief in full: extract user text only for classification;
preserve duplicates for traffic counts; normalize whitespace, truncate to 300
characters, deduplicate after truncation and sample at most 120 distinct questions
for proposal. Validate model JSON, edited taxonomy and policy before explicit
acceptance. Missing set_aside warns and defaults to false. Measure coverage.

Longest literal marker wins; ties preserve type and marker order. Classification
is distinct from routing. Exclusion requires accepted normalized whole-turn
examples. Mixed, ambiguous and unmatched requests remain eligible. Excluded
turns remain context in eligible conversations; excluded-only inputs make no
satisfaction LLM call. Persist input/taxonomy/policy hashes and reject stale routing.

## Evidence contract

Every material assertion cites a stored turn/tool record. Valid citation IDs
establish provenance, not semantic truth: code checks structural consistency,
and independent review measures whether model interpretations are justified.

Keep separate fields for requirements (open/fulfilled/failed/withdrawn), task
outcome (fulfilled/partly_fulfilled/failed/unverifiable), user response
(acceptance/productive_use/rejection_frustration/no_clear_evidence), correctness
(verified/unverified/failed), recovery (none/apparent/confirmed/unresolved),
evidence basis (direct/inferred/none), labels, reasons and versions.

Preserve chronological events and source references, not only a final response
field. Requirements and their importance must be grounded in user requests.
Do not invent requirements from asks_for or assistant suggestions. An explicit
scope change supersedes earlier scope; a correction preserves the requirement
and failure. Giving up because of failure remains negative evidence, not a
convenient withdrawal. Unrelated tasks cannot repair earlier failures.

## Goal rules version 2

First resolve chronology, scope changes, feedback attribution and completeness
for each goal. Later evidence supersedes earlier evidence only for the same
result/issue. Labels describe the observed snapshot cutoff, not future events.

Apply these ordered decisions to validated evidence:

1. Acceptance/productive use conflicting with a known material failure yields
   Neutral / conflicting_evidence unless later scoped evidence resolves it.
2. Attributable rejection or giving up still applicable yields Dissatisfied /
   explicit_rejection, direct. Exception: a concrete apparent repair addressing
   all material issues behind that rejection, without later acceptance/rejection,
   yields Neutral / recovery_unconfirmed. Merely saying "fixed" is insufficient.
   Rejected or demonstrably inadequate repair remains Dissatisfied. Missing
   history needed to resolve recovery yields Neutral / incomplete_trace while
   preserving the earlier rejection signal.
3. Observable unresolved material requirement failure yields Dissatisfied /
   unresolved_material_failure, inferred. Require enough relevant history to
   distinguish failure from awaiting input or incomplete capture. Silence,
   assistant claims, suspected incorrectness and turn counts alone cannot prove it.
4. Relevant acceptance or clear productive use, without material contradiction,
   yields Satisfied / accepted_result (direct) or productive_use (inferred).
   Same-issue repair accepted/used is confirmed recovery; retain failure history.
   Acceptance does not verify factual correctness.
5. Otherwise return Neutral with a reason: recovery_unconfirmed, missing_context,
   incomplete_trace, awaiting_input, unverifiable, or no_clear_user_response.
   Preserve additional diagnostic reasons where applicable.

A file/clarification request can leave a goal open. Independently supported
inability to deliver an essential outcome can establish inferred failure. If
the user accepts alternative scope, evaluate that changed request. Bare thanks,
permission to proceed, a new task or continued conversation alone cannot establish
acceptance. Productive use must build on a specific delivered result.

## Aggregation and operational states

Evaluate independent goals first. Uniform goal labels produce that label. For
different labels, overall feedback must explicitly cover relevant goals and
survive contradiction checks. Priority can control only when the user explicitly
identifies a goal as decisive; do not infer weights from vague preferences.
Otherwise return Neutral / mixed_goals. Never majority-vote or erase goal results.

- evaluated: successfully evaluated eligible goals; three-way labels exist.
- skipped: excluded_only or no_eligible_goal; label null.
- error: extraction/evaluator failure prevents valid overall evaluation; label
  null. Keep completed goal records but do not aggregate only successful goals.

A source-agent ERROR is evidence about the task, not automatically an evaluator
error. Missing historical context in successfully read records may yield Neutral.
An artifact download failure is operational: do not silently score incomplete data.

Report question, goal and conversation counts separately. Outcome shares divide
by evaluated conversations, including Neutral. Skipped/errors divide by input
conversations. Zero evaluated means null outcome shares. Enforce input = evaluated
+ skipped + error and evaluated = Satisfied + Dissatisfied + Neutral. Separate
traffic provenance exclusions from category filtering and operational failures.

## Acceptance matrix

Synthetic behavioral specifications; these are not claims of observed outcomes.

| Case | Expected |
| --- | --- |
| Accepted standalone greeting/capability example | Skipped; null label; no evaluator call |
| Greeting plus task, or unmatched substantive task | Retained; unmatched stays unclassified |
| Answer followed by relevant acceptance | Satisfied absent contradiction |
| Apparently complete answer then silence | Neutral / no_clear_user_response |
| Bare thanks with missing preceding result | Neutral / missing_context |
| Thanks plus substantive rejection | Dissatisfied while applicable |
| Yes, proceed before delivery | Permission, not acceptance |
| Specific result used in a new deliverable | May support original goal; evaluate new goal separately |
| Same request in unrelated sessions | No automatic correction/frustration inference |
| User explicitly changes daily to weekly | Update scope |
| User corrects weekly answer to requested daily | Preserve original requirement and failure |
| Concrete same-issue repair, no response | Neutral / recovery_unconfirmed |
| Same repair plus acceptance | Satisfied / confirmed recovery |
| "Fixed" without concrete repair | Negative evidence remains applicable |
| Unrelated later success | Earlier failure unaffected |
| Acceptance plus tool-proven material incorrectness | Neutral / conflicting_evidence |
| Strict date constraint visibly violated in complete result | Inferred failure unless chronology resolves it |
| File requested, no follow-up | Neutral / awaiting_input |
| Mixed goals without decisive feedback | Neutral / mixed_goals |
| Invalid evidence, fabricated citations, exhausted retries | Error; null overall verdict |
| Partial evaluation failure | Keep completed goals; overall error |

Tests assert requirements, feedback, outcome, recovery and labels separately,
including paired cases differing by one meaningful turn. Also implement all
classification, extraction and operational tests in the original brief.

## Decisions and remaining inputs

- 2026-11-24: User requested planning for revised criteria and selected convosignal/.
- 2026-11-24: Version the revised recovery semantics as rules version 2 and preserve
  the original brief for comparison.
- 2026-11-24: The user granted dependency approval for this session. The isolated
  package now uses Pydantic >=2.12.5,<3 with exact versions in uv.lock.
- A Databricks model endpoint needs configuration. Verified MLflow access from
  exploration does not establish model-serving connectivity.
- Independent reviewers/labels are needed for accuracy claims. Offline functional
  completion and empirical validation have separate milestones.

## C0 contract clarifications — 2026-11-24

- Acceptance/use/rejection identifies a prior assistant result. Missing preceding
  results stay missing-context diagnostics, rather than fabricated events.
- Repair identifies its own concrete revised assistant result and must follow
  a failure/rejection on every scoped requirement. Correctness assertions identify
  a result and cite independent tool evidence. Bare claims cannot verify facts.
- Multiple events at one source turn are allowed for disjoint requirements;
  competing interpretations of one requirement/turn are rejected for repair.
- Explicit withdrawal removes requirements; withdrawn-only goals are skipped
  with null labels. Giving up remains rejection, not withdrawal.
- Overall feedback identifies scoped goal IDs and aligned result IDs; the same
  feedback is not duplicated into both goal and overall evidence. Overall
  priority is cited, not supplied as an ungrounded goal-selection parameter.
- Future model adapters must attach evidence to the application's immutable source
  snapshot; they must never replace source turns with model-generated turn text.

## C1 delivery — 2026-11-24

The classification/filtering library and offline artifact contracts are implemented.
Exact accepted category IDs control exclusions; recognized set-aside matches remain
distinct from policy inclusion overrides. Matching/canonicalization and file formats
are documented in README. Proposal/marker guidance can emit warnings without
inventing missing categories or marker phrases. Live model proposal calls remain C3.

The public conversation snapshot has ordered source turns and explicit completeness.
Malformed records stay in ExtractionBatch.failures and zero extracted user requests
raise an actionable error by default. Full-run orchestration must expose those
failures rather than counting them as clean skipped conversations.

## Delivery state — 2026-11-24

The CLI, both stages, schemas, local artifacts, synthetic demo, bounded real trace
reader, Databricks chat adapter and independent comparison commands are delivered.
Input/model failures remain operational errors with null labels. All eligible
conversations share a fixed routing snapshot; model evidence cannot replace the
source snapshot or invent final labels. Counts are computed in Python.

The user authorized continuing milestones without repeated permission requests.
Functional delivery is verified separately from C4 human validation: the latter
requires independently annotated, attributable real conversations, including
acceptance and recovery cases that were not established by the exploratory sample.
Do not claim improved accuracy, survey satisfaction rates or production readiness
from connectivity, fixture results or the single live synthetic example.

## Real-data pilot decision — 2026-11-24

The authorized operational pilot is complete on a frozen convenience sample.
Its report separates baseline failures, targeted diagnostic retries and final
processing coverage. Assistant-reviewed taxonomy and evidence are not human
ground truth. Inferred unmet requirements must not be reported as observed user
complaints, especially where requests allow unavailable data or conditional scope.
Independent review and a separate frozen holdout remain necessary before claiming
label accuracy or tuning rules against an acceptance gate.

- 2026-11-24 — User requested expansion to 100 conversations. Reuse the accepted
  classification/filter policy and satisfaction criteria; freeze the cohort and
  report overlap with the original pilot, all outcome counts and operational
  coverage. This is a larger operational sample, not independent ground truth.
