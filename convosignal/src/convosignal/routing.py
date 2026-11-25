"""Deterministic classification and conservative evaluation-target routing."""

import collections
import json
import pathlib
from collections.abc import Sequence
from typing import Any, Literal, TypeAlias

import pydantic

from convosignal import conversations, taxonomy

ROUTING_VERSION = "1"
RoutingReason: TypeAlias = Literal[
    "included_category",
    "unclassified",
    "mixed_request",
    "ambiguous_exclusion",
    "accepted_standalone_example",
    "accepted_standalone_context",
]


class RoutedQuestion(taxonomy.Contract):
    """One user message, faithful category assignment and separate routing."""

    conversation_id: str
    trace_id: str
    turn_id: str
    message_position: int
    question: str
    classification_status: Literal["classified", "set_aside", "unclassified"]
    type_name: str | None
    routing_decision: Literal["evaluate", "context_only", "exclude"]
    routing_reason: RoutingReason
    taxonomy_checksum: str
    filter_policy_checksum: str


class RoutingSnapshot(taxonomy.Contract):
    """One reproducible assignment bound to input, policy and taxonomy."""

    version: Literal["1"] = "1"
    extraction_version: Literal["1"] = "1"
    input_checksum: str
    taxonomy_checksum: str
    filter_policy_checksum: str
    questions: tuple[RoutedQuestion, ...]
    eligible_conversation_ids: tuple[str, ...]
    excluded_only_conversation_ids: tuple[str, ...]
    no_user_conversation_ids: tuple[str, ...]


def route(
    source: Sequence[conversations.Conversation],
    accepted: taxonomy.AcceptedArtifacts,
) -> RoutingSnapshot:
    """Assign categories and conservatively route evaluation targets.

    No category names, tool counts or prefix exclusions determine importance.
    This function neither removes source turns nor invokes an evaluator.
    """
    if not isinstance(accepted, taxonomy.AcceptedArtifacts):
        raise ValueError(
            "Classification requires explicitly accepted artifacts"
        )
    taxonomy.validate_accepted(accepted)
    conversations.validate_conversations(source)
    policy = taxonomy.validate_policy(accepted.filter_policy, accepted.taxonomy)
    excluded = set(policy.excluded_type_ids)
    rows = []
    for question in conversations.extract_questions(source):
        selected = taxonomy.assignment(question.question, accepted.taxonomy)
        status: Literal["classified", "set_aside", "unclassified"] = (
            "unclassified"
            if selected is None
            else "set_aside"
            if selected.set_aside
            else "classified"
        )
        decision: Literal["evaluate", "context_only", "exclude"] = "evaluate"
        reason: RoutingReason = "unclassified"
        if selected is not None:
            reason = "included_category"
            if selected.name in excluded:
                included_matches = any(
                    item.name not in excluded
                    for item, _ in taxonomy.matching_types(
                        question.question, accepted.taxonomy
                    )
                )
                if included_matches:
                    reason = "mixed_request"
                elif taxonomy.normalize(question.question) in (
                    policy.standalone_examples.get(selected.name, ())
                ):
                    decision, reason = "exclude", "accepted_standalone_example"
                else:
                    reason = "ambiguous_exclusion"
        rows.append(
            RoutedQuestion(
                **question.__dict__,
                classification_status=status,
                type_name=None if selected is None else selected.name,
                routing_decision=decision,
                routing_reason=reason,
                taxonomy_checksum=accepted.taxonomy_checksum,
                filter_policy_checksum=accepted.filter_policy_checksum,
            )
        )
    eligible = {
        r.conversation_id for r in rows if r.routing_decision == "evaluate"
    }
    final = tuple(
        row.model_copy(
            update={
                "routing_decision": "context_only",
                "routing_reason": "accepted_standalone_context",
            }
        )
        if row.routing_decision == "exclude" and row.conversation_id in eligible
        else row
        for row in rows
    )
    user_conversations = {row.conversation_id for row in final}
    return RoutingSnapshot(
        input_checksum=taxonomy.checksum(
            conversations.conversation_data(source)
        ),
        taxonomy_checksum=accepted.taxonomy_checksum,
        filter_policy_checksum=accepted.filter_policy_checksum,
        questions=final,
        eligible_conversation_ids=tuple(
            c.conversation_id for c in source if c.conversation_id in eligible
        ),
        excluded_only_conversation_ids=tuple(
            c.conversation_id
            for c in source
            if c.conversation_id in user_conversations - eligible
        ),
        no_user_conversation_ids=tuple(
            c.conversation_id
            for c in source
            if c.conversation_id not in user_conversations
        ),
    )


def validate_snapshot(
    snapshot: RoutingSnapshot,
    source: Sequence[conversations.Conversation],
    accepted: taxonomy.AcceptedArtifacts,
) -> None:
    """Reject cached routing after input, rule, taxonomy or policy changes."""
    if snapshot != route(source, accepted):
        raise ValueError("Routing snapshot mismatch; recompute classification")


def summary(
    snapshot: RoutingSnapshot,
    accepted: taxonomy.AcceptedArtifacts,
    *,
    enough_threshold: int = 3,
) -> dict[str, Any]:
    """Report question traffic separately from conversation-level filtering."""
    taxonomy.validate_accepted(accepted)
    if (
        snapshot.taxonomy_checksum != accepted.taxonomy_checksum
        or snapshot.filter_policy_checksum != accepted.filter_policy_checksum
    ):
        raise ValueError("Snapshot and accepted artifacts differ")
    if type(enough_threshold) is not int or enough_threshold < 1:
        raise ValueError("Enough threshold must be a positive integer")
    rows = snapshot.questions
    total = len(rows)
    statuses = collections.Counter(row.classification_status for row in rows)
    decisions: collections.Counter[str] = collections.Counter(
        row.routing_decision for row in rows
    )
    actionable: list[dict[str, Any]] = []
    set_aside = []
    asks_for: set[str] = set()
    excluded_categories = set(accepted.filter_policy.excluded_type_ids)
    category_counts = {}
    for item in accepted.taxonomy.types:
        matched = [r for r in rows if r.type_name == item.name]
        count = len(matched)
        category_counts[item.name] = count
        entry = {
            "name": item.name,
            "count": count,
            "traffic_share": count / total if total else None,
            "description": item.description,
            "asks_for": list(item.asks_for),
            "examples": [r.question for r in matched[:2]],
            "enough": count >= enough_threshold,
        }
        if item.set_aside:
            set_aside.append(entry)
        elif count:
            actionable.append(entry)
            asks_for.update(item.asks_for)
    actionable.sort(key=lambda row: (-row["count"], row["name"]))
    unclassified = [
        r.question for r in rows if r.classification_status == "unclassified"
    ]
    filtered = decisions["exclude"] + decisions["context_only"]
    return {
        "unit": "user_question",
        "total_nonblank_questions": total,
        "actionable_count": statuses["classified"],
        "set_aside_count": statuses["set_aside"],
        "unclassified_count": statuses["unclassified"],
        "unclassified_share": len(unclassified) / total if total else None,
        "unclassified_examples": unclassified[:2],
        "actionable_types": actionable,
        "set_aside_types": set_aside,
        "category_counts": category_counts,
        "actionable_asks_for": sorted(asks_for),
        "excluded_category_matches": sum(
            r.type_name in excluded_categories for r in rows
        ),
        "routing_counts": {
            key: decisions[key]
            for key in ("evaluate", "context_only", "exclude")
        },
        "filtered_evaluation_targets": filtered,
        "filtering_rate": filtered / total if total else None,
        "taxonomy_checksum": snapshot.taxonomy_checksum,
        "filter_policy_checksum": snapshot.filter_policy_checksum,
        "input_checksum": snapshot.input_checksum,
        "conversations": {
            "unit": "conversation",
            "input": len(snapshot.eligible_conversation_ids)
            + len(snapshot.excluded_only_conversation_ids)
            + len(snapshot.no_user_conversation_ids),
            "eligible": len(snapshot.eligible_conversation_ids),
            "excluded_only": len(snapshot.excluded_only_conversation_ids),
            "no_user_questions": len(snapshot.no_user_conversation_ids),
        },
    }


def save_snapshot(
    path: pathlib.Path, snapshot: RoutingSnapshot, *, overwrite: bool = False
) -> None:
    """Persist one routing snapshot; no source traces are fetched here."""
    taxonomy.save_json(path, snapshot, overwrite=overwrite)


def write_classification(
    output_dir: pathlib.Path,
    source: Sequence[conversations.Conversation],
    accepted: taxonomy.AcceptedArtifacts,
    *,
    overwrite: bool = False,
    enough_threshold: int = 3,
) -> RoutingSnapshot:
    """Write offline source, classification, routing and traffic artifacts.

    All target names are preflighted before writing. Partial filesystem failures
    are visible exceptions; existing artifacts are never silently overwritten.
    Satisfaction evaluation and its output are added in C2.
    """
    snapshot = route(source, accepted)
    report = summary(snapshot, accepted, enough_threshold=enough_threshold)
    output_dir.mkdir(parents=True, exist_ok=True)
    filenames = (
        "questions.jsonl",
        "routing.jsonl",
        "summary.json",
        "routing_snapshot.json",
        "conversations.jsonl",
    )
    if not overwrite and any(
        (output_dir / name).exists() for name in filenames
    ):
        raise FileExistsError("Classification output exists; request overwrite")
    mode = "w" if overwrite else "x"
    adapter = pydantic.TypeAdapter(conversations.Question)
    with (output_dir / "questions.jsonl").open(
        mode, encoding="utf-8"
    ) as stream:
        for question in conversations.extract_questions(source):
            stream.write(adapter.dump_json(question).decode("utf-8") + "\n")
    with (output_dir / "routing.jsonl").open(mode, encoding="utf-8") as stream:
        for row in snapshot.questions:
            stream.write(row.model_dump_json() + "\n")
    with (output_dir / "summary.json").open(mode, encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    save_snapshot(
        output_dir / "routing_snapshot.json", snapshot, overwrite=overwrite
    )
    conversations.save_conversations(
        output_dir / "conversations.jsonl", source, overwrite=overwrite
    )
    return snapshot
