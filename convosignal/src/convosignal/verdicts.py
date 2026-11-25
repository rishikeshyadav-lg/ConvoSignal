"""Pure rules over attributed evidence, with no text heuristics or I/O."""

import dataclasses
from collections.abc import Sequence

from convosignal import evidence, models, revision


@dataclasses.dataclass
class _RequirementState:
    """The observable trajectory for one requested outcome."""

    requirement: models.Requirement
    status: models.RequirementStatus = "open"
    failure: bool = False
    rejection: bool = False
    repaired: bool = False
    had_failure: bool = False
    had_rejection: bool = False
    accepted: str | None = None
    correctness: models.Correctness = "unverified"

    def apply(self, event: models.Event) -> None:
        """Advance this requirement without forgetting earlier failures."""
        kind = event.kind
        if kind == models.EventKind.WITHDRAWAL:
            self.status = "withdrawn"
        elif kind in {
            models.EventKind.FAILURE,
            models.EventKind.CORRECTNESS_FAILED,
            models.EventKind.REJECTION,
        }:
            self.status = "failed"
            self.had_failure = True
            self.repaired = False
            if kind == models.EventKind.REJECTION:
                self.had_rejection = True
                self.rejection = True
                self.accepted = None
            else:
                self.failure = True
            if kind == models.EventKind.CORRECTNESS_FAILED:
                self.correctness = "failed"
        elif kind == models.EventKind.REPAIR:
            self.status = "fulfilled"
            self.repaired = self.had_failure
            self.failure = self.rejection = False
            self.accepted = None
            self.correctness = "unverified"
        elif kind in {
            models.EventKind.ACCEPTANCE,
            models.EventKind.PRODUCTIVE_USE,
        }:
            self.accepted = kind.value
            if not (self.failure or self.rejection):
                self.status = "fulfilled"
        elif kind == models.EventKind.FULFILLMENT:
            # Apparent completion alone never clears a prior failure.
            if not (self.failure or self.rejection):
                self.status = "fulfilled"
        elif kind == models.EventKind.CORRECTNESS_VERIFIED:
            self.correctness = "verified"


def _goal_verdict(
    goal: models.Goal, states: Sequence[_RequirementState]
) -> models.Verdict:
    """Derive a verdict from resolved requirement trajectories."""
    active = [s for s in states if s.status != "withdrawn"]
    material = [s for s in active if s.requirement.material]
    failed = [s for s in material if s.failure or s.rejection]
    repaired = [s for s in material if s.repaired]
    history = [s for s in material if s.had_failure]
    recovery: models.Recovery = "none"
    if history:
        recovery = "unresolved"
        if not failed and all(s.repaired for s in history):
            recovery = "apparent"
            if all(s.accepted for s in history):
                recovery = "confirmed"
    label: models.Label | None = models.Label.NEUTRAL
    reason: models.GoalReason = "no_clear_user_response"
    basis: models.Basis = "none"
    if any(s.accepted for s in failed):
        reason = "conflicting_evidence"
    elif not goal.context_complete and (failed or repaired):
        reason = "incomplete_trace"
    elif any(s.rejection for s in failed):
        label = models.Label.DISSATISFIED
        reason, basis = "explicit_rejection", "direct"
    elif failed:
        label = models.Label.DISSATISFIED
        reason, basis = "unresolved_material_failure", "inferred"
    elif any(not s.accepted for s in repaired):
        reason = "recovery_unconfirmed"
    elif material and all(s.accepted for s in material):
        label = models.Label.SATISFIED
        basis = "direct"
        reason = "accepted_result"
        if any(s.accepted == "productive_use" for s in material):
            basis, reason = "inferred", "productive_use"
    elif goal.missing_context:
        reason = "missing_context"
    elif not goal.context_complete:
        reason = "incomplete_trace"
    elif goal.awaiting_input:
        reason = "awaiting_input"
    if not active:
        label, reason, basis = None, "withdrawn_goal", "none"
    outcome: models.Outcome = "unverifiable"
    if material and all(s.status == "fulfilled" for s in material):
        outcome = "fulfilled"
    elif any(s.status == "fulfilled" for s in material):
        outcome = "partly_fulfilled"
    elif failed:
        outcome = "failed"
    response: models.UserResponse = "no_clear_evidence"
    if any(s.rejection for s in material):
        response = "rejection_frustration"
    elif any(s.accepted for s in material):
        response = "acceptance"
        if any(s.accepted == "productive_use" for s in material):
            response = "productive_use"
    correctness: models.Correctness = "unverified"
    if any(s.correctness == "failed" for s in material):
        correctness = "failed"
    elif material and all(s.correctness == "verified" for s in material):
        correctness = "verified"
    citations = tuple(
        dict.fromkeys(
            citation
            for event in goal.events
            for citation in (
                event.turn_id,
                *event.evidence_turn_ids,
                *((event.result_turn_id,) if event.result_turn_id else ()),
            )
        )
    )
    requirements = tuple(
        models.RequirementResult(
            s.requirement.requirement_id,
            s.status,
            tuple(
                dict.fromkeys(
                    (
                        s.requirement.source_turn_id,
                        *(
                            event.turn_id
                            for event in goal.events
                            if s.requirement.requirement_id
                            in event.requirement_ids
                        ),
                    )
                )
            ),
        )
        for s in states
    )
    return models.Verdict(
        label,
        reason,
        basis,
        recovery,
        citations,
        requirements,
        outcome,
        response,
        correctness,
        tuple(
            s.requirement.requirement_id
            for s in material
            if s.status in {"open", "failed"}
        ),
        "skipped" if label is None else "evaluated",
    )


def _revised_verdict(
    goal: models.Goal,
    states: Sequence[_RequirementState],
    result: models.Verdict,
    turns: Sequence[models.Turn],
) -> models.Verdict:
    """Apply version 3 completion and limitation gates to replayed evidence."""
    result = dataclasses.replace(result, rules_version="3")
    if result.status == "skipped" or result.reason == "conflicting_evidence":
        return result
    material = [
        s for s in states if s.requirement.material and s.status != "withdrawn"
    ]
    if goal.missing_context or not goal.context_complete:
        return dataclasses.replace(
            result,
            label=models.Label.NEUTRAL,
            basis="none",
            reason="missing_context"
            if goal.missing_context
            else "incomplete_trace",
        )
    if any(s.failure or s.rejection for s in material):
        return result
    if any(s.had_rejection and not s.accepted for s in material):
        return dataclasses.replace(
            result,
            label=models.Label.NEUTRAL,
            basis="none",
            reason="recovery_unconfirmed",
        )
    if isinstance(goal, revision.Goal):
        positions = {turn.turn_id: index for index, turn in enumerate(turns)}
        for limitation in goal.unavailable:
            active = {s.requirement.requirement_id for s in material}
            unresolved = active & set(limitation.requirement_ids)
            for event in goal.events:
                if (
                    event.kind
                    in {models.EventKind.FULFILLMENT, models.EventKind.REPAIR}
                    and positions[event.turn_id]
                    > positions[limitation.result_turn_id]
                ):
                    unresolved -= set(event.requirement_ids)
            if unresolved:
                return dataclasses.replace(
                    result,
                    label=models.Label.NEUTRAL,
                    basis="none",
                    reason="honest_inability",
                )
    if result.label == models.Label.SATISFIED:
        return result
    if goal.awaiting_input:
        return dataclasses.replace(result, reason="awaiting_input")
    deliverables = (
        set(goal.deliverable_requirement_ids)
        if isinstance(goal, revision.Goal)
        else set()
    )
    supported = material and all(
        s.status == "fulfilled"
        and s.correctness != "failed"
        and (
            s.accepted
            or s.correctness == "verified"
            or s.requirement.requirement_id in deliverables
        )
        for s in material
    )
    if supported:
        recovery = result.recovery
        if any(s.had_rejection for s in material):
            recovery = "confirmed"
        elif any(s.had_failure for s in material):
            recovery = "apparent"
        return dataclasses.replace(
            result,
            label=models.Label.SATISFIED,
            basis="inferred",
            reason="supported_completion",
            recovery=recovery,
        )
    return dataclasses.replace(
        result, label=models.Label.NEUTRAL, basis="none", reason="unverifiable"
    )


def evaluate_goal(
    goal: models.Goal,
    turns: Sequence[models.Turn],
    *,
    rules_version: str = "2",
) -> models.Verdict:
    """Validate and replay scoped evidence through the selected rule policy.

    Args:
        goal: Attributed interpretation, including concrete repair events.
        turns: Source conversation in snapshot order.
        rules_version: Policy identifier, defaulting to historical version 2.

    Returns:
        Derived verdict and separate task, feedback and correctness states.

    Raises:
        ValueError: Evidence is structurally unsupported.
    """
    if rules_version not in {"2", "3"}:
        raise ValueError(f"Unsupported rule version: {rules_version}")
    if rules_version == "2" and isinstance(goal, revision.Goal):
        raise ValueError("Version 3 goal cannot be replayed as version 2")
    evidence.validate_goal(goal, turns, rules_version=rules_version)
    if isinstance(goal, revision.Goal):
        revision.validate_goal(goal, turns)
    states = {
        item.requirement_id: _RequirementState(item)
        for item in goal.requirements
    }
    delivered: dict[str, str] = {}
    verified: dict[str, str | None] = {}
    for event in goal.events:
        for requirement_id in event.requirement_ids:
            state = states[requirement_id]
            if rules_version == "3" and event.kind in {
                models.EventKind.FULFILLMENT,
                models.EventKind.REPAIR,
            }:
                if delivered.get(requirement_id) != event.turn_id:
                    state.accepted = None
                    state.correctness = "unverified"
                delivered[requirement_id] = event.turn_id
            if event.kind == models.EventKind.CORRECTNESS_VERIFIED:
                verified[requirement_id] = event.result_turn_id
            state.apply(event)
            if (
                rules_version == "3"
                and event.kind
                in {models.EventKind.REPAIR, models.EventKind.FULFILLMENT}
                and verified.get(requirement_id) == event.turn_id
            ):
                state.correctness = "verified"
    result = _goal_verdict(goal, tuple(states.values()))
    if rules_version == "2":
        return result
    return _revised_verdict(goal, tuple(states.values()), result, turns)


def evaluate_conversation(
    goals: Sequence[models.Goal],
    turns: Sequence[models.Turn],
    *,
    excluded_only: bool = False,
    overall_feedback: Sequence[models.OverallFeedback] = (),
    rules_version: str = "2",
) -> models.Evaluation:
    """Evaluate goals, retaining partial failures and explicit overall scope.

    Args:
        goals: Independent user goals with explicitly attributed scope.
        turns: Ordered conversation evidence.
        excluded_only: Accepted routing excluded every evaluation target.
        overall_feedback: Cited user feedback or explicitly decisive priority.

    Returns:
        An evaluation retaining completed goal records and partial errors.
    """
    if rules_version not in {"2", "3"}:
        raise ValueError(f"Unsupported rule version: {rules_version}")
    try:
        evidence.validate_turns(turns)
        if excluded_only and goals:
            raise ValueError("Excluded-only input cannot contain goals")
        if len({g.goal_id for g in goals}) != len(goals):
            raise ValueError("Duplicate goal IDs")
    except ValueError as error:
        return models.Evaluation(
            "error", None, "evaluation_error", (), (str(error),)
        )
    completed: list[tuple[str, models.Verdict]] = []
    errors: list[str] = []
    for goal in goals:
        try:
            completed.append(
                (
                    goal.goal_id,
                    evaluate_goal(goal, turns, rules_version=rules_version),
                )
            )
        except ValueError as error:
            errors.append(f"{goal.goal_id}: {error}")
    try:
        evidence.validate_overall_feedback(overall_feedback, goals, turns)
    except (ValueError, KeyError) as error:
        errors.append(str(error))
    if errors:
        return models.Evaluation(
            "error", None, "evaluation_error", tuple(completed), tuple(errors)
        )
    if not goals:
        return models.Evaluation(
            "skipped",
            None,
            "excluded_only" if excluded_only else "no_eligible_goal",
            (),
        )
    # Overall acceptance/rejection uses the same goal rules and cannot hide
    # a material contradiction. Each scoped goal identifies its own result.
    effective_goals = {g.goal_id: g for g in goals}
    for feedback in overall_feedback:
        if feedback.kind == "priority":
            continue
        for index, (goal_id, _) in enumerate(completed):
            if goal_id not in feedback.goal_ids:
                continue
            goal = effective_goals[goal_id]
            result_id = feedback.result_turn_ids[
                feedback.goal_ids.index(goal_id)
            ]
            withdrawn = {
                r
                for event in goal.events
                if event.kind == models.EventKind.WITHDRAWAL
                for r in event.requirement_ids
            }
            scope = tuple(
                r.requirement_id
                for r in goal.requirements
                if r.requirement_id not in withdrawn
            )
            if not scope:
                continue
            event = models.Event(
                models.EventKind(feedback.kind),
                feedback.turn_id,
                scope,
                result_turn_id=result_id,
            )
            # Include prior overall feedback when replaying later feedback.
            goal = dataclasses.replace(goal, events=(*goal.events, event))
            effective_goals[goal_id] = goal
            try:
                completed[index] = (
                    goal_id,
                    evaluate_goal(goal, turns, rules_version=rules_version),
                )
            except ValueError as error:
                errors.append(f"{goal_id}: {error}")
    if errors:
        return models.Evaluation(
            "error", None, "evaluation_error", tuple(completed), tuple(errors)
        )
    eligible = [(key, v) for key, v in completed if v.status == "evaluated"]
    if not eligible:
        return models.Evaluation(
            "skipped", None, "no_eligible_goal", tuple(completed)
        )
    labels = {verdict.label for _, verdict in eligible}
    if len(labels) == 1:
        return models.Evaluation(
            "evaluated", labels.pop(), "consistent_goals", tuple(completed)
        )
    priorities = [item for item in overall_feedback if item.kind == "priority"]
    if priorities:
        chosen = dict(eligible).get(priorities[-1].goal_ids[0])
        if chosen is not None:
            return models.Evaluation(
                "evaluated", chosen.label, "explicit_priority", tuple(completed)
            )
    return models.Evaluation(
        "evaluated", models.Label.NEUTRAL, "mixed_goals", tuple(completed)
    )
