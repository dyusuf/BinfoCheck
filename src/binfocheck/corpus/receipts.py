"""Supplementary capture artifacts, not new domain record kinds."""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from binfocheck.domain.common import Contract, Id, UTCRecord, VersionRef, require_utc

from .config import FETCH_VERSION, URLS, FetchPolicy


class Receipt(UTCRecord):
    format: Literal["t06-transport/1"] = "t06-transport/1"
    batch_id: Id
    url: str
    ordinal: Annotated[int, Field(ge=0, le=5)]
    status: int | None
    headers: dict[str, str]
    omitted_headers: tuple[str, ...]
    body_artifact_id: Id | None
    encoded_artifact_id: Id | None
    partial_artifact_id: Id | None
    complete: bool
    dispatched: bool
    received_bytes: int | None
    decoded_bytes: int | None
    error: str | None
    finished_at: datetime
    fetch_version: VersionRef = FETCH_VERSION

    @model_validator(mode="after")
    def consistent_receipt(self) -> Self:
        require_utc(self.finished_at)
        if self.finished_at < self.created_at:
            raise ValueError("receipt_time_order")
        if self.complete and (self.body_artifact_id is None or self.error is not None):
            raise ValueError("complete_receipt_requires_body_without_error")
        if not self.complete and (self.body_artifact_id is not None or self.error is None):
            raise ValueError("incomplete_receipt_requires_error_without_body")
        return self


class Batch(UTCRecord):
    format: Literal["t06-batch/1"] = "t06-batch/1"
    urls: tuple[str, ...] = URLS
    origin: Literal["synthetic", "live"]
    receipt_ids: tuple[Id, ...]
    robots_receipt_id: Id | None
    requests_dispatched: Annotated[int, Field(ge=0, le=6)]
    policy: FetchPolicy = FetchPolicy()


class AuthorizationEvidence(Contract):
    """Restricted immutable record of the operator-supplied capture approval."""

    format: Literal["t06-live-authorization/1"] = "t06-live-authorization/1"
    batch_id: Id
    approval_reference: str
    policy_sha256: str
    robots_url: str
    page_urls: tuple[str, ...]
    fetch_policy: FetchPolicy
