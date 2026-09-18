from datetime import datetime
from math import fsum, isclose
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, field_validator, model_validator

from .common import (
    Available,
    Contract,
    DerivedRecord,
    ErrorDetail,
    Finite,
    Id,
    NonEmpty,
    NonNegative,
    Score,
    VersionRef,
    require_utc,
)


class Usage(Contract):
    input_tokens: NonNegative | None
    output_tokens: NonNegative | None
    requests: NonNegative | None
    cost: Annotated[Finite, Field(ge=0)] | None
    currency: str | None

    @model_validator(mode="after")
    def cost_currency(self) -> Self:
        if self.cost is not None and self.currency is None:
            raise ValueError("known_cost_requires_currency")
        return self


class DecisionResult(Contract):
    result_kind: Literal["decision"] = "decision"
    allowed_labels: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    label: NonEmpty
    probabilities: Available[dict[str, Score]] = Field(
        description=(
            "Choice probabilities, not independent confidence scores. When available, all labels "
            "must be present and their probabilities must sum to 1 within absolute tolerance 1e-6. "
            "Incomplete distributions retain captured values without normalization."
        )
    )

    @model_validator(mode="after")
    def valid_labels(self) -> Self:
        if len(set(self.allowed_labels)) != len(self.allowed_labels):
            raise ValueError("duplicate_allowed_label")
        if self.label not in self.allowed_labels:
            raise ValueError("unknown_decision_label")
        if self.probabilities.data is not None:
            if not set(self.probabilities.data).issubset(self.allowed_labels):
                raise ValueError("unknown_probability_label")
            if self.probabilities.availability == "available" and set(
                self.probabilities.data
            ) != set(self.allowed_labels):
                raise ValueError("available_probabilities_require_all_labels")
            if self.probabilities.availability == "available" and not isclose(
                fsum(self.probabilities.data.values()), 1.0, rel_tol=0.0, abs_tol=1e-6
            ):
                raise ValueError("available_probabilities_must_sum_to_one")
        return self


class GenerationResult(Contract):
    result_kind: Literal["generation"] = "generation"
    output_schema: VersionRef
    structured_output: dict[str, JsonValue]
    output_artifact_id: Id


ModelResult = Annotated[DecisionResult | GenerationResult, Field(discriminator="result_kind")]


class DecisionRecord(DerivedRecord):
    kind: Literal["decision_record"] = "decision_record"
    task_type: NonEmpty
    input_artifact_ids: tuple[Id, ...]
    requested_model_id: NonEmpty
    returned_model_id: Available[str]
    prompt_version: VersionRef | None
    rubric_version: VersionRef | None
    config_version: VersionRef
    status: Literal["succeeded", "failed"]
    result: ModelResult | None
    usage: Available[Usage]
    started_at: datetime
    finished_at: datetime
    error: ErrorDetail | None
    provider_request_id: str | None

    @field_validator("started_at", "finished_at")
    @classmethod
    def utc_timing(cls, value: datetime) -> datetime:
        return require_utc(value)

    @model_validator(mode="after")
    def model_state(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("model_timing_reversed")
        if self.status == "succeeded" and (self.result is None or self.error is not None):
            raise ValueError("model_success_requires_result_without_error")
        if self.status == "failed" and (self.result is not None or self.error is None):
            raise ValueError("model_failure_requires_error_without_result")
        return self
