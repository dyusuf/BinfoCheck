from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from .common import (
    Available,
    Category,
    Contract,
    DerivedRecord,
    ErrorDetail,
    FindingStatus,
    Finite,
    Id,
    NonEmpty,
    NonNegative,
    Positive,
    ProcessingStatus,
    Settings,
    UTCRecord,
    VersionRef,
    require_utc,
)
from .decisions import Usage


class Budget(Contract):
    request_limit: NonNegative
    cost_limit: Annotated[Finite, Field(ge=0)]
    currency: NonEmpty
    timeout_seconds: Annotated[Finite, Field(gt=0)]
    concurrency: Positive
    retry_limit: NonNegative


class RunManifest(UTCRecord):
    kind: Literal["run_manifest"] = "run_manifest"
    input_ids: tuple[Id, ...]
    observation_ids: tuple[Id, ...]
    corpus_manifest_id: Id | None
    purpose: Literal["diagnostic", "monitoring"]
    mode: Literal["capture", "reanalysis"]
    capture_settings: Settings
    configuration: VersionRef
    model_ids: tuple[str, ...]
    prompt_versions: tuple[VersionRef, ...]
    rubric_versions: tuple[VersionRef, ...]
    budget: Budget
    status: ProcessingStatus


class StepAttempt(DerivedRecord):
    kind: Literal["step_attempt"] = "step_attempt"
    step: NonEmpty
    work_key: NonEmpty
    attempt_number: Positive
    status: ProcessingStatus
    output_ids: tuple[Id, ...]
    started_at: datetime
    finished_at: datetime | None
    provider_request_id: str | None
    usage: Available[Usage]
    error: ErrorDetail | None
    outcome_uncertain: bool

    @field_validator("started_at", "finished_at")
    @classmethod
    def utc_timing(cls, value: datetime | None) -> datetime | None:
        return require_utc(value) if value is not None else None

    @model_validator(mode="after")
    def attempt_state(self) -> Self:
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("attempt_timing_reversed")
        if (self.status == ProcessingStatus.FAILED) != (self.error is not None):
            raise ValueError("attempt_failure_requires_error_only_on_failure")
        terminal = self.status in {"succeeded", "failed", "skipped"}
        if terminal != (self.finished_at is not None):
            raise ValueError("terminal_attempt_requires_finish_time")
        if self.outcome_uncertain and self.status != ProcessingStatus.FAILED:
            raise ValueError("uncertain_attempt_cannot_be_successful")
        return self


class ReviewCorrection(Contract):
    status: FindingStatus
    category: Category | None

    @model_validator(mode="after")
    def corrected_category(self) -> Self:
        if (self.status == FindingStatus.CATEGORIZED) != (self.category is not None):
            raise ValueError("correction_category_status_mismatch")
        return self


class Review(DerivedRecord):
    kind: Literal["review"] = "review"
    finding_id: Id
    reviewer_id: NonEmpty
    decision: Literal["confirmed", "rejected", "corrected"]
    note: str
    correction: ReviewCorrection | None
    supersedes_review_id: Id | None = None

    @model_validator(mode="after")
    def review_state(self) -> Self:
        if (self.decision == "corrected") != (self.correction is not None):
            raise ValueError("corrected_review_requires_correction_only")
        if self.supersedes_review_id == self.id:
            raise ValueError("review_cannot_supersede_itself")
        return self
