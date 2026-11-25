"""Source-bound comparisons and prediction-free independent review packets."""

import collections
import json
import pathlib
from collections.abc import Sequence
from typing import Any

from convosignal import (
    conversations,
    reporting,
    review_contracts,
    schemas,
    taxonomy,
)


def _index_run(
    predictions: Sequence[dict[str, Any]],
    source: Sequence[conversations.Conversation],
) -> dict[str, dict[str, Any]]:
    """Bind every saved prediction to its authoritative source snapshot."""
    conversations.validate_conversations(source)
    source_by_id = {item.conversation_id: item for item in source}
    whole_checksum = taxonomy.checksum(conversations.conversation_data(source))
    indexed = {}
    for row in predictions:
        schemas.EVALUATION_RECORD.validate_python(row)
        key = row["conversation_id"]
        if key in indexed or key not in source_by_id:
            raise ValueError("Duplicate or unknown prediction conversation")
        single_checksum = taxonomy.checksum(
            conversations.conversation_data((source_by_id[key],))
        )
        if row["input_checksum"] not in {whole_checksum, single_checksum}:
            raise ValueError(
                "Prediction checksum does not match supplied source"
            )
        indexed[key] = row
    if indexed.keys() != source_by_id.keys():
        raise ValueError("Prediction and source coverage differ")
    return indexed


def _audit(
    indexed: dict[str, dict[str, Any]],
    source: Sequence[conversations.Conversation],
) -> int:
    """Verify authoritative sources and policy-specific evidence replay."""
    count = 0
    for conversation in source:
        row = indexed[conversation.conversation_id]
        if row["status"] != "evaluated":
            continue
        record = schemas.parse_evidence(
            json.dumps(row["evidence_details"]["evidence"])
        )
        if (
            record.conversation_id != conversation.conversation_id
            or record.turns != conversation.turns
            or schemas.evidence_data(record)["versions"] != row["versions"]
        ):
            raise ValueError("Saved evidence replaced source or provenance")
        replay = schemas.EVALUATION.dump_python(
            schemas.evaluate_record(record), mode="json"
        )
        if any(
            replay[field] != row[field]
            for field in ("status", "label", "reason", "goals", "errors")
        ):
            raise ValueError(
                "Saved evaluation does not reproduce under its policy"
            )
        count += 1
    return count


def compare_runs(
    baseline: Sequence[dict[str, Any]],
    revised: Sequence[dict[str, Any]],
    baseline_source: Sequence[conversations.Conversation],
    revised_source: Sequence[conversations.Conversation],
) -> dict[str, Any]:
    """Compare complete saved runs without treating either as human truth.

    Args:
        baseline: Original saved evaluation records, including errors/skips.
        revised: Revised saved records, preserving their actual run checksums.
        baseline_source: Authoritative normalized source for the original run.
        revised_source: Authoritative normalized source for the revised run.

    Returns:
        Transitions, provenance, replay counts and validation status.

    Raises:
        ValueError: Sources, policies, checksums or replay differ unexpectedly.
    """
    if conversations.conversation_data(
        baseline_source
    ) != conversations.conversation_data(revised_source):
        raise ValueError("Comparison requires identical ordered frozen sources")
    old = _index_run(baseline, baseline_source)
    new = _index_run(revised, revised_source)
    transitions: collections.Counter[str] = collections.Counter()
    changes = []
    for key, original in old.items():
        updated = new[key]
        for field in ("taxonomy_checksum", "filter_policy_checksum"):
            if original[field] != updated[field]:
                raise ValueError("Comparison classification policy changed")
        before = original["label"] or original["status"]
        after = updated["label"] or updated["status"]
        transitions[f"{before} -> {after}"] += 1
        changes.append(
            {
                "conversation_id": key,
                "before": before,
                "after": after,
                "baseline_reason": original["reason"],
                "revised_reason": updated["reason"],
                "baseline_versions": original["versions"],
                "revised_versions": updated["versions"],
                "baseline_input_checksum": original["input_checksum"],
                "revised_input_checksum": updated["input_checksum"],
                "baseline_goals": original["goals"],
                "revised_goals": updated["goals"],
            }
        )
    return {
        "input_conversations": len(old),
        "transitions": dict(transitions),
        "baseline": reporting.outcome_report(
            [schemas.EVALUATION_RECORD.validate_python(row) for row in baseline]
        ),
        "revised": reporting.outcome_report(
            [schemas.EVALUATION_RECORD.validate_python(row) for row in revised]
        ),
        "replay_audit": {
            "baseline": _audit(old, baseline_source),
            "revised": _audit(new, revised_source),
        },
        "changes": changes,
        "goal_basis_counts": dict(
            collections.Counter(
                f"{v['label']}:{v['basis']}"
                for row in revised
                for _, v in row["goals"]
                if v["label"]
            )
        ),
        "independent_validation": reporting.compare(revised, [])[
            "validation_gate"
        ],
        "caution": (
            "Exploratory comparison, not accuracy or user sentiment change. "
            "Prompt changes may require fresh extraction; reusing source "
            "does not isolate rule changes from interpretation variability."
        ),
    }


def write_review_packet(
    predictions: Sequence[dict[str, Any]],
    source: Sequence[conversations.Conversation],
    output_dir: pathlib.Path,
) -> dict[str, Any]:
    """Write source plus blank reviews without exposing model predictions.

    Args:
        predictions: Saved records used only to bind IDs and snapshot checksums.
        source: Authoritative source conversations for independent annotation.
        output_dir: New private destination; existing directories are rejected.

    Returns:
        Aggregate packet record count, with no prediction content.
    """
    indexed = _index_run(predictions, source)
    output_dir.mkdir(parents=True, exist_ok=False)
    conversations.save_conversations(output_dir / "conversations.jsonl", source)
    context = review_contracts.ValidationContext(
        input_checksums=tuple(
            sorted({row["input_checksum"] for row in indexed.values()})
        )
    )
    (output_dir / "review_context.json").write_text(
        context.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    records = 0
    with (output_dir / "reviews.jsonl").open("x", encoding="utf-8") as stream:
        for row in indexed.values():
            if row["status"] != "evaluated":
                continue
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
            records += 1
    (output_dir / "instructions.json").write_text(
        json.dumps(
            {
                "independence": (
                    "Read source and criteria before predictions; "
                    "freeze annotations first."
                ),
                "provenance": (
                    "Fill reviewer, label and source-cited reason; preserve "
                    "IDs/checksums. No model-generated independent labels."
                ),
                "sampling": "Record and disclose review sampling method.",
                "scope": "Review does not establish original user feelings.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "criteria.md").write_text(
        """# Independent review criteria

Judge each goal against the user's actual current request and captured evidence.
Essential campaign identity, dates, key metrics and explicit instructions remain
essential unless the user genuinely makes them optional or changes scope.

Satisfied: clear acceptance without a known essential contradiction; or
supported completion/productive use with no unresolved essential issue.
Without feedback, require corroboration for essential factual claims. Drafts and
advice may be complete without evidence of subjective taste or future outcomes.
Courtesy, permission, unrelated follow-ups and silence alone are not acceptance.

Dissatisfied: applicable unresolved rejection or a proven substantive failure of
the essential request. Honest external inability alone is insufficient; do not
turn absence of proof of success into proof of failure.

Neutral: insufficient context, unverified completion without acceptance,
pending necessary inputs, honest inability, conflicting positive feedback and a
known essential error, or unconfirmed recovery after user rejection. A supported
repair needs later acceptance/use covering all rejected issues; partial use does
not confirm every issue. Preserve genuine scope changes and rejection history.

Uniform goal labels carry through. Mixed labels remain Neutral unless clearly
scoped overall feedback or explicit decisive priority determines the overall
judgment. Do not majority-vote or erase subordinate goal outcomes.
Unrelated missing history alone need not prevent judging a self-contained goal.
Do not invent reading, session closure or feelings. Cite source IDs.
""",
        encoding="utf-8",
    )
    return {"review_records": records, "status": "blank_review_packet"}
