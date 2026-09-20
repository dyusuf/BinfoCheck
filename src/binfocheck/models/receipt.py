"""Versioned adapter artifact contents, not additional domain wire records."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, JsonValue, field_validator

from binfocheck.domain.common import Contract, Digest, ErrorDetail, Finite, Id, require_utc
from binfocheck.domain.interfaces import DecisionRequest, GenerationRequest
from binfocheck.domain.text import ArtifactRef

from .config import AdapterConfig
from .json import canonical, digest


class PreparedRequest(Contract):
    preparation_version: Literal["1"] = "1"
    request: DecisionRequest | GenerationRequest
    config: AdapterConfig
    body: dict[str, JsonValue]
    resource_bytes_base64: dict[str, str]
    input_hashes: dict[str, Digest]

    @property
    def work_key(self) -> str:
        return digest(canonical(self.model_dump(mode="json")))

    @property
    def record_id(self) -> str:
        kind = "decision" if isinstance(self.request, DecisionRequest) else "generation"
        return "model-" + kind + "-" + self.work_key


def role_id(record_id: str, role: str) -> str:
    return "model-artifact-" + digest(canonical([record_id, role]))


class ModelReceipt(Contract):
    receipt_version: Literal["1"] = "1"
    normalization_version: Literal["1"] = "1"
    record_id: Id
    prepared_artifact: ArtifactRef
    outbound_artifact: ArtifactRef
    raw_response_artifact: ArtifactRef | None
    structured_output_artifact: ArtifactRef | None
    started_at: datetime
    finished_at: datetime
    elapsed_seconds: Annotated[Finite, Field(ge=0)] | None
    http_status: int | None
    response_headers: dict[str, str]
    complete: bool
    dispatched: bool
    outcome_uncertain: bool
    transport_error: ErrorDetail | None
    normalization_error: ErrorDetail | None
    provider_response_id: str | None
    raw_usage: JsonValue
    estimated_cost_usd: Annotated[Finite, Field(ge=0)] | None
    estimate_basis: str
    pricing_version: Literal["2026-09-19"] = "2026-09-19"

    @field_validator("started_at", "finished_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return require_utc(value)
