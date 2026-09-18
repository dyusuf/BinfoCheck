from typing import Literal, Self

from pydantic import model_validator

from .common import (
    Available,
    DerivedRecord,
    ErrorDetail,
    Id,
    NonEmpty,
    NonNegative,
    ProcessingStatus,
    Settings,
    UTCRecord,
    VersionRef,
)
from .text import SpanRef


class CaptureRequest(UTCRecord):
    kind: Literal["capture_request"] = "capture_request"
    query_id: Id
    query: NonEmpty
    product: Literal["google_ai_mode"]
    provider: Literal["dataforseo"]
    requested_settings: Settings


class Observation(UTCRecord):
    kind: Literal["observation"] = "observation"
    request_id: Id
    query_id: Id
    product: Literal["google_ai_mode"]
    provider: Literal["dataforseo"]
    requested_settings: Settings
    reported_settings: Available[Settings]
    status: ProcessingStatus
    raw_artifact_id: Id | None
    answer_text_id: Id | None
    source_reference_ids: Available[tuple[Id, ...]]
    citation_reference_ids: Available[tuple[Id, ...]]
    fanout_queries: Available[tuple[str, ...]]
    normalization_version: VersionRef
    provider_request_id: str | None = None
    error: ErrorDetail | None = None

    @model_validator(mode="after")
    def capture_state(self) -> Self:
        if self.status == ProcessingStatus.SUCCEEDED:
            if self.raw_artifact_id is None or self.answer_text_id is None:
                raise ValueError("successful_capture_requires_raw_and_answer")
        if (self.status == ProcessingStatus.FAILED) != (self.error is not None):
            raise ValueError("capture_failure_requires_error_only_on_failure")
        return self


class SourceReference(UTCRecord):
    kind: Literal["source_reference"] = "source_reference"
    observation_id: Id
    url: NonEmpty
    metadata_artifact_id: Id
    metadata_location: NonEmpty
    reference_kind: Literal["citation", "reference", "search_result"]
    excerpt: Available[SpanRef]
    citation_span: SpanRef | None = None
    duplicate_group: Id | None = None


class TextUnit(DerivedRecord):
    kind: Literal["text_unit"] = "text_unit"
    observation_id: Id
    unit_kind: Literal["heading", "paragraph", "bullet", "sentence"]
    order: NonNegative
    parent_unit_id: Id | None = None
    heading_unit_id: Id | None = None
    span: SpanRef
