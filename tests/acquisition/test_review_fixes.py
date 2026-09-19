import hashlib
import json
from pathlib import Path

import pytest
from pydantic import JsonValue

from binfocheck.acquisition import CapturePolicy, DataForSEOObservationProvider, replay_capture
from binfocheck.acquisition.config import LiveAuthorization, request_body
from binfocheck.acquisition.live_check import main
from binfocheck.acquisition.normalize import normalize, object_value
from binfocheck.acquisition.persistence import load_receipt
from binfocheck.storage import SQLiteStore
from tests.storage.helpers import failure

from .helpers import AT, FakeTransport, Store, fixture, request, response, task


def test_fixture_tag_matches_outbound_request_and_extra_fields_are_allowed() -> None:
    data = fixture()
    returned = object_value(task(data)["data"])
    assert returned["tag"] == json.loads(request_body(request()))[0]["tag"]
    assert normalize(request(), response(data), AT).observation.status == "succeeded"
    returned["provider_added_field"] = {"canonicalized": True}
    returned["location_name"] = "Provider canonical location label"
    assert normalize(request(), response(data), AT).observation.status == "succeeded"


@pytest.mark.parametrize("returned", [None, [], "not-object", {}, {"tag": "wrong"}, {"tag": 1}])
def test_invalid_correlation_is_typed_and_replays(store: Store, returned: JsonValue) -> None:
    data = fixture()
    task(data)["data"] = returned
    transport = FakeTransport(response(data))
    result = DataForSEOObservationProvider(store, store, transport, clock=lambda: AT).capture(
        request()
    )
    failure(result, "response_correlation_failed")
    failure(replay_capture(store, store, request().id), "response_correlation_failed")
    assert len(transport.calls) == 1
    assert load_receipt(store, request().id).normalization_error is not None


def test_missing_task_data_fails_correlation() -> None:
    data = fixture()
    del task(data)["data"]
    capture = normalize(request(), response(data), AT)
    assert capture.observation.error is not None
    assert capture.observation.error.code == "response_correlation_failed"
    assert capture.observation.answer_text_id is None


@pytest.mark.parametrize(
    ("envelope", "task_cost", "ceiling", "verified"),
    [
        (0.004, 0.004, 0.01, True),
        (0.004, None, 0.01, True),
        (None, 0.004, 0.01, True),
        (None, None, 0.01, False),
        (0.004, 0.006, 0.01, False),
        (0.006, 0.004, 0.01, False),
        (0.02, 0.02, 0.01, False),
        (0.004, 0.02, 0.01, False),
        (0.02, 0.004, 0.01, False),
        (0.004, 0.0040000005, 0.01, True),
        (0.004, 0.004000002, 0.01, False),
        (0.01, 0.0100000005, 0.01, False),
        (0.0, 0.0, 0.01, True),
    ],
)
def test_budget_exit_status_with_mocked_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    envelope: float | None,
    task_cost: float | None,
    ceiling: float,
    verified: bool,
) -> None:
    data = fixture()
    data["cost"] = envelope
    task(data)["cost"] = task_cost
    transport = FakeTransport(response(data))

    def fake_transport(*args: object) -> FakeTransport:
        return transport

    monkeypatch.setattr("binfocheck.acquisition.live_check.HttpsTransport", fake_transport)
    monkeypatch.setenv("DATAFORSEO_LOGIN", "synthetic-test-login")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "synthetic-test-password")
    authorization = LiveAuthorization(
        approval_reference="synthetic-offline-test-only",
        request_sha256=hashlib.sha256(request_body(request())).hexdigest(),
        cost_ceiling_usd=ceiling,
        verified_request_price_usd=0.004,
    )
    files = {
        "request": request().model_dump_json(),
        "authorization": authorization.model_dump_json(),
        "policy": CapturePolicy().model_dump_json(),
    }
    argv = ["mocked-live-check"]
    for name, content in files.items():
        path = tmp_path / (name + ".json")
        path.write_text(content)
        argv.extend(["--" + name, str(path)])
    root = tmp_path / "store"
    argv.extend(["--store", str(root)])
    monkeypatch.setattr("sys.argv", argv)
    assert main() == (0 if verified else 2)
    output = json.loads(capsys.readouterr().out)
    assert output["budget_verified"] is verified
    assert output["envelope_cost_usd"] == envelope
    assert output["task_cost_usd"] == task_cost
    assert len(transport.calls) == 1
    with SQLiteStore(root) as store:
        receipt = load_receipt(store, request().id)
        assert receipt.envelope_cost_usd == envelope
        assert receipt.task_cost_usd == task_cost
