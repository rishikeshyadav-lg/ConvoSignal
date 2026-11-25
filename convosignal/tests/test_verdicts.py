"""Behavioral evidence pairs; these tests do not measure LLM accuracy."""

import dataclasses

import pytest

from convosignal import models, verdicts

K = models.EventKind
L = models.Label


@pytest.fixture
def turns():
    return (
        models.Turn("u1", "user", "Compare November only; include CTR"),
        models.Turn("a1", "assistant", "October and November comparison"),
        models.Turn("u2", "user", "Thanks, but that includes the wrong dates"),
        models.Turn("a2", "assistant", "Revised November-only comparison"),
        models.Turn("u3", "user", "Those are the dates I needed"),
        models.Turn("t1", "tool", "Independent contradiction"),
        models.Turn("u4", "user", "That is still incorrect"),
        models.Turn("a3", "assistant", "A new revised comparison"),
        models.Turn("u5", "user", "Use those findings for my email"),
    )


@pytest.fixture
def goal():
    return models.Goal(
        "comparison", (models.Requirement("dates", "November only", "u1"),)
    )


def event(kind, turn_id, result=None, scope=("dates",), evidence=()):
    return models.Event(kind, turn_id, scope, evidence, result)


def decide(goal, turns, *events, **changes):
    return verdicts.evaluate_goal(
        dataclasses.replace(goal, events=events, **changes), turns
    )


def test_apparent_completion_and_acceptance_are_distinct(goal, turns):
    completion = event(K.FULFILLMENT, "a1")
    silent = decide(goal, turns, completion)
    assert (silent.label, silent.outcome, silent.user_response) == (
        L.NEUTRAL,
        "fulfilled",
        "no_clear_evidence",
    )
    accepted = decide(goal, turns, completion, event(K.ACCEPTANCE, "u3", "a1"))
    assert (accepted.label, accepted.basis, accepted.correctness) == (
        L.SATISFIED,
        "direct",
        "unverified",
    )


def test_rejection_apparent_and_confirmed_recovery(goal, turns):
    rejection = event(K.REJECTION, "u2", "a1")
    repair = event(K.REPAIR, "a2", "a2")
    acceptance = event(K.ACCEPTANCE, "u3", "a2")
    failed = decide(goal, turns, rejection)
    assert (failed.label, failed.user_response, failed.recovery) == (
        L.DISSATISFIED,
        "rejection_frustration",
        "unresolved",
    )
    apparent = decide(goal, turns, rejection, repair)
    assert (apparent.label, apparent.reason, apparent.recovery) == (
        L.NEUTRAL,
        "recovery_unconfirmed",
        "apparent",
    )
    confirmed = decide(goal, turns, rejection, repair, acceptance)
    assert (confirmed.label, confirmed.recovery) == (L.SATISFIED, "confirmed")
    assert "u2" in confirmed.source_turn_ids


def test_productive_use_confirms_repair(goal, turns):
    verdict = decide(
        goal,
        turns,
        event(K.REJECTION, "u2", "a1"),
        event(K.REPAIR, "a2", "a2"),
        event(K.PRODUCTIVE_USE, "u5", "a2"),
    )
    assert (verdict.label, verdict.basis, verdict.recovery) == (
        L.SATISFIED,
        "inferred",
        "confirmed",
    )


def test_rejected_repair_and_unsubstantiated_fixed_claim(goal, turns):
    rejection = event(K.REJECTION, "u2", "a1")
    # Ordinary completion is not sufficient evidence of same-issue repair.
    assert (
        decide(goal, turns, rejection, event(K.FULFILLMENT, "a2")).label
        == L.DISSATISFIED
    )
    assert (
        decide(
            goal,
            turns,
            rejection,
            event(K.REPAIR, "a2", "a2"),
            event(K.REJECTION, "u4", "a2"),
        ).label
        == L.DISSATISFIED
    )


def test_acceptance_and_proven_incorrectness_conflict(goal, turns):
    verdict = decide(
        goal,
        turns,
        event(K.ACCEPTANCE, "u3", "a1"),
        event(K.CORRECTNESS_FAILED, "t1", "a1", evidence=("t1",)),
    )
    assert (
        verdict.label,
        verdict.reason,
        verdict.correctness,
        verdict.user_response,
    ) == (L.NEUTRAL, "conflicting_evidence", "failed", "acceptance")
    rejected = decide(
        goal,
        turns,
        event(K.ACCEPTANCE, "u3", "a1"),
        event(K.CORRECTNESS_FAILED, "t1", "a1", evidence=("t1",)),
        event(K.REJECTION, "u4", "a1"),
    )
    assert rejected.label == L.DISSATISFIED


def test_scope_failure_is_distinct_from_correctness(goal, turns):
    failure = event(K.FAILURE, "a1", evidence=("u1", "a1"))
    verdict = decide(goal, turns, failure)
    assert (verdict.label, verdict.correctness, verdict.outcome) == (
        L.DISSATISFIED,
        "unverified",
        "failed",
    )
    assert verdict.unresolved_requirement_ids == ("dates",)
    assert decide(goal, turns, failure, context_complete=False).reason == (
        "incomplete_trace"
    )


def test_new_requirement_does_not_retroactively_require_earlier_result(
    goal, turns
):
    changed = dataclasses.replace(
        goal,
        requirements=(
            *goal.requirements,
            models.Requirement("weekly", "Weekly is fine", "u2"),
        ),
    )
    revised = decide(
        changed,
        turns,
        event(K.WITHDRAWAL, "u2"),
        event(K.ACCEPTANCE, "u3", "a2", scope=("weekly",)),
    )
    assert revised.label == L.SATISFIED
    assert [r.status for r in revised.requirements] == [
        "withdrawn",
        "fulfilled",
    ]
    # Correcting the answer does not withdraw the original date constraint.
    assert decide(goal, turns, event(K.REJECTION, "u2", "a1")).label == (
        L.DISSATISFIED
    )


def test_partial_repair_does_not_hide_remaining_failure(goal, turns):
    multi = dataclasses.replace(
        goal,
        requirements=(
            *goal.requirements,
            models.Requirement("ctr", "Include CTR", "u1"),
        ),
    )
    verdict = decide(
        multi,
        turns,
        event(K.REJECTION, "u2", "a1", ("dates", "ctr")),
        event(K.REPAIR, "a2", "a2"),
    )
    assert verdict.label == L.DISSATISFIED
    assert verdict.recovery == "unresolved"
    assert verdict.outcome == "partly_fulfilled"
    assert verdict.unresolved_requirement_ids == ("ctr",)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({}, "no_clear_user_response"),
        ({"missing_context": True}, "missing_context"),
        ({"awaiting_input": True}, "awaiting_input"),
        ({"context_complete": False}, "incomplete_trace"),
    ],
)
def test_weak_or_missing_feedback_is_neutral(goal, turns, changes, reason):
    result = decide(goal, turns, **changes)
    assert (result.label, result.reason) == (L.NEUTRAL, reason)


def test_all_withdrawn_goals_are_skipped(goal, turns):
    withdrawn = dataclasses.replace(goal, events=(event(K.WITHDRAWAL, "u2"),))
    result = verdicts.evaluate_conversation((withdrawn,), turns)
    assert (result.status, result.label) == ("skipped", None)
    assert result.goals[0][1].requirements[0].status == "withdrawn"


@pytest.mark.parametrize(
    "bad",
    [
        event(K.ACCEPTANCE, "missing", "a1"),
        event(K.ACCEPTANCE, "a1", "a1"),
        event(K.ACCEPTANCE, "u3", "a1", ("unknown",)),
        event(K.ACCEPTANCE, "u3"),
        event(K.ACCEPTANCE, "u3", "a3"),
        event(K.FAILURE, "a1"),
        event(K.CORRECTNESS_VERIFIED, "u3", evidence=("a1",)),
        event(K.FAILURE, "a1", evidence=("t1",)),
    ],
)
def test_unsupported_evidence_fails(goal, turns, bad):
    with pytest.raises(ValueError):
        decide(goal, turns, bad)


def test_old_acceptance_cannot_confirm_new_repair(goal, turns):
    with pytest.raises(ValueError, match="superseded"):
        decide(
            goal,
            turns,
            event(K.REJECTION, "u2", "a1"),
            event(K.REPAIR, "a2", "a2"),
            event(K.ACCEPTANCE, "u3", "a1"),
        )


def test_out_of_order_conflicting_and_withdrawn_events_fail(goal, turns):
    cases = [
        (event(K.ACCEPTANCE, "u3", "a1"), event(K.REJECTION, "u2", "a1")),
        (event(K.ACCEPTANCE, "u3", "a1"), event(K.REJECTION, "u3", "a1")),
        (event(K.WITHDRAWAL, "u2"), event(K.ACCEPTANCE, "u3", "a2")),
    ]
    for events in cases:
        with pytest.raises(ValueError):
            decide(goal, turns, *events)


def test_mixed_goals_do_not_erase_failure(goal, turns):
    failed = dataclasses.replace(goal, events=(event(K.REJECTION, "u2", "a1"),))
    success = dataclasses.replace(
        goal, goal_id="email", events=(event(K.ACCEPTANCE, "u3", "a1"),)
    )
    result = verdicts.evaluate_conversation((failed, success), turns)
    assert (result.label, result.reason) == (L.NEUTRAL, "mixed_goals")
    assert result.goals[0][1].label == L.DISSATISFIED


def test_priority_requires_attribution_and_selects_only_cited_goal(goal, turns):
    accepted = dataclasses.replace(
        goal, events=(event(K.ACCEPTANCE, "u3", "a1"),)
    )
    other = dataclasses.replace(goal, goal_id="other")
    priority = models.OverallFeedback("priority", "u5", (goal.goal_id,))
    result = verdicts.evaluate_conversation(
        (accepted, other), turns, overall_feedback=(priority,)
    )
    assert (result.label, result.reason) == (L.SATISFIED, "explicit_priority")
    invalid = dataclasses.replace(priority, turn_id="a3")
    assert (
        verdicts.evaluate_conversation(
            (accepted, other), turns, overall_feedback=(invalid,)
        ).status
        == "error"
    )


def test_overall_acceptance_cannot_hide_independent_failure(goal, turns):
    failed = dataclasses.replace(
        goal, events=(event(K.FAILURE, "a1", evidence=("u1", "a1")),)
    )
    other = dataclasses.replace(goal, goal_id="other")
    feedback = models.OverallFeedback(
        "acceptance", "u5", (goal.goal_id, other.goal_id), ("a1", "a1")
    )
    result = verdicts.evaluate_conversation(
        (failed, other), turns, overall_feedback=(feedback,)
    )
    assert result.label == L.NEUTRAL
    assert result.goals[0][1].reason == "conflicting_evidence"
    assert result.goals[1][1].label == L.SATISFIED


def test_global_and_partial_errors_keep_null_label(goal, turns):
    invalid = dataclasses.replace(goal, goal_id="bad", requirements=())
    result = verdicts.evaluate_conversation((goal, invalid), turns)
    assert (result.status, result.label, len(result.goals)) == (
        "error",
        None,
        1,
    )
    assert (
        verdicts.evaluate_conversation((goal,), (*turns, turns[0])).status
        == "error"
    )


@pytest.mark.parametrize(
    "excluded,reason",
    [
        (True, "excluded_only"),
        (False, "no_eligible_goal"),
    ],
)
def test_skips_never_have_neutral_labels(excluded, reason):
    result = verdicts.evaluate_conversation((), (), excluded_only=excluded)
    assert (result.status, result.label, result.reason) == (
        "skipped",
        None,
        reason,
    )


def test_identical_evidence_replays_identically_without_mutation(goal, turns):
    original = dataclasses.asdict(goal)
    assert verdicts.evaluate_goal(goal, turns) == verdicts.evaluate_goal(
        goal, turns
    )
    assert dataclasses.asdict(goal) == original


def test_overall_feedback_can_resolve_all_goals(goal, turns):
    other = dataclasses.replace(goal, goal_id="other")
    feedback = models.OverallFeedback(
        "acceptance", "u5", (goal.goal_id, other.goal_id), ("a1", "a1")
    )
    result = verdicts.evaluate_conversation(
        (goal, other), turns, overall_feedback=(feedback,)
    )
    assert result.label == L.SATISFIED
    assert all(v.basis == "direct" for _, v in result.goals)


def test_later_overall_rejection_supersedes_acceptance(goal, turns):
    feedback = (
        models.OverallFeedback("acceptance", "u3", (goal.goal_id,), ("a1",)),
        models.OverallFeedback("rejection", "u4", (goal.goal_id,), ("a1",)),
    )
    result = verdicts.evaluate_conversation(
        (goal,), turns, overall_feedback=feedback
    )
    assert result.label == L.DISSATISFIED


def test_stale_or_underspecified_overall_feedback_fails(goal, turns):
    progressed = dataclasses.replace(
        goal, events=(event(K.REJECTION, "u4", "a1"),)
    )
    stale = models.OverallFeedback("acceptance", "u3", (goal.goal_id,), ("a1",))
    assert (
        verdicts.evaluate_conversation(
            (progressed,), turns, overall_feedback=(stale,)
        ).status
        == "error"
    )
    bad_scope = models.OverallFeedback(
        "acceptance", "u5", ("unknown",), ("a1",)
    )
    assert (
        verdicts.evaluate_conversation(
            (goal,), turns, overall_feedback=(bad_scope,)
        ).status
        == "error"
    )


def test_incomplete_history_does_not_negate_observed_acceptance(goal, turns):
    result = decide(
        goal, turns, event(K.ACCEPTANCE, "u3", "a1"), context_complete=False
    )
    assert result.label == L.SATISFIED


def test_minor_failure_does_not_override_material_success(goal, turns):
    multi = dataclasses.replace(
        goal,
        requirements=(
            *goal.requirements,
            models.Requirement("style", "Optional table styling", "u1", False),
        ),
    )
    result = decide(
        multi,
        turns,
        event(K.FAILURE, "a1", scope=("style",), evidence=("a1",)),
        event(K.ACCEPTANCE, "u3", "a1"),
    )
    assert result.label == L.SATISFIED
    assert result.requirements[1].status == "failed"


def test_repeat_questions_and_permission_are_not_acceptance(goal, turns):
    # These user turns intentionally produce no ACCEPTANCE evidence event.
    altered = tuple(
        dataclasses.replace(t, text="Yes, proceed") if t.turn_id == "u3" else t
        for t in turns
    )
    result = decide(goal, altered)
    assert (result.label, result.user_response) == (
        L.NEUTRAL,
        "no_clear_evidence",
    )


def test_multiple_requirements_can_have_events_on_the_same_turn(goal, turns):
    multi = dataclasses.replace(
        goal,
        requirements=(
            *goal.requirements,
            models.Requirement("ctr", "CTR", "u1"),
        ),
    )
    result = decide(
        multi,
        turns,
        event(K.ACCEPTANCE, "u3", "a1"),
        event(K.PRODUCTIVE_USE, "u3", "a1", scope=("ctr",)),
    )
    assert (result.label, result.basis) == (L.SATISFIED, "inferred")


def test_withdrawn_goal_does_not_erase_another_failure(goal, turns):
    failed = dataclasses.replace(goal, events=(event(K.REJECTION, "u2", "a1"),))
    withdrawn = dataclasses.replace(
        goal, goal_id="other", events=(event(K.WITHDRAWAL, "u2"),)
    )
    result = verdicts.evaluate_conversation((failed, withdrawn), turns)
    assert result.label == L.DISSATISFIED
    assert result.goals[1][1].label is None


def test_correctness_verification_alone_is_not_satisfaction(goal, turns):
    verified = event(K.CORRECTNESS_VERIFIED, "t1", "a1", evidence=("t1",))
    result = decide(goal, turns, verified)
    assert (result.label, result.correctness) == (L.NEUTRAL, "verified")


def test_repair_requires_a_prior_failure_on_every_scoped_requirement(
    goal, turns
):
    with pytest.raises(ValueError, match="prior scoped failure"):
        decide(goal, turns, event(K.REPAIR, "a2", "a2"))


@pytest.mark.parametrize("reverse", [False, True])
def test_completion_and_correctness_can_share_requirement_and_turn(reverse):
    turns = (
        models.Turn("request", "user", "Return the synthetic metric"),
        models.Turn("data", "tool", "Synthetic metric: 12"),
        models.Turn("answer", "assistant", "Synthetic metric: 12"),
    )
    events = (
        models.Event(K.FULFILLMENT, "answer", ("metric",)),
        models.Event(
            K.CORRECTNESS_VERIFIED, "answer", ("metric",), ("data",), "answer"
        ),
    )
    goal = models.Goal(
        "metric",
        (models.Requirement("metric", "Return metric", "request"),),
        tuple(reversed(events)) if reverse else events,
    )
    result = verdicts.evaluate_goal(goal, turns)
    assert (result.label, result.outcome, result.correctness) == (
        L.NEUTRAL,
        "fulfilled",
        "verified",
    )
    assert result.user_response == "no_clear_evidence"


def test_same_turn_completion_does_not_override_supported_failure(goal, turns):
    with pytest.raises(ValueError, match="Conflicting events"):
        decide(
            goal,
            turns,
            event(K.FULFILLMENT, "a1"),
            event(K.FAILURE, "a1", evidence=("u1", "a1")),
        )
