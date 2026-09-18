"""Saved text and explicit Unicode code-point locations."""

from typing import Literal, Self

from pydantic import model_validator

from .common import Contract, Digest, Id, NonEmpty, NonNegative, RecordBase, VersionRef


class ArtifactRef(RecordBase):
    kind: Literal["artifact"] = "artifact"
    storage_key: NonEmpty
    sha256: Digest
    media_type: NonEmpty
    access: Literal["shareable_fixture", "restricted"]
    redacted_transport_fields: tuple[str, ...] = ()


class TextRecord(RecordBase):
    kind: Literal["text"] = "text"
    text: str
    artifact_id: Id
    source_text_id: Id | None = None
    transformation: VersionRef | None = None

    @model_validator(mode="after")
    def transformation_provenance(self) -> Self:
        if (self.source_text_id is None) != (self.transformation is None):
            raise ValueError("transformation_requires_source_and_version")
        if self.source_text_id == self.id:
            raise ValueError("text_cannot_transform_itself")
        return self


class SpanRef(Contract):
    text_id: Id
    start: NonNegative
    end: NonNegative
    exact_text: NonEmpty
    source_unit_id: Id | None = None

    @model_validator(mode="after")
    def bounds(self) -> Self:
        if self.end <= self.start:
            raise ValueError("span_end_must_exceed_start")
        if len(self.exact_text) != self.end - self.start:
            raise ValueError("span_length_mismatch")
        return self
