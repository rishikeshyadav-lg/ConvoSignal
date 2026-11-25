"""Reconciled outcome denominators and independent-label comparison."""

import collections
import math
from collections.abc import Sequence
from typing import Any

from convosignal import models, review_contracts


def outcome_report(results: Sequence[models.Evaluation]) -> dict[str, Any]:
    """Keep operational coverage distinct from the three outcome shares."""
    statuses = collections.Counter(item.status for item in results)
    labels = collections.Counter(
        item.label.value for item in results if item.label is not None
    )
    evaluated = statuses["evaluated"]
    total = len(results)
    goals = [
        verdict
        for item in results
        for _, verdict in item.goals
        if verdict.status == "evaluated"
    ]
    goal_counts = collections.Counter(v.label.value for v in goals if v.label)
    reasons = collections.Counter(
        verdict.reason
        for item in results
        for _, verdict in item.goals
        if verdict.label == models.Label.NEUTRAL
    )
    if evaluated != sum(labels.values()) or total != sum(statuses.values()):
        raise ValueError("Outcome counts do not reconcile")
    return {
        "unit": "conversation",
        "input_conversations": total,
        "evaluated_conversations": evaluated,
        "skipped_conversations": statuses["skipped"],
        "error_conversations": statuses["error"],
        "outcome_counts": {
            label.value: labels[label.value] for label in models.Label
        },
        "outcome_shares": {
            label.value: labels[label.value] / evaluated if evaluated else None
            for label in models.Label
        },
        "skipped_share": statuses["skipped"] / total if total else None,
        "error_share": statuses["error"] / total if total else None,
        "skip_reasons": dict(
            collections.Counter(
                r.reason for r in results if r.status == "skipped"
            )
        ),
        "neutral_reasons": dict(
            collections.Counter(
                (
                    next(iter({v.reason for _, v in r.goals}))
                    if r.reason == "consistent_goals"
                    and len({v.reason for _, v in r.goals}) == 1
                    else r.reason
                )
                for r in results
                if r.label == models.Label.NEUTRAL
            )
        ),
        "goal_results": {
            "unit": "goal",
            "evaluated": len(goals),
            "counts": {
                label.value: goal_counts[label.value] for label in models.Label
            },
            "neutral_reasons": dict(reasons),
            "includes_completed_goals_in_error_conversations": True,
        },
    }


def _metrics(pairs: Sequence[tuple[str, str]]) -> dict[str, Any]:
    """Compute three-class metrics with explicit undefined denominators."""
    names = [label.value for label in models.Label]
    matrix = {gold: {prediction: 0 for prediction in names} for gold in names}
    for gold, prediction in pairs:
        matrix[gold][prediction] += 1
    per_class = {}
    for name in names:
        actual = sum(matrix[name].values())
        predicted = sum(matrix[row][name] for row in names)
        per_class[name] = {
            "precision": matrix[name][name] / predicted if predicted else None,
            "recall": matrix[name][name] / actual if actual else None,
            "gold_count": actual,
            "predicted_count": predicted,
            "precision_interval_95": _interval(matrix[name][name], predicted),
            "recall_interval_95": _interval(matrix[name][name], actual),
        }
    return {
        "compared": len(pairs),
        "confusion_matrix": matrix,
        "matrix_rows": "independent_label",
        "matrix_columns": "prediction",
        "per_class": per_class,
    }


def _interval(correct: int, count: int) -> list[float] | None:
    """Return a Wilson 95% interval, conditional on the reviewed sample."""
    if not count:
        return None
    z = 1.959963984540054
    share = correct / count
    denominator = 1 + z * z / count
    center = (share + z * z / (2 * count)) / denominator
    radius = (
        z
        * math.sqrt(share * (1 - share) / count + z * z / (4 * count * count))
        / denominator
    )
    return [max(0.0, center - radius), min(1.0, center + radius)]


def _validation_gate(
    metrics: dict[str, Any], unit: str, eligible: bool
) -> dict[str, Any]:
    """Assess conversation review thresholds without passing absent evidence."""
    classes = {}
    for label in ("Satisfied", "Dissatisfied"):
        row = metrics["per_class"][label]
        status = "pending"
        if row["predicted_count"] >= 30:
            status = "passed" if row["precision"] >= 0.9 else "failed"
        classes[label] = {**row, "status": status}
    statuses = {row["status"] for row in classes.values()}
    status = "passed"
    if "failed" in statuses:
        status = "failed"
    elif "pending" in statuses:
        status = "pending"
    if not eligible:
        status = "pending"
    if unit != "conversation":
        status = "not_applicable"
    return {
        "status": status,
        "minimum_precision": 0.9,
        "minimum_reviewed_per_class": 30,
        "unit": "conversation",
        "per_class": classes,
        "review_context_eligible": eligible,
        "meaning": "Independent reviewer agreement, not actual user feelings",
    }


def compare(
    predictions: Sequence[dict[str, Any]],
    reviews: Sequence[dict[str, Any]],
    *,
    unit: str = "conversation",
    sampling: str = "unknown",
    validation_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare saved predictions with independently supplied human labels.

    No review text or labels enter an evaluation prompt. Technical failures stay
    out of three-class metrics while remaining visible in coverage.
    """
    if unit not in {"conversation", "goal"}:
        raise ValueError("Comparison unit must be conversation or goal")
    if sampling not in {"unknown", "representative", "class_targeted"}:
        raise ValueError("Unknown review sampling method")
    context = review_contracts.ValidationContext.model_validate(
        validation_context or {}
    )
    checksums = {row["input_checksum"] for row in predictions}
    if (
        validation_context is not None
        and set(context.input_checksums) != checksums
    ):
        raise ValueError(
            "Review context is bound to different source snapshots"
        )
    eligible = (
        context.dataset_role == "holdout"
        and context.reviewers_blind
        and context.annotations_frozen
        and context.holdout_frozen_before_tuning
        and bool(checksums)
    )
    indexed: dict[tuple[str, str | None], dict[str, Any]] = {}
    key: tuple[str, str | None]
    for row in predictions:
        if unit == "conversation":
            key = (row["conversation_id"], None)
            if key in indexed:
                raise ValueError("Duplicate prediction IDs")
            indexed[key] = row
        else:
            for goal_id, goal in row.get("goals", []):
                key = (row["conversation_id"], goal_id)
                if key in indexed:
                    raise ValueError("Duplicate prediction goal IDs")
                indexed[key] = {**goal, "input_checksum": row["input_checksum"]}
    pairs = []
    old_pairs = []
    seen = set()
    missing = technical = skipped = 0
    neutral_reasons: collections.Counter[str] = collections.Counter()
    for raw in reviews:
        review = review_contracts.Review.model_validate(raw)
        if (unit == "goal") != (review.goal_id is not None):
            raise ValueError("Review goal_id must match the comparison unit")
        key = (review.conversation_id, review.goal_id)
        if key in seen:
            raise ValueError("Duplicate independently reviewed IDs")
        seen.add(key)
        prediction = indexed.get(key)
        if prediction is None:
            missing += 1
            continue
        if review.input_checksum != prediction["input_checksum"]:
            raise ValueError(
                "Independent review references a different snapshot"
            )
        if prediction.get("status") == "error":
            technical += 1
            continue
        if prediction.get("status") == "skipped":
            skipped += 1
            continue
        label = models.Label(prediction["label"]).value
        pairs.append((review.label.value, label))
        if review.existing_judge_label is not None:
            old_pairs.append(
                (review.label.value, review.existing_judge_label.value)
            )
        if label == models.Label.NEUTRAL:
            reason = prediction["reason"]
            if reason == "consistent_goals":
                goal_reasons = {
                    v["reason"] for _, v in prediction.get("goals", [])
                }
                reason = (
                    next(iter(goal_reasons))
                    if len(goal_reasons) == 1
                    else "multiple_unknown_reasons"
                )
            neutral_reasons[reason] += 1
    count = len(pairs)
    unknown_reasons = {
        "no_clear_user_response",
        "missing_context",
        "incomplete_trace",
        "awaiting_input",
        "unverifiable",
        "recovery_unconfirmed",
        "multiple_unknown_reasons",
    }
    metrics = _metrics(pairs)
    return {
        **metrics,
        "validation_gate": _validation_gate(metrics, unit, eligible),
        "validation_context": context.model_dump(mode="json"),
        "review_sampling": sampling,
        "population_recall_supported": sampling == "representative",
        "interval_method": "Wilson 95%; sample only, no selection correction",
        "unit": unit,
        "reviews": len(reviews),
        "prediction_units": len(indexed),
        "missing_predictions": missing,
        "technical_failures_excluded": technical,
        "skipped_excluded": skipped,
        "review_coverage": count / len(indexed) if indexed else None,
        "evaluated_review_coverage": count / len(reviews) if reviews else None,
        "neutral_share": sum(p == "Neutral" for _, p in pairs) / count
        if count
        else None,
        "neutral_reasons": dict(neutral_reasons),
        "unknown_share": sum(neutral_reasons[r] for r in unknown_reasons)
        / count
        if count
        else None,
        "existing_judge": _metrics(old_pairs) if old_pairs else None,
        "caution": (
            "Reviewer agreement does not establish user feelings. Recall and "
            "rates describe the reviewed sample; targeted/unknown sampling "
            "does not justify population estimates."
        ),
    }
