"""One immutable conversation/routing snapshot through evidence and verdicts."""

import dataclasses
import json
import pathlib
from collections.abc import Sequence
from typing import Any

import pydantic

from convosignal import (
    conversations,
    evidence,
    llm,
    models,
    prompts,
    reporting,
    revision,
    routing,
    schemas,
    taxonomy,
)

RESPONSE = pydantic.TypeAdapter(models.ModelEvidence)


def _versions(
    client: llm.ChatClient,
    accepted: taxonomy.AcceptedArtifacts,
    rules_version: str,
) -> models.Versions:
    """Keep normal, skipped/error and manifest policy identifiers consistent."""
    return models.Versions(
        "convosignal",
        client.model_identifier,
        prompts.for_rules(rules_version)[0],
        accepted.taxonomy_checksum,
        rules="3" if rules_version == "3" else "2",
        schema="2" if rules_version == "3" else "1",
    )


def extract_json(text: str) -> dict[str, Any]:
    """Find one complete evidence object in plain, fenced or prose output."""
    candidates = []
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "goals" in value:
            candidates.append(value)
    if len(candidates) != 1:
        raise ValueError("Expected one complete evidence object with goals")
    return candidates[0]


def validate_targets(
    goals: Sequence[models.Goal],
    conversation: conversations.Conversation,
    rows: Sequence[routing.RoutedQuestion],
    accepted: taxonomy.AcceptedArtifacts,
) -> tuple[models.Goal, ...]:
    """Validate goal origins and normalize source completeness consistently.

    Args:
        goals: Versioned goal evidence extracted from the captured source.
        conversation: Authoritative source with completeness diagnostics.
        rows: Routing decisions for that conversation's captured user turns.
        accepted: Explicitly accepted classification and filtering policy.

    Returns:
        Goals with source completeness normalized for their policy version.

    Raises:
        ValueError: Context or excluded turns open an evaluation requirement.
    """
    targets = {
        row.turn_id for row in rows if row.routing_decision == "evaluate"
    }
    revised = []
    for goal in goals:
        if (
            isinstance(goal, revision.Goal)
            and not conversation.context_complete
            and goal.context_complete
            and not goal.context_evidence_turn_ids
        ):
            raise ValueError(
                "Incomplete source needs cited goal-relevant context"
            )
        included = {item.name for item in accepted.taxonomy.types} - set(
            accepted.filter_policy.excluded_type_ids
        )
        if goal.category not in {None, "unclassified", *included}:
            raise ValueError("Goal category must be included or unclassified")
        if not any(r.source_turn_id in targets for r in goal.requirements):
            raise ValueError(
                "Goal must originate from a retained evaluation target"
            )
        if any(r.source_turn_id not in targets for r in goal.requirements):
            raise ValueError("Excluded context cannot open a requirement")
        revised.append(
            dataclasses.replace(
                goal,
                context_complete=goal.context_complete
                and (
                    isinstance(goal, revision.Goal)
                    or conversation.context_complete
                ),
            )
        )
    return tuple(revised)


def evaluate_one(
    conversation: conversations.Conversation,
    rows: Sequence[routing.RoutedQuestion],
    accepted: taxonomy.AcceptedArtifacts,
    client: llm.ChatClient,
    *,
    max_input_chars: int = 200_000,
    rules_version: str = "2",
) -> tuple[models.Evaluation, dict[str, Any]]:
    """Extract evidence with one repair attempt and preserve diagnostics."""
    if rules_version not in {"2", "3"}:
        raise ValueError(f"Unsupported rule version: {rules_version}")
    response_adapter = (
        revision.MODEL_EVIDENCE if rules_version == "3" else RESPONSE
    )
    _, prompt_text = prompts.for_rules(rules_version)
    versions = _versions(client, accepted, rules_version)
    request = {
        "conversation_id": conversation.conversation_id,
        "conversation": conversations.conversation_data((conversation,))[0],
        "routing": [row.model_dump(mode="json") for row in rows],
        "taxonomy": accepted.taxonomy.model_dump(mode="json"),
        "schema": response_adapter.json_schema(),
    }
    attempts: list[dict[str, Any]] = []
    completed: models.Evaluation | None = None
    validated_record: dict[str, Any] | None = None
    user = json.dumps(request, ensure_ascii=False)
    if len(user) > max_input_chars:
        error = "Input exceeds configured character budget; no turns dropped"
    else:
        error = "Evidence extraction failed"
        for attempt in range(2):
            if len(user) > max_input_chars:
                error = "Repair request exceeds character budget"
                break
            try:
                raw = client.complete(prompt_text, user)
            except Exception as exc:  # Provider boundary; never score failures.
                error = f"Model call failed ({type(exc).__name__})"
                attempts.append({"error": error})
                break
            attempts.append({"raw_response": raw})
            try:
                parsed = response_adapter.validate_python(extract_json(raw))
                if rules_version == "3" and not parsed.goals:
                    raise ValueError(
                        "Eligible conversation requires goal evidence"
                    )
                target_errors = []
                invalid_targets = set()
                goals: list[models.Goal] = []
                for goal in parsed.goals:
                    try:
                        checked = validate_targets(
                            (goal,),
                            conversation,
                            rows,
                            accepted,
                        )
                        goals.extend(checked)
                    except ValueError as target_error:
                        invalid_targets.add(goal.goal_id)
                        target_errors.append(str(target_error))
                        goals.append(goal)
                record = schemas.parse_evidence(
                    json.dumps(
                        {
                            "conversation_id": conversation.conversation_id,
                            "turns": [
                                dataclasses.asdict(t)
                                for t in conversation.turns
                            ],
                            "goals": [dataclasses.asdict(g) for g in goals],
                            "versions": dataclasses.asdict(versions),
                            "overall_feedback": [
                                dataclasses.asdict(f)
                                for f in parsed.overall_feedback
                            ],
                        }
                    )
                )
                validated_record = schemas.evidence_data(record)
                completed = schemas.evaluate_record(record)
                if target_errors:
                    completed = dataclasses.replace(
                        completed,
                        status="error",
                        label=None,
                        reason="evaluation_error",
                        goals=tuple(
                            (key, value)
                            for key, value in completed.goals
                            if key not in invalid_targets
                        ),
                        errors=(*completed.errors, *target_errors),
                    )
                if completed.status == "error":
                    raise ValueError("; ".join(completed.errors))
                return completed, {
                    "evidence": schemas.evidence_data(record),
                    "attempts": attempts,
                }
            except (ValueError, KeyError) as exc:
                error = "Invalid or unsupported model evidence"
                # No raw user data or validation input is echoed to logs.
                if isinstance(exc, pydantic.ValidationError):
                    diagnostic = "; ".join(
                        f"{item['loc']}: {item['type']}"
                        for item in exc.errors(
                            include_input=False, include_context=False
                        )
                    )
                else:
                    diagnostic = str(exc)
                request["validation_error"] = diagnostic[:2000]
                request["previous_response"] = raw
                user = json.dumps(request, ensure_ascii=False)
                if attempt == 0:
                    continue
    failed = models.Evaluation(
        "error",
        None,
        "evaluation_error",
        completed.goals if completed else (),
        (error,),
        conversation.conversation_id,
        versions,
        tuple(t.turn_id for t in conversation.turns),
    )
    return failed, {
        "attempts": attempts,
        "errors": [error],
        "evidence": validated_record,
    }


def evaluate(
    source: Sequence[conversations.Conversation],
    accepted: taxonomy.AcceptedArtifacts,
    client: llm.ChatClient,
    output_dir: pathlib.Path,
    *,
    overwrite: bool = False,
    cached_routing: routing.RoutingSnapshot | None = None,
    source_errors: dict[str, str] | None = None,
    source_metadata: dict[str, Any] | None = None,
    max_input_chars: int = 200_000,
    rules_version: str = "2",
) -> dict[str, Any]:
    """Run both stages automatically and persist local artifacts."""
    if rules_version not in {"2", "3"}:
        raise ValueError(f"Unsupported rule version: {rules_version}")
    versions = _versions(client, accepted, rules_version)
    if not source or (
        not conversations.extract_questions(source) and not source_errors
    ):
        raise ValueError("No user questions to evaluate")
    if cached_routing is not None:
        routing.validate_snapshot(cached_routing, source, accepted)
    output_dir.mkdir(parents=True, exist_ok=True)
    extra_names = ("evaluations.jsonl", "manifest.json")
    if not overwrite and any(
        (output_dir / name).exists() for name in extra_names
    ):
        raise FileExistsError("Evaluation output exists; request overwrite")
    snapshot = routing.write_classification(
        output_dir,
        source,
        accepted,
        overwrite=overwrite,
    )
    results = []
    records = []
    for conversation in source:
        rows = tuple(
            row
            for row in snapshot.questions
            if row.conversation_id == conversation.conversation_id
        )
        details: dict[str, Any]
        if conversation.conversation_id in (source_errors or {}):
            result = models.Evaluation(
                "error",
                None,
                "evaluation_error",
                (),
                ((source_errors or {})[conversation.conversation_id],),
                conversation.conversation_id,
            )
            details = {"attempts": [], "source_error": True}
        elif (
            conversation.conversation_id
            not in snapshot.eligible_conversation_ids
        ):
            result = models.Evaluation(
                "skipped",
                None,
                "excluded_only" if rows else "no_eligible_goal",
                (),
                conversation_id=conversation.conversation_id,
            )
            details = {"attempts": []}
        else:
            result, details = evaluate_one(
                conversation,
                rows,
                accepted,
                client,
                max_input_chars=max_input_chars,
                rules_version=rules_version,
            )
        if result.versions is None:
            result = dataclasses.replace(
                result,
                versions=versions,
                source_turn_ids=tuple(t.turn_id for t in conversation.turns),
            )
        results.append(result)
        records.append(
            {
                **schemas.EVALUATION.dump_python(result, mode="json"),
                "evaluation_status": result.status,
                "evidence_details": details,
                "input_checksum": snapshot.input_checksum,
                "taxonomy_checksum": snapshot.taxonomy_checksum,
                "filter_policy_checksum": snapshot.filter_policy_checksum,
            }
        )
    report = routing.summary(snapshot, accepted)
    report["outcomes"] = reporting.outcome_report(results)
    report["source"] = source_metadata or {}
    categories: dict[str, list[models.Evaluation]] = {}
    for result, record in zip(results, records, strict=True):
        # Use validated evidence categories, never excluded turn categories.
        evidence_record = record["evidence_details"].get("evidence") or {}
        names = sorted(
            {
                g.get("category") or "unclassified"
                for g in evidence_record.get("goals", [])
            }
        )
        key = (
            names[0]
            if len(names) == 1
            else "multi_category"
            if names
            else "unclassified"
        )
        if result.status == "evaluated":
            categories.setdefault(key, []).append(result)
    report["outcomes_by_retained_category"] = {
        key: reporting.outcome_report(values)
        for key, values in categories.items()
    }
    with (output_dir / "evaluations.jsonl").open(
        "w", encoding="utf-8"
    ) as stream:
        for record in records:
            saved = schemas.EVALUATION_RECORD.validate_python(record)
            stream.write(
                schemas.EVALUATION_RECORD.dump_json(saved).decode() + "\n"
            )
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    manifest = {
        "validation_version": "2"
        if rules_version == "3"
        else evidence.VALIDATION_VERSION,
        "schema_version": versions.schema,
        "rules_version": versions.rules,
        "prompt_version": versions.prompt,
        "model": client.model_identifier,
        "input_checksum": snapshot.input_checksum,
        "taxonomy_checksum": snapshot.taxonomy_checksum,
        "filter_policy_checksum": snapshot.filter_policy_checksum,
        "offline": isinstance(client, llm.FakeLLM),
        "source": source_metadata or {},
        "model_diagnostics": getattr(client, "diagnostics", []),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    return report
