"""Versioned, immutable contracts for attributed conversation evidence."""

import enum
from typing import Final, Literal, TypeAlias

import pydantic
from pydantic import dataclasses

SCHEMA_VERSION: Final = "1"
RULES_VERSION: Final = "2"
RequirementStatus: TypeAlias = Literal[
    "open", "fulfilled", "failed", "withdrawn"
]
Basis: TypeAlias = Literal["direct", "inferred", "none"]
Recovery: TypeAlias = Literal["none", "apparent", "confirmed", "unresolved"]
Outcome: TypeAlias = Literal[
    "fulfilled", "partly_fulfilled", "failed", "unverifiable"
]
UserResponse: TypeAlias = Literal[
    "acceptance", "productive_use", "rejection_frustration", "no_clear_evidence"
]
Correctness: TypeAlias = Literal["verified", "unverified", "failed"]
GoalReason: TypeAlias = Literal[
    "conflicting_evidence",
    "explicit_rejection",
    "incomplete_trace",
    "unresolved_material_failure",
    "recovery_unconfirmed",
    "accepted_result",
    "productive_use",
    "missing_context",
    "awaiting_input",
    "unverifiable",
    "no_clear_user_response",
    "withdrawn_goal",
    "supported_completion",
    "honest_inability",
]
ConversationReason: TypeAlias = Literal[
    "evaluation_error",
    "excluded_only",
    "no_eligible_goal",
    "consistent_goals",
    "explicit_priority",
    "mixed_goals",
]
CONTRACT_CONFIG = pydantic.ConfigDict(extra="forbid", validate_default=True)


class Label(enum.StrEnum):
    """The three successful evaluation outcomes."""

    SATISFIED = "Satisfied"
    DISSATISFIED = "Dissatisfied"
    NEUTRAL = "Neutral"


class EventKind(enum.StrEnum):
    """Evidence interpretations, never keyword or sentiment matches."""

    FAILURE = "failure"
    REJECTION = "rejection"
    REPAIR = "repair"
    ACCEPTANCE = "acceptance"
    PRODUCTIVE_USE = "productive_use"
    WITHDRAWAL = "withdrawal"
    FULFILLMENT = "fulfillment"
    CORRECTNESS_VERIFIED = "correctness_verified"
    CORRECTNESS_FAILED = "correctness_failed"


@dataclasses.dataclass(frozen=True, config=CONTRACT_CONFIG)
class Turn:
    """A source turn; tuple position establishes chronology."""

    turn_id: str
    role: Literal["user", "assistant", "tool"]
    text: str
    trace_id: str | None = None
    source_position: int | None = None


@dataclasses.dataclass(frozen=True, config=CONTRACT_CONFIG)
class Requirement:
    """A user-requested outcome, including its explicit material constraints."""

    requirement_id: str
    text: str
    source_turn_id: str
    material: pydantic.StrictBool = True


@dataclasses.dataclass(frozen=True, config=CONTRACT_CONFIG)
class Event:
    """An interpretation affecting scoped requirements at a cited source turn.

    Repair means concrete apparent repair, not an assistant assertion.
    Acceptance,
    use, rejection and repair identify the relevant assistant result explicitly.
    Correctness events require independent tool evidence. Structural validation
    cannot prove that cited text semantically supports an interpretation.
    """

    kind: EventKind
    turn_id: str
    requirement_ids: tuple[str, ...]
    evidence_turn_ids: tuple[str, ...] = ()
    result_turn_id: str | None = None


@dataclasses.dataclass(frozen=True, config=CONTRACT_CONFIG)
class Goal:
    """A goal with its requirements, chronology and context diagnostics."""

    goal_id: str
    requirements: tuple[Requirement, ...]
    events: tuple[Event, ...] = ()
    context_complete: pydantic.StrictBool = True
    awaiting_input: pydantic.StrictBool = False
    missing_context: pydantic.StrictBool = False
    category: str | None = None


@dataclasses.dataclass(frozen=True, config=CONTRACT_CONFIG)
class OverallFeedback:
    """Explicit overall feedback or decisive priority, scoped to goal IDs.

    Overall acceptance/rejection must identify the delivered assistant results.
    Priority selects one goal explicitly; the engine never infers weights.
    """

    kind: Literal["acceptance", "rejection", "priority"]
    turn_id: str
    goal_ids: tuple[str, ...]
    result_turn_ids: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True, config=CONTRACT_CONFIG)
class Versions:
    """Identifiers for evidence extraction and deterministic interpretation."""

    evaluator: str
    model: str
    prompt: str
    taxonomy_checksum: str
    rules: Literal["2", "3"] = RULES_VERSION
    schema: Literal["1", "2"] = SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Keep rule and evidence contract versions paired explicitly."""
        if (self.rules, self.schema) not in {("2", "1"), ("3", "2")}:
            raise ValueError("Unsupported rule/schema version combination")


@dataclasses.dataclass(frozen=True, config=CONTRACT_CONFIG)
class EvidenceRecord:
    """Model evidence input without authoritative model-generated verdicts."""

    conversation_id: str
    turns: tuple[Turn, ...]
    goals: tuple[Goal, ...]
    versions: Versions
    overall_feedback: tuple[OverallFeedback, ...] = ()
    excluded_only: pydantic.StrictBool = False


@dataclasses.dataclass(frozen=True, config=CONTRACT_CONFIG)
class ModelEvidence:
    """Model interpretation without source replacement or final labels."""

    goals: tuple[Goal, ...]
    overall_feedback: tuple[OverallFeedback, ...] = ()


@dataclasses.dataclass(frozen=True, config=CONTRACT_CONFIG)
class RequirementResult:
    """Derived requirement state at the observed cutoff."""

    requirement_id: str
    status: RequirementStatus
    source_turn_ids: tuple[str, ...]


@dataclasses.dataclass(frozen=True, config=CONTRACT_CONFIG)
class Verdict:
    """A derived goal verdict, separate from completion and correctness."""

    label: Label | None
    reason: GoalReason
    basis: Basis
    recovery: Recovery
    source_turn_ids: tuple[str, ...]
    requirements: tuple[RequirementResult, ...] = ()
    outcome: Outcome = "unverifiable"
    user_response: UserResponse = "no_clear_evidence"
    correctness: Correctness = "unverified"
    unresolved_requirement_ids: tuple[str, ...] = ()
    status: Literal["evaluated", "skipped"] = "evaluated"
    rules_version: Literal["2", "3"] = RULES_VERSION

    def __post_init__(self) -> None:
        """Enforce the label/status invariant on construction and JSON input."""
        if (self.status == "evaluated") != (self.label is not None):
            raise ValueError("Only evaluated goals have labels")


@dataclasses.dataclass(frozen=True, config=CONTRACT_CONFIG)
class Evaluation:
    """Conversation status retaining partial results and diagnostics."""

    status: Literal["evaluated", "skipped", "error"]
    label: Label | None
    reason: ConversationReason
    goals: tuple[tuple[str, Verdict], ...]
    errors: tuple[str, ...] = ()
    conversation_id: str = ""
    versions: Versions | None = None
    source_turn_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Keep operational errors outside valid-outcome denominators."""
        if (self.status == "evaluated") != (self.label is not None):
            raise ValueError("Only evaluated conversations have labels")
        if self.status == "evaluated" and not any(
            verdict.status == "evaluated" for _, verdict in self.goals
        ):
            raise ValueError("Evaluated conversations require goal results")
        if self.errors and self.status != "error":
            raise ValueError("Diagnostics require error status")
        if self.status == "error" and not self.errors:
            raise ValueError("Error status requires diagnostics")
        if len({goal_id for goal_id, _ in self.goals}) != len(self.goals):
            raise ValueError("Duplicate goal result IDs")


@dataclasses.dataclass(frozen=True, config=CONTRACT_CONFIG)
class EvaluationRecord(Evaluation):
    """Persisted JSONL record, including audit details and snapshot hashes."""

    evaluation_status: Literal["evaluated", "skipped", "error"] = "error"
    evidence_details: dict[str, object] = pydantic.Field(default_factory=dict)
    input_checksum: str = ""
    taxonomy_checksum: str = ""
    filter_policy_checksum: str = ""

    def __post_init__(self) -> None:
        """Keep the public evaluation_status consistent with internal status."""
        Evaluation.__post_init__(self)
        if self.status != self.evaluation_status:
            raise ValueError("evaluation_status and status disagree")
