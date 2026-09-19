"""Adapter-owned artifact contents, not new domain records or wire contracts."""

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import JsonValue, TypeAdapter, field_validator

from binfocheck.domain.common import Available, Contract, ErrorDetail, Id, require_utc
from binfocheck.domain.decisions import Usage
from binfocheck.domain.observations import Observation
from binfocheck.domain.records import Record
from binfocheck.domain.text import ArtifactRef

from .transport import ALLOWED_HEADERS

JSON_OBJECT: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])


def identifier(request_id: str, role: str, location: str = "") -> str:
    content = json.dumps([request_id, role, location], ensure_ascii=False, separators=(",", ":"))
    return "capture-" + role + "-" + hashlib.sha256(content.encode()).hexdigest()


class CaptureReceipt(Contract):
    receipt_version: Literal["1"] = "1"
    normalization_version: Literal["1"] = "1"
    request_id: Id
    observation_id: Id
    received_at: datetime
    raw_artifact: ArtifactRef | None
    http_status: int | None
    response_headers: dict[str, str]
    provider_request_id: str | None
    envelope_status: int | None
    task_status: int | None
    envelope_cost_usd: float | None
    task_cost_usd: float | None
    provider_time: str | None
    usage: Available[Usage]
    transport_error: ErrorDetail | None
    normalization_error: ErrorDetail | None
    answer_location: str | None
    diagnostics: tuple[str, ...]

    @field_validator("received_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return require_utc(value)

    @field_validator("response_headers")
    @classmethod
    def allowlisted(cls, value: dict[str, str]) -> dict[str, str]:
        if not set(value).issubset(ALLOWED_HEADERS):
            raise ValueError("non_allowlisted_transport_metadata")
        return value


class NormalizedCapture(Contract):
    receipt: CaptureReceipt
    observation: Observation
    records: tuple[Record, ...]
