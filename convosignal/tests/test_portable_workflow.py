"""Portable saved-run replay, checkpoint integrity and report round trips."""

import csv
import dataclasses
import datetime
import json
import pathlib
import re
import threading
import types
import xml.etree.ElementTree as element_tree
import zipfile

import pydantic
import pytest

from convosignal import (
    audit_report,
    cli,
    config,
    conversations,
    demo,
    llm,
    models,
    pipeline,
    report_exports,
    run_artifacts,
    taxonomy,
    word_reports,
    workflow,
)


@pytest.fixture
def saved_demo(tmp_path):
    directory = tmp_path / "run"
    demo.run(directory)
    return directory


@pytest.fixture
def metadata():
    return audit_report.ReportMetadata(
        agent_name="Synthetic agent",
        stage="test",
        stage_basis="Fixture",
        report_date=datetime.date(2026, 1, 2),
    )


def test_replay_preserves_every_status_without_network(saved_demo, tmp_path):
    result = run_artifacts.replay(saved_demo, tmp_path / "replayed")
    original = run_artifacts.load(saved_demo)
    replayed = run_artifacts.load(tmp_path / "replayed")
    assert original.records == replayed.records
    assert result["replayed_conversations"] == 6
    assert result["outcomes"]["error_conversations"] == 1
    assert (
        json.loads((tmp_path / "replayed/replay.json").read_text())[
            "model_calls"
        ]
        == 0
    )


def test_jsonl_preserves_unicode_line_separators(tmp_path):
    path = tmp_path / "records.jsonl"
    row = {"text": "first\u2028second\u2029third\nline"}
    path.write_text(
        json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    assert run_artifacts.read_jsonl(path) == [row]


def test_jsonl_errors_do_not_echo_source(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"sensitive": "secret"\n', encoding="utf-8")
    with pytest.raises(
        ValueError, match="Invalid JSONL record at line 1"
    ) as error:
        run_artifacts.read_jsonl(path)
    assert "secret" not in str(error.value)


def test_changed_label_fails_replay(saved_demo):
    path = saved_demo / "evaluations.jsonl"
    rows = run_artifacts.read_jsonl(path)
    row = next(item for item in rows if item["label"] == "Satisfied")
    row["label"] = "Dissatisfied"
    path.write_text("".join(json.dumps(item) + "\n" for item in rows))
    with pytest.raises(ValueError, match="does not replay"):
        run_artifacts.load(saved_demo)


def test_changed_source_fails_before_replay(saved_demo):
    path = saved_demo / "conversations.jsonl"
    source = list(conversations.load_conversations(path))
    first = source[0]
    source[0] = dataclasses.replace(
        first,
        turns=(
            dataclasses.replace(first.turns[0], text="Changed request"),
            *first.turns[1:],
        ),
    )
    conversations.save_conversations(path, source, overwrite=True)
    with pytest.raises(ValueError, match="checksum"):
        run_artifacts.load(saved_demo)


def test_policy_and_duplicate_predictions_are_rejected(saved_demo):
    path = saved_demo / "evaluations.jsonl"
    rows = run_artifacts.read_jsonl(path)
    rows[-1] = rows[0]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="Duplicate"):
        run_artifacts.load(saved_demo)


def test_unknown_statistics_are_not_invented(saved_demo, metadata):
    report = audit_report.build(run_artifacts.load(saved_demo), metadata)
    assert report.date_range_utc is None
    assert report.distinct_attributed_users is None
    assert "Not captured" in str(audit_report.summary_sections(report))
    with pytest.raises(pydantic.ValidationError):
        audit_report.ReportMetadata.model_validate(
            {
                **metadata.model_dump(),
                "satisfied_count": 999,
            }
        )


def test_selected_headers_require_source_coverage(saved_demo, metadata):
    run = run_artifacts.load(saved_demo)
    selection = audit_report.Selection(
        traces=(
            audit_report.TraceHeader(
                trace_id="missing",
                session_id="missing",
                timestamp_ms=0,
            ),
        )
    )
    with pytest.raises(ValueError, match="unknown conversation"):
        audit_report.build(run, metadata, selection)


def test_report_exports_are_deterministic_and_navigable(
    saved_demo, metadata, tmp_path
):
    first = tmp_path / "first"
    second = tmp_path / "second"
    report_exports.write(saved_demo, metadata, first)
    report_exports.write(saved_demo, metadata, second)
    assert run_artifacts.file_hashes(first) == run_artifacts.file_hashes(second)
    data = audit_report.ReportData.model_validate_json(
        (first / "decision-data.json").read_text()
    )
    with zipfile.ZipFile(first / "Explore-Every-Sample.docx") as archive:
        document = element_tree.fromstring(archive.read("word/document.xml"))
        bookmarks = {
            n.get(word_reports.tag("name"))
            for n in document.iter(word_reports.tag("bookmarkStart"))
        }
        anchors = {
            n.get(word_reports.tag("anchor"))
            for n in document.iter(word_reports.tag("hyperlink"))
            if n.get(word_reports.tag("anchor"))
        }
        assert anchors <= bookmarks
        assert all(f"Sample{s.number:04d}" in bookmarks for s in data.samples)
        content_types = element_tree.fromstring(
            archive.read("[Content_Types].xml")
        )
        assert all(
            n.tag.startswith("{" + word_reports.CONTENT_TYPES + "}")
            for n in content_types
        )
    summary = (first / "One-Page-Summary.html").read_text()
    assert "Satisfied (rules 2)" in summary
    assert len(re.findall(r"<li><a href=", summary)) == 3
    assert (
        json.loads((first / "manifest.json").read_text())[
            "replayed_conversations"
        ]
        == 6
    )


def test_source_is_safe_and_exact_in_html_word_and_csv(
    tmp_path, accepted, metadata
):
    text = "  =sensitive\n</script><img src=x onerror=alert(1)>\u2028tail\tend"
    conversation = conversations.Conversation(
        "unknown",
        (
            # Preserve source even when its fixture input is unknown.
            models.Turn("u", "user", text, trace_id="t"),
        ),
    )
    run = tmp_path / "run"
    taxonomy.save_accepted(
        tmp_path / "taxonomy.json", tmp_path / "policy.json", accepted
    )
    run.mkdir()
    taxonomy.save_accepted(
        run / "taxonomy.json", run / "filter_policy.json", accepted
    )
    pipeline.evaluate((conversation,), accepted, llm.FakeLLM({}), run)
    output = tmp_path / "report"
    report_exports.write(run, metadata, output)
    page = (output / "Explore-Every-Sample.html").read_text()
    embedded = re.search(
        r'<script id="dataset" type="application/json">(.*?)</script>',
        page,
        re.S,
    )
    assert embedded is not None
    assert (
        json.loads(embedded.group(1))["samples"][0]["messages"][0]["text"]
        == text
    )
    assert "</script><img src=x" not in page
    assert "connect-src 'none'" in page
    with zipfile.ZipFile(output / "Explore-Every-Sample.docx") as archive:
        root = element_tree.fromstring(archive.read("word/document.xml"))
        paragraphs = [_word_text(p) for p in root.iter(word_reports.tag("p"))]
        assert text in paragraphs
    with (output / "decisions.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        rows = list(csv.reader(stream))
    assert rows[1][5] == "'" + text


def _word_text(paragraph):
    values = {
        word_reports.tag("br"): "\n",
        word_reports.tag("cr"): "\r",
        word_reports.tag("tab"): "\t",
    }
    return "".join(
        (node.text or "")
        if node.tag == word_reports.tag("t")
        else values.get(node.tag, "")
        for node in paragraph.iter()
    )


def test_failed_export_never_publishes_partial_directory(
    saved_demo, metadata, tmp_path, monkeypatch
):
    destination = tmp_path / "report"

    def failure(*args, **kwargs):
        raise OSError("Simulated write failure")

    monkeypatch.setattr(word_reports, "write_explorer", failure)
    with pytest.raises(OSError, match="Simulated"):
        report_exports.write(saved_demo, metadata, destination)
    assert not destination.exists()
    destination.mkdir()
    marker = destination / "owner.txt"
    marker.write_text("keep")
    with pytest.raises(FileExistsError):
        report_exports.write(saved_demo, metadata, destination)
    assert marker.read_text() == "keep"


def test_batch_resume_keeps_errors_and_makes_no_repeat_calls(
    saved_demo, tmp_path
):
    run = run_artifacts.load(saved_demo)
    responses = json.loads(
        (
            pathlib.Path(demo.__file__).parent / "fixtures/demo_responses.json"
        ).read_text()
    )
    calls = []
    lock = threading.Lock()

    class Counted(llm.FakeLLM):
        def complete(self, system, user):
            with lock:
                calls.append(json.loads(user)["conversation_id"])
            return super().complete(system, user)

    def factory():
        return Counted(responses)

    destination = tmp_path / "batch"
    kwargs = {
        "model_identifier": llm.FakeLLM.model_identifier,
        "rules_version": "2",
        "workers": 2,
    }
    workflow.evaluate_batch(
        saved_demo / "conversations.jsonl",
        run.accepted,
        factory,
        destination,
        **kwargs,
    )
    completed_calls = len(calls)
    first = run_artifacts.load(destination / "completed")
    workflow.evaluate_batch(
        saved_demo / "conversations.jsonl",
        run.accepted,
        factory,
        destination,
        resume=True,
        **kwargs,
    )
    assert len(calls) == completed_calls
    assert (
        run_artifacts.load(destination / "completed").records == first.records
    )
    assert any(row.status == "error" for row in first.records)
    with pytest.raises(ValueError, match="contract changed"):
        workflow.evaluate_batch(
            saved_demo / "conversations.jsonl",
            run.accepted,
            factory,
            destination,
            resume=True,
            **{**kwargs, "max_input_chars": 300000},
        )
    assert not (destination / ".writer.lock").exists()
    checkpoint_file = destination / "cases/000001/summary.json"
    checkpoint_file.write_text(checkpoint_file.read_text() + "\n")
    with pytest.raises(ValueError, match="checkpoint integrity"):
        workflow.evaluate_batch(
            saved_demo / "conversations.jsonl",
            run.accepted,
            factory,
            destination,
            resume=True,
            **kwargs,
        )
    assert len(calls) == completed_calls


def test_batch_interruption_retains_attempt_and_can_resume(
    saved_demo, tmp_path
):
    original = run_artifacts.load(saved_demo)
    source = tmp_path / "one.jsonl"
    conversations.save_conversations(source, (original.source[0],))
    responses = json.loads(
        (
            pathlib.Path(demo.__file__).parent / "fixtures/demo_responses.json"
        ).read_text()
    )
    destination = tmp_path / "batch"

    class StopRun(BaseException):
        pass

    class Interrupted(llm.FakeLLM):
        def complete(self, system, user):
            raise StopRun()

    with pytest.raises(StopRun):
        workflow.evaluate_batch(
            source,
            original.accepted,
            lambda: Interrupted(responses),
            destination,
            model_identifier=llm.FakeLLM.model_identifier,
            rules_version="2",
            workers=1,
        )
    assert not (destination / ".writer.lock").exists()
    workflow.evaluate_batch(
        source,
        original.accepted,
        lambda: llm.FakeLLM(responses),
        destination,
        model_identifier=llm.FakeLLM.model_identifier,
        rules_version="2",
        workers=1,
        resume=True,
    )
    assert tuple((destination / "incomplete-attempts").iterdir())
    assert len(run_artifacts.load(destination / "completed").records) == 1


def test_cli_replay_and_report_from_arbitrary_working_directory(
    saved_demo, metadata, tmp_path, monkeypatch
):
    config_path = tmp_path / "metadata.json"
    config_path.write_text(metadata.model_dump_json())
    monkeypatch.chdir(tmp_path)
    # This replay contains one intentional original error; a successful audit
    # preserves that error and returns the documented nonzero coverage status.
    assert (
        cli.main(
            ["replay", "--run-dir", str(saved_demo), "--output-dir", "replayed"]
        )
        == 1
    )
    assert (
        cli.main(
            [
                "report",
                "--run-dir",
                "replayed",
                "--metadata",
                str(config_path),
                "--output-dir",
                "reports",
            ]
        )
        == 0
    )
    assert (tmp_path / "reports/One-Page-Summary.docx").is_file()


def test_source_acquisition_records_headers_and_failed_sessions(tmp_path):
    class Page(list):
        token = None

    headers = [
        types.SimpleNamespace(
            info=types.SimpleNamespace(
                trace_id=key,
                timestamp_ms=1000 + index,
                state="OK",
                trace_metadata={
                    "mlflow.trace.session": "session",
                    "mlflow.trace.user": "person@example.test",
                },
            )
        )
        for index, key in enumerate(("ok", "missing"))
    ]

    class Client:
        def search_traces(self, **kwargs):
            assert "trace.timestamp_ms <=" in kwargs["filter_string"]
            return Page(headers)

        def get_trace(self, trace_id, **kwargs):
            if trace_id == "missing":
                raise OSError("fixture artifact missing")
            return types.SimpleNamespace(
                data=types.SimpleNamespace(
                    spans=[
                        types.SimpleNamespace(
                            name="interaction",
                            span_id="root",
                            status="OK",
                            inputs={"query": "Compare weeks"},
                            outputs={"answer": "Captured answer"},
                        )
                    ]
                )
            )

    settings = config.Settings(
        tracking_uri="databricks://fixture",
        experiment_id="fixture",
        session_path="session_id",
        limit=2,
    )
    directory = tmp_path / "snapshot"
    result = workflow.acquire(settings, directory, client=Client())
    assert result == {"conversations": 1, "source_errors": 1}
    selected = audit_report.Selection.model_validate_json(
        (directory / "selection.json").read_text()
    )
    assert len(selected.traces) == 2
    assert json.loads(
        (directory / "source_errors.json").read_text()
    ).keys() == {"session"}
    assert not conversations.load_conversations(
        directory / "conversations.jsonl"
    )[0].context_complete


def test_capture_failure_retains_source_as_error_sample(
    tmp_path, accepted, metadata
):
    source = (conversations.Conversation("failed", (), context_complete=False),)
    directory = tmp_path / "run"
    directory.mkdir()
    taxonomy.save_accepted(
        directory / "taxonomy.json", directory / "filter_policy.json", accepted
    )
    pipeline.evaluate(
        source,
        accepted,
        llm.FakeLLM({}),
        directory,
        source_errors={"failed": "Artifact download failed (OSError)"},
    )
    selection = audit_report.Selection(
        traces=(
            audit_report.TraceHeader(
                trace_id="missing-trace",
                session_id="failed",
                timestamp_ms=1000,
                user=None,
            ),
        )
    )
    report = audit_report.build(
        run_artifacts.load(directory), metadata, selection
    )
    assert report.samples[0].label == "Error"
    assert report.samples[0].prompt_count == 0
    assert report.distinct_attributed_users == 0
    assert report.unattributed_traces == 1


def test_unicode_line_separator_is_preserved_by_compare_cli(
    saved_demo, tmp_path
):
    # A metadata field can contain JSON's legal Unicode line separator. The
    # comparison reader must not turn it into an extra JSONL record.
    rows = run_artifacts.read_jsonl(saved_demo / "evaluations.jsonl")
    rows[0]["evidence_details"]["note"] = "before\u2028after"
    predictions = tmp_path / "predictions.jsonl"
    predictions.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    assert (
        cli.main(
            [
                "compare-runs",
                "--baseline",
                str(predictions),
                "--predictions",
                str(predictions),
                "--baseline-source",
                str(saved_demo / "conversations.jsonl"),
                "--source",
                str(saved_demo / "conversations.jsonl"),
                "--output",
                str(tmp_path / "comparison.json"),
            ]
        )
        == 0
    )


def test_cli_batch_version3_resume_and_reports(saved_demo, metadata, tmp_path):
    config_path = tmp_path / "metadata.json"
    config_path.write_text(metadata.model_dump_json())
    arguments = [
        "batch-evaluate",
        "--input-jsonl",
        str(saved_demo / "conversations.jsonl"),
        "--taxonomy",
        str(saved_demo / "taxonomy.json"),
        "--filter-policy",
        str(saved_demo / "filter_policy.json"),
        "--fake-responses",
        str(
            pathlib.Path(demo.__file__).parent / "fixtures/demo_responses.json"
        ),
        "--rules-version",
        "3",
        "--output-dir",
        str(tmp_path / "batch"),
    ]
    assert (
        cli.main(arguments) == 1
    )  # Intentionally invalid demo inputs remain errors.
    original = run_artifacts.load(tmp_path / "batch/completed")
    assert {row.versions.rules for row in original.records} == {"3"}
    assert cli.main([*arguments, "--resume"]) == 1
    assert (
        cli.main(
            [
                "report",
                "--run-dir",
                str(tmp_path / "batch/completed"),
                "--metadata",
                str(config_path),
                "--output-dir",
                str(tmp_path / "report"),
            ]
        )
        == 0
    )
    assert (
        run_artifacts.load(tmp_path / "batch/completed").records
        == original.records
    )


def test_replay_preserves_captured_header_metadata(saved_demo, tmp_path):
    selection = {"traces": [], "note": "Frozen captured metadata"}
    (saved_demo / "selection.json").write_text(json.dumps(selection))
    output = tmp_path / "replayed"
    run_artifacts.replay(saved_demo, output)
    assert (output / "selection.json").read_bytes() == (
        saved_demo / "selection.json"
    ).read_bytes()
