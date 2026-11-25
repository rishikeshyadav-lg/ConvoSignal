"""Mechanical evidence checks; semantic attribution remains reviewable."""

from collections.abc import Sequence

from convosignal import models

VALIDATION_VERSION = "1.1"


def validate_turns(turns: Sequence[models.Turn]) -> dict[str, int]:
    """Return positions after checking unique, nonblank source identifiers."""
    positions = {turn.turn_id: index for index, turn in enumerate(turns)}
    if len(positions) != len(turns) or any(
        not turn.turn_id.strip() for turn in turns
    ):
        raise ValueError("Source turn IDs must be unique and nonempty")
    return positions


def validate_goal(
    goal: models.Goal, turns: Sequence[models.Turn], *, rules_version: str = "2"
) -> None:
    """Check requirement scope, source roles, chronology and result references.

    Args:
        goal: Attributed interpretation of one user goal.
        turns: Ordered source conversation with available tool evidence.

    Raises:
        ValueError: Citations or relationships are structurally unsupported.
    """
    positions = validate_turns(turns)
    sources = {turn.turn_id: turn for turn in turns}
    requirements = {item.requirement_id: item for item in goal.requirements}
    if not goal.goal_id.strip() or not requirements:
        raise ValueError("Goal ID and requirements are required")
    if len(requirements) != len(goal.requirements):
        raise ValueError("Duplicate requirement IDs")
    for item in goal.requirements:
        source = sources.get(item.source_turn_id)
        if not item.requirement_id.strip() or not item.text.strip():
            raise ValueError("Requirement ID and text are required")
        if source is None or source.role != "user":
            raise ValueError("Requirements must cite user turns")
    previous = -1
    withdrawn: set[str] = set()
    seen: dict[tuple[int, str], set[models.EventKind]] = {}
    feedback_kinds = {
        models.EventKind.ACCEPTANCE,
        models.EventKind.PRODUCTIVE_USE,
        models.EventKind.REJECTION,
        models.EventKind.WITHDRAWAL,
    }
    result_kinds = feedback_kinds - {models.EventKind.WITHDRAWAL}
    result_kinds |= {
        models.EventKind.REPAIR,
        models.EventKind.CORRECTNESS_FAILED,
        models.EventKind.CORRECTNESS_VERIFIED,
    }
    latest_repair: dict[str, str] = {}
    unresolved: set[str] = set()
    for event in goal.events:
        source = sources.get(event.turn_id)
        if source is None:
            raise ValueError("Event cites an unknown turn")
        position = positions[event.turn_id]
        if position < previous:
            raise ValueError("Events must be chronological")
        previous = position
        scope = set(event.requirement_ids)
        if not scope or not scope <= requirements.keys():
            raise ValueError("Event must scope existing requirements")
        if len(scope) != len(event.requirement_ids) or scope & withdrawn:
            raise ValueError("Duplicate or previously withdrawn scope")
        for requirement_id in scope:
            key = (position, requirement_id)
            existing = seen.get(key, set())
            # Completion and independently supported correctness describe
            # separate axes of the same answer. Other same-turn transitions
            # remain conflicts, including duplicate observations.
            compatible = {
                models.EventKind.FULFILLMENT,
                models.EventKind.CORRECTNESS_VERIFIED,
            }
            repair_pair = {
                models.EventKind.REPAIR,
                models.EventKind.CORRECTNESS_VERIFIED,
            }
            allowed = existing | {event.kind} == compatible or (
                rules_version == "3" and existing | {event.kind} == repair_pair
            )
            if event.kind in existing or (existing and not allowed):
                raise ValueError("Conflicting events for one requirement/turn")
            seen.setdefault(key, set()).add(event.kind)
            requested_at = positions[
                requirements[requirement_id].source_turn_id
            ]
            if position < requested_at:
                raise ValueError("Event precedes its requirement")
        if event.kind in feedback_kinds and source.role != "user":
            raise ValueError("Feedback and scope changes must cite user turns")
        if (
            event.kind
            in {
                models.EventKind.REPAIR,
                models.EventKind.FULFILLMENT,
            }
            and source.role != "assistant"
        ):
            raise ValueError("Completion/repair must cite assistant results")
        if event.kind in result_kinds:
            result = sources.get(event.result_turn_id or "")
            if (
                result is None
                or result.role != "assistant"
                or not result.text.strip()
            ):
                raise ValueError("Feedback/repair requires an assistant result")
            result_position = positions[result.turn_id]
            if result_position > position:
                raise ValueError("Result cannot be in the future")
            if event.kind in feedback_kinds and result_position == position:
                raise ValueError("Feedback must follow the result")
            if any(
                result_position < positions[requirements[r].source_turn_id]
                for r in scope
            ):
                raise ValueError("Result precedes its requirement")
            if event.kind == models.EventKind.REPAIR:
                if not scope <= unresolved:
                    raise ValueError("Repair requires a prior scoped failure")
                unresolved -= scope
                if result.turn_id != event.turn_id:
                    raise ValueError("Repair must identify the revised result")
                latest_repair.update(dict.fromkeys(scope, result.turn_id))
            elif any(
                r in latest_repair
                and result_position < positions[latest_repair[r]]
                for r in scope
            ):
                raise ValueError("Feedback refers to a superseded result")
        if (
            event.kind
            in {
                models.EventKind.FAILURE,
                models.EventKind.CORRECTNESS_FAILED,
                models.EventKind.CORRECTNESS_VERIFIED,
            }
            and not event.evidence_turn_ids
        ):
            raise ValueError("Failure/correctness needs supporting evidence")
        for citation in event.evidence_turn_ids:
            if citation not in positions or positions[citation] > position:
                raise ValueError("Supporting evidence is missing or in future")
        if event.kind in {
            models.EventKind.CORRECTNESS_FAILED,
            models.EventKind.CORRECTNESS_VERIFIED,
        } and not any(
            sources[c].role == "tool" for c in event.evidence_turn_ids
        ):
            raise ValueError("Correctness requires independent tool evidence")
        if event.kind in {
            models.EventKind.FAILURE,
            models.EventKind.REJECTION,
            models.EventKind.CORRECTNESS_FAILED,
        }:
            unresolved |= scope
        if event.kind == models.EventKind.WITHDRAWAL:
            withdrawn |= scope
            unresolved -= scope


def validate_overall_feedback(
    feedback: Sequence[models.OverallFeedback],
    goals: Sequence[models.Goal],
    turns: Sequence[models.Turn],
) -> None:
    """Require explicit user-scoped, chronological conversation feedback."""
    positions = validate_turns(turns)
    sources = {turn.turn_id: turn for turn in turns}
    goal_ids = {goal.goal_id for goal in goals}
    previous = -1
    for item in feedback:
        source = sources.get(item.turn_id)
        if source is None or source.role != "user":
            raise ValueError("Overall feedback must cite a user turn")
        position = positions[source.turn_id]
        if position <= previous:
            raise ValueError("Overall feedback must be chronological")
        previous = position
        if not item.goal_ids or not set(item.goal_ids) <= goal_ids:
            raise ValueError("Overall feedback has unknown or empty goal scope")
        if len(set(item.goal_ids)) != len(item.goal_ids):
            raise ValueError("Duplicate overall goal scope")
        if item.kind == "priority":
            if len(item.goal_ids) != 1:
                raise ValueError("Priority must identify one decisive goal")
        elif len(item.result_turn_ids) != len(item.goal_ids):
            raise ValueError("Overall feedback must identify delivered results")
        for result_id in item.result_turn_ids:
            result = sources.get(result_id)
            if (
                result is None
                or result.role != "assistant"
                or not result.text.strip()
            ):
                raise ValueError("Overall feedback result must be assistant")
            if positions[result_id] >= position:
                raise ValueError("Overall feedback must follow results")
        for goal in goals:
            if goal.goal_id not in item.goal_ids:
                continue
            for requirement in goal.requirements:
                if positions[requirement.source_turn_id] > position:
                    raise ValueError("Overall feedback precedes a requirement")
            if item.kind != "priority" and any(
                positions[event.turn_id] > position for event in goal.events
            ):
                raise ValueError("Overall feedback is stale for a scoped goal")
