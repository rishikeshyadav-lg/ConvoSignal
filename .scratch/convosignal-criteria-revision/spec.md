# ConvoSignal — evidence-based satisfaction criteria revision

Status: ready-for-agent
Scope: Versioned criteria, evidence contracts, evaluation, comparison and review.
Runtime state: Specification only; current version 2 code and results are unchanged.

## Problem Statement

Users need a credible estimate of whether the campaign agent met their needs,
including short interactions that end without praise or a rating. The current
classifier requires acceptance or productive use for every material requirement,
so a complete, useful answer followed by silence cannot become Satisfied.

The 100-conversation pilot produced 93 evaluated conversations: 0 Satisfied,
40 Dissatisfied and 53 Neutral, alongside 7 skips and no processing errors.
Of the Dissatisfied conversations, 39 relied entirely on inferred unmet tasks.
These counts expose limitations in the criteria; they do not establish how users
actually felt or prove that any particular result should be relabeled.

The revision must recognize supported completion without manufacturing positive
feedback, distinguish honest inability from substantive agent failure, preserve
negative history and uncertainty, and make every decision auditable. Success
must not depend on increasing the proportion of Satisfied labels.

## Solution

Introduce a separately versioned evaluation policy implementing all eighteen
agreed decisions. Estimate satisfaction using direct feedback and supported task
completion while retaining separate task outcome, user response, correctness,
recovery and evidence basis.

| Outcome | Required interpretation |
| --- | --- |
| Satisfied — direct | Clear acceptance of the delivered goal, without a known unresolved essential contradiction. Factual correctness may remain unverified. |
| Satisfied — inferred | Supported completion of essential current requirements, or sufficiently scoped productive use, without an applicable unresolved failure or rejection. No reaction is invented. |
| Dissatisfied — direct | Attributable rejection or giving up because of an applicable unresolved material problem. |
| Dissatisfied — inferred | Relevant evidence establishes an unresolved essential failure beyond an honest external limitation. Silence or uncertainty alone is insufficient. |
| Neutral | The evidence cannot justify either directional judgment, including honest inability without another failure, pending necessary input, relevant missing context, conflicting evidence, unconfirmed recovery or unresolved mixed goals. |

The labels remain the existing three classes. Direct and inferred describe the
evidence basis, not additional label classes. Operational errors and skipped
conversations retain null labels and remain separate from Neutral.

First compare the new policy with the original predictions on the same frozen
100-session source. Preserve all baseline artifacts and disclose fresh evidence
extraction where needed. Independently validate against blind human review on
fresh data; do not describe changed counts as improved accuracy or actual changes
in user sentiment.

## User Stories

1. As an evaluator user, I want a complete, supported answer to qualify for
   inferred satisfaction without a follow-up, so that successful short sessions
   are not automatically classified Neutral.
2. As an evaluator user, I want silence alone to provide no positive evidence,
   so that abandonment is not automatically treated as success.
3. As an evaluator user, I want convincing but unsupported figures to remain
   Neutral without acceptance or corroboration, so that fluent prose is not
   mistaken for successful work.
4. As an evaluator user, I want a clearly accepted result to be Satisfied when
   no essential contradiction is known, so that direct feedback is respected.
5. As an evaluator user, I want correctness to remain unverified when appropriate
   even after acceptance, so that satisfaction does not imply factual verification.
6. As an evaluator user, I want praise that conflicts with a proven essential
   error to produce Neutral with both signals retained, so that neither praise
   nor correctness evidence disappears.
7. As an evaluator user, I want bare courtesy distinguished from clear acceptance,
   so that a polite thanks does not establish direct satisfaction.
8. As an evaluator user, I want an answer followed by courtesy to remain eligible
   for completion-based inferred satisfaction, so that courtesy does not block
   an otherwise supported judgment.
9. As an evaluator user, I want genuine productive use linked to a delivered
   result, so that unrelated follow-up questions are not treated as acceptance.
10. As an evaluator user, I want essential campaign identity and reporting dates
    preserved, so that a correct-looking answer about the wrong scope cannot pass.
11. As an evaluator user, I want explicitly requested key metrics treated as
    essential unless made optional, so that the evaluator does not silently
    simplify my request.
12. As an evaluator user, I want explicitly optional details handled conditionally,
    so that unavailable optional information does not create a false failure.
13. As an evaluator user, I want minor presentation imperfections distinguished
    from missing essential work, so that useful completion is judged fairly.
14. As an evaluator user, I want missing essential work to block satisfaction
    even when another part was useful, so that partial use does not erase scope.
15. As an evaluator user, I want supported honest inability separated from agent
    failure, so that unavailable source data alone does not imply dissatisfaction.
16. As an evaluator user, I want clear essential failures to permit inferred
    dissatisfaction without a complaint, so that demonstrably failed work remains
    visible.
17. As an evaluator user, I want an inability to verify success distinguished
    from evidence of failure, so that uncertainty is not automatically negative.
18. As an evaluator user, I want a genuine accepted scope change to replace old
    requirements while preserving history, so that the latest agreed task is judged.
19. As an evaluator user, I want frustration or giving up distinguished from a
    scope change, so that abandonment after failure is not treated as a waiver.
20. As an evaluator user, I want grounded writing and advisory deliverables judged
    against essential requested content and format, so that useful outputs can
    qualify without proof of subjective taste or future business performance.
21. As an evaluator user, I want necessary missing inputs to leave a goal awaiting
    input when no separate failure exists, so that a valid clarification request
    is not automatically dissatisfaction.
22. As an evaluator user, I want sufficiently captured current goals evaluated
    despite unrelated missing history, so that irrelevant omissions do not block
    all judgments in a long session.
23. As an evaluator user, I want relevant missing history to produce Neutral,
    so that uncertain scope or recovery is not guessed.
24. As an evaluator user, I want task correction recorded separately from recovery
    confirmation, so that a repaired answer does not erase an earlier rejection.
25. As an evaluator user, I want a verified correction after rejection to remain
    Neutral until relevant acceptance or use, so that recovery is not assumed.
26. As an evaluator user, I want recovery confirmation scoped to the previously
    rejected issues, so that every unrelated fulfilled detail need not be praised.
27. As an evaluator user, I want use of one corrected issue preserved without
    automatically confirming other rejected issues, so that partial recovery
    remains visible.
28. As an evaluator user, I want independent goals evaluated separately, so that
    one successful goal does not conceal a failed goal.
29. As an evaluator user, I want mixed goals without decisive feedback or priority
    to remain Neutral overall, so that the system does not invent importance weights.
30. As an evaluator user, I want clearly scoped overall acceptance to cover the
    delivered goals it actually names, so that broad feedback can be respected.
31. As an evaluator user, I want explicitly decisive user priority honored without
    deleting other goal results, so that overall judgments reflect stated priorities.
32. As an evaluator user, I want later evidence to affect a later snapshot without
    rewriting older predictions, so that historical reports remain reproducible.
33. As an auditor, I want each material interpretation tied to stored source
    evidence, so that I can inspect why a label was assigned.
34. As an auditor, I want inferred satisfaction to retain unknown user reaction
    when no reaction exists, so that the report does not invent acceptance or reading.
35. As an operator, I want failed source reads and invalid model evidence reported
    as operational errors, so that technical failures do not inflate Neutral or
    satisfaction counts.
36. As an operator, I want excluded-only traffic to remain skipped, so that
    capability questions are not silently counted as task outcomes.
37. As a maintainer, I want true version 2 replay alongside the revised policy,
    so that new behavior cannot silently reinterpret historical evidence.
38. As a maintainer, I want independent rule, prompt and contract versions with
    source and policy hashes, so that a comparison identifies what actually changed.
39. As an evaluator user, I want the first comparison to reuse the frozen
    100-session source and accepted classification policy, so that source selection
    is not confounded with the criteria revision.
40. As an evaluator user, I want label transitions, reasons, evidence bases and
    processing coverage reported, so that changed totals can be explained.
41. As an evaluator user, I want fresh extraction variation distinguished from
    deterministic replay, so that model variability is not called a rule improvement.
42. As an independent reviewer, I want original source context without predictions,
    so that my annotations can be formed without label leakage.
43. As an evaluation owner, I want a stated reviewer-agreement gate with minimum
    sample sizes, so that validation is not claimed from a few convenient examples.
44. As an evaluation owner, I want uncertainty, confusion, recall, Neutral share
    and coverage alongside precision, so that the reported quality is assessable.
45. As an evaluation owner, I want insufficient examples or missing reviewers to
    leave validation pending, so that labels are never fabricated to pass a gate.
46. As an evaluation owner, I want no required Satisfied percentage, so that a
    defensible zero-positive result is accepted rather than tuned away.
47. As an evaluation owner, I want reviewer agreement distinguished from actual
    end-user sentiment, so that rule consistency is not presented as measured feelings.
48. As a maintainer, I want functional delivery separated from independent
    validation, so that useful software can ship with its empirical limits explicit.

## Implementation Decisions

- Reuse the existing extraction, taxonomy, routing, evidence-validation,
  deterministic verdict, evaluation-pipeline and comparison boundaries. Avoid
  creating a parallel orchestration framework or changing traffic classification.
- Introduce a new explicitly selectable rule version while retaining genuine
  version 2 behavior. Historical replay follows the record's declared version;
  unsupported versions fail visibly instead of being evaluated by a newer rule.
- Independently version the evidence prompt and any changed contracts. Existing
  serialized evidence must retain a valid compatibility/replay path. Never
  silently relabel old evidence as belonging to the new policy.
- The model extracts cited observations. Python validates structural relationships,
  resolves scope and chronology, derives labels, and computes report counts.
  Stored source turns are authoritative and cannot be replaced by model output.
- Extend typed evidence only as needed to represent supported fulfillment, honest
  inability, essential versus optional scope, relevant completeness and rejection
  recovery. An assistant's unsupported assertion that data are unavailable is
  not sufficient proof of honest inability.
- Preserve requirement state, task outcome, user response, correctness, recovery,
  evidence basis, label, reasons, source citations and operational status as
  separate observations. A new inferred-positive reason must identify supported
  completion without manufacturing an acceptance event.
- Completion evidence depends on the task. Essential factual claims require
  relevant corroboration when inferring satisfaction without feedback. Delivered
  content can support requested drafting and format completion; it cannot establish
  that a user liked the wording or that future business outcomes occurred.
- Resolve the current request and accepted scope changes before judging failure.
  Preserve failure history and distinguish a genuine changed request from giving
  up. Do not demote an explicit essential requirement merely because it is hard.
- Apply the following decision order to valid goal evidence:
  1. Preserve known essential contradictions with positive feedback as Neutral
     with conflicting evidence, until later scoped evidence resolves them.
  2. Require enough relevant context to attribute the goal's current outcome.
     Missing relevant history yields Neutral; unrelated missing history alone
     does not. Source-read failures remain operational errors.
  3. Applicable unresolved rejection or substantiated essential failure yields
     Dissatisfied with the corresponding direct or inferred basis. Account for
     honest inability, optional requirements and accepted scope before this step.
  4. A corrected goal following explicit rejection remains Neutral until
     acceptance/use covers every rejected material issue. Partially confirmed
     recovery is retained without declaring the whole goal recovered.
  5. Applicable clear acceptance or productive use may establish Satisfied.
     Without such feedback, supported completion of the essential current request
     may establish Satisfied with inferred basis. No essential failure may remain.
  6. Otherwise preserve Neutral with its applicable reason, including awaiting
     input, missing context, honest inability or unverified completion.
- Recovery confirmation is required for applicable rejected issues, not every
  unrelated detail. A failure inferred only from task evidence can be resolved by
  supported correction without inventing a prior negative user reaction.
- Bare courtesy is not direct acceptance. Permission to proceed, topic changes
  and unrelated follow-up requests do not alone establish productive use.
- Uniform goal labels carry through to the conversation. Mixed labels yield
  Neutral unless valid overall feedback or explicitly decisive user priority
  resolves the overall result. Never majority-vote, invent priorities or erase
  subordinate goal outcomes. Known contradictions remain visible in their scope.
- Use only captured snapshot evidence. Current normalized inputs do not establish
  answer reading or session closure. Do not invent interaction telemetry or a
  silence-duration threshold. Later feedback may change a later snapshot only.
- Preserve bounded evidence-repair and provider-error handling. Do not weaken
  validation, drop source turns, broaden exclusions or retry because of a label.
- Persist original per-run versions, checksums, evidence attempts, citations and
  operational diagnostics. Sensitive real-data artifacts remain private and
  ignored by version control.
- Run the first revision comparison on the final frozen 100-session source with
  unchanged accepted taxonomy and filter policy. Retain original predictions;
  save the revised run separately. Where compatible, replay common evidence
  through both rule versions; disclose new extraction and any resulting variation.
- Report conversation and goal results separately, with label transitions,
  reasons, direct/inferred bases, Neutral reasons, skips, errors and reconciled
  denominators. Never imply that a new distribution proves greater accuracy.
- Keep independent validation separate from functional completion. Conversation
  precision against adjudicated reviewer labels must reach at least 90% for
  each predicted non-Neutral class, with at least 30 independently reviewed
  predictions per class. This is an agreed project target, not a literature-derived
  standard or proof of end-user feelings.
- Reviewers work without predictions and freeze annotations before comparison.
  Use fresh conversations and an untouched holdout after tuning; the existing
  100-session sample is exploratory. Resolve annotation disagreements without
  leaking predictions into the review process.
- Also report per-class recall, confusion matrix, Neutral share, operational and
  review coverage, sample sizes and uncertainty intervals. Disclose class-targeted
  sampling and avoid presenting unweighted recall or population rates as
  representative when the sampling does not justify that interpretation.
- Missing reviewers, too few predictions in a class or a missed target leave the
  validation gate pending. Do not fabricate annotations, replace human review
  with a model, or require a minimum Satisfied share.

## Testing Decisions

- Prefer one primary existing seam: the public evaluation workflow from immutable
  normalized conversations and accepted classification artifacts to persisted
  evaluation records and aggregate reports. Exercise it with controlled fake
  evidence responses, so tests cover observable behavior without live model calls.
- Test externally visible labels, evidence bases, requirement outcomes, user
  response, correctness, recovery, reasons, citations, statuses, versions and
  reconciled counts. Do not test private call order or mirror implementation.
- Reuse the pure evidence-replay boundary for exact chronology, version dispatch
  and paired rule cases that are harder to diagnose through a larger workflow.
  Reuse the existing saved-prediction comparison boundary for metric calculations
  and gate checks. No new dependency seam is required.
- Prior art includes the existing offline pipeline/demo tests, source-attachment
  protection tests, bounded invalid-evidence repair tests, paired verdict cases,
  schema freshness tests and snapshot-bound comparison tests with undefined
  metrics, skipped/error coverage and rejection of model-generated human labels.
- Cover these paired external behaviors:
  - Complete supported answer without feedback becomes inferred Satisfied;
    otherwise similar unsupported figures remain Neutral.
  - Explicit acceptance with unverified correctness becomes direct Satisfied;
    acceptance plus a proven essential contradiction becomes Neutral.
  - Bare courtesy does not establish direct acceptance; supported completion
    remains eligible for inferred satisfaction.
  - Honest unavailable data without another failure remains Neutral; a proven
    failure to use available necessary data permits inferred Dissatisfied.
  - Wrong campaign, required dates or essential metric block satisfaction;
    explicitly optional missing information and minor presentation issues do not
    independently create failure.
  - Grounded complete drafts/recommendations can qualify; missing essential
    content and essential unsupported facts cannot.
  - A genuine accepted scope change removes an obsolete requirement; giving up
    after failure does not erase the applicable rejection.
  - A self-contained current goal can be judged despite unrelated missing history;
    missing relevant scope or recovery context remains Neutral.
  - Necessary pending input remains Neutral when no other established failure
    applies; a failed download or invalid evaluator response stays an error.
  - Verified correction after rejection stays Neutral without confirmation;
    acceptance/use covering all rejected issues permits confirmed recovery.
  - Use of only one of several corrected rejected issues preserves partial
    recovery without confirming the entire goal.
  - Clearly scoped overall acceptance can cover several delivered goals;
    feedback about one result cannot silently cover another.
  - Mixed goals without valid overall feedback/priority remain Neutral;
    valid explicit priority is honored without hiding other goal results.
  - Later snapshots can incorporate later feedback while saved historical
    evidence still replays identically under its declared rule version.
- Check null labels for skipped/error cases, absence of invented acceptance/read
  signals, actual source identity, rejection of invalid citations and unsupported
  versions, and old/new serialization compatibility.
- At the comparison seam, test precision denominator, the 90% target and 30-case
  minimum independently for Satisfied and Dissatisfied. Test missing-class and
  absent-review cases as pending, and include metric/interval edge cases and
  disclosed nonrepresentative review sampling.
- Keep synthetic reviewers explicitly synthetic in tests. Real validation requires
  independently produced human annotations; fixtures do not satisfy that gate.
- Complete configured lint, formatting, types and tests for the package, plus
  root-required Account360 regression checks and Databricks dev bundle validation.
- After local checks, perform the separately saved real-data exploratory comparison.
  Live model outputs and label distribution are not deterministic test oracles.

## Out of Scope

- Changing Account360, deploying an application, or writing to source systems.
- Changing accepted taxonomy, exclusions or source selection to improve results.
- Fixing the broader taxonomy-coverage gap exposed by the 100-session pilot.
- Replacing the model endpoint or upgrading dependencies solely for this revision.
- New UI interaction telemetry, read receipts, copy/download tracking or invented
  session-end signals.
- A required Satisfied percentage, manufactured balanced classes or label-driven
  retries and tuning to pass a release gate.
- Rewriting historical predictions or applying new semantics while claiming an
  old rule or prompt version.
- Claiming actual user feelings from third-party reviewer judgments or equating
  successful replay with validated satisfaction estimates.
- Sending outreach, surveys, email or Slack requests to obtain annotations.
- Fabricating independent reviews or marking the independent gate complete
  without its required evidence.

## Further Notes

All eighteen business decisions were approved across six interview rounds. This
specification synthesizes those decisions without reopening the interview.
The test boundaries above use the existing workflow and replay/comparison seams
already reflected in the agreed verification plan; no new testing interface is
being introduced for separate approval.

Functional implementation and the exploratory comparison can proceed before
independent annotations exist. Until the review gate is actually met, report the
software as functionally delivered with independent validation pending. Even
passing that gate establishes agreement with reviewers, not original users'
subjective feelings; that claim needs actual end-user feedback.

Authoritative planning context:

- [All eighteen agreed decisions and implementation sequence](../../convosignal/docs/criteria-revision-plan.md)
- [Domain glossary](../../GLOSSARY.md)
- [Accepted design decision](../../docs/adr/0001-distinguish-inferred-satisfaction-from-user-feedback.md)
- [Current product specification](../../convosignal/docs/Prod-Spec.md)
- [Current architecture](../../convosignal/docs/Architecture.md)
- [Implementation issue](../convosignal/issues/07-criteria-revision.md)

The operational baseline contains 100 sessions and 173 user messages, including
the original 12 sessions and 88 additional ones. Its original artifacts and final
frozen source remain in the private pilot area. Neither the original 100-session
sample nor any sample used for tuning may later be called an untouched holdout.
