"""Portable run artifacts, safe publication and source-bound offline replay."""

import contextlib
import dataclasses
import hashlib
import json
import pathlib
import shutil
import tempfile
from collections.abc import Iterator, Sequence
from typing import Any

from convosignal import (
    conversations,
    models,
    pipeline,
    reporting,
    routing,
    schemas,
    taxonomy,
)


@dataclasses.dataclass(frozen=True)
class SavedRun:
    """Validated source, policy and predictions from one frozen run."""

    source: tuple[conversations.Conversation, ...]
    records: tuple[models.EvaluationRecord, ...]
    accepted: taxonomy.AcceptedArtifacts
    replayed: int


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    """Read physical JSONL lines without splitting Unicode source characters.

    Args:
        path: UTF-8 JSONL containing one object per physical line.

    Returns:
        Parsed objects in file order.

    Raises:
        ValueError: A line is blank, malformed or not a JSON object. Source
            content is deliberately excluded from the diagnostic.
    """
    rows = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                value = json.loads(line)
            except ValueError:
                raise ValueError(
                    f"Invalid JSONL record at line {number}"
                ) from None
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSON object at line {number}")
            rows.append(value)
    return rows


def write_json(path: pathlib.Path, value: Any) -> None:
    """Write a new UTF-8 artifact, failing rather than replacing an old file."""
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def write_records(
    path: pathlib.Path, records: Sequence[models.EvaluationRecord]
) -> None:
    """Write validated predictions as physical UTF-8 JSONL records."""
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(schemas.EVALUATION_RECORD.dump_json(record).decode())
            stream.write("\n")


@contextlib.contextmanager
def publish_directory(destination: pathlib.Path) -> Iterator[pathlib.Path]:
    """Stage outputs and atomically expose a complete, new directory.

    Args:
        destination: New output directory; an existing path is never replaced.

    Yields:
        Private staging directory on the same filesystem.

    Raises:
        FileExistsError: The destination already exists.
    """
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Output path already exists; choose a new path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = pathlib.Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent)
    )
    try:
        yield temporary
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("Output path was created by another writer")
        temporary.rename(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def file_hashes(directory: pathlib.Path) -> dict[str, str]:
    """Return stable relative names and SHA-256 values for report outputs."""
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def load(directory: pathlib.Path) -> SavedRun:
    """Validate and replay a saved run without calling a model or data source.

    Args:
        directory: Contains conversations.jsonl, evaluations.jsonl,
            taxonomy.json and filter_policy.json.

    Returns:
        Source-bound run with every evaluated verdict reproduced.

    Raises:
        ValueError: Coverage, source, policy, versions or replay differ.
    """
    source = conversations.load_conversations(directory / "conversations.jsonl")
    accepted = taxonomy.load_accepted(
        directory / "taxonomy.json", directory / "filter_policy.json"
    )
    records = tuple(
        schemas.EVALUATION_RECORD.validate_python(row)
        for row in read_jsonl(directory / "evaluations.jsonl")
    )
    source_by_id = {item.conversation_id: item for item in source}
    if not source or len(records) != len(source):
        raise ValueError("Saved source and prediction coverage differ")
    whole_hash = taxonomy.checksum(conversations.conversation_data(source))
    snapshot = routing.route(source, accepted)
    seen = set()
    replayed = 0
    for row in records:
        if (
            row.conversation_id in seen
            or row.conversation_id not in source_by_id
        ):
            raise ValueError("Duplicate or unknown prediction conversation")
        seen.add(row.conversation_id)
        conversation = source_by_id[row.conversation_id]
        single_hash = taxonomy.checksum(
            conversations.conversation_data((conversation,))
        )
        if row.input_checksum not in {single_hash, whole_hash}:
            raise ValueError("Prediction input checksum differs from source")
        if (
            row.taxonomy_checksum != accepted.taxonomy_checksum
            or row.filter_policy_checksum != accepted.filter_policy_checksum
            or row.versions is None
            or row.versions.taxonomy_checksum != accepted.taxonomy_checksum
        ):
            raise ValueError("Prediction policy or version provenance differs")
        if row.source_turn_ids != tuple(t.turn_id for t in conversation.turns):
            raise ValueError("Prediction source turn references differ")
        evidence = row.evidence_details.get("evidence")
        if evidence is not None:
            record = schemas.parse_evidence(json.dumps(evidence))
            if (
                record.conversation_id != conversation.conversation_id
                or record.turns != conversation.turns
                or record.versions != row.versions
            ):
                raise ValueError("Saved evidence replaced source or versions")
        if row.status == "evaluated" or (
            row.status == "skipped" and evidence is not None
        ):
            if evidence is None:
                raise ValueError("Completed verdict has no saved evidence")
            record = schemas.parse_evidence(json.dumps(evidence))
            if (
                record.versions.rules == "3"
                and not record.goals
                and row.conversation_id in snapshot.eligible_conversation_ids
            ):
                raise ValueError(
                    "Eligible version 3 verdict has no goal evidence"
                )
            routed = tuple(
                r
                for r in snapshot.questions
                if r.conversation_id == row.conversation_id
            )
            checked_goals = pipeline.validate_targets(
                record.goals, conversation, routed, accepted
            )
            if checked_goals != record.goals:
                raise ValueError("Evidence completeness disagrees with source")
            computed = schemas.EVALUATION.dump_python(
                schemas.evaluate_record(record), mode="json"
            )
            original = schemas.EVALUATION_RECORD.dump_python(row, mode="json")
            for field in ("status", "label", "reason", "goals", "errors"):
                if computed[field] != original[field]:
                    raise ValueError(
                        "Saved verdict does not replay identically"
                    )
            replayed += row.status == "evaluated"
        elif row.status == "skipped":
            eligible = row.conversation_id in snapshot.eligible_conversation_ids
            if eligible or row.reason not in {
                "excluded_only",
                "no_eligible_goal",
            }:
                raise ValueError("Skipped prediction disagrees with routing")
    return SavedRun(source, records, accepted, replayed)


def replay(directory: pathlib.Path, output_dir: pathlib.Path) -> dict[str, Any]:
    """Reproduce saved labels offline and publish an independently audited copy.

    Args:
        directory: Complete saved run directory.
        output_dir: New destination for the replay and verification manifest.

    Returns:
        Counts and replay verification; no user text is returned to the console.
    """
    run = load(directory)
    result = reporting.outcome_report(run.records)
    with publish_directory(output_dir) as staging:
        for name in (
            "conversations.jsonl",
            "taxonomy.json",
            "filter_policy.json",
        ):
            shutil.copyfile(directory / name, staging / name)
        for name in (
            "selection.json",
            "source_errors.json",
            "acquisition.json",
        ):
            if (directory / name).is_file():
                shutil.copyfile(directory / name, staging / name)
        write_records(staging / "evaluations.jsonl", run.records)
        write_json(staging / "summary.json", {"outcomes": result})
        write_json(
            staging / "replay.json",
            {
                "replayed_conversations": run.replayed,
                "differences": 0,
                "model_calls": 0,
                "source_fetches": 0,
                "sha256": file_hashes(staging),
                "independent_human_validation": "pending",
            },
        )
    return {"outcomes": result, "replayed_conversations": run.replayed}
