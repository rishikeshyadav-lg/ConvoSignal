"""Version 3 evidence extends the unchanged version 2 goal contract."""

from collections.abc import Sequence

import pydantic
from pydantic import dataclasses

from convosignal import evidence, models


@dataclasses.dataclass(frozen=True, config=models.CONTRACT_CONFIG)
class Limitation:
    """A cited external limitation, not an assertion of agent failure."""

    requirement_ids: tuple[str, ...]
    evidence_turn_ids: tuple[str, ...]
    result_turn_id: str
    explanation: str


@dataclasses.dataclass(frozen=True, config=models.CONTRACT_CONFIG)
class Goal(models.Goal):
    """Separate observable deliverable completion from factual verification."""

    deliverable_requirement_ids: tuple[str, ...] = ()
    unavailable: tuple[Limitation, ...] = ()
    context_evidence_turn_ids: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True, config=models.CONTRACT_CONFIG)
class ModelEvidence:
    """Version 3 observations without source replacement or predicted labels."""

    goals: tuple[Goal, ...]
    overall_feedback: tuple[models.OverallFeedback, ...] = ()


@dataclasses.dataclass(frozen=True, config=models.CONTRACT_CONFIG)
class EvidenceRecord:
    """Version 3 evidence with authoritative source turns and provenance."""

    conversation_id: str
    turns: tuple[models.Turn, ...]
    goals: tuple[Goal, ...]
    versions: models.Versions
    overall_feedback: tuple[models.OverallFeedback, ...] = ()
    excluded_only: pydantic.StrictBool = False


EVIDENCE = pydantic.TypeAdapter(EvidenceRecord)
MODEL_EVIDENCE = pydantic.TypeAdapter(ModelEvidence)


def validate_goal(goal: Goal, turns: Sequence[models.Turn]) -> None:
    """Validate revision-specific scope and independently cited limitations."""
    positions = evidence.validate_turns(turns)
    sources = {turn.turn_id: turn for turn in turns}
    requirements = {r.requirement_id: r for r in goal.requirements}
    latest_results: dict[str, int] = {}
    for event in goal.events:
        if event.kind in {
            models.EventKind.FULFILLMENT,
            models.EventKind.REPAIR,
        }:
            latest_results.update(
                dict.fromkeys(event.requirement_ids, positions[event.turn_id])
            )
        elif event.result_turn_id is not None:
            if any(
                positions[event.result_turn_id] < latest_results.get(r, -1)
                for r in event.requirement_ids
            ):
                raise ValueError(
                    "Evidence refers to a superseded delivered result"
                )
    deliverables = goal.deliverable_requirement_ids
    if (
        len(set(deliverables)) != len(deliverables)
        or not set(deliverables) <= requirements.keys()
    ):
        raise ValueError("Deliverable scope must identify unique requirements")
    for limitation in goal.unavailable:
        scope = set(limitation.requirement_ids)
        if (
            not scope
            or len(scope) != len(limitation.requirement_ids)
            or not scope <= requirements.keys()
        ):
            raise ValueError(
                "Limitation must scope existing unique requirements"
            )
        result = sources.get(limitation.result_turn_id)
        if (
            result is None
            or result.role != "assistant"
            or not result.text.strip()
        ):
            raise ValueError("Limitation needs its delivered assistant result")
        end = positions[result.turn_id]
        if any(positions[requirements[r].source_turn_id] > end for r in scope):
            raise ValueError("Limitation result precedes its request")
        if (
            not limitation.explanation.strip()
            or not limitation.evidence_turn_ids
        ):
            raise ValueError(
                "Limitation needs supporting evidence and explanation"
            )
        for citation in limitation.evidence_turn_ids:
            if citation not in positions or positions[citation] > end:
                raise ValueError(
                    "Limitation evidence is unknown or in the future"
                )
        if not any(
            sources[c].role in {"tool", "user"}
            for c in limitation.evidence_turn_ids
        ):
            raise ValueError("Assistant assertion alone cannot prove inability")
    if goal.context_evidence_turn_ids:
        if not set(goal.context_evidence_turn_ids) <= sources.keys():
            raise ValueError("Context evidence cites unknown source")
        if not {r.source_turn_id for r in goal.requirements} <= set(
            goal.context_evidence_turn_ids
        ):
            raise ValueError("Relevant context must include all goal requests")
        if not any(
            sources[c].role == "assistant"
            for c in goal.context_evidence_turn_ids
        ):
            raise ValueError("Relevant context needs a captured result")
