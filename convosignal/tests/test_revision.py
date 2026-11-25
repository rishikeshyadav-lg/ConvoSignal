"""Versioned behavior through public evidence replay and evaluation seams."""

import copy
import json

import pytest

from convosignal import (
    cli,
    comparison,
    conversations,
    llm,
    models,
    pipeline,
    schemas,
    verdicts,
)


def test_unknown_rule_version_never_falls_back_to_current_rules():
    goal = models.Goal("summary", (models.Requirement("r", "Summarize", "u"),))
    turns = (models.Turn("u", "user", "Summarize"),)
    with pytest.raises(ValueError, match="Unsupported rule version"):
        verdicts.evaluate_goal(goal, turns, rules_version="99")


def source_record():
    return {
        "conversation_id": "synthetic",
        "turns": [
            {"turn_id": "u", "role": "user", "text": "Summarize metric"},
            {"turn_id": "t", "role": "tool", "text": "Metric: 12"},
            {"turn_id": "a", "role": "assistant", "text": "Metric: 12"},
        ],
        "goals": [
            {
                "goal_id": "g",
                "requirements": [
                    {
                        "requirement_id": "r",
                        "text": "Metric",
                        "source_turn_id": "u",
                    }
                ],
                "events": [
                    {
                        "kind": "fulfillment",
                        "turn_id": "a",
                        "requirement_ids": ["r"],
                    },
                    {
                        "kind": "correctness_verified",
                        "turn_id": "a",
                        "requirement_ids": ["r"],
                        "evidence_turn_ids": ["t"],
                        "result_turn_id": "a",
                    },
                ],
            }
        ],
        "versions": {
            "evaluator": "synthetic",
            "model": "fake",
            "prompt": "fixture",
            "taxonomy_checksum": "synthetic",
            "rules": "3",
            "schema": "2",
        },
    }


def test_supported_completion_is_positive_only_under_new_policy():
    payload = source_record()
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == models.Label.SATISFIED
    verdict = result.goals[0][1]
    assert (verdict.reason, verdict.basis, verdict.user_response) == (
        "supported_completion",
        "inferred",
        "no_clear_evidence",
    )
    payload["versions"].update(rules="2", schema="1")
    legacy = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert legacy.label == models.Label.NEUTRAL
    assert legacy.goals[0][1].rules_version == "2"


def test_new_policy_runs_through_saved_evaluation_workflow(accepted, tmp_path):
    record = source_record()
    record["turns"][0]["text"] = "Compare metric"
    source = conversations.Conversation(
        "synthetic", tuple(models.Turn(**item) for item in record["turns"])
    )
    fake = llm.FakeLLM({"synthetic": {"goals": record["goals"]}})
    report = pipeline.evaluate(
        (source,), accepted, fake, tmp_path, rules_version="3"
    )
    assert report["outcomes"]["outcome_counts"]["Satisfied"] == 1
    saved = json.loads((tmp_path / "evaluations.jsonl").read_text())
    assert saved["versions"]["rules"] == "3"
    assert (
        saved["evidence_details"]["evidence"]["turns"][0]["text"]
        == "Compare metric"
    )


def test_saved_runs_explain_transition_without_claiming_accuracy(
    accepted, tmp_path
):
    payload = source_record()
    payload["turns"][0]["text"] = "Compare metric"
    source = (
        conversations.Conversation(
            "synthetic", tuple(models.Turn(**t) for t in payload["turns"])
        ),
    )
    rows = []
    for version in ("2", "3"):
        destination = tmp_path / version
        fake = llm.FakeLLM({"synthetic": {"goals": payload["goals"]}})
        pipeline.evaluate(
            source, accepted, fake, destination, rules_version=version
        )
        rows.append(
            [json.loads((destination / "evaluations.jsonl").read_text())]
        )
    report = comparison.compare_runs(rows[0], rows[1], source, source)
    assert report["transitions"] == {"Neutral -> Satisfied": 1}
    assert report["independent_validation"]["status"] == "pending"
    assert report["replay_audit"] == {"baseline": 1, "revised": 1}
    packet = tmp_path / "review"
    comparison.write_review_packet(rows[1], source, packet)
    blank = json.loads((packet / "reviews.jsonl").read_text())
    assert blank["label"] is None
    assert "Satisfied" not in (packet / "instructions.json").read_text()
    assert (
        cli.main(
            [
                "compare-runs",
                "--baseline",
                str(tmp_path / "2/evaluations.jsonl"),
                "--predictions",
                str(tmp_path / "3/evaluations.jsonl"),
                "--baseline-source",
                str(tmp_path / "2/conversations.jsonl"),
                "--source",
                str(tmp_path / "3/conversations.jsonl"),
                "--output",
                str(tmp_path / "comparison.json"),
            ]
        )
        == 0
    )
    assert (
        cli.main(
            [
                "review-packet",
                "--predictions",
                str(tmp_path / "3/evaluations.jsonl"),
                "--source",
                str(tmp_path / "3/conversations.jsonl"),
                "--output-dir",
                str(tmp_path / "cli-packet"),
            ]
        )
        == 0
    )
    changed = copy.deepcopy(rows[1])
    changed[0]["filter_policy_checksum"] = "changed"
    with pytest.raises(ValueError, match="policy changed"):
        comparison.compare_runs(rows[0], changed, source, source)
    with pytest.raises(ValueError, match="coverage differ"):
        comparison.compare_runs(rows[0], [], source, source)


def test_complete_deliverable_needs_no_tool_proof_of_subjective_taste():
    payload = source_record()
    goal = payload["goals"][0]
    goal["events"] = goal["events"][:1]
    goal["deliverable_requirement_ids"] = ["r"]
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == models.Label.SATISFIED
    assert result.goals[0][1].correctness == "unverified"


def test_honest_unavailability_is_not_an_agent_failure():
    payload = source_record()
    goal = payload["goals"][0]
    goal["events"] = []
    goal["unavailable"] = [
        {
            "requirement_ids": ["r"],
            "evidence_turn_ids": ["t"],
            "result_turn_id": "a",
            "explanation": "Source has no requested data",
        }
    ]
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == models.Label.NEUTRAL
    assert result.goals[0][1].reason == "honest_inability"


def test_verified_repair_without_user_rejection_can_complete_task():
    payload = source_record()
    payload["turns"].append(
        {"turn_id": "a2", "role": "assistant", "text": "Corrected metric: 12"}
    )
    goal = payload["goals"][0]
    goal["events"] = [
        {
            "kind": "failure",
            "turn_id": "a",
            "requirement_ids": ["r"],
            "evidence_turn_ids": ["t"],
        },
        {
            "kind": "repair",
            "turn_id": "a2",
            "requirement_ids": ["r"],
            "result_turn_id": "a2",
        },
        {
            "kind": "correctness_verified",
            "turn_id": "a2",
            "requirement_ids": ["r"],
            "result_turn_id": "a2",
            "evidence_turn_ids": ["t"],
        },
    ]
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == models.Label.SATISFIED
    assert result.goals[0][1].user_response == "no_clear_evidence"


def test_old_verification_cannot_support_a_later_changed_answer():
    payload = source_record()
    payload["turns"].append(
        {"turn_id": "a2", "role": "assistant", "text": "Metric: 99"}
    )
    payload["goals"][0]["events"].append(
        {"kind": "fulfillment", "turn_id": "a2", "requirement_ids": ["r"]}
    )
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == models.Label.NEUTRAL
    assert result.goals[0][1].correctness == "unverified"


@pytest.mark.parametrize("explicit_acceptance", [False, True])
def test_unsupported_figures_require_real_acceptance(explicit_acceptance):
    payload = source_record()
    payload["goals"][0]["events"] = payload["goals"][0]["events"][:1]
    if explicit_acceptance:
        payload["turns"].append(
            {"turn_id": "v", "role": "user", "text": "Perfect, that answers it"}
        )
        payload["goals"][0]["events"].append(
            {
                "kind": "acceptance",
                "turn_id": "v",
                "requirement_ids": ["r"],
                "result_turn_id": "a",
            }
        )
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == (
        models.Label.SATISFIED if explicit_acceptance else models.Label.NEUTRAL
    )
    assert result.goals[0][1].correctness == "unverified"


def test_praise_cannot_erase_a_proven_material_error():
    payload = source_record()
    payload["turns"].append({"turn_id": "v", "role": "user", "text": "Perfect"})
    payload["goals"][0]["events"] = [
        {
            "kind": "correctness_failed",
            "turn_id": "a",
            "requirement_ids": ["r"],
            "evidence_turn_ids": ["t"],
            "result_turn_id": "a",
        },
        {
            "kind": "acceptance",
            "turn_id": "v",
            "requirement_ids": ["r"],
            "result_turn_id": "a",
        },
    ]
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == models.Label.NEUTRAL
    verdict = result.goals[0][1]
    assert (verdict.reason, verdict.user_response, verdict.correctness) == (
        "conflicting_evidence",
        "acceptance",
        "failed",
    )


@pytest.mark.parametrize("confirm", [False, True])
def test_rejected_issue_needs_confirmation_after_verified_repair(confirm):
    payload = source_record()
    payload["turns"].extend(
        [
            {"turn_id": "v", "role": "user", "text": "That is wrong"},
            {"turn_id": "a2", "role": "assistant", "text": "Corrected: 12"},
            {
                "turn_id": "w",
                "role": "user",
                "text": "Using the corrected value",
            },
        ]
    )
    events = payload["goals"][0]["events"]
    events.extend(
        [
            {
                "kind": "rejection",
                "turn_id": "v",
                "requirement_ids": ["r"],
                "result_turn_id": "a",
            },
            {
                "kind": "repair",
                "turn_id": "a2",
                "requirement_ids": ["r"],
                "result_turn_id": "a2",
            },
            {
                "kind": "correctness_verified",
                "turn_id": "a2",
                "requirement_ids": ["r"],
                "result_turn_id": "a2",
                "evidence_turn_ids": ["t"],
            },
        ]
    )
    if confirm:
        events.append(
            {
                "kind": "productive_use",
                "turn_id": "w",
                "requirement_ids": ["r"],
                "result_turn_id": "a2",
            }
        )
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == (
        models.Label.SATISFIED if confirm else models.Label.NEUTRAL
    )
    assert result.goals[0][1].recovery == (
        "confirmed" if confirm else "apparent"
    )


@pytest.mark.parametrize("optional", [False, True])
def test_only_explicitly_optional_unavailability_can_leave_goal_complete(
    optional,
):
    payload = source_record()
    payload["goals"][0]["requirements"].append(
        {
            "requirement_id": "budget",
            "text": "Budget",
            "source_turn_id": "u",
            "material": not optional,
        }
    )
    payload["goals"][0]["unavailable"] = [
        {
            "requirement_ids": ["budget"],
            "evidence_turn_ids": ["t"],
            "result_turn_id": "a",
            "explanation": "No budget source",
        }
    ]
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == (
        models.Label.SATISFIED if optional else models.Label.NEUTRAL
    )


def test_proven_essential_failure_is_negative_without_user_feedback():
    payload = source_record()
    payload["goals"][0]["events"] = [
        {
            "kind": "failure",
            "turn_id": "a",
            "requirement_ids": ["r"],
            "evidence_turn_ids": ["t"],
        }
    ]
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == models.Label.DISSATISFIED
    assert result.goals[0][1].basis == "inferred"


def test_self_contained_goal_can_override_unrelated_source_gap(
    accepted, tmp_path
):
    payload = source_record()
    payload["turns"][0]["text"] = "Compare metric"
    payload["goals"][0]["context_evidence_turn_ids"] = ["u", "t", "a"]
    source = conversations.Conversation(
        "synthetic",
        tuple(models.Turn(**t) for t in payload["turns"]),
        context_complete=False,
    )
    fake = llm.FakeLLM({"synthetic": {"goals": payload["goals"]}})
    report = pipeline.evaluate(
        (source,), accepted, fake, tmp_path, rules_version="3"
    )
    assert report["outcomes"]["outcome_counts"]["Satisfied"] == 1


def test_missing_relevant_history_blocks_inferred_success():
    payload = source_record()
    payload["goals"][0]["context_complete"] = False
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == models.Label.NEUTRAL
    assert result.goals[0][1].reason == "incomplete_trace"


@pytest.mark.parametrize("priority", [False, True])
def test_mixed_goals_require_explicit_decisive_priority(priority):
    payload = source_record()
    second = copy.deepcopy(payload["goals"][0])
    second["goal_id"] = "other"
    second["events"] = [
        {
            "kind": "failure",
            "turn_id": "a",
            "requirement_ids": ["r"],
            "evidence_turn_ids": ["t"],
        }
    ]
    payload["goals"].append(second)
    if priority:
        payload["turns"].append(
            {
                "turn_id": "v",
                "role": "user",
                "text": "Only the first result matters",
            }
        )
        payload["overall_feedback"] = [
            {"kind": "priority", "turn_id": "v", "goal_ids": ["g"]}
        ]
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == (
        models.Label.SATISFIED if priority else models.Label.NEUTRAL
    )
    assert result.goals[1][1].label == models.Label.DISSATISFIED


def test_overall_acceptance_can_cover_both_delivered_goals():
    payload = source_record()
    payload["goals"][0]["events"] = payload["goals"][0]["events"][:1]
    second = copy.deepcopy(payload["goals"][0])
    second["goal_id"] = "other"
    payload["goals"].append(second)
    payload["turns"].append(
        {"turn_id": "v", "role": "user", "text": "Both cover everything I need"}
    )
    payload["overall_feedback"] = [
        {
            "kind": "acceptance",
            "turn_id": "v",
            "goal_ids": ["g", "other"],
            "result_turn_ids": ["a", "a"],
        }
    ]
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == models.Label.SATISFIED
    assert all(v.basis == "direct" for _, v in result.goals)


def test_partial_use_does_not_confirm_two_rejected_issues():
    payload = source_record()
    goal = payload["goals"][0]
    goal["requirements"].append(
        {"requirement_id": "dates", "text": "Dates", "source_turn_id": "u"}
    )
    payload["turns"].extend(
        [
            {"turn_id": "v", "role": "user", "text": "Wrong dates and metric"},
            {"turn_id": "a2", "role": "assistant", "text": "Both corrected"},
            {"turn_id": "w", "role": "user", "text": "Using this metric"},
        ]
    )
    goal["events"].extend(
        [
            {
                "kind": "rejection",
                "turn_id": "v",
                "requirement_ids": ["r", "dates"],
                "result_turn_id": "a",
            },
            {
                "kind": "repair",
                "turn_id": "a2",
                "requirement_ids": ["r", "dates"],
                "result_turn_id": "a2",
            },
            {
                "kind": "correctness_verified",
                "turn_id": "a2",
                "requirement_ids": ["r", "dates"],
                "result_turn_id": "a2",
                "evidence_turn_ids": ["t"],
            },
            {
                "kind": "productive_use",
                "turn_id": "w",
                "requirement_ids": ["r"],
                "result_turn_id": "a2",
            },
        ]
    )
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == models.Label.NEUTRAL
    assert result.goals[0][1].reason == "recovery_unconfirmed"
    assert result.goals[0][1].user_response == "productive_use"


def test_assistant_assertion_alone_cannot_prove_unavailability():
    payload = source_record()
    payload["goals"][0]["events"] = []
    payload["goals"][0]["unavailable"] = [
        {
            "requirement_ids": ["r"],
            "evidence_turn_ids": ["a"],
            "result_turn_id": "a",
            "explanation": "I cannot do this",
        }
    ]
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert (result.status, result.label) == ("error", None)


def test_accepted_scope_change_can_remove_unavailable_requirement():
    payload = source_record()
    goal = payload["goals"][0]
    goal["requirements"].append(
        {"requirement_id": "budget", "text": "Budget", "source_turn_id": "u"}
    )
    goal["unavailable"] = [
        {
            "requirement_ids": ["budget"],
            "evidence_turn_ids": ["t"],
            "result_turn_id": "a",
            "explanation": "Budget unavailable",
        }
    ]
    payload["turns"].append(
        {"turn_id": "v", "role": "user", "text": "Skip budget"}
    )
    goal["events"].append(
        {"kind": "withdrawal", "turn_id": "v", "requirement_ids": ["budget"]}
    )
    result = schemas.evaluate_record(
        schemas.parse_evidence(json.dumps(payload))
    )
    assert result.label == models.Label.SATISFIED
    assert result.goals[0][1].requirements[-1].status == "withdrawn"
