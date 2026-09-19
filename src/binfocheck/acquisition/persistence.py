"""Use shared stores only. No database access, cross-record transactions, or scheduling."""

import base64
import hashlib
from datetime import datetime

from binfocheck.domain.common import ErrorDetail
from binfocheck.domain.observations import CaptureRequest, Observation
from binfocheck.domain.storage import ArtifactPayload, ArtifactStore, IdRequest, RecordStore
from binfocheck.domain.text import ArtifactRef

from .errors import AcquisitionError, require
from .normalize import normalize, raw_reference
from .receipt import CaptureReceipt, NormalizedCapture, identifier
from .transport import HttpResponse


def artifact(ref: ArtifactRef, content: bytes) -> ArtifactPayload:
    return ArtifactPayload(ref=ref, content_base64=base64.b64encode(content).decode())


def receipt_payload(receipt: CaptureReceipt) -> ArtifactPayload:
    content = receipt.model_dump_json().encode()
    ref = ArtifactRef(
        id=identifier(receipt.request_id, "receipt"),
        storage_key="acquisition/receipt-v1",
        sha256=hashlib.sha256(content).hexdigest(),
        media_type="application/json",
        access="restricted",
    )
    return artifact(ref, content)


def save_records(records: RecordStore, capture: NormalizedCapture) -> Observation:
    for record in capture.records:
        require(records.put_record(record))
    if capture.observation.error:
        raise AcquisitionError(
            capture.observation.error.code, capture.observation.provider_request_id
        )
    return capture.observation


def persist_response(
    records: RecordStore,
    artifacts: ArtifactStore,
    request: CaptureRequest,
    response: HttpResponse | None,
    received_at: datetime,
    error: ErrorDetail | None = None,
) -> Observation:
    # Raw content is durable before the first JSON parse, including malformed/error bodies.
    if response is not None:
        require(
            artifacts.put_artifact(
                artifact(raw_reference(request.id, response.payload), response.payload)
            )
        )
    capture = normalize(request, response, received_at, error)
    require(artifacts.put_artifact(receipt_payload(capture.receipt)))
    return save_records(records, capture)


def load_receipt(artifacts: ArtifactStore, request_id: str) -> CaptureReceipt:
    payload = require(artifacts.get_artifact(IdRequest(id=identifier(request_id, "receipt"))))
    try:
        receipt = CaptureReceipt.model_validate_json(
            base64.b64decode(payload.content_base64, validate=True)
        )
        if receipt.request_id != request_id or receipt.observation_id != identifier(
            request_id, "observation"
        ):
            raise ValueError("mismatch")
        return receipt
    except ValueError:
        raise AcquisitionError("invalid_acquisition_receipt") from None
