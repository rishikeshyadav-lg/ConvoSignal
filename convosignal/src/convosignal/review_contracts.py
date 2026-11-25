"""Independent annotations are separate from model evidence and prompts."""

from typing import Literal

import pydantic

from convosignal import models, taxonomy


class ValidationContext(taxonomy.Contract):
    """Declared review provenance bound to the evaluated source snapshots."""

    dataset_role: Literal["unknown", "exploratory", "holdout"] = "unknown"
    reviewers_blind: pydantic.StrictBool = False
    annotations_frozen: pydantic.StrictBool = False
    holdout_frozen_before_tuning: pydantic.StrictBool = False
    input_checksums: tuple[str, ...] = ()


class Review(taxonomy.Contract):
    """An independent human annotation bound to its source snapshot."""

    conversation_id: str = pydantic.Field(min_length=1)
    input_checksum: str = pydantic.Field(min_length=1)
    reviewer: str = pydantic.Field(min_length=1)
    label: models.Label
    annotation_source: str = "human"
    goal_id: str | None = None
    reason: str = ""
    existing_judge_label: models.Label | None = None

    @pydantic.field_validator("annotation_source")
    @classmethod
    def require_independent_source(cls, value: str) -> str:
        """Do not present fake/model-generated fixtures as independent truth."""
        if value != "human":
            raise ValueError(
                "Independent comparison requires human review labels"
            )
        return value
