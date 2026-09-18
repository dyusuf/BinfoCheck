"""Storage interfaces only; T11A owns backend and durable-write behavior.

Writes must be immutable by ID: identical content is idempotent, different content
is an explicit conflict. Decisions/reviews append new IDs, never overwrite history.
Get/list operations return typed failures; absence is not an empty success. Listing
is bounded and continuation tokens are opaque. No credentials belong in artifacts.
"""

import base64
import binascii
import hashlib
from typing import Annotated, Protocol, Self

from pydantic import Field, model_validator

from .common import Contract, Id, Outcome
from .decisions import DecisionRecord
from .records import Record
from .runs import Review
from .text import ArtifactRef


class IdRequest(Contract):
    id: Id


class ArtifactPayload(Contract):
    """Base64 is an exchange encoding; the hash covers the decoded bytes."""

    ref: ArtifactRef
    content_base64: str

    @model_validator(mode="after")
    def content_matches_ref(self) -> Self:
        try:
            content = base64.b64decode(self.content_base64, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("invalid_artifact_base64") from error
        if hashlib.sha256(content).hexdigest() != self.ref.sha256:
            raise ValueError("artifact_hash_mismatch")
        return self


class ListRequest(Contract):
    record_kind: str | None = None
    analysis_run_id: Id | None = None
    limit: Annotated[int, Field(ge=1, le=1000)] = 100
    cursor: str | None = None


class RecordPage(Contract):
    records: tuple[Record, ...]
    next_cursor: str | None


class ArtifactStore(Protocol):
    def put_artifact(self, request: ArtifactPayload) -> Outcome[ArtifactRef]: ...
    def get_artifact(self, request: IdRequest) -> Outcome[ArtifactPayload]: ...


class RecordStore(Protocol):
    def put_record(self, request: Record) -> Outcome[Record]: ...
    def get_record(self, request: IdRequest) -> Outcome[Record]: ...
    def list_records(self, request: ListRequest) -> Outcome[RecordPage]: ...
    def append_decision(self, request: DecisionRecord) -> Outcome[DecisionRecord]: ...
    def append_review(self, request: Review) -> Outcome[Review]: ...
