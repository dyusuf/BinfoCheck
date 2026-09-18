"""Version-one value types. No I/O or business decisions happen in these models."""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

Id = Annotated[str, Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")]
NonEmpty = Annotated[str, Field(min_length=1)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonNegative = Annotated[int, Field(ge=0)]
Positive = Annotated[int, Field(gt=0)]
Score = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Finite = Annotated[float, Field(allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)


class RecordBase(Contract):
    id: Id
    schema_version: Literal["1"] = "1"


class Availability(StrEnum):
    AVAILABLE = "available"
    INCOMPLETE = "incomplete"
    UNAVAILABLE = "unavailable"


class Available[T](Contract):
    availability: Availability
    data: T | None
    reason: NonEmpty | None = None

    @model_validator(mode="after")
    def consistent_availability(self) -> Self:
        if self.availability == Availability.UNAVAILABLE:
            if self.data is not None or self.reason is None:
                raise ValueError("unavailable_requires_null_data_and_reason")
        elif self.data is None:
            raise ValueError("available_or_incomplete_requires_data")
        if self.availability == Availability.INCOMPLETE and self.reason is None:
            raise ValueError("incomplete_requires_reason")
        return self


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class CitationStatus(StrEnum):
    YES = "yes"
    NO = "no"
    UNCLEAR = "unclear"


class CorrespondenceStatus(StrEnum):
    MATCH = "match"
    PARTIAL = "partial_match"
    NO_MATCH = "no_match"
    UNCERTAIN = "uncertain"
    NOT_ASSESSED = "not_assessed"


class FindingStatus(StrEnum):
    CATEGORIZED = "categorized"
    NO_MATCH = "no_match_found"
    CITATION_UNCLEAR = "citation_unclear"
    INSUFFICIENT = "not_enough_evidence"
    PENDING = "pending"
    FAILED = "processing_failed"


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CORRECTED = "corrected"


def strict_category(value: object) -> object:
    # Literal integer validation alone accepts numerically equal bool/float values.
    if type(value) is not int:
        raise ValueError("category_must_be_integer")
    return value


Category = Annotated[Literal[1, 2, 3, 4], BeforeValidator(strict_category)]


class ErrorDetail(Contract):
    code: NonEmpty
    message: NonEmpty
    retryable: bool = False
    provider_request_id: str | None = None


class Outcome[T](Contract):
    status: Literal["succeeded", "failed", "skipped"]
    value: T | None
    error: ErrorDetail | None
    reason: NonEmpty | None = None

    @model_validator(mode="after")
    def consistent_outcome(self) -> Self:
        if self.status == "succeeded":
            if self.value is None or self.error is not None:
                raise ValueError("success_requires_value_without_error")
        elif self.value is not None:
            raise ValueError("unsuccessful_outcome_cannot_have_value")
        if self.status == "failed" and self.error is None:
            raise ValueError("failure_requires_error")
        if self.status == "skipped" and (self.reason is None or self.error is not None):
            raise ValueError("skipped_requires_reason_without_error")
        return self


class VersionRef(Contract):
    name: NonEmpty
    version: NonEmpty
    sha256: Digest | None = None


class Settings(Contract):
    version: VersionRef
    values: dict[str, JsonValue]


class UTCRecord(RecordBase):
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def utc_only(cls, value: datetime) -> datetime:
        return require_utc(value)


def require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp_must_be_utc")
    return value


class DerivedRecord(UTCRecord):
    analysis_run_id: Id
    input_ids: Annotated[tuple[Id, ...], Field(min_length=1)]
