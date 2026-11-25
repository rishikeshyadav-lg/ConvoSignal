"""Proposal normalization, explicit acceptance and canonical checksums."""

import json

import pydantic
import pytest

from convosignal import taxonomy


def type_payload(**changes):
    return dict(
        name="Period Comparison",
        description="Compare periods",
        markers=[" LAST   WEEK "],
        asks_for=["Current Value"],
        set_aside=False,
        **changes,
    )


def test_sampling_deduplicates_after_truncation_and_preserves_order():
    prefix = "A" * 300
    sample = taxonomy.sample_questions(
        [
            "  First \n question ",
            "first question",
            prefix + "x",
            prefix.lower() + "y",
            "Third question",
            " ",
        ],
        cap=2,
    )
    assert sample.questions == ("First question", prefix)
    assert sample.distinct_total == 3
    assert sample.sample_size == 2
    assert sample.cap_bound
    assert sample.truncated_occurrences == 2


@pytest.mark.parametrize("cap", [0, 121, True])
def test_invalid_sample_caps_fail(cap):
    with pytest.raises(ValueError):
        taxonomy.sample_questions(["Question"], cap)


def test_fenced_prose_and_structured_text_blocks_parse():
    payload = json.dumps({"types": [type_payload()]})
    parsed = taxonomy.parse_response(
        f"Here is the JSON:\n```json\n{payload}\n```"
    )
    assert parsed.types[0].name == "period_comparison"
    assert parsed.types[0].markers == ("last week",)
    assert parsed.types[0].asks_for == ("current_value",)
    blocks = [
        {"type": "reasoning", "text": "Do not parse this {"},
        {"type": "text", "text": payload},
    ]
    assert taxonomy.parse_response(blocks) == parsed


@pytest.mark.parametrize(
    "payload",
    [
        "not JSON",
        '{"types":[',
        '{"types":[]}',
        '{"types":[]} {"types":[]}',
    ],
)
def test_unusable_or_truncated_responses_are_visible(payload):
    with pytest.raises(ValueError):
        taxonomy.parse_response(payload)


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "general"},
        {"name": "Other"},
        {"name": ""},
        {"markers": []},
        {"markers": [" "]},
        {"markers": [123]},
        {"set_aside": "false"},
        {"description": ""},
        {"asks_for": [" "]},
    ],
)
def test_invalid_taxonomy_content_is_rejected(changes):
    payload = type_payload()
    payload.update(changes)
    with pytest.raises(ValueError):
        taxonomy.parse_response(json.dumps({"types": [payload]}))


def test_duplicate_normalized_names_fail():
    first = type_payload()
    second = dict(first, name="period-comparison")
    with pytest.raises(ValueError, match="unique normalized"):
        taxonomy.parse_response(json.dumps({"types": [first, second]}))


def test_omitted_set_aside_warns_and_defaults_false():
    payload = type_payload()
    del payload["set_aside"]
    with pytest.warns(UserWarning, match="Missing set_aside"):
        proposal = taxonomy.propose(
            json.dumps({"types": [payload]}),
            ["Last week"],
            model_identifier="fake",
        )
    assert proposal.taxonomy.types[0].set_aside is False
    assert any("Missing set_aside" in warning for warning in proposal.warnings)


def test_proposal_reports_coverage_unseen_markers_and_unused_types(proposal):
    assert proposal.status == "proposal"
    assert proposal.coverage["comparison"] == 1
    assert any("absent" in warning for warning in proposal.warnings)
    assert (
        "what can you do?"
        in taxonomy.validate_policy(
            proposal.filter_policy, proposal.taxonomy
        ).standalone_examples["capability"]
    )
    payload = type_payload()
    unused = taxonomy.propose(
        json.dumps({"types": [payload]}), ["Unrelated"], model_identifier="fake"
    )
    assert unused.coverage["period_comparison"] == 0
    assert any("no assigned" in warning for warning in unused.warnings)
    with pytest.raises(ValueError, match="No user questions"):
        taxonomy.propose(
            json.dumps({"types": [payload]}), [], model_identifier="fake"
        )


def test_canonical_hash_tracks_only_relevant_taxonomy_fields(
    proposal,
):
    original = proposal.taxonomy
    data = original.model_dump(mode="json")
    data["types"][0]["description"] = "Edited documentation only"
    same = taxonomy.Taxonomy.model_validate(data)
    assert taxonomy.taxonomy_checksum(original) == taxonomy.taxonomy_checksum(
        same
    )
    data["types"][0]["markers"].reverse()
    assert taxonomy.taxonomy_checksum(original) != taxonomy.taxonomy_checksum(
        taxonomy.Taxonomy.model_validate(data)
    )
    assert taxonomy.checksum({"a": 1, "b": 2}) == taxonomy.checksum(
        {"b": 2, "a": 1}
    )


def test_explicit_acceptance_recomputes_edited_proposal_hash(proposal):
    edited = proposal.model_dump(mode="json")
    edited["taxonomy"]["types"][-1]["asks_for"].append("new_requested_value")
    accepted = taxonomy.accept(taxonomy.Proposal.model_validate(edited))
    assert accepted.status == "accepted"
    assert accepted.taxonomy_checksum != proposal.taxonomy_checksum
    taxonomy.validate_accepted(accepted)


def test_policy_requires_exact_known_ids_and_nonblank_examples(accepted):
    for policy in [
        taxonomy.FilterPolicy(
            excluded_type_ids=("Greeting",), standalone_examples={}
        ),
        taxonomy.FilterPolicy(
            excluded_type_ids=(), standalone_examples={"missing": ("hi",)}
        ),
        taxonomy.FilterPolicy(
            excluded_type_ids=(), standalone_examples={"greeting": (" ",)}
        ),
    ]:
        with pytest.raises(ValueError):
            taxonomy.validate_policy(policy, accepted.taxonomy)


def test_save_and_load_acceptance_never_silently_overwrites(proposal, tmp_path):
    accepted = taxonomy.accept(proposal)
    tax_path, policy_path = (
        tmp_path / "taxonomy.json",
        tmp_path / "filter_policy.json",
    )
    taxonomy.save_accepted(tax_path, policy_path, accepted)
    assert taxonomy.load_accepted(tax_path, policy_path) == accepted
    before = tax_path.read_text()
    with pytest.raises(FileExistsError):
        taxonomy.save_accepted(tax_path, policy_path, accepted)
    assert tax_path.read_text() == before
    taxonomy.save_accepted(tax_path, policy_path, accepted, overwrite=True)
    data = json.loads(policy_path.read_text())
    data["filter_policy"]["excluded_type_ids"] = []
    policy_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="checksum mismatch"):
        taxonomy.load_accepted(tax_path, policy_path)
    with pytest.raises(pydantic.ValidationError):
        taxonomy.AcceptedArtifacts.model_validate(proposal.model_dump())


def test_missing_required_fields_are_not_invented():
    for field in ("name", "markers", "asks_for", "description"):
        payload = type_payload()
        del payload[field]
        with pytest.raises(ValueError):
            taxonomy.parse_response(json.dumps({"types": [payload]}))


def test_structured_reasoning_only_and_malformed_blocks_fail():
    for blocks in (
        [{"type": "reasoning", "text": '{"types":[]}'}],
        [{"type": "text", "text": {"value": "not supported"}}],
        [123],
    ):
        with pytest.raises(ValueError):
            taxonomy.parse_response(blocks)


def test_every_classification_relevant_edit_changes_the_checksum(proposal):
    original = proposal.taxonomy
    baseline = taxonomy.taxonomy_checksum(original)
    for field, replacement in (
        ("name", "period_delta"),
        ("asks_for", ["new_value"]),
        ("set_aside", True),
    ):
        data = original.model_dump(mode="json")
        data["types"][-1][field] = replacement
        assert (
            taxonomy.taxonomy_checksum(taxonomy.Taxonomy.model_validate(data))
            != baseline
        )
    data = original.model_dump(mode="json")
    data["types"].reverse()
    assert (
        taxonomy.taxonomy_checksum(taxonomy.Taxonomy.model_validate(data))
        != baseline
    )


def test_policy_standalone_example_edits_change_checksum(proposal):
    accepted = taxonomy.accept(proposal)
    payload = proposal.model_dump(mode="json")
    payload["filter_policy"]["standalone_examples"]["greeting"].append(
        "Hello there"
    )
    changed = taxonomy.accept(taxonomy.Proposal.model_validate(payload))
    assert accepted.filter_policy_checksum != changed.filter_policy_checksum
    assert accepted.taxonomy_checksum == changed.taxonomy_checksum


def test_exclusive_proposal_save_does_not_accept_it(proposal, tmp_path):
    path = tmp_path / "proposal.json"
    taxonomy.save_json(path, proposal)
    saved = taxonomy.Proposal.model_validate_json(path.read_text())
    assert saved.status == "proposal"
    with pytest.raises(FileExistsError):
        taxonomy.save_json(path, proposal)
