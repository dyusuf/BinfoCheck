"""Offline replay accepts stores and IDs only: never credentials or a transport."""

import base64

from pydantic import ValidationError

from binfocheck.domain.common import Outcome
from binfocheck.domain.decisions import DecisionRecord
from binfocheck.domain.storage import ArtifactStore, IdRequest, RecordStore

from .config import LocalGenerationConfig
from .errors import ModelError, failure, require
from .json import canonical, digest
from .persistence import load, normalize, record_outcome, usage_metadata
from .receipt import ModelReceipt, PreparedRequest, role_id
from .transport import ALLOWED_HEADERS, HttpResponse


def replay(
    records: RecordStore, artifacts: ArtifactStore, record_id: str
) -> Outcome[DecisionRecord]:
    try:
        receipt_payload = require(
            artifacts.get_artifact(IdRequest(id=role_id(record_id, "receipt")))
        )
        receipt = ModelReceipt.model_validate_json(load(artifacts, receipt_payload.ref))
        if receipt.record_id != record_id or not set(receipt.response_headers).issubset(
            ALLOWED_HEADERS
        ):
            raise ModelError("replay_receipt_mismatch")
        prepared = PreparedRequest.model_validate_json(load(artifacts, receipt.prepared_artifact))
        if isinstance(prepared.config, LocalGenerationConfig) and receipt.dispatched:
            runtime = require(artifacts.get_artifact(IdRequest(id=role_id(record_id, "runtime"))))
            if digest(load(artifacts, runtime.ref)) != prepared.config.runtime_manifest_sha256:
                raise ModelError("local_runtime_manifest_mismatch")
        if (
            prepared.record_id != record_id
            or receipt.prepared_artifact.id != role_id(record_id, "prepared")
            or receipt.outbound_artifact.id != role_id(record_id, "outbound")
            or load(artifacts, receipt.outbound_artifact) != canonical(prepared.body)
        ):
            raise ModelError("replay_request_mismatch")
        for id, expected in prepared.input_hashes.items():
            payload = require(artifacts.get_artifact(IdRequest(id=id)))
            if digest(load(artifacts, payload.ref)) != expected:
                raise ModelError("replay_input_mismatch")
        for value in prepared.resource_bytes_base64.values():
            base64.b64decode(value, validate=True)
        raw = None
        if receipt.raw_response_artifact is not None:
            if receipt.raw_response_artifact.id != role_id(record_id, "raw"):
                raise ModelError("replay_artifact_mismatch")
            raw = load(artifacts, receipt.raw_response_artifact)
        response = HttpResponse(
            raw,
            receipt.http_status,
            tuple(receipt.response_headers.items()),
            receipt.complete,
            receipt.dispatched,
            receipt.outcome_uncertain,
            receipt.transport_error,
        )
        record, structured, body = normalize(
            prepared, response, receipt.started_at, receipt.finished_at
        )
        if record.error != receipt.normalization_error:
            raise ModelError("replay_receipt_mismatch")
        if structured is not None:
            if (
                receipt.structured_output_artifact is None
                or receipt.structured_output_artifact.id != role_id(record_id, "structured")
                or load(artifacts, receipt.structured_output_artifact) != canonical(structured)
            ):
                raise ModelError("replay_output_mismatch")
        elif receipt.structured_output_artifact is not None:
            raise ModelError("replay_output_mismatch")
        _, estimate, basis = usage_metadata(prepared.config.provider, body)
        if (
            receipt.estimated_cost_usd != estimate
            or receipt.estimate_basis != basis
            or receipt.raw_usage != body.get("usage")
        ):
            raise ModelError("replay_usage_mismatch")
        require(records.append_decision(record))
        return record_outcome(record)
    except (ModelError, ValidationError, ValueError, KeyError):
        return failure(ModelError("replay_failed").detail)


replay_decision = replay
replay_generation = replay
