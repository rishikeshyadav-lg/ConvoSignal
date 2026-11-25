"""Typed, source-bound report data shared by offline HTML and Word exports."""

import collections
import dataclasses
import datetime
import json
from collections.abc import Sequence
from typing import Literal

import pydantic

from convosignal import (
    conversations,
    models,
    prompts,
    revision,
    run_artifacts,
    schemas,
    taxonomy,
)


class ReportMetadata(pydantic.BaseModel):
    """Owner-declared report context; counts are never accepted as metadata."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)
    agent_name: str = pydantic.Field(min_length=1, max_length=200)
    stage: str = pydantic.Field(
        default="Unspecified", min_length=1, max_length=80
    )
    stage_basis: str = pydantic.Field(default="Owner-declared", max_length=300)
    report_date: datetime.date
    source_description: str = pydantic.Field(
        default="Frozen run artifacts", max_length=500
    )


class TraceHeader(pydantic.BaseModel):
    """Captured source header; identity is used only to compute aggregate
    counts.
    """

    model_config = pydantic.ConfigDict(extra="ignore", frozen=True)
    trace_id: str = pydantic.Field(min_length=1)
    session_id: str = pydantic.Field(min_length=1)
    timestamp_ms: int = pydantic.Field(ge=0, strict=True)
    user: str | None = None


class Selection(pydantic.BaseModel):
    """Selected source headers, accepting older acquisition diagnostics too."""

    model_config = pydantic.ConfigDict(extra="ignore", frozen=True)
    traces: tuple[TraceHeader, ...]
    experiment_id: str | None = None
    experiment_name: str | None = None
    requested_interactions: int | None = pydantic.Field(default=None, ge=1)
    headers_scanned: int | None = pydantic.Field(default=None, ge=0)
    session_context: str | None = None


class RequirementView(pydantic.BaseModel):
    """Human-readable requirement and its mechanically derived state."""

    requirement_id: str
    text: str
    source_turn_id: str
    material: bool
    status: str


class GoalView(pydantic.BaseModel):
    """Decision explanation without raw provider responses or tool payloads."""

    id: str
    category: str
    label: str | None
    reason: str
    explanation: str
    basis: str
    outcome: str
    user_response: str
    correctness: str
    recovery: str
    requirements: tuple[RequirementView, ...]
    limitations: tuple[str, ...]
    source_turn_ids: tuple[str, ...]


class MessageView(pydantic.BaseModel):
    """Captured source text, rendered only as text in export formats."""

    role: Literal["user", "assistant"]
    turn_id: str
    text: str


class SampleView(pydantic.BaseModel):
    """One selected trace and the final decision of its containing
    conversation.
    """

    id: str
    number: int
    conversation_number: int
    trace_id: str
    timestamp_ms: int | None
    label: str
    status: str
    reason: str
    explanation: str
    messages: tuple[MessageView, ...]
    prompt_count: int
    errors: tuple[str, ...]


class ConversationView(pydantic.BaseModel):
    """Conversation decision and requirements, stored once despite many
    traces.
    """

    number: int
    label: str
    status: str
    reason: str
    explanation: str
    context_complete: bool
    messages: tuple[MessageView, ...]
    goals: tuple[GoalView, ...]
    errors: tuple[str, ...]
    input_checksum: str
    versions: dict[str, str]


class ReportData(pydantic.BaseModel):
    """Validated portable rendering input; identities and raw tools are
    excluded.
    """

    format_version: Literal["convosignal-report-v1"] = "convosignal-report-v1"
    metadata: ReportMetadata
    sample_count: int
    prompt_count: int
    captured_answers: int
    conversation_count: int
    counts: dict[str, int]
    conversation_counts: dict[str, int]
    date_range_utc: tuple[str, str] | None
    distinct_attributed_users: int | None
    unattributed_traces: int | None
    source_experiment: str | None
    requested_interactions: int | None
    session_context: str | None
    replayed_conversations: int
    source_checksum: str
    samples: tuple[SampleView, ...]
    conversations: tuple[ConversationView, ...]
    evaluator_prompts: dict[str, str]
    independent_human_validation: Literal["pending"] = "pending"


REASONS = {
    "supported_completion": "Every essential requirement is "
    "recorded as complete and supported. "
    "Satisfaction is inferred; a positive "
    "user reaction is not implied.",
    "honest_inability": "Source evidence records an external "
    "limitation affecting essential work. That "
    "limitation alone does not establish "
    "dissatisfaction.",
    "unverifiable": "Evidence does not establish supported "
    "completion or applicable acceptance. This "
    "does not prove the answer is wrong.",
    "mixed_goals": "Independent goals have different outcomes, "
    "without applicable overall feedback or an "
    "explicit priority deciding the conversation.",
    "consistent_goals": "All evaluated goals share this decision. "
    "See their individual requirements and "
    "reasons.",
    "explicit_priority": "An explicitly decisive user priority "
    "determines the conversation decision; "
    "other outcomes remain visible.",
    "missing_context": "Relevant request scope or history is missing.",
    "incomplete_trace": "The captured history cannot resolve this "
    "outcome or recovery.",
    "awaiting_input": "Necessary user input remains pending, "
    "without a separately established failure.",
    "recovery_unconfirmed": "A rejected issue was corrected, but "
    "later acceptance or use does not "
    "cover every previously rejected "
    "essential issue.",
    "explicit_rejection": "Applicable user feedback rejects the "
    "result or gives up because of an "
    "unresolved issue.",
    "unresolved_material_failure": "Evidence records an unresolved "
    "essential task failure. "
    "Dissatisfaction is inferred; "
    "an explicit complaint is not "
    "required.",
    "conflicting_evidence": "Applicable positive feedback "
    "conflicts with a known essential "
    "error; neither signal is discarded.",
    "accepted_result": "The user clearly accepted the result, "
    "without a known essential contradiction. "
    "Acceptance does not verify factual "
    "correctness.",
    "productive_use": "The user used a specific result to advance "
    "work, without an unresolved essential "
    "issue.",
    "excluded_only": "Accepted filtering left no evaluation "
    "target. No satisfaction label was assigned.",
    "no_eligible_goal": "No eligible substantive goal was "
    "available. No satisfaction label was "
    "assigned.",
    "withdrawn_goal": "The user withdrew this goal's active scope.",
    "no_clear_user_response": "No sufficiently scoped acceptance "
    "or rejection resolves this goal "
    "under the recorded policy.",
    "evaluation_error": "Processing did not produce a validated "
    "conversation verdict. Error is separate "
    "from Neutral; captured source remains "
    "inspectable.",
}

RESEARCH = (
    (
        "Google · Good Abandonment (2009)",
        "https://research.google/pubs/good-abandonment-in-mobile-and-pc-internet-search/",
        "A search can end successfully without another click or query.",
    ),
    (
        "Amazon Alexa · Implicit User Feedback (2021)",
        "https://aclanthology.org/2021.emnlp-main.489/",
        "Conversation context and interaction patterns can provide "
        "implicit feedback.",
    ),
    (
        "Microsoft · Learning from Copilot Interactions (2024)",
        "https://www.microsoft.com/en-us/research/blog/learning-from-interaction-with-microsoft-copilot-web/",
        "Completion is associated with estimated satisfaction; "
        "estimates were tested against user votes.",
    ),
)


def _goals(row: models.EvaluationRecord) -> tuple[GoalView, ...]:
    """Join validated goal states to their scoped requirements."""
    evidence = row.evidence_details.get("evidence")
    if evidence is None:
        if row.goals:
            raise ValueError("Partial goal results lack supporting evidence")
        return ()
    record = schemas.parse_evidence(json.dumps(evidence))
    interpreted = {goal.goal_id: goal for goal in record.goals}
    result = []
    for goal_id, verdict in row.goals:
        goal = interpreted[goal_id]
        requirements = {r.requirement_id: r for r in goal.requirements}
        limitations: tuple[str, ...] = ()
        if isinstance(goal, revision.Goal):
            limitations = tuple(item.explanation for item in goal.unavailable)
        result.append(
            GoalView(
                id=goal_id,
                category=goal.category or "unclassified",
                label=verdict.label.value if verdict.label else None,
                reason=verdict.reason,
                explanation=REASONS[verdict.reason],
                basis=verdict.basis,
                outcome=verdict.outcome,
                user_response=verdict.user_response,
                correctness=verdict.correctness,
                recovery=verdict.recovery,
                limitations=limitations,
                source_turn_ids=verdict.source_turn_ids,
                requirements=tuple(
                    RequirementView(
                        requirement_id=r.requirement_id,
                        text=requirements[r.requirement_id].text,
                        material=requirements[r.requirement_id].material,
                        source_turn_id=requirements[
                            r.requirement_id
                        ].source_turn_id,
                        status=r.status,
                    )
                    for r in verdict.requirements
                ),
            )
        )
    return tuple(result)


def _counts(labels: Sequence[str]) -> dict[str, int]:
    """Include zero-valued outcomes and separate skips/errors."""
    counts = collections.Counter(labels)
    return {
        key: counts[key]
        for key in ("Satisfied", "Dissatisfied", "Neutral", "Skipped", "Error")
    }


def build(
    run: run_artifacts.SavedRun,
    metadata: ReportMetadata,
    selection: Selection | None = None,
) -> ReportData:
    """Derive export data entirely from audited source and saved verdicts.

    Args:
        run: Source-bound run returned by run_artifacts.load.
        metadata: Owner-declared agent/stage and explicit report date.
        selection: Optional captured headers; required for user/date statistics.

    Returns:
        Typed report preserving captured source text and decision denominators.

    Raises:
        ValueError: Header coverage conflicts with the authoritative source.
    """
    rows = {row.conversation_id: row for row in run.records}
    conversation_views = []
    grouped: dict[tuple[str, str], tuple[int, list[models.Turn]]] = {}
    for number, conversation in enumerate(run.source, 1):
        row = rows[conversation.conversation_id]
        label = row.label.value if row.label else row.status.title()
        visible = []
        for turn in conversation.turns:
            key = (
                conversation.conversation_id,
                turn.trace_id or conversation.conversation_id,
            )
            grouped.setdefault(key, (number, []))[1].append(turn)
            if turn.role in {"user", "assistant"}:
                visible.append(
                    MessageView(
                        role="user" if turn.role == "user" else "assistant",
                        text=turn.text,
                        turn_id=turn.turn_id,
                    )
                )
        conversation_views.append(
            ConversationView(
                number=number,
                label=label,
                status=row.status,
                reason=row.reason,
                explanation=REASONS[row.reason],
                context_complete=conversation.context_complete,
                messages=tuple(visible),
                goals=_goals(row),
                errors=row.errors,
                input_checksum=row.input_checksum,
                versions=dataclass_versions(row),
            )
        )
    keys = list(grouped)
    headers = {}
    if selection is not None:
        keys = []
        for header in selection.traces:
            key = (header.session_id, header.trace_id)
            if key in headers:
                raise ValueError("Duplicate selected trace header")
            if header.session_id not in rows:
                raise ValueError(
                    "Selected header refers to an unknown conversation"
                )
            if key not in grouped:
                row = rows[header.session_id]
                if row.status != "error" or not row.evidence_details.get(
                    "source_error"
                ):
                    raise ValueError(
                        "Selected header is absent from captured source"
                    )
                number = next(
                    i
                    for i, c in enumerate(run.source, 1)
                    if c.conversation_id == header.session_id
                )
                grouped[key] = (number, [])
            keys.append(key)
            headers[key] = header
        if {h.session_id for h in selection.traces} != set(rows):
            raise ValueError(
                "Selected headers and conversation coverage differ"
            )
        if not keys:
            raise ValueError("Selected header list is empty")
    samples = []
    for number, key in enumerate(keys, 1):
        conversation_number, turns = grouped[key]
        view = conversation_views[conversation_number - 1]
        messages = tuple(
            MessageView(
                role="user" if t.role == "user" else "assistant",
                text=t.text,
                turn_id=t.turn_id,
            )
            for t in turns
            if t.role in {"user", "assistant"}
        )
        selected_header = headers.get(key)
        samples.append(
            SampleView(
                id=f"sample-{number:04d}",
                number=number,
                conversation_number=conversation_number,
                trace_id=key[1],
                timestamp_ms=selected_header.timestamp_ms
                if selected_header
                else None,
                label=view.label,
                status=view.status,
                reason=view.reason,
                explanation=view.explanation,
                messages=messages,
                prompt_count=sum(m.role == "user" for m in messages),
                errors=view.errors,
            )
        )
    dates: tuple[str, str] | None = None
    users = None
    unattributed = None
    if selection is not None:
        timestamps = [header.timestamp_ms for header in selection.traces]
        date_values = tuple(
            datetime.datetime.fromtimestamp(t / 1000, datetime.UTC).isoformat()
            for t in (min(timestamps), max(timestamps))
        )
        dates = (date_values[0], date_values[1])
        users = len(
            {
                h.user.strip().casefold()
                for h in selection.traces
                if h.user and h.user.strip()
            }
        )
        unattributed = sum(
            not h.user or not h.user.strip() for h in selection.traces
        )
    prompt_ids = {row.versions.prompt for row in run.records if row.versions}
    known_prompts = dict((prompts.for_rules("2"), prompts.for_rules("3")))
    return ReportData(
        metadata=metadata,
        sample_count=len(samples),
        prompt_count=sum(s.prompt_count for s in samples),
        captured_answers=sum(
            m.role == "assistant" for s in samples for m in s.messages
        ),
        conversation_count=len(conversation_views),
        counts=_counts([s.label for s in samples]),
        conversation_counts=_counts([c.label for c in conversation_views]),
        date_range_utc=dates,
        distinct_attributed_users=users,
        unattributed_traces=unattributed,
        source_experiment=(selection.experiment_name or selection.experiment_id)
        if selection
        else None,
        requested_interactions=selection.requested_interactions
        if selection
        else None,
        session_context=selection.session_context if selection else None,
        replayed_conversations=run.replayed,
        source_checksum=taxonomy.checksum(
            conversations.conversation_data(run.source)
        ),
        samples=tuple(samples),
        conversations=tuple(conversation_views),
        evaluator_prompts={
            name: known_prompts.get(
                name, "Prompt text not packaged for this archived version"
            )
            for name in sorted(prompt_ids)
        },
    )


def dataclass_versions(row: models.EvaluationRecord) -> dict[str, str]:
    """Serialize the validated immutable version contract for audit display."""
    if row.versions is None:
        raise ValueError("Prediction is missing versions")
    return dataclasses.asdict(row.versions)


def summary_sections(
    data: ReportData,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return consistent factual prose for both summary export formats."""
    dates = "Not captured"
    if data.date_range_utc:
        dates = (
            f"{data.date_range_utc[0][:10]} through "
            f"{data.date_range_utc[1][:10]} (UTC)"
        )
    users = "Not captured"
    if data.distinct_attributed_users is not None:
        users = f"{data.distinct_attributed_users} normalized attributed IDs"
        if data.unattributed_traces:
            users = (
                f"{users}; {data.unattributed_traces} selected traces "
                "lack attribution"
            )
    satisfaction = (
        "Satisfied: applicable acceptance/use without a known "
        "essential contradiction. "
        "Under rules 3, every essential requirement being complete "
        "and supported "
        "can also justify inferred satisfaction without user feedback."
    )
    if {c.versions["rules"] for c in data.conversations} == {"2"}:
        satisfaction = (
            "Satisfied (rules 2): all essential work has applicable acceptance "
            "or productive use, without a known essential contradiction. "
            "Apparently complete work followed by silence stays Neutral."
        )
    selection_note = ""
    if data.requested_interactions is not None:
        selection_note = (
            f" Requested {data.requested_interactions} interactions; "
            f"{data.sample_count} selected traces were supplied."
        )
    return (
        (
            "Agent and source [E1 · source]",
            (
                f"Agent: {data.metadata.agent_name}. "
                f"Stage: {data.metadata.stage} "
                f"({data.metadata.stage_basis}). "
                f"Source: {data.metadata.source_description}.",
                "Source experiment: "
                f"{data.source_experiment or 'Not captured'}. "
                f"Prompt dates: {dates}. Distinct attributed users: {users}. "
                "Attribution does not prove unique human authorship.",
                f"{data.sample_count} selected trace rows; "
                f"{data.prompt_count} captured "
                f"user messages; {data.captured_answers} captured "
                "assistant messages; "
                f"{data.conversation_count} conversations.{selection_note} "
                "Session context: "
                f"{data.session_context or 'as recorded in source'}.",
            ),
        ),
        (
            "How decisions are measured [E2 · source]",
            (
                satisfaction,
                "Dissatisfied: unresolved applicable rejection or a "
                "proven essential "
                "task failure; inferred failure is distinct from a "
                "user complaint.",
                "Neutral: insufficient or conflicting evidence, "
                "honest inability "
                "without rejection, pending input, unconfirmed "
                "recovery, or mixed "
                "goals without a deciding priority. Silence alone is "
                "not feedback.",
                "The LLM interprets requirements and evidence. Python"
                " validates "
                "citation references and applies the recorded version"
                " of the rules. "
                "Known essential error plus praise stays Neutral. "
                "These are task "
                "assessments, not measured user feelings.",
            ),
        ),
    )
