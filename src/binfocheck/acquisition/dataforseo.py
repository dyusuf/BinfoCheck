"""Single-attempt acquisition boundary. Calling replay never enters this transport path."""

from collections.abc import Callable
from datetime import UTC, datetime

from binfocheck.domain.observations import CaptureRequest, Observation
from binfocheck.domain.storage import ArtifactStore, IdRequest, RecordStore

from .config import CapturePolicy, request_body
from .errors import AcquisitionError, PersistenceError, boundary, require
from .persistence import persist_response
from .transport import HttpResponse, Transport


def utc_now() -> datetime:
    return datetime.now(UTC)


class DataForSEOObservationProvider:
    def __init__(
        self,
        records: RecordStore,
        artifacts: ArtifactStore,
        transport: Transport,
        policy: CapturePolicy | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._records = records
        self._artifacts = artifacts
        self._transport = transport
        self._policy = policy or CapturePolicy()
        self._clock = clock
        self._attempts = 0

    @boundary
    def capture(self, request: CaptureRequest) -> Observation:
        request = CaptureRequest.model_validate_json(request.model_dump_json(warnings="error"))
        policy = CapturePolicy.model_validate_json(self._policy.model_dump_json())
        body = request_body(request)
        if self._attempts >= policy.request_limit:
            raise AcquisitionError("request_limit_exhausted")
        existing = self._records.get_record(IdRequest(id=request.id))
        if existing.status == "succeeded":
            raise AcquisitionError("capture_already_started_use_offline_replay")
        if existing.error is None or existing.error.code != "not_found":
            raise PersistenceError(existing.error or AcquisitionError("storage_failed").detail)
        require(self._records.put_record(request))  # Must precede every possible dispatch.
        self._attempts += 1
        response: HttpResponse | None = None
        error = None
        try:
            response = self._transport.post(body, policy)
            if len(response.payload) > policy.max_payload_bytes:
                raise AcquisitionError("response_too_large")
        except AcquisitionError as caught:
            error = caught.detail
        except (OSError, TimeoutError):
            error = AcquisitionError("capture_outcome_uncertain").detail
        return persist_response(
            self._records, self._artifacts, request, response, self._clock(), error
        )
