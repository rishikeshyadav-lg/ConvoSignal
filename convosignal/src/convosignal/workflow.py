"""Explicit snapshot acquisition and resumable conversation evaluation."""

import concurrent.futures
import datetime
import hashlib
import importlib.metadata
import json
import logging
import os
import pathlib
import shutil
import sys
import threading
from collections.abc import Callable
from typing import Any

from convosignal import (
    config,
    conversations,
    llm,
    models,
    pipeline,
    prompts,
    reporting,
    run_artifacts,
    taxonomy,
    traces,
)


def acquire(
    settings: config.Settings, output_dir: pathlib.Path, *, client: Any = None
) -> dict[str, Any]:
    """Freeze bounded MLflow input before making any evaluation calls.

    Args:
        settings: Connection, source paths, time window and read bounds.
        output_dir: New private snapshot directory.
        client: Optional MLflow-compatible client for offline verification.

    Returns:
        Source counts and failure counts without source text or identities.
    """
    cutoff_ms = int(datetime.datetime.now(datetime.UTC).timestamp() * 1000)
    end_time = (
        min(settings.end_time_ms, cutoff_ms)
        if settings.end_time_ms is not None
        else cutoff_ms
    )
    bounded = settings.model_copy(update={"end_time_ms": end_time})
    captured = traces.read(bounded, client=client)
    source = list(captured.batch.conversations)
    ids = {item.conversation_id for item in source}
    errors = {}
    origins = {
        header["trace_id"]: header["session_id"]
        for header in captured.metadata.get("traces", [])
    }
    origins.update(captured.metadata.get("failure_conversations", {}))
    for index, (trace_id, reason) in enumerate(captured.batch.failures):
        key = origins.get(trace_id, trace_id)
        if key == "<missing>":
            key = f"source-error-{index}"
        errors[key] = reason
        if key not in ids:
            source.append(
                conversations.Conversation(
                    key, (), context_complete=False, diagnostics=(reason,)
                )
            )
            ids.add(key)
    if not source:
        raise ValueError("Acquisition found no eligible source conversations")
    with run_artifacts.publish_directory(output_dir) as staging:
        conversations.save_conversations(
            staging / "conversations.jsonl", source
        )
        run_artifacts.write_json(staging / "source_errors.json", errors)
        run_artifacts.write_json(staging / "selection.json", captured.metadata)
        run_artifacts.write_json(
            staging / "acquisition.json",
            {
                "statistics": captured.batch.statistics,
                "source_errors": len(errors),
                "source_checksum": taxonomy.checksum(
                    conversations.conversation_data(source)
                ),
                "session_context": captured.metadata["session_context"],
            },
        )
    return {"conversations": len(source), "source_errors": len(errors)}


def evaluator_checksum() -> str:
    """Hash installed Python modules to reject incompatible checkpoint reuse."""
    directory = pathlib.Path(__file__).parent
    return taxonomy.checksum(
        {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.glob("*.py"))
        }
    )


def evaluate_batch(
    source_path: pathlib.Path,
    accepted: taxonomy.AcceptedArtifacts,
    client_factory: Callable[[], llm.ChatClient],
    output_dir: pathlib.Path,
    *,
    model_identifier: str,
    rules_version: str = "3",
    workers: int = 4,
    max_input_chars: int = 200000,
    model_parameters: dict[str, Any] | None = None,
    source_errors: dict[str, str] | None = None,
    resume: bool = False,
    selection_path: pathlib.Path | None = None,
) -> dict[str, Any]:
    """Evaluate immutable conversations with atomically published checkpoints.

    Args:
        source_path: Frozen normalized conversations, never fetched implicitly.
        accepted: Explicitly accepted taxonomy/filter policy.
        client_factory: Creates one independent model adapter per worker task.
        output_dir: Run directory; resume requires an exact matching contract.
        model_identifier: Expected adapter model ID, checked before each call.
        rules_version: Existing policy version 2 or 3.
        workers: Bounded number of concurrent tasks, from 1 through 32.
        max_input_chars: Hard input bound; oversized inputs are visible errors.
        model_parameters: Serving budgets/settings bound into resume identity.
        source_errors: Preserved acquisition failures by conversation ID.
        resume: Reuse completed checkpoints, including completed errors.
        selection_path: Optional captured headers copied into the final run.

    Returns:
        Reconciled final outcome counts. No source text is logged.

    Raises:
        ValueError: Resume identity or a completed checkpoint differs.
    """
    if rules_version not in {"2", "3"} or not 1 <= workers <= 32:
        raise ValueError("Unsupported rules version or worker count")
    if max_input_chars < 1000:
        raise ValueError("Input character budget must be at least 1000")
    source = conversations.load_conversations(source_path)
    if not source:
        raise ValueError("Batch source contains no conversations")
    errors = source_errors or {}
    if set(errors) - {c.conversation_id for c in source}:
        raise ValueError("Source error references an unknown conversation")
    contract = {
        "schema": "convosignal-batch-v1",
        "source_checksum": taxonomy.checksum(
            conversations.conversation_data(source)
        ),
        "taxonomy_checksum": accepted.taxonomy_checksum,
        "filter_policy_checksum": accepted.filter_policy_checksum,
        "rules_version": rules_version,
        "prompt_version": prompts.for_rules(rules_version)[0],
        "model_identifier": model_identifier,
        "max_input_chars": max_input_chars,
        "model_parameters": model_parameters or {},
        "source_errors": errors,
        "code_checksum": evaluator_checksum(),
        "runtime": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            **{
                name: importlib.metadata.version(name)
                for name in ("pydantic", "mlflow-skinny", "databricks-sdk")
            },
        },
        "selection_checksum": hashlib.sha256(
            selection_path.read_bytes()
        ).hexdigest()
        if selection_path is not None
        else None,
    }
    if not resume:
        output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    elif not output_dir.is_dir():
        raise ValueError("Resume requires an existing batch directory")
    lock = output_dir / ".writer.lock"
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(f"{os.getpid()}\n")
    try:
        return _run_batch(
            source,
            accepted,
            client_factory,
            output_dir,
            contract,
            rules_version,
            workers,
            max_input_chars,
            errors,
            resume,
            selection_path,
        )
    finally:
        lock.unlink()


def _run_batch(
    source: tuple[conversations.Conversation, ...],
    accepted: taxonomy.AcceptedArtifacts,
    client_factory: Callable[[], llm.ChatClient],
    output_dir: pathlib.Path,
    contract: dict[str, Any],
    rules_version: str,
    workers: int,
    max_input_chars: int,
    source_errors: dict[str, str],
    resume: bool,
    selection_path: pathlib.Path | None,
) -> dict[str, Any]:
    """Own the single-writer checkpoint lifecycle for an acquired run lock."""
    contract_path = output_dir / "batch.json"
    if resume:
        if json.loads(contract_path.read_text(encoding="utf-8")) != contract:
            raise ValueError(
                "Resume rejected: source or evaluation contract changed"
            )
        saved = conversations.load_conversations(
            output_dir / "conversations.jsonl"
        )
        policy = taxonomy.load_accepted(
            output_dir / "taxonomy.json", output_dir / "filter_policy.json"
        )
        selection_changed = False
        if selection_path is not None:
            stored = output_dir / "selection.json"
            selection_changed = (
                not stored.exists()
                or stored.read_bytes() != selection_path.read_bytes()
            )
        if saved != source or policy != accepted or selection_changed:
            raise ValueError("Resume rejected: frozen run inputs changed")
    else:
        conversations.save_conversations(
            output_dir / "conversations.jsonl", source
        )
        taxonomy.save_accepted(
            output_dir / "taxonomy.json",
            output_dir / "filter_policy.json",
            accepted,
        )
        if selection_path is not None:
            shutil.copyfile(selection_path, output_dir / "selection.json")
        run_artifacts.write_json(contract_path, contract)
    cases = output_dir / "cases"
    cases.mkdir(exist_ok=True)
    attempts = output_dir / "incomplete-attempts"
    attempts.mkdir(exist_ok=True)
    # Interrupted staging directories are evidence, not completed checkpoints.
    for path in sorted(cases.glob(".*-working")):
        archived = (
            attempts / f"{path.name}-{len(tuple(attempts.iterdir())):04d}"
        )
        path.rename(archived)

    worker_state = threading.local()

    def evaluate_case(index: int) -> None:
        conversation = source[index]
        destination = cases / f"{index + 1:06d}"
        if destination.exists():
            checkpoint = json.loads(
                (destination / "checkpoint.json").read_text(encoding="utf-8")
            )
            current_hashes = run_artifacts.file_hashes(destination)
            current_hashes.pop("checkpoint.json", None)
            if (
                checkpoint["contract_checksum"] != taxonomy.checksum(contract)
                or checkpoint["sha256"] != current_hashes
            ):
                raise ValueError(
                    "Resume rejected: checkpoint integrity differs"
                )
            saved = run_artifacts.load(destination)
            if saved.source != (conversation,) or any(
                r.versions is None
                or r.versions.model != contract["model_identifier"]
                or r.versions.rules != rules_version
                for r in saved.records
            ):
                raise ValueError(
                    "Resume checkpoint disagrees with batch contract"
                )
            return
        working = cases / f".{index + 1:06d}-working"
        working.mkdir(mode=0o700)
        client: llm.ChatClient | None = getattr(worker_state, "client", None)
        if client is None:
            client = client_factory()
            worker_state.client = client
        if client.model_identifier != contract["model_identifier"]:
            raise ValueError("Model adapter disagrees with batch contract")
        taxonomy.save_accepted(
            working / "taxonomy.json", working / "filter_policy.json", accepted
        )
        pipeline.evaluate(
            (conversation,),
            accepted,
            client,
            working,
            rules_version=rules_version,
            max_input_chars=max_input_chars,
            source_errors=source_errors,
            source_metadata={"case_index": index + 1, "source_fetches": 0},
        )
        run_artifacts.load(working)
        run_artifacts.write_json(
            working / "checkpoint.json",
            {
                "contract_checksum": taxonomy.checksum(contract),
                "sha256": run_artifacts.file_hashes(working),
            },
        )
        working.rename(destination)
        logging.getLogger(__name__).info(
            "Completed conversation checkpoint %d/%d", index + 1, len(source)
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(evaluate_case, range(len(source))))
    records: list[models.EvaluationRecord] = []
    for index in range(len(source)):
        records.extend(run_artifacts.load(cases / f"{index + 1:06d}").records)
    # Completed batch output is replaced as one directory, never half a file.
    completed = output_dir / "completed"
    if completed.exists():
        completed_run = run_artifacts.load(completed)
        saved_contract = json.loads(
            (completed / "manifest.json").read_text(encoding="utf-8")
        )
        if (
            tuple(records) != completed_run.records
            or saved_contract != contract
        ):
            raise ValueError("Completed batch changed during resume")
    else:
        with run_artifacts.publish_directory(completed) as staging:
            for name in (
                "conversations.jsonl",
                "taxonomy.json",
                "filter_policy.json",
            ):
                shutil.copyfile(output_dir / name, staging / name)
            if (output_dir / "selection.json").exists():
                shutil.copyfile(
                    output_dir / "selection.json", staging / "selection.json"
                )
            run_artifacts.write_records(staging / "evaluations.jsonl", records)
            run_artifacts.write_json(staging / "manifest.json", contract)
    return {"outcomes": reporting.outcome_report(records)}
