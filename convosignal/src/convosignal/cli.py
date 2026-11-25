"""Local CLI for review, safe classification and evidence-based evaluation."""

import argparse
import dataclasses
import json
import pathlib
import sys
from collections.abc import Sequence
from typing import Any

import pydantic

from convosignal import (
    audit_report,
    comparison,
    config,
    conversations,
    demo,
    llm,
    pipeline,
    prompts,
    report_exports,
    reporting,
    routing,
    run_artifacts,
    taxonomy,
    traces,
    workflow,
)


@dataclasses.dataclass(frozen=True)
class LoadedSource:
    """One source snapshot with failures and acquisition diagnostics."""

    conversations: tuple[conversations.Conversation, ...]
    errors: dict[str, str]
    metadata: dict[str, Any]


def _loaded(
    batch: conversations.ExtractionBatch,
    metadata: dict[str, Any],
    failure_conversations: dict[str, str] | None = None,
) -> LoadedSource:
    """Keep failed source records as operational errors, not silent skips."""
    source = list(batch.conversations)
    ids = {item.conversation_id for item in source}
    errors = {}
    for index, (trace_id, message) in enumerate(batch.failures):
        key = (failure_conversations or {}).get(trace_id, trace_id)
        if key == "<missing>":
            key = f"source-error-{index}"
        errors[key] = message
        if key not in ids:
            source.append(
                conversations.Conversation(
                    key,
                    (),
                    context_complete=False,
                    diagnostics=(message,),
                )
            )
            ids.add(key)
    return LoadedSource(
        tuple(source),
        errors,
        {
            **metadata,
            "extraction_statistics": batch.statistics,
        },
    )


def _source(args: argparse.Namespace) -> LoadedSource:
    """Load or fetch once; preserve operational failures in the run."""
    settings = config.load(args.config)
    if args.trace_json is not None:
        records = json.loads(args.trace_json.read_text())
        if not isinstance(records, list):
            raise ValueError("Trace JSON must contain a list")
        cfg = conversations.ExtractionConfig(
            shape=args.shape or "chat",
            messages_path=args.messages_path,
            question_path=args.question_path,
            answer_path=args.answer_path,
            session_path=args.session_path,
        )
        batch = conversations.extract_traces(
            records, cfg, require_questions=False
        )
        mapping = {}
        if args.session_path:
            for record in records:
                try:
                    mapping[record["trace_id"]] = conversations.read_path(
                        record, args.session_path
                    )
                except (ValueError, KeyError, TypeError):
                    continue
        return _loaded(batch, {"source": "offline_traces"}, mapping)
    if args.input_jsonl is not None:
        if args.input_kind == "questions":
            if args.command == "evaluate":
                raise ValueError(
                    "Question-only input cannot support satisfaction evaluation"
                )
            return LoadedSource(
                conversations.load_questions(args.input_jsonl),
                {},
                {"source": "question_snapshot"},
            )
        return LoadedSource(
            conversations.load_conversations(args.input_jsonl),
            {},
            {"source": "conversation_snapshot"},
        )
    if args.shape:
        settings = settings.model_copy(update={"shape": args.shape})
    fetched = traces.read(settings)
    return _loaded(
        fetched.batch,
        fetched.metadata,
        fetched.metadata.get("failure_conversations"),
    )


def _client(args: argparse.Namespace) -> llm.ChatClient:
    """Select explicit fixtures or a configured Databricks model endpoint."""
    if args.fake_responses is not None:
        return llm.FakeLLM(json.loads(args.fake_responses.read_text()))
    settings = config.load(args.config)
    if not settings.endpoint:
        return llm.UnconfiguredClient()
    return llm.DatabricksChat(settings)


def _accepted(args: argparse.Namespace) -> taxonomy.AcceptedArtifacts:
    """Require a separately accepted taxonomy and filtering policy."""
    return taxonomy.load_accepted(args.taxonomy, args.filter_policy)


def _batch(args: argparse.Namespace) -> dict[str, Any]:
    """Bind explicit serving settings and fixture identity to a batch run."""
    settings = config.load(args.config)
    parameters: dict[str, Any] = {
        "max_tokens": settings.max_tokens,
        "timeout_seconds": settings.timeout_seconds,
        "endpoint": settings.endpoint,
    }
    if args.fake_responses is not None:
        responses = json.loads(args.fake_responses.read_text(encoding="utf-8"))
        parameters["fixture_checksum"] = taxonomy.checksum(responses)
        model_identifier = llm.FakeLLM.model_identifier

        def factory() -> llm.ChatClient:
            return llm.FakeLLM(responses)
    else:
        first = llm.DatabricksChat(settings)
        model_identifier = first.model_identifier
        parameters["workspace_host"] = first.workspace.config.host

        def factory() -> llm.ChatClient:
            return llm.DatabricksChat(settings, workspace=first.workspace)

    errors = {}
    if args.source_errors is not None:
        errors = pydantic.TypeAdapter(dict[str, str]).validate_json(
            args.source_errors.read_text(encoding="utf-8"), strict=True
        )
    return workflow.evaluate_batch(
        args.input_jsonl,
        _accepted(args),
        factory,
        args.output_dir,
        model_identifier=model_identifier,
        rules_version=args.rules_version,
        workers=args.workers,
        max_input_chars=settings.max_input_chars,
        model_parameters=parameters,
        source_errors=errors,
        resume=args.resume,
        selection_path=args.selection,
    )


def parser() -> argparse.ArgumentParser:
    """Describe review and evaluation commands with explicit acceptance."""
    root = argparse.ArgumentParser(prog="convosignal", description=__doc__)
    root.add_argument("--config", type=pathlib.Path)
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("propose", "classify", "evaluate"):
        command = commands.add_parser(name)
        command.add_argument("--input-jsonl", type=pathlib.Path)
        command.add_argument(
            "--input-kind",
            choices=("conversations", "questions"),
            default="conversations",
        )
        command.add_argument("--trace-json", type=pathlib.Path)
        command.add_argument(
            "--shape", choices=("chat", "interaction"), default=None
        )
        command.add_argument("--messages-path", default="messages")
        command.add_argument("--question-path", default="query")
        command.add_argument("--answer-path", default="answer")
        command.add_argument("--session-path")
        command.add_argument("--overwrite", action="store_true")
        if name == "propose":
            command.add_argument("--response-json", type=pathlib.Path)
            command.add_argument("--fake-responses", type=pathlib.Path)
            command.add_argument("--sample-cap", type=int, default=120)
            command.add_argument("--output", type=pathlib.Path, required=True)
        else:
            command.add_argument("--taxonomy", type=pathlib.Path, required=True)
            command.add_argument(
                "--filter-policy", type=pathlib.Path, required=True
            )
            command.add_argument("--output-dir", type=pathlib.Path)
            if name == "evaluate":
                command.add_argument(
                    "--rules-version", choices=("2", "3"), default="2"
                )
                command.add_argument("--fake-responses", type=pathlib.Path)
                command.add_argument("--routing-snapshot", type=pathlib.Path)
    accept = commands.add_parser("accept")
    accept.add_argument("--input", type=pathlib.Path, required=True)
    accept.add_argument(
        "--output", type=pathlib.Path, default=pathlib.Path("taxonomy.json")
    )
    accept.add_argument("--filter-policy", type=pathlib.Path)
    accept.add_argument("--overwrite", action="store_true")
    example = commands.add_parser("demo")
    example.add_argument("--output-dir", type=pathlib.Path, required=True)
    example.add_argument("--overwrite", action="store_true")
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--llm", action="store_true")
    compare = commands.add_parser("compare")
    compare.add_argument("--predictions", type=pathlib.Path, required=True)
    compare.add_argument("--reviews", type=pathlib.Path, required=True)
    compare.add_argument(
        "--unit", choices=("conversation", "goal"), default="conversation"
    )
    compare.add_argument("--output", type=pathlib.Path, required=True)
    compare.add_argument("--overwrite", action="store_true")
    compare.add_argument("--review-context", type=pathlib.Path)
    compare.add_argument(
        "--review-sampling",
        choices=("unknown", "representative", "class_targeted"),
        default="unknown",
    )
    runs = commands.add_parser("compare-runs")
    runs.add_argument("--baseline", type=pathlib.Path, required=True)
    runs.add_argument("--predictions", type=pathlib.Path, required=True)
    runs.add_argument("--baseline-source", type=pathlib.Path, required=True)
    runs.add_argument("--source", type=pathlib.Path, required=True)
    runs.add_argument("--output", type=pathlib.Path, required=True)
    packet = commands.add_parser("review-packet")
    packet.add_argument("--predictions", type=pathlib.Path, required=True)
    packet.add_argument("--source", type=pathlib.Path, required=True)
    packet.add_argument("--output-dir", type=pathlib.Path, required=True)
    template = commands.add_parser("review-template")
    template.add_argument("--predictions", type=pathlib.Path, required=True)
    template.add_argument("--output", type=pathlib.Path, required=True)
    template.add_argument("--overwrite", action="store_true")
    acquire = commands.add_parser(
        "acquire", help="Freeze bounded MLflow source"
    )
    acquire.add_argument("--output-dir", type=pathlib.Path, required=True)
    batch = commands.add_parser(
        "batch-evaluate", help="Checkpoint frozen conversations"
    )
    batch.add_argument("--input-jsonl", type=pathlib.Path, required=True)
    batch.add_argument("--taxonomy", type=pathlib.Path, required=True)
    batch.add_argument("--filter-policy", type=pathlib.Path, required=True)
    batch.add_argument("--source-errors", type=pathlib.Path)
    batch.add_argument("--selection", type=pathlib.Path)
    batch.add_argument("--fake-responses", type=pathlib.Path)
    batch.add_argument("--output-dir", type=pathlib.Path, required=True)
    batch.add_argument("--rules-version", choices=("2", "3"), default="3")
    batch.add_argument("--workers", type=int, default=4)
    batch.add_argument("--resume", action="store_true")
    replay = commands.add_parser("replay", help="Audit saved evidence offline")
    replay.add_argument("--run-dir", type=pathlib.Path, required=True)
    replay.add_argument("--output-dir", type=pathlib.Path, required=True)
    report = commands.add_parser(
        "report", help="Export audited HTML/Word reports offline"
    )
    report.add_argument("--run-dir", type=pathlib.Path, required=True)
    report.add_argument("--metadata", type=pathlib.Path, required=True)
    report.add_argument("--selection", type=pathlib.Path)
    report.add_argument("--output-dir", type=pathlib.Path, required=True)
    report.add_argument(
        "--formats",
        nargs="+",
        choices=("html", "docx"),
        default=("html", "docx"),
    )
    return root


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    """Execute a command and report aggregate information only."""
    if args.command == "acquire":
        return workflow.acquire(config.load(args.config), args.output_dir)
    if args.command == "replay":
        return run_artifacts.replay(args.run_dir, args.output_dir)
    if args.command == "report":
        metadata = audit_report.ReportMetadata.model_validate_json(
            args.metadata.read_text(encoding="utf-8")
        )
        return report_exports.write(
            args.run_dir,
            metadata,
            args.output_dir,
            selection_path=args.selection,
            formats=args.formats,
        )
    if args.command == "batch-evaluate":
        return _batch(args)
    if args.command in {"compare-runs", "review-packet"}:
        predictions = run_artifacts.read_jsonl(args.predictions)
        source = conversations.load_conversations(args.source)
        if args.command == "review-packet":
            return comparison.write_review_packet(
                predictions, source, args.output_dir
            )
        baseline = run_artifacts.read_jsonl(args.baseline)
        report = comparison.compare_runs(
            baseline,
            predictions,
            conversations.load_conversations(args.baseline_source),
            source,
        )
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2) + "\n")
        return {
            key: report[key]
            for key in (
                "input_conversations",
                "transitions",
                "replay_audit",
                "independent_validation",
            )
        }
    if args.command in {"compare", "review-template"}:
        predictions = run_artifacts.read_jsonl(args.predictions)
        mode = "w" if args.overwrite else "x"
        if args.command == "review-template":
            with args.output.open(mode, encoding="utf-8") as stream:
                for row in predictions:
                    stream.write(
                        json.dumps(
                            {
                                "conversation_id": row["conversation_id"],
                                "input_checksum": row["input_checksum"],
                                "reviewer": "",
                                "label": None,
                                "annotation_source": "human",
                                "reason": "",
                            }
                        )
                        + "\n"
                    )
            return {"status": "review_template", "records": len(predictions)}
        reviews = run_artifacts.read_jsonl(args.reviews)
        report = reporting.compare(
            predictions,
            reviews,
            unit=args.unit,
            sampling=args.review_sampling,
            validation_context=json.loads(args.review_context.read_text())
            if args.review_context
            else None,
        )
        with args.output.open(mode, encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2) + "\n")
        return report
    if args.command == "demo":
        return demo.run(args.output_dir, overwrite=args.overwrite)
    if args.command == "doctor":
        from convosignal import diagnostics

        return diagnostics.doctor(config.load(args.config), probe_llm=args.llm)
    if args.command == "accept":
        proposal = taxonomy.Proposal.model_validate_json(args.input.read_text())
        accepted = taxonomy.accept(proposal)
        policy_path = args.filter_policy or args.output.with_name(
            "filter_policy.json"
        )
        taxonomy.save_accepted(
            args.output, policy_path, accepted, overwrite=args.overwrite
        )
        return {
            "status": "accepted",
            "taxonomy_checksum": accepted.taxonomy_checksum,
            "filter_policy_checksum": accepted.filter_policy_checksum,
        }
    if args.command in {"classify", "evaluate"} and args.output_dir is None:
        args.output_dir = config.load(args.config).output_dir
    loaded = _source(args)
    source = loaded.conversations
    if (
        args.command in {"propose", "evaluate"}
        and not loaded.errors
        and not conversations.extract_questions(source)
    ):
        raise ValueError(
            "No user questions; check extraction paths and traffic filters. "
            f"Counts: {loaded.metadata.get('extraction_statistics', {})}"
        )
    if args.command == "propose":
        if loaded.errors:
            raise ValueError("Resolve extraction failures before proposal")
        if loaded.errors:
            raise ValueError(
                "Resolve source extraction failures before proposal"
            )
        questions = [
            q.question for q in conversations.extract_questions(source)
        ]
        if args.response_json is not None:
            content = args.response_json.read_text()
            model_identifier = "supplied-response"
        else:
            client = _client(args)

            sample = taxonomy.sample_questions(questions, args.sample_cap)
            content = client.complete(
                prompts.TAXONOMY,
                json.dumps(
                    {
                        "questions": sample.questions,
                    }
                ),
            )
            model_identifier = client.model_identifier
        proposal = taxonomy.propose(
            content,
            questions,
            model_identifier=model_identifier,
            cap=args.sample_cap,
        )
        taxonomy.save_json(args.output, proposal, overwrite=args.overwrite)
        return {
            "status": "proposal",
            "sample_size": proposal.sample.sample_size,
            "warning_count": len(proposal.warnings),
        }
    accepted = _accepted(args)
    if args.command == "classify":
        snapshot = routing.write_classification(
            args.output_dir, source, accepted, overwrite=args.overwrite
        )
        report = routing.summary(snapshot, accepted)
        report["source_errors"] = loaded.errors
        report["source"] = loaded.metadata
        (args.output_dir / "summary.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        return report
    cached = None
    if args.routing_snapshot:
        cached = routing.RoutingSnapshot.model_validate_json(
            args.routing_snapshot.read_text()
        )
    return pipeline.evaluate(
        source,
        accepted,
        _client(args),
        args.output_dir,
        overwrite=args.overwrite,
        cached_routing=cached,
        source_errors=loaded.errors,
        source_metadata=loaded.metadata,
        max_input_chars=config.load(args.config).max_input_chars,
        rules_version=args.rules_version,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run a command with visible nonzero exits for invalid inputs/errors."""
    args = parser().parse_args(argv)
    try:
        report = dispatch(args)
    except pydantic.ValidationError:
        print(
            "Invalid artifact schema; inspect the documented JSON contract",
            file=sys.stderr,
        )
        return 2
    except (KeyError, TypeError):
        print(
            "Unsupported input shape; inspect the documented schema",
            file=sys.stderr,
        )
        return 2
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2
    except (
        Exception
    ) as error:  # CLI integration boundary; no sensitive payloads.
        print(
            f"Integration failed ({type(error).__name__}); run doctor",
            file=sys.stderr,
        )
        return 2
    # Full reports/examples can contain sensitive source text: persist them in
    # local artifacts; the terminal gets counts/status only.
    visible = report.get("outcomes", report)
    if "category_counts" in visible:
        visible = {
            "total_nonblank_questions": visible["total_nonblank_questions"],
            "category_counts": visible["category_counts"],
            "conversations": visible["conversations"],
            "source_error_count": len(report.get("source_errors", {})),
        }
    print(json.dumps(visible, indent=2))
    return (
        1
        if args.command != "demo"
        and (
            visible.get("error_conversations", 0)
            or report.get("source_errors")
            or report.get("status") == "error"
        )
        else 0
    )
