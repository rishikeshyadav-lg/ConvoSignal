"""Reviewable taxonomy proposals, validation and explicit acceptance."""

import hashlib
import json
import pathlib
import re
import warnings
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import pydantic


class Contract(pydantic.BaseModel):
    """Immutable artifact contract rejecting unrecognized fields."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)


def normalize(text: str) -> str:
    """Collapse whitespace and lowercase without tokenization."""
    return " ".join(text.split()).lower()


def snake_name(text: str) -> str:
    """Normalize a specific identifier to lower snake case."""
    value = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
        raise ValueError("Names must normalize to lower_snake_case")
    if value in {"general", "other", "misc", "unknown"}:
        raise ValueError("Generic names are not usable taxonomy identifiers")
    return value


class QuestionType(Contract):
    """An ordered collection of literal markers and requested information."""

    name: pydantic.StrictStr
    description: pydantic.StrictStr
    markers: tuple[pydantic.StrictStr, ...]
    asks_for: tuple[pydantic.StrictStr, ...]
    set_aside: pydantic.StrictBool = False

    @pydantic.field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Require a specific normalized identifier."""
        return snake_name(value)

    @pydantic.field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        """Require a useful description rather than empty metadata."""
        if not value.strip():
            raise ValueError("Description cannot be empty")
        return value.strip()

    @pydantic.field_validator("markers")
    @classmethod
    def validate_markers(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Keep declared priority while normalizing literal phrases."""
        markers = tuple(normalize(value) for value in values)
        if not markers or any(not value for value in markers):
            raise ValueError("At least one nonempty marker is required")
        return markers

    @pydantic.field_validator("asks_for")
    @classmethod
    def validate_asks_for(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Normalize requested information without inferring requirements."""
        return tuple(snake_name(value) for value in values)

    @pydantic.model_validator(mode="before")
    @classmethod
    def warn_missing_set_aside(cls, value: Any) -> Any:
        """Make the conservative missing-flag behavior visible."""
        if isinstance(value, Mapping) and "set_aside" not in value:
            warnings.warn(
                "Missing set_aside; defaulting to false",
                UserWarning,
                stacklevel=2,
            )
        return value


class Taxonomy(Contract):
    """Ordered types whose declaration order resolves marker ties."""

    types: tuple[QuestionType, ...]

    @pydantic.field_validator("types")
    @classmethod
    def validate_types(
        cls, values: tuple[QuestionType, ...]
    ) -> tuple[QuestionType, ...]:
        """Reject empty or ambiguously named taxonomies."""
        if not values or len({item.name for item in values}) != len(values):
            raise ValueError(
                "Types must be nonempty with unique normalized names"
            )
        return values


def checksum(value: Any) -> str:
    """Hash canonical UTF-8 JSON, preserving array order."""
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def taxonomy_checksum(taxonomy: Taxonomy) -> str:
    """Hash classification-relevant fields, excluding descriptive prose."""
    return checksum(
        [
            item.model_dump(mode="json", exclude={"description"})
            for item in taxonomy.types
        ]
    )


class FilterPolicy(Contract):
    """Explicit exclusions and reviewed whole-turn examples by exact type ID."""

    excluded_type_ids: tuple[pydantic.StrictStr, ...]
    standalone_examples: dict[str, tuple[pydantic.StrictStr, ...]]


def validate_policy(policy: FilterPolicy, taxonomy: Taxonomy) -> FilterPolicy:
    """Validate exact category IDs and normalize standalone examples."""
    names = {item.name for item in taxonomy.types}
    excluded = set(policy.excluded_type_ids)
    if len(excluded) != len(policy.excluded_type_ids):
        raise ValueError("Duplicate excluded category IDs")
    if not excluded <= names or not policy.standalone_examples.keys() <= names:
        raise ValueError("Policy references unknown exact accepted type IDs")
    examples = {}
    for name, values in policy.standalone_examples.items():
        normalized = tuple(normalize(value) for value in values)
        if any(not value for value in normalized):
            raise ValueError("Standalone examples cannot be empty")
        examples[name] = normalized
    return policy.model_copy(update={"standalone_examples": examples})


def policy_checksum(policy: FilterPolicy, taxonomy: Taxonomy) -> str:
    """Hash normalized policy, including explicit examples and overrides."""
    return checksum(validate_policy(policy, taxonomy).model_dump(mode="json"))


def matching_types(
    text: str, taxonomy: Taxonomy
) -> list[tuple[QuestionType, str]]:
    """Return literal marker matches in declared type and marker order."""
    padded = f" {normalize(text)} "
    return [
        (item, marker)
        for item in taxonomy.types
        for marker in item.markers
        if marker in padded
    ]


def assignment(text: str, taxonomy: Taxonomy) -> QuestionType | None:
    """Select the longest marker, preserving first-declared ties."""
    matches = matching_types(text, taxonomy)
    if not matches:
        return None
    return max(matches, key=lambda match: len(match[1]))[0]


class Sample(Contract):
    """Questions only; counts distinguish normalization from traffic volume."""

    questions: tuple[str, ...]
    distinct_total: int
    sample_size: int
    truncated_occurrences: int
    cap_bound: bool


def sample_questions(questions: Sequence[str], cap: int = 120) -> Sample:
    """Deduplicate after whitespace collapse and 300-character truncation."""
    if type(cap) is not int or not 1 <= cap <= 120:
        raise ValueError("Proposal sample cap must be between 1 and 120")
    distinct: dict[str, str] = {}
    truncated = 0
    for question in questions:
        clean = " ".join(question.split())
        if len(clean) > 300:
            truncated += 1
        clean = clean[:300]
        if clean:
            distinct.setdefault(clean.lower(), clean)
    selected = tuple(distinct.values())[:cap]
    return Sample(
        questions=selected,
        distinct_total=len(distinct),
        sample_size=len(selected),
        truncated_occurrences=truncated,
        cap_bound=len(distinct) > cap,
    )


def parse_response(content: str | Sequence[Mapping[str, Any]]) -> Taxonomy:
    """Read JSON from plain/fenced/prose or text blocks, ignoring reasoning."""
    if not isinstance(content, str):
        text_blocks = []
        for block in content:
            if not isinstance(block, Mapping):
                raise ValueError("Response blocks must be objects")
            if block.get("type") in {"text", "output_text"}:
                value = block.get("text")
                if not isinstance(value, str):
                    raise ValueError(
                        "Text response blocks must contain strings"
                    )
                text_blocks.append(value)
        content = "\n".join(text_blocks)
    decoder = json.JSONDecoder()
    candidates = []
    for position, char in enumerate(content):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(content[position:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "types" in value:
            candidates.append(value)
    if len(candidates) != 1:
        raise ValueError("Expected exactly one complete taxonomy JSON object")
    return Taxonomy.model_validate(candidates[0])


class Proposal(Contract):
    """Review artifact; creating it never authorizes classification."""

    status: Literal["proposal"] = "proposal"
    version: Literal["1"] = "1"
    taxonomy: Taxonomy
    filter_policy: FilterPolicy
    sample: Sample
    source_statistics: dict[str, int]
    model_identifier: str
    taxonomy_checksum: str
    warnings: tuple[str, ...]
    coverage: dict[str, int]


class AcceptedArtifacts(Contract):
    """Validated taxonomy and policy explicitly accepted by the caller."""

    status: Literal["accepted"] = "accepted"
    version: Literal["1"] = "1"
    taxonomy: Taxonomy
    filter_policy: FilterPolicy
    taxonomy_checksum: str
    filter_policy_checksum: str


def propose(
    content: str | Sequence[Mapping[str, Any]],
    questions: Sequence[str],
    *,
    model_identifier: str,
    source_statistics: dict[str, int] | None = None,
    cap: int = 120,
) -> Proposal:
    """Build a reviewable proposal from a supplied model response.

    The live/fake model calls belong to later milestones. Candidates seeded here
    require review, especially compound questions matching excluded types.
    """
    sample = sample_questions(questions, cap)
    if not sample.questions:
        raise ValueError("No user questions available for taxonomy proposal")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        taxonomy = parse_response(content)
    diagnostics = [str(item.message) for item in caught]
    for diagnostic in diagnostics:
        warnings.warn(diagnostic, UserWarning, stacklevel=2)
    coverage = {item.name: 0 for item in taxonomy.types}
    standalone: dict[str, tuple[str, ...]] = {}
    for item in taxonomy.types:
        for marker in item.markers:
            if not any(marker in normalize(text) for text in sample.questions):
                diagnostics.append(
                    f"Marker absent from sample: {item.name}: {marker}"
                )
        if not 3 <= len(item.markers) <= 10:
            diagnostics.append(f"Outside suggested 3–10 markers: {item.name}")
        if item.set_aside:
            standalone[item.name] = tuple(
                text
                for text in sample.questions
                if assignment(text, taxonomy) == item
            )
    for text in sample.questions:
        selected = assignment(text, taxonomy)
        if selected is not None:
            coverage[selected.name] += 1
    for name, count in coverage.items():
        if count == 0:
            diagnostics.append(f"Type has no assigned sample questions: {name}")
    policy = FilterPolicy(
        excluded_type_ids=tuple(t.name for t in taxonomy.types if t.set_aside),
        standalone_examples=standalone,
    )
    return Proposal(
        taxonomy=taxonomy,
        filter_policy=validate_policy(policy, taxonomy),
        sample=sample,
        source_statistics=source_statistics or {},
        model_identifier=model_identifier,
        taxonomy_checksum=taxonomy_checksum(taxonomy),
        warnings=tuple(diagnostics),
        coverage=coverage,
    )


def accept(proposal: Proposal) -> AcceptedArtifacts:
    """Explicitly accept edited content and recalculate checksums."""
    taxonomy = Taxonomy.model_validate(proposal.taxonomy.model_dump())
    policy = validate_policy(proposal.filter_policy, taxonomy)
    return AcceptedArtifacts(
        taxonomy=taxonomy,
        filter_policy=policy,
        taxonomy_checksum=taxonomy_checksum(taxonomy),
        filter_policy_checksum=policy_checksum(policy, taxonomy),
    )


def validate_accepted(artifacts: AcceptedArtifacts) -> None:
    """Reject stale/tampered accepted data before classification."""
    if (
        taxonomy_checksum(artifacts.taxonomy) != artifacts.taxonomy_checksum
        or policy_checksum(artifacts.filter_policy, artifacts.taxonomy)
        != artifacts.filter_policy_checksum
    ):
        raise ValueError(
            "Accepted taxonomy/policy checksum mismatch; accept again"
        )


def save_json(
    path: pathlib.Path, value: Contract, *, overwrite: bool = False
) -> None:
    """Save exclusively unless overwrite was explicitly requested."""
    with path.open("w" if overwrite else "x", encoding="utf-8") as stream:
        stream.write(value.model_dump_json(indent=2) + "\n")


class AcceptedTaxonomy(Contract):
    """Accepted taxonomy artifact saved separately from the filtering policy."""

    status: Literal["accepted"] = "accepted"
    version: Literal["1"] = "1"
    taxonomy: Taxonomy
    taxonomy_checksum: str


class AcceptedPolicy(Contract):
    """Policy artifact bound to the reviewed taxonomy and its own checksum."""

    status: Literal["accepted"] = "accepted"
    version: Literal["1"] = "1"
    taxonomy_checksum: str
    filter_policy: FilterPolicy
    filter_policy_checksum: str


def save_accepted(
    taxonomy_path: pathlib.Path,
    policy_path: pathlib.Path,
    accepted: AcceptedArtifacts,
    *,
    overwrite: bool = False,
) -> None:
    """Persist both accepted artifacts after preflighting path collisions."""
    validate_accepted(accepted)
    if taxonomy_path.resolve() == policy_path.resolve():
        raise ValueError("Taxonomy and policy paths must be different")
    if not overwrite and (taxonomy_path.exists() or policy_path.exists()):
        raise FileExistsError("Accepted artifact exists; request overwrite")
    save_json(
        taxonomy_path,
        AcceptedTaxonomy(
            taxonomy=accepted.taxonomy,
            taxonomy_checksum=accepted.taxonomy_checksum,
        ),
        overwrite=overwrite,
    )
    save_json(
        policy_path,
        AcceptedPolicy(
            taxonomy_checksum=accepted.taxonomy_checksum,
            filter_policy=accepted.filter_policy,
            filter_policy_checksum=accepted.filter_policy_checksum,
        ),
        overwrite=overwrite,
    )


def load_accepted(
    taxonomy_path: pathlib.Path,
    policy_path: pathlib.Path,
) -> AcceptedArtifacts:
    """Load both artifacts and reject changes that need renewed acceptance."""
    tax = AcceptedTaxonomy.model_validate_json(taxonomy_path.read_text())
    policy = AcceptedPolicy.model_validate_json(policy_path.read_text())
    if tax.taxonomy_checksum != policy.taxonomy_checksum:
        raise ValueError("Accepted taxonomy and policy do not belong together")
    accepted = AcceptedArtifacts(
        taxonomy=tax.taxonomy,
        filter_policy=policy.filter_policy,
        taxonomy_checksum=tax.taxonomy_checksum,
        filter_policy_checksum=policy.filter_policy_checksum,
    )
    validate_accepted(accepted)
    return accepted
