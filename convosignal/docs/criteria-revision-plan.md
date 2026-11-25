# Satisfaction criteria revision — consolidated plan

Status: All 18 decisions approved; nine implementation tickets completed and reviewed.
Scope: ConvoSignal only. Existing version 2 rules and pilot artifacts remain intact.

Published implementation contract:
[criteria revision specification](../../.scratch/convosignal-criteria-revision/spec.md).
The user's to-spec request completed synthesis without another interview. This
document preserves the decision history; the published spec governs implementation.

## Agreed outcome

Estimate satisfaction using direct feedback and supported task completion while
keeping estimated satisfaction separate from observed user reaction. There is
no target percentage of Satisfied labels.

| Label | Agreed basis |
| --- | --- |
| Satisfied — direct | Clear acceptance of the delivered result with no unresolved essential contradiction; correctness may remain unverified. |
| Satisfied — inferred | Supported completion of essential current requirements, or sufficiently scoped productive use, without applicable unresolved failure or rejection. Absent user reaction remains unknown. |
| Dissatisfied — direct | Attributable rejection or giving up due to an applicable unresolved material problem. |
| Dissatisfied — inferred | Relevant evidence substantiates an unresolved essential failure beyond an honest external limitation. Silence or uncertainty alone is insufficient. |
| Neutral | Insufficient relevant evidence, honest inability without another failure, pending necessary input, conflicting evidence, unconfirmed recovery, or unresolved mixed goals. |

Missing an essential requirement blocks Satisfied even if another part was useful,
unless the user genuinely accepts a different scope. A supported correction after
rejection remains Neutral until acceptance/use covers every previously rejected
material issue. Operational errors have null labels; they are not Neutral judgments.

## Requested direction

The user requested planning for research-informed Satisfied, Dissatisfied and
Neutral criteria. Consider successful completion without a follow-up as possible
inferred satisfaction, and reconsider the requirement for acceptance/use of every
material detail. Do not target a desired proportion of Satisfied labels.

The research supports investigating this direction; it does not validate a
specific decision rule for campaign traces. Search abandonment studies and
conversational-assistant studies have different settings.

## Verified starting point

- Current rules require acceptance/use for every active material requirement
  before a goal becomes Satisfied. Delivery alone is insufficient.
- Dissatisfied can follow explicit rejection or an inferred unresolved material
  failure. Missing history, conflicting evidence and recovery have separate gates.
- Task outcome, user response, correctness, recovery and evidence basis are
  already separate concepts. Preserve that distinction as the criteria change.
- Normalized records have no structured read, copy, download, delivery time or
  verified session-end signals. A session grouping is not proof of closure.
- The fixed 100-session pilot evaluated 93 conversations: 0 Satisfied,
  40 Dissatisfied, 53 Neutral; 7 were skipped and none had processing errors.
  Of 40 Dissatisfied conversations, 39 rely entirely on inferred failures.
- Independent human annotations remain unavailable; existing predictions are
  exploratory evidence rather than accuracy ground truth.

References: [current spec](Prod-Spec.md), [architecture](Architecture.md),
[pilot milestone](Milestones.md#100-conversation-expansion-completed--2026-11-24),
[glossary](../../GLOSSARY.md). Sensitive source evidence remains in the private
pilot folder and is not reproduced here.

## Research already examined

- [Google: Good Abandonment](https://research.google/pubs/good-abandonment-in-mobile-and-pc-internet-search/):
  some searches end because the result page has met the information need.
- [Amazon Alexa: Learning From Implicit Feedback](https://aclanthology.org/2021.emnlp-main.489/):
  interaction context and reformulations can help identify misunderstood requests;
  ending an unfinished interaction can also indicate problems.
- [Microsoft: Learning From Copilot Interactions](https://www.microsoft.com/en-us/research/blog/learning-from-interaction-with-microsoft-copilot-web/):
  task completion is associated with estimated satisfaction; satisfaction
  estimation was evaluated against actual user voting signals.

## Decision tree

### Round 1: approved by the user

1. Positive evidence threshold: when feedback is absent, how much evidence is
   required to conclude the main requested outcome was delivered?
   Approved boundary: unsupported figures in an otherwise convincing answer
   remain Neutral without user acceptance or relevant corroborating evidence.
2. Honest inability: when the agent correctly explains that necessary source data
   are unavailable, does unmet demand alone justify inferred Dissatisfied?
   Approved boundary: Neutral unless there is attributable rejection or evidence
   of a substantive agent failure beyond the external limitation.
3. Observation limit: without read or session-end telemetry, what does a positive
   label claim at the snapshot cutoff?
   Approved boundary: allow a completion-based inferred judgment where justified,
   while preserving unknown user reaction and making no claim of verified reading
   or session closure. Missing feedback itself supplies no positive proof.

The user answered "yes to all" for these three boundaries. They are design
decisions for the revision, not claims about the unchanged version 2 results.

### Round 2: approved by the user

4. Essential scope: explicitly requested campaign identity, date boundaries and
   key metrics remain essential unless the user makes them conditional/optional.
   Approved boundary: missing an essential blocks Satisfied; minor presentation
   imperfections need not. This does not by itself choose Dissatisfied over Neutral.
5. Relevant completeness: does missing unrelated earlier history prevent judging
   a self-contained current goal?
   Approved boundary: evaluate a sufficiently captured current goal; use Neutral
   when missing history could affect its scope, correctness or recovery. This
   does not convert failed source downloads or evaluator errors into valid labels.
6. Recovery after rejection: does a verified correction with no later user reply
   qualify for inferred satisfaction?
   Approved boundary: preserve Neutral / recovery_unconfirmed after explicit
   rejection until acceptance/use confirms recovery, even when the task is now
   apparently fulfilled. Preserve the corrected outcome separately.

The user answered "yes to all" for these three boundaries. Explicit requested
scope remains essential; feedback need not separately acknowledge each fulfilled
detail. Partial use does not silently waive an unfulfilled essential requirement.

### Round 3: approved by the user

7. Accepted but unverified: if the user explicitly accepts a delivered result,
   but figures cannot be independently verified and no contradiction is known,
   should the goal be Satisfied with direct basis and unverified correctness?
   Approved boundary: yes; direct feedback and factual verification remain separate.
8. Mixed independent goals: if one goal is Satisfied and another Dissatisfied,
   with no explicit overall feedback or decisive user priority, how is the
   conversation labeled?
   Approved boundary: Neutral / mixed_goals with both goal outcomes retained;
   no majority vote or inferred importance weights.
9. Provable failure without a complaint: should clear evidence that the agent
   failed an essential request still permit Dissatisfied with inferred basis?
   Approved boundary: yes for a substantiated failure such as wrong campaign or
   wrong required period, with enough relevant context and no applicable honest
   inability, scope change, recovery or conflicting-feedback exception. Mere
   absence of praise or inability to verify success is insufficient.

The user answered "yes to all" for these three boundaries. Explicit acceptance
can establish satisfaction without establishing correctness. Mixed goal outcomes
remain visible, and an inferred negative judgment requires evidence of failure,
not merely an absence of evidence of success.

### Round 4: approved by the user

10. Accepted but contradicted: when the user accepts an answer but stored source
    evidence proves an essential claim wrong, which signal controls?
    Approved boundary: Neutral / conflicting_evidence; preserve positive user
    feedback and failed correctness separately, pending scoped resolution.
11. Writing and recommendations: what can completion establish when user taste
    or future business performance cannot be independently verified?
    Approved boundary: a complete deliverable matching the essential requested
    content/format and supported facts may qualify as Satisfied / inferred.
    Do not claim the user liked its style or that a recommendation achieved a
    future outcome. Unavailable necessary inputs or essential unsupported claims
    still block inferred satisfaction.
12. User-approved scope change: if a user explicitly drops an unavailable detail
    and requests a narrower deliverable, should the old detail remain a blocker?
    Approved boundary: evaluate the accepted revised scope and preserve the
    history. Do not treat frustration or giving up as a convenient scope waiver.

The user answered "yes to all" for these three boundaries. Known contradictions
take precedence over positive feedback, while subjective taste or unobserved
future performance need not block judging a grounded deliverable complete.

### Round 5: approved by the user

13. Courtesy versus acceptance: should a bare "thanks" automatically become
    direct acceptance?
    Approved boundary: no; clear acceptance is stronger than courtesy. A supported,
    complete result may still be Satisfied / inferred without treating courtesy
    as proof, while an unverified result needs additional evidence.
14. Overall feedback: can explicitly broad acceptance such as "Both the report
    and email cover everything I need" cover multiple delivered goals?
    Approved boundary: yes, when its scope is clear and there is no unresolved
    material contradiction. Do not extend feedback about one result to other
    goals or use it to erase a known factual failure.
15. Partial use after multiple rejected issues: if the user rejected both wrong
    dates and wrong CTR, both were corrected, but later uses only the corrected
    CTR, is recovery confirmed for the whole goal?
    Approved boundary: no; preserve the productive-use signal for CTR, but keep
    the goal Neutral / recovery_unconfirmed until the date issue is also covered
    by acceptance/use or a genuine accepted scope change.

The user answered "yes to all" for these three boundaries. Courtesy alone is
not direct acceptance; clearly scoped overall feedback can cover several goals;
confirmed recovery must cover each previously rejected material issue.

### Round 6: approved by the user

16. First comparison: should the new criteria first run on the same frozen
    100 conversations with all old artifacts retained?
    Approved boundary: yes; compare label transitions, reasons, evidence bases and
    processing coverage. Any fresh evidence extraction is versioned and disclosed;
    do not present differences as measured accuracy or changes in user sentiment.
17. Initial reviewer-agreement gate: what minimum evidence is needed to describe
    the revised classifier as validated against independent reviewers?
    Approved initial target: at least 90% precision against reviewer labels for
    each predicted non-Neutral class, reviewing at least 30 predictions per class.
    Reviewers work blind to predictions; report confusion matrix, recall, Neutral
    share, coverage, sample sizes and uncertainty as well. Insufficient cases or
    reviewers leave the gate pending. This is an agreed project target, not a
    research-established threshold or proof of actual user feelings.
18. No positive-label quota: should there be no required Satisfied percentage
    in the exploratory rerun?
    Approved boundary: yes; zero Satisfied remains a legitimate observed result.
    Never change evidence or rules merely to produce more positive labels.

The user answered "yes to all" for these three boundaries. All branches are
settled and the subsequent to-spec request published the specification.
Implementation had not begun at publication; the subsequent implementation and
comparison are now complete. Historical predictions remain unchanged.

### Consequences of decisions already approved

- A genuine scope change supersedes old requirements; it does not erase history.
- An essential requirement still missing cannot be silently waived because a
  different part of the result was useful.
- Supported fulfillment without negative history need not be acknowledged detail
  by detail to qualify for inferred satisfaction.
- Necessary pending user input remains Neutral / awaiting_input when no separate
  established failure applies. Asking for clarification is not itself a failure.
- Failed downloads, malformed evidence and evaluator failures remain operational
  errors with null labels, rather than Neutral or inferred success.
- Judgments concern their stored snapshot cutoff; later feedback may change a
  later snapshot without rewriting historical predictions.

## Implementation sequence

1. Publish the confirmed decision table and paired edge cases in the product spec.
   Keep the version 2 specification and original pilot results available.
2. Introduce an explicitly versioned new rule path, with the old rule path still
   available for genuine historical replay. Update the evidence prompt and any
   required contracts with independent versions; never label new decisions as
   version 2 or fabricate user acceptance.
3. Extract cited observations needed to distinguish supported fulfillment,
   honest inability, essential scope, goal-relevant completeness and unresolved
   rejection. Python owns labels, reasons and aggregation. Reviewer judgments
   of evidential support do not prove actual end-user feelings.
4. Resolve current scope and chronology first. Known essential contradictions
   with positive feedback become Neutral; otherwise require relevant context
   before attributing success or failure. Unresolved rejection or substantiated
   essential failure becomes Dissatisfied; unconfirmed repair after rejection
   stays Neutral. Scoped acceptance/use or supported completion can then establish
   Satisfied; remaining uncertainty stays Neutral.
   Encode honest inability and accepted scope changes before deciding that a
   requirement failed. Preserve diagnostic evidence when one reason wins.
5. Preserve separate task outcome, user response, correctness, recovery and basis.
   Add a distinct reason for supported completion without feedback. A positive
   inferred label must retain unknown user reaction where no reaction exists.
6. Apply the approved multi-goal rules and clearly scoped overall feedback without
   majority voting or hidden importance weights. Missing unrelated source history
   must not automatically invalidate a fully evidenced current goal; actual read
   failures and invalid evidence remain operational errors.
7. Test every decision with paired positive/negative cases, scoped chronology,
   recovery, partial use, optional requirements, missing context and versioned
   historical replay. Run package lint/types/tests and root-required checks.
8. Compare on the existing frozen 100-session source in a new
   private run. Save manifests, raw attempts, citations, per-goal results, transition
   counts and coverage. Treat this as exploratory comparison, not a holdout.
9. Validate rule/evidence application on fresh conversations with independent
   reviewers, resolve disagreements without leaking predictions, and report the
   agreed metrics. A separate untouched holdout is required after tuning; actual
   user feedback is needed to validate claims about users' felt satisfaction.
   Do not send user outreach or fabricate reviews as part of this plan.

## Validation and delivery gates

Functional delivery requires paired-case tests, historical replay, schema
compatibility and package/root checks to pass. Compare against unchanged original
100-session predictions with hashes, versions, reasons, transitions and operational
coverage reported. A different label distribution is not an accuracy result.

Independent validation is separate. At the conversation level, precision against
independently adjudicated reviewer labels must reach 90% for each predicted
non-Neutral class, with at least 30 independently reviewed predictions per class.
This is the fraction of reviewed Satisfied predictions judged Satisfied, and
separately the fraction of reviewed Dissatisfied predictions judged Dissatisfied.
Reviewers do not see predictions before freezing their annotations.

Also report confusion matrix, recall, Neutral share, operational coverage, sample
sizes and uncertainty intervals. Preserve direct/inferred breakdowns. Disclose
class-targeted review sampling and avoid interpreting unweighted recall or
population rates as representative when sampling is not representative.
Insufficient examples, absent reviewers or a missed target leave validation open.
Never fabricate labels to balance classes. The existing 100 sessions are exploratory,
not an untouched holdout. Reviewer agreement validates rule/evidence application;
validating actual users' feelings requires actual user feedback.

Implementation need not wait for human annotations, but it must report that
independent validation remains pending until its evidence and targets are met.

## Planned verification cases

- Supported complete report without feedback versus plausible unsupported report.
- Correct reporting period versus a proven wrong reporting period.
- Explicit acceptance with unverified figures versus known contradictory figures.
- Honest unavailable data versus an avoidable failure with available data.
- Explicitly optional metric versus omitted essential metric.
- Complete grounded draft versus missing essential content or invented facts.
- Scope genuinely narrowed versus user giving up after failure.
- Self-contained goal with unrelated missing history versus missing relevant scope.
- Correction without acknowledgment versus use covering all rejected issues.
- Partial use covering one of several rejected issues versus broad scoped acceptance.
- Courtesy alone versus explicit acceptance of a particular result.
- Uniform versus mixed goals, with and without valid overall feedback/priority.
- Pending necessary input versus a substantiated failure to execute a complete ask.
- Operational errors versus valid Neutral outcomes, and old/new rule replay.

## Documentation and implementation boundary

Settled vocabulary lives in the root glossary and consequential design rationale
in the ADR. This plan records the agreed decisions; the published specification
is ready-for-agent. Publication changes documentation only, not runtime labels
or pilot artifacts, and does not itself begin implementation or a new pilot run.
