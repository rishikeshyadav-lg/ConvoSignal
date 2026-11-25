"""Offline HTML, CSV, JSON and Word exports from audited frozen run data."""

import csv
import hashlib
import html
import importlib.resources
import json
import pathlib
import re
from collections.abc import Sequence
from typing import Any, Literal

from convosignal import audit_report, run_artifacts, word_reports

REPORT_VERSION = "convosignal-exports-v1"


def _asset(name: str) -> str:
    """Read a packaged resource without depending on the checkout location."""
    return (
        importlib.resources.files("convosignal")
        .joinpath("assets", name)
        .read_text(encoding="utf-8")
    )


def _summary(data: audit_report.ReportData) -> str:
    """Render a compact printable summary with escaped owner-supplied text."""
    sections = []
    for title, paragraphs in audit_report.summary_sections(data):
        body = "".join(f"<p>{html.escape(text)}</p>" for text in paragraphs)
        sections.append(
            f'<section class="card"><h2>{html.escape(title)}</h2>'
            f"{body}</section>"
        )
    rows = "".join(
        f"<tr><td>{key}</td><td>{data.counts[key]}</td>"
        f"<td>{data.conversation_counts[key]}</td></tr>"
        for key in data.counts
    )
    references = "".join(
        f'<li><a href="{html.escape(url, quote=True)}">{html.escape(title)}</a>'
        f" — {html.escape(finding)}</li>"
        for title, url, finding in audit_report.RESEARCH
    )
    return "".join(
        (
            '<!doctype html><html lang="en"><head><meta charset="utf-8">',
            '<meta name="viewport" '
            'content="width=device-width,initial-scale=1">',
            '<meta http-equiv="Content-Security-Policy" '
            "content=\"default-src 'none'; style-src 'unsafe-inline'; "
            "img-src data:; base-uri 'none'; form-action 'none'\">",
            "<title>Agent Satisfaction Audit · ConvoSignal</title>",
            '<link rel="icon" href="data:image/svg+xml,%3Csvg '
            "xmlns='http://www.w3.org/2000/svg'%3E%3Ctext "
            "y='16'%3EC%3C/text%3E%3C/svg%3E\">",
            f"<style>{_asset('report.css')}</style></head>"
            '<body><main class="summary">',
            '<p class="eyebrow">ConvoSignal / Source-bound audit</p>',
            "<h1>Agent Satisfaction Audit</h1>",
            f"<p>{data.metadata.report_date.isoformat()} · Private · "
            "Independent human validation pending</p>",
            *sections,
            '<section class="card"><h2>Results [E3 · ran]</h2>',
            "<table><thead><tr><th>Decision</th><th>Selected trace "
            "rows</th><th>Distinct "
            "conversations</th></tr></thead><tbody>",
            rows,
            f"<tr><th>Total</th><th>{data.sample_count}</th>"
            f"<th>{data.conversation_count}</th></tr></tbody></table>",
            '<p class="small">Each trace row carries its containing '
            "conversation’s final decision; several rows can share "
            "one decision. These are not independent prompt ratings. "
            "Skips/errors have no satisfaction label.</p></section>",
            "<section><h2>Research behind the approach [source]</h2>",
            f'<ol class="small">{references}</ol>',
            '<p class="small">The studies motivate this approach; '
            "they do not validate this classifier.</p></section>",
            "<footer><b>Still open:</b> independent human review; "
            f"{data.conversation_counts['Error']} unclassified conversations. ",
            f"<b>Ran:</b> {data.replayed_conversations} classified "
            "conversations replayed identically. ",
            "E1: captured source/header metadata; E2: recorded "
            "rules/prompts; E3: saved verdicts and manifest.json. ",
            "This summary excludes captured prompt/answer text, "
            "identities and credentials. ",
            f"Source checksum: {data.source_checksum}.</footer>",
            '<p class="no-print"><a '
            'href="Explore-Every-Sample.html">Explore every sample '
            "→</a> · Use your browser’s Print / Save as PDF for a PDF"
            " copy.</p>",
            "</main></body></html>",
        )
    )


def _cell(value: object) -> str:
    """Keep source text literal when opened by spreadsheet applications."""
    text = str(value)
    if text.lstrip(" \t\r\n").startswith(
        ("=", "+", "-", "@")
    ) or text.startswith(("\t", "\r")):
        return f"'{text}"
    return text


def _csv(data: audit_report.ReportData, path: pathlib.Path) -> None:
    """Write selected source text with explicit conversation-level decisions."""
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, quoting=csv.QUOTE_ALL)
        writer.writerow(
            [
                "Sample",
                "Conversation",
                "Conversation decision",
                "Reason",
                "Prompt count",
                "User prompts",
                "Agent answers",
            ]
        )
        for sample in data.samples:
            writer.writerow(
                [
                    _cell(value)
                    for value in (
                        sample.id,
                        sample.conversation_number,
                        sample.label,
                        sample.reason,
                        sample.prompt_count,
                        "\n\n".join(
                            m.text for m in sample.messages if m.role == "user"
                        ),
                        "\n\n".join(
                            m.text
                            for m in sample.messages
                            if m.role == "assistant"
                        ),
                    )
                ]
            )


def write(
    run_dir: pathlib.Path,
    metadata: audit_report.ReportMetadata,
    output_dir: pathlib.Path,
    *,
    selection_path: pathlib.Path | None = None,
    formats: Sequence[Literal["html", "docx"]] = ("html", "docx"),
) -> dict[str, Any]:
    """Replay saved evidence and atomically publish portable report files.

    Args:
        run_dir: Source-bound run directory; contains no required local paths.
        metadata: Owner-supplied context with explicit report date.
        output_dir: New destination; existing files are never overwritten.
        selection_path: Optional captured source headers for date/user counts.
        formats: HTML and/or Word, with CSV/JSON/manifest always included.

    Returns:
        Aggregate coverage and outcome counts, without captured text.

    Raises:
        ValueError: Run provenance, selection, formats or source encoding fail.
    """
    if not formats or set(formats) - {"html", "docx"}:
        raise ValueError("Report formats must include html and/or docx")
    run = run_artifacts.load(run_dir)
    selection = None
    if selection_path is None and (run_dir / "selection.json").exists():
        selection_path = run_dir / "selection.json"
    if selection_path is not None:
        selection = audit_report.Selection.model_validate_json(
            selection_path.read_text(encoding="utf-8")
        )
    data = audit_report.build(run, metadata, selection)
    payload = data.model_dump(mode="json")
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if re.search(
        "\\bdapi[0-9a-f]{24,}\\b|\\bsk-[A-Za-z0-9_-]{24,}\\b|-----BEGIN "
        "[A-Z ]*PRIVATE KEY-----",
        serialized,
    ):
        raise ValueError(
            "Credential-like content detected; review source before export"
        )
    with run_artifacts.publish_directory(output_dir) as staging:
        run_artifacts.write_json(staging / "decision-data.json", payload)
        _csv(data, staging / "decisions.csv")
        if "html" in formats:
            escaped = (
                serialized.replace("<", "\\u003c")
                .replace("&", "\\u0026")
                .replace("\u2028", "\\u2028")
                .replace("\u2029", "\\u2029")
            )
            page = (
                _asset("explorer.html")
                .replace("__CSS__", _asset("report.css"))
                .replace("__SCRIPT__", _asset("explorer.js"))
                .replace("__DATA__", escaped)
            )
            (staging / "Explore-Every-Sample.html").write_text(
                page, encoding="utf-8"
            )
            (staging / "One-Page-Summary.html").write_text(
                _summary(data), encoding="utf-8"
            )
        if "docx" in formats:
            word_reports.write_summary(data, staging / "One-Page-Summary.docx")
            word_reports.write_explorer(
                data, staging / "Explore-Every-Sample.docx"
            )
        run_artifacts.write_json(
            staging / "manifest.json",
            {
                "format_version": REPORT_VERSION,
                "report_date": metadata.report_date.isoformat(),
                "source_checksum": data.source_checksum,
                "metadata_checksum": hashlib.sha256(
                    metadata.model_dump_json().encode("utf-8")
                ).hexdigest(),
                "selection_checksum": hashlib.sha256(
                    selection_path.read_bytes()
                ).hexdigest()
                if selection_path is not None
                else None,
                "template_checksums": {
                    name: hashlib.sha256(
                        _asset(name).encode("utf-8")
                    ).hexdigest()
                    for name in ("explorer.html", "explorer.js", "report.css")
                },
                "taxonomy_checksum": run.accepted.taxonomy_checksum,
                "filter_policy_checksum": run.accepted.filter_policy_checksum,
                "replayed_conversations": run.replayed,
                "replay_differences": 0,
                "model_calls": 0,
                "source_fetches": 0,
                "selected_trace_rows": data.sample_count,
                "captured_user_messages": data.prompt_count,
                "captured_assistant_messages": data.captured_answers,
                "conversation_counts": data.conversation_counts,
                "trace_counts": data.counts,
                "independent_human_validation": "pending",
                "sha256": run_artifacts.file_hashes(staging),
            },
        )
    return {
        "selected_trace_rows": data.sample_count,
        "captured_user_messages": data.prompt_count,
        "conversation_counts": data.conversation_counts,
        "trace_counts": data.counts,
        "replayed_conversations": run.replayed,
        "model_calls": 0,
    }
