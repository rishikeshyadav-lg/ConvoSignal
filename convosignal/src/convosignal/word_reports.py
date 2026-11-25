"""Dependency-free, deterministic Word exports for source-bound reports."""

import pathlib
import re
import xml.etree.ElementTree as element_tree
import zipfile
from collections.abc import Sequence

from convosignal import audit_report

WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"


def tag(name: str) -> str:
    """Return a qualified WordprocessingML name."""
    return f"{{{WORD}}}{name}"


def add(
    parent: element_tree.Element, element_name: str, **attributes: str
) -> element_tree.Element:
    """Append an element with WordprocessingML attributes."""
    return element_tree.SubElement(
        parent, tag(element_name), {tag(k): v for k, v in attributes.items()}
    )


class WordDocument:
    """Own the document body, styles, bookmarks and link relationships."""

    def __init__(self, *, compact: bool = False) -> None:
        self.root = element_tree.Element(tag("document"))
        self.body = add(self.root, "body")
        self.relationships = element_tree.Element(f"{{{PACKAGE}}}Relationships")
        self.bookmarks = 0
        self.compact = compact
        self.external_links: list[str] = []

    def paragraph(
        self,
        text: str = "",
        *,
        style: str | None = None,
        bookmark: str | None = None,
        parent: element_tree.Element | None = None,
    ) -> element_tree.Element:
        """Append a styled paragraph with an optional navigation bookmark."""
        paragraph = add(self.body if parent is None else parent, "p")
        if style:
            add(add(paragraph, "pPr"), "pStyle", val=style)
        if bookmark:
            self.bookmarks += 1
            add(
                paragraph,
                "bookmarkStart",
                id=str(self.bookmarks),
                name=bookmark,
            )
        if text:
            self.run(paragraph, text)
        if bookmark:
            add(paragraph, "bookmarkEnd", id=str(self.bookmarks))
        return paragraph

    def run(
        self, parent: element_tree.Element, text: str, *, bold: bool = False
    ) -> None:
        """Preserve source whitespace and line breaks in editable text runs."""
        if any(ord(c) < 32 and c not in "\n\r\t" for c in text):
            raise ValueError("Source contains an XML-incompatible control")
        run = add(parent, "r")
        if bold:
            add(add(run, "rPr"), "b")
        for piece in re.split(r"([\n\r\t])", text):
            if piece in {"\n", "\r", "\t"}:
                add(run, {"\n": "br", "\r": "cr", "\t": "tab"}[piece])
            elif piece:
                node = add(run, "t")
                node.set(
                    "{http://www.w3.org/XML/1998/namespace}space", "preserve"
                )
                node.text = piece

    def link(
        self, parent: element_tree.Element, label: str, target: str
    ) -> None:
        """Add a clickable internal bookmark or external research link."""
        hyperlink = add(parent, "hyperlink")
        if target.startswith("#"):
            hyperlink.set(tag("anchor"), target[1:])
        else:
            relation = f"link{len(self.external_links) + 1}"
            self.external_links.append(target)
            element_tree.SubElement(
                self.relationships,
                f"{{{PACKAGE}}}Relationship",
                {
                    "Id": relation,
                    "Type": REL + "/hyperlink",
                    "Target": target,
                    "TargetMode": "External",
                },
            )
            hyperlink.set(f"{{{REL}}}id", relation)
        run = add(hyperlink, "r")
        properties = add(run, "rPr")
        add(properties, "color", val="60548F")
        add(properties, "u", val="single")
        text = add(run, "t")
        text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        text.text = label

    def table(self, rows: list[list[str]]) -> None:
        """Append a readable table with a repeated, shaded header row."""
        table = add(self.body, "tbl")
        properties = add(table, "tblPr")
        add(properties, "tblW", w="0", type="auto")
        borders = add(properties, "tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            add(borders, edge, val="single", sz="4", color="DDD5C8")
        for index, cells in enumerate(rows):
            row = add(table, "tr")
            if index == 0:
                add(add(row, "trPr"), "tblHeader")
            for value in cells:
                cell = add(row, "tc")
                if index == 0:
                    add(add(cell, "tcPr"), "shd", fill="EEE8FA")
                paragraph = self.paragraph(parent=cell)
                self.run(paragraph, str(value), bold=index == 0)

    def save(self, path: pathlib.Path) -> None:
        """Write a standards-based DOCX without requiring new dependencies."""
        section = add(self.body, "sectPr")
        add(section, "pgSz", w="11906", h="16838")
        margin = "680" if self.compact else "1000"
        add(
            section,
            "pgMar",
            top=margin,
            bottom=margin,
            left=margin,
            right=margin,
            header="300",
            footer="300",
            gutter="0",
        )
        styles = element_tree.Element(tag("styles"))
        normal_size = "18" if self.compact else "20"
        defaults = add(styles, "docDefaults")
        default_run = add(add(defaults, "rPrDefault"), "rPr")
        add(
            default_run,
            "rFonts",
            ascii="Arial",
            hAnsi="Arial",
            eastAsia="Arial",
        )
        add(default_run, "sz", val=normal_size)
        definitions = [
            ("Normal", "Normal", normal_size, False, None),
            ("Title", "Title", "36", True, None),
            ("Heading1", "heading 1", "28", True, "0"),
            (
                "Heading2",
                "heading 2",
                "23" if not self.compact else "22",
                True,
                "1",
            ),
            ("Heading3", "heading 3", "21", True, "2"),
            ("Caption", "Caption", "17", False, None),
        ]
        for identity, name, size, bold, outline in definitions:
            style = add(styles, "style", type="paragraph", styleId=identity)
            if identity == "Normal":
                style.set(tag("default"), "1")
            add(style, "name", val=name)
            if identity != "Normal":
                add(style, "basedOn", val="Normal")
            paragraph = add(style, "pPr")
            add(
                paragraph,
                "spacing",
                after="45" if self.compact else "90",
                before="90" if identity.startswith("Heading") else "0",
                line="240" if self.compact else "264",
                lineRule="auto",
            )
            if outline is not None:
                add(paragraph, "outlineLvl", val=outline)
            if identity.startswith("Heading"):
                add(paragraph, "keepNext")
            properties = add(style, "rPr")
            add(
                properties,
                "rFonts",
                ascii="Arial",
                hAnsi="Arial",
                eastAsia="Arial",
            )
            add(properties, "sz", val=size)
            add(properties, "color", val="60548F" if bold else "26231E")
            if bold:
                add(properties, "b")
        element_tree.SubElement(
            self.relationships,
            f"{{{PACKAGE}}}Relationship",
            {
                "Id": "styles",
                "Type": REL + "/styles",
                "Target": "styles.xml",
            },
        )
        types = element_tree.Element(f"{{{CONTENT_TYPES}}}Types")
        for extension, content in (
            (
                "rels",
                "application/vnd.openxmlformats-package.relationships+xml",
            ),
            ("xml", "application/xml"),
        ):
            element_tree.SubElement(
                types,
                f"{{{CONTENT_TYPES}}}Default",
                Extension=extension,
                ContentType=content,
            )
        for name, content in (
            ("document", "document.main"),
            ("styles", "styles"),
        ):
            element_tree.SubElement(
                types,
                f"{{{CONTENT_TYPES}}}Override",
                PartName=f"/word/{name}.xml",
                ContentType=f"application/vnd.openxmlformats-officedocument.wordprocessingml.{content}+xml",
            )
        root_relationships = element_tree.Element(f"{{{PACKAGE}}}Relationships")
        element_tree.SubElement(
            root_relationships,
            f"{{{PACKAGE}}}Relationship",
            {
                "Id": "document",
                "Type": REL + "/officeDocument",
                "Target": "word/document.xml",
            },
        )
        parts = {
            "[Content_Types].xml": types,
            "_rels/.rels": root_relationships,
            "word/document.xml": self.root,
            "word/styles.xml": styles,
            "word/_rels/document.xml.rels": self.relationships,
        }
        with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED) as archive:
            for name, node in parts.items():
                entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o600 << 16
                archive.writestr(
                    entry,
                    element_tree.tostring(
                        node, encoding="utf-8", xml_declaration=True
                    ),
                )


def write_summary(data: audit_report.ReportData, path: pathlib.Path) -> None:
    """Write the editable summary, with captured counts and research links.

    Args:
        data: Validated report payload with source-derived statistics.
        path: DOCX path inside the caller's new output staging directory.
    """
    document = WordDocument(compact=True)
    document.paragraph("Agent Satisfaction Audit", style="Title")
    document.paragraph(
        f"ConvoSignal · {data.metadata.report_date.isoformat()} · Private"
    )
    for title, paragraphs in audit_report.summary_sections(data):
        document.paragraph(title, style="Heading2")
        for text in paragraphs:
            document.paragraph(text)
    document.paragraph("Results [E3 · ran]", style="Heading2")
    document.table(_count_rows(data))
    document.paragraph(
        "Each trace row carries its containing conversation's final decision; "
        "several rows can share one decision. These are not independent prompt "
        "ratings. Skips/errors have no satisfaction label.",
        style="Caption",
    )
    document.paragraph("Research behind the approach", style="Heading2")
    for title, url, finding in audit_report.RESEARCH:
        paragraph = document.paragraph()
        document.link(paragraph, title, url)
        document.run(paragraph, f" — {finding}")
    document.paragraph(
        "The research motivates this approach; it does not validate this "
        "classifier. Independent human review remains pending.",
        style="Caption",
    )
    document.paragraph(
        f"Verification: {data.replayed_conversations} classified "
        "conversations "
        f"replay identically; {data.conversation_counts['Error']} "
        "conversations "
        "remain unclassified. E1: captured source/header metadata; "
        "E2: recorded "
        "rules and evaluator prompts; E3: saved verdicts and manifest.json. "
        "This summary contains no captured prompts, answers or identities.",
        style="Caption",
    )
    document.save(path)


def _count_rows(data: audit_report.ReportData) -> list[list[str]]:
    """Keep trace and conversation denominators explicit in Word tables."""
    return [
        ["Decision", "Selected trace rows", "Distinct conversations"],
        *[
            [key, str(data.counts[key]), str(data.conversation_counts[key])]
            for key in data.counts
        ],
        ["Total", str(data.sample_count), str(data.conversation_count)],
    ]


def write_explorer(data: audit_report.ReportData, path: pathlib.Path) -> None:
    """Write every selected sample with linked conversation decision details.

    Args:
        data: Validated captured source and replayed decisions.
        path: DOCX path inside the caller's new output staging directory.
    """
    document = WordDocument()
    document.paragraph("Explore Every Sample", style="Title")
    document.paragraph(
        f"{data.metadata.agent_name} · {data.metadata.stage} "
        f"({data.metadata.stage_basis}) · "
        f"{data.metadata.report_date.isoformat()}"
    )
    document.paragraph(
        f"{data.sample_count} selected trace rows; "
        f"{data.prompt_count} captured "
        f"user messages across {data.conversation_count} conversations. "
        "Each sample carries its conversation's final decision, not an "
        "independent prompt rating. Errors/skips have no satisfaction label. "
        "Independent human validation remains pending."
    )
    document.paragraph(
        "Use the sample index, Word's Navigation pane or Find a sample ID. "
        "Each sample links to its conversation's full captured history, "
        "requirements and reasons. Source text retains original line breaks."
    )
    document.table(_count_rows(data))
    document.paragraph("Sample index", style="Heading1")
    for offset in range(0, len(data.samples), 24):
        paragraph = document.paragraph()
        for sample in data.samples[offset : offset + 24]:
            document.link(
                paragraph,
                f"{sample.number:04d}  ",
                f"#Sample{sample.number:04d}",
            )
    document.paragraph("Samples", style="Heading1")
    by_conversation: dict[int, list[audit_report.SampleView]] = {}
    for sample in data.samples:
        by_conversation.setdefault(sample.conversation_number, []).append(
            sample
        )
        document.paragraph(
            f"{sample.id} — {sample.label}",
            style="Heading2",
            bookmark=f"Sample{sample.number:04d}",
        )
        paragraph = document.paragraph()
        document.link(
            paragraph,
            f"Inspect conversation {sample.conversation_number:04d}",
            f"#Conversation{sample.conversation_number:04d}",
        )
        document.paragraph(sample.explanation)
        document.paragraph(
            f"Trace: {sample.trace_id}; reason: {sample.reason}",
            style="Caption",
        )
        for error in sample.errors:
            document.paragraph(f"Processing error: {error}")
        _messages(document, sample.messages)
        if not any(message.role == "assistant" for message in sample.messages):
            document.paragraph(
                "No agent answer was captured for this interaction."
            )
    document.paragraph(
        "Conversation decisions and captured history", style="Heading1"
    )
    for conversation in data.conversations:
        document.paragraph(
            f"Conversation {conversation.number:04d} — {conversation.label}",
            style="Heading2",
            bookmark=f"Conversation{conversation.number:04d}",
        )
        document.paragraph(conversation.explanation)
        paragraph = document.paragraph("Selected interactions: ")
        for sample in by_conversation.get(conversation.number, []):
            document.link(
                paragraph, f"{sample.id}  ", f"#Sample{sample.number:04d}"
            )
        if not conversation.context_complete:
            document.paragraph(
                "The source has incomplete history; individual "
                "goals may still be evaluated when relevant evidence "
                "is complete."
            )
        for error in conversation.errors:
            document.paragraph(f"Processing error: {error}")
        for goal in conversation.goals:
            document.paragraph(
                f"{goal.id} — {goal.label or 'Skipped'}", style="Heading3"
            )
            document.paragraph(goal.explanation)
            document.paragraph(
                f"Reason: {goal.reason}; basis: {goal.basis}; "
                f"outcome: {goal.outcome}; "
                f"user response: {goal.user_response}; "
                f"correctness: {goal.correctness}; "
                f"recovery: {goal.recovery}."
            )
            document.table(
                [
                    ["Requirement", "Importance", "State"],
                    *[
                        [
                            r.text,
                            "Essential" if r.material else "Optional",
                            r.status,
                        ]
                        for r in goal.requirements
                    ],
                ]
            )
            for limitation in goal.limitations:
                document.paragraph(f"Recorded limitation: {limitation}")
            document.paragraph(
                "Evidence turn IDs: " + ", ".join(goal.source_turn_ids),
                style="Caption",
            )
        document.paragraph(
            "Full captured history (chronological)", style="Heading3"
        )
        _messages(document, conversation.messages)
        document.paragraph(
            f"Input checksum: {conversation.input_checksum}", style="Caption"
        )
    document.paragraph(
        "Private: captured prompts/answers and model-interpreted requirements. "
        "Raw tool payloads, provider responses, identity metadata and"
        " credentials "
        "are excluded. Full evaluator prompts are in decision-data.json. "
        "Structural replay does not establish semantic accuracy.",
        style="Caption",
    )
    document.save(path)


def _messages(
    document: WordDocument, messages: Sequence[audit_report.MessageView]
) -> None:
    """Write captured source text without interpreting Markdown or HTML."""
    for message in messages:
        document.paragraph(
            "User prompt" if message.role == "user" else "Actual agent answer",
            style="Heading3",
        )
        document.paragraph(message.text)
        document.paragraph(message.turn_id, style="Caption")
