"""Explicit offline replay: no transport or credentials are accepted here."""

import base64

from binfocheck.domain.observations import CaptureRequest, Observation
from binfocheck.domain.storage import ArtifactStore, IdRequest, RecordStore

from .errors import AcquisitionError, boundary, require
from .normalize import normalize
from .persistence import load_receipt, save_records
from .transport import HttpResponse


@boundary
def replay_capture(records: RecordStore, artifacts: ArtifactStore, request_id: str) -> Observation:
    request = require(records.get_record(IdRequest(id=request_id)))
    if not isinstance(request, CaptureRequest):
        raise AcquisitionError("invalid_capture_request")
    receipt = load_receipt(artifacts, request_id)
    response: HttpResponse | None = None
    if receipt.raw_artifact is not None:
        payload = require(artifacts.get_artifact(IdRequest(id=receipt.raw_artifact.id)))
        if payload.ref != receipt.raw_artifact or receipt.http_status is None:
            raise AcquisitionError("invalid_acquisition_receipt")
        response = HttpResponse(
            payload=base64.b64decode(payload.content_base64, validate=True),
            status=receipt.http_status,
            headers=tuple(receipt.response_headers.items()),
        )
    capture = normalize(request, response, receipt.received_at, receipt.transport_error)
    if capture.receipt != receipt:
        raise AcquisitionError("replay_receipt_mismatch")
    return save_records(records, capture)
