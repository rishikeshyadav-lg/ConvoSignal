"""Independent-label comparison never invokes a model."""

import pytest

from convosignal import reporting


def prediction(key, label, status="evaluated", reason="consistent_goals"):
    return {
        "conversation_id": key,
        "input_checksum": "snapshot",
        "label": label,
        "status": status,
        "reason": reason,
        "goals": [],
    }


def review(key, label, **extra):
    return {
        "conversation_id": key,
        "input_checksum": "snapshot",
        "label": label,
        "reviewer": "synthetic-human-format-fixture",
        **extra,
    }


def test_three_class_metrics_confusion_matrix_and_coverage():
    predictions = [
        prediction("a", "Satisfied"),
        prediction("b", "Neutral"),
        prediction("c", "Dissatisfied"),
        prediction("d", None, "error"),
        prediction("e", None, "skipped"),
    ]
    reviews = [
        review("a", "Satisfied"),
        review("b", "Dissatisfied"),
        review("c", "Dissatisfied"),
        review("d", "Neutral"),
        review("e", "Neutral"),
    ]
    report = reporting.compare(predictions, reviews)
    assert report["compared"] == 3
    assert report["confusion_matrix"]["Dissatisfied"]["Neutral"] == 1
    assert report["per_class"]["Dissatisfied"]["precision"] == 1
    assert report["per_class"]["Dissatisfied"]["recall"] == 0.5
    assert report["per_class"]["Neutral"]["recall"] is None
    assert report["technical_failures_excluded"] == 1
    assert report["skipped_excluded"] == 1
    assert report["review_coverage"] == 3 / 5


def test_undefined_metrics_stay_null_and_all_classes_remain():
    report = reporting.compare([], [])
    assert report["review_coverage"] is None
    assert len(report["per_class"]) == 3
    assert all(row["precision"] is None for row in report["per_class"].values())


def test_independent_validation_stays_pending_without_reviewed_classes():
    report = reporting.compare([], [])
    assert report["validation_gate"]["status"] == "pending"
    assert report["validation_gate"]["minimum_reviewed_per_class"] == 30


@pytest.mark.parametrize(
    ("size", "mistakes", "expected"),
    [(29, 0, "pending"), (30, 3, "passed"), (30, 4, "failed")],
)
def test_review_gate_checks_each_predicted_class(size, mistakes, expected):
    predictions = []
    reviews = []
    for label in ("Satisfied", "Dissatisfied"):
        for index in range(size):
            key = f"synthetic-{label}-{index}"
            predictions.append(prediction(key, label))
            reviews.append(
                review(key, "Neutral" if index < mistakes else label)
            )
    report = reporting.compare(
        predictions,
        reviews,
        sampling="class_targeted",
        validation_context={
            "dataset_role": "holdout",
            "reviewers_blind": True,
            "annotations_frozen": True,
            "holdout_frozen_before_tuning": True,
            "input_checksums": ["snapshot"],
        },
    )
    assert report["validation_gate"]["status"] == expected
    assert report["population_recall_supported"] is False
    assert report["per_class"]["Satisfied"]["precision_interval_95"] is not None


def test_goal_metrics_cannot_pass_the_conversation_review_gate():
    report = reporting.compare([], [], unit="goal")
    assert report["validation_gate"]["status"] == "not_applicable"


def test_exploratory_reviews_cannot_pass_even_with_perfect_precision():
    predictions = [
        prediction(f"synthetic-{label}-{i}", label)
        for label in ("Satisfied", "Dissatisfied")
        for i in range(30)
    ]
    reviews = [
        review(row["conversation_id"], row["label"]) for row in predictions
    ]
    report = reporting.compare(predictions, reviews)
    assert report["validation_gate"]["status"] == "pending"


@pytest.mark.parametrize(
    "missing",
    ["reviewers_blind", "annotations_frozen", "holdout_frozen_before_tuning"],
)
def test_review_provenance_must_establish_every_eligibility_condition(missing):
    predictions = [
        prediction(f"synthetic-{label}-{i}", label)
        for label in ("Satisfied", "Dissatisfied")
        for i in range(30)
    ]
    reviews = [
        review(row["conversation_id"], row["label"]) for row in predictions
    ]
    context = {
        "dataset_role": "holdout",
        "reviewers_blind": True,
        "annotations_frozen": True,
        "holdout_frozen_before_tuning": True,
        "input_checksums": ["snapshot"],
    }
    context[missing] = False
    report = reporting.compare(predictions, reviews, validation_context=context)
    assert report["validation_gate"]["status"] == "pending"
    context["input_checksums"] = ["different"]
    with pytest.raises(ValueError, match="different source snapshots"):
        reporting.compare(predictions, reviews, validation_context=context)


def test_snapshot_mismatch_duplicate_review_and_model_annotations_fail():
    pred = [prediction("a", "Satisfied")]
    bad_cases = [
        [review("a", "Satisfied", input_checksum="different")],
        [review("a", "Satisfied"), review("a", "Satisfied")],
        [review("a", "Satisfied", annotation_source="model")],
    ]
    for reviews in bad_cases:
        with pytest.raises(ValueError):
            reporting.compare(pred, reviews)


def test_goal_comparison_and_existing_judge_labels():
    row = prediction("c", "Neutral")
    row["goals"] = [
        [
            "g",
            {
                "status": "evaluated",
                "label": "Neutral",
                "reason": "missing_context",
            },
        ]
    ]
    report = reporting.compare(
        [row],
        [review("c", "Neutral", goal_id="g", existing_judge_label="Satisfied")],
        unit="goal",
    )
    assert report["unknown_share"] == 1
    assert report["existing_judge"]["compared"] == 1
    assert report["existing_judge"]["per_class"]["Neutral"]["recall"] == 0
