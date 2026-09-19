import base64
from pathlib import Path

import pytest

from binfocheck.acquisition import CapturePolicy, DataForSEOObservationProvider, replay_capture
from binfocheck.acquisition.config import request_tag
from binfocheck.acquisition.errors import AcquisitionError
from binfocheck.acquisition.normalize import parse
from binfocheck.acquisition.persistence import load_receipt
from binfocheck.acquisition.receipt import identifier
from binfocheck.domain.common import ErrorDetail, Outcome
from binfocheck.domain.interfaces import ObservationProvider
from binfocheck.domain.observations import Observation
from binfocheck.domain.records import Record, RecordSet
from binfocheck.domain.storage import IdRequest
from binfocheck.domain.validation import validate_links
from binfocheck.storage import MemoryStore, SQLiteStore
from tests.storage.helpers import all_records, failure, success

from .helpers import AT, FIXTURE, FakeTransport, Store, fixture, overview, request, response, task


def test_capture_then_replay_exact_payload_and_no_network(store: Store) -> None:
    transport = FakeTransport(response())
    provider: ObservationProvider = DataForSEOObservationProvider(
        store, store, transport, clock=lambda: AT
    )
    observation = success(provider.capture(request()))
    assert len(transport.calls) == 1
    assert observation.raw_artifact_id is not None
    raw = success(store.get_artifact(IdRequest(id=observation.raw_artifact_id)))
    assert base64.b64decode(raw.content_base64) == FIXTURE.read_bytes()
    original = all_records(store)
    validate_links(RecordSet(records=original))
    replayed = success(replay_capture(store, store, request().id))
    assert replayed == observation
    assert all_records(store) == original
    assert len(transport.calls) == 1
    receipt = load_receipt(store, request().id)
    assert receipt.received_at == AT
    assert receipt.response_headers == {
        "content-type": "application/json",
        "x-request-id": "synthetic-http-id",
    }
    assert receipt.answer_location == "/tasks/0/result/0/items/0/markdown"


def test_persistent_close_reopen(tmp_path: Path) -> None:
    with SQLiteStore(tmp_path) as store:
        transport = FakeTransport(response())
        original = success(
            DataForSEOObservationProvider(store, store, transport, clock=lambda: AT).capture(
                request()
            )
        )
        saved = all_records(store)
    with SQLiteStore(tmp_path) as store:
        assert success(replay_capture(store, store, request().id)) == original
        assert all_records(store) == saved
        validate_links(RecordSet(records=saved))
        assert original.raw_artifact_id is not None
        raw = success(store.get_artifact(IdRequest(id=original.raw_artifact_id)))
        assert base64.b64decode(raw.content_base64) == FIXTURE.read_bytes()


def test_request_persisted_before_dispatch_and_raw_before_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with MemoryStore() as store:

        class CheckingTransport(FakeTransport):
            def post(self, body: bytes, policy: CapturePolicy):
                assert success(store.get_record(IdRequest(id=request().id))) == request()
                return super().post(body, policy)

        def check_parse(payload: bytes):
            raw = success(store.get_artifact(IdRequest(id=identifier(request().id, "raw"))))
            assert base64.b64decode(raw.content_base64) == payload
            return parse(payload)

        monkeypatch.setattr("binfocheck.acquisition.normalize.parse", check_parse)
        success(
            DataForSEOObservationProvider(
                store, store, CheckingTransport(response()), clock=lambda: AT
            ).capture(request())
        )


@pytest.mark.parametrize("kind", ["text", "source_reference", "observation"])
def test_offline_replay_finishes_partial_persistence(kind: str) -> None:
    class FailingStore(MemoryStore):
        fail_kind: str | None = kind

        def put_record(self, request: Record) -> Outcome[Record]:
            if request.kind == self.fail_kind:
                return Outcome(
                    status="failed",
                    value=None,
                    error=ErrorDetail(code="storage_io_error", message="storage io error"),
                )
            return super().put_record(request)

    with FailingStore() as store:
        transport = FakeTransport(response())
        failure(
            DataForSEOObservationProvider(store, store, transport, clock=lambda: AT).capture(
                request()
            ),
            "storage_io_error",
        )
        # Raw response and receipt are already stored; no request is required to repair records.
        assert load_receipt(store, request().id).raw_artifact is not None
        store.fail_kind = None
        observation = success(replay_capture(store, store, request().id))
        assert observation.status == "succeeded"
        validate_links(RecordSet(records=all_records(store)))
        assert len(transport.calls) == 1


def test_request_write_failure_prevents_dispatch() -> None:
    class FailingStore(MemoryStore):
        def put_record(self, request: Record) -> Outcome[Record]:
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="storage_io_error", message="storage io error"),
            )

    with FailingStore() as store:
        transport = FakeTransport(response())
        failure(
            DataForSEOObservationProvider(store, store, transport).capture(request()),
            "storage_io_error",
        )
        assert transport.calls == []


@pytest.mark.parametrize(
    "error", [TimeoutError("SYNTHETIC SECRET"), AcquisitionError("capture_outcome_uncertain")]
)
def test_uncertain_outcome_not_retried_and_failure_replays(store: Store, error: Exception) -> None:
    transport = FakeTransport(error)
    provider = DataForSEOObservationProvider(store, store, transport, clock=lambda: AT)
    outcome = provider.capture(request())
    failure(outcome, "capture_outcome_uncertain")
    assert "SYNTHETIC SECRET" not in outcome.model_dump_json()
    assert len(transport.calls) == 1
    failure(provider.capture(request()), "request_limit_exhausted")
    failure(replay_capture(store, store, request().id), "capture_outcome_uncertain")
    saved = success(store.get_record(IdRequest(id=identifier(request().id, "observation"))))
    assert (
        isinstance(saved, Observation) and saved.status == "failed" and saved.answer_text_id is None
    )
    another = FakeTransport(response())
    failure(
        DataForSEOObservationProvider(store, store, another).capture(request()),
        "capture_already_started_use_offline_replay",
    )
    assert another.calls == []


def test_rate_limit_no_retry(store: Store) -> None:
    transport = FakeTransport(response(status=429))
    outcome = DataForSEOObservationProvider(store, store, transport, clock=lambda: AT).capture(
        request()
    )
    failure(outcome, "rate_limited")
    assert len(transport.calls) == 1
    failure(replay_capture(store, store, request().id), "rate_limited")


def test_absent_answer_persists_raw_and_terminal_failure(store: Store) -> None:
    data = fixture()
    overview(data)["markdown"] = " \n"
    transport = FakeTransport(response(data))
    failure(
        DataForSEOObservationProvider(store, store, transport, clock=lambda: AT).capture(request()),
        "answer_absent",
    )
    receipt = load_receipt(store, request().id)
    assert receipt.raw_artifact is not None
    raw = success(store.get_artifact(IdRequest(id=receipt.raw_artifact.id)))
    assert base64.b64decode(raw.content_base64) == response(data).payload
    failure(replay_capture(store, store, request().id), "answer_absent")
    validate_links(RecordSet(records=all_records(store)))


def test_zero_limit_and_invalid_settings_prevent_dispatch(store: Store) -> None:
    transport = FakeTransport(response())
    failure(
        DataForSEOObservationProvider(
            store, store, transport, CapturePolicy(request_limit=0)
        ).capture(request()),
        "request_limit_exhausted",
    )
    bad = request()
    bad.requested_settings.values["language_code"] = "en"
    failure(
        DataForSEOObservationProvider(store, store, transport).capture(bad), "invalid_capture_input"
    )
    bad.requested_settings.values["password"] = "SYNTHETIC SECRET"
    failure(
        DataForSEOObservationProvider(store, store, transport).capture(bad), "invalid_capture_input"
    )
    assert transport.calls == []
    assert all_records(store) == ()


def test_new_capture_id_not_same_identity(store: Store) -> None:
    first_payload = fixture()
    second_payload = fixture()
    task(first_payload)["data"] = {"tag": request_tag(request("capture-a"))}
    task(second_payload)["data"] = {"tag": request_tag(request("capture-b"))}
    first = success(
        DataForSEOObservationProvider(
            store, store, FakeTransport(response(first_payload)), clock=lambda: AT
        ).capture(request("capture-a"))
    )
    second = success(
        DataForSEOObservationProvider(
            store, store, FakeTransport(response(second_payload)), clock=lambda: AT
        ).capture(request("capture-b"))
    )
    assert first.id != second.id
    assert first.answer_text_id != second.answer_text_id


def test_malformed_payload_saved_exactly(store: Store) -> None:
    raw_response = response()
    from binfocheck.acquisition.transport import HttpResponse

    malformed = HttpResponse(b" \n{ invalid JSON \t", 200, raw_response.headers)
    failure(
        DataForSEOObservationProvider(
            store, store, FakeTransport(malformed), clock=lambda: AT
        ).capture(request()),
        "malformed_response",
    )
    receipt = load_receipt(store, request().id)
    assert receipt.raw_artifact is not None
    payload = success(store.get_artifact(IdRequest(id=receipt.raw_artifact.id)))
    assert base64.b64decode(payload.content_base64) == malformed.payload
    failure(replay_capture(store, store, request().id), "malformed_response")
