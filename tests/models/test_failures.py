from dataclasses import replace

import pytest

from binfocheck.domain.common import ErrorDetail, Outcome
from binfocheck.domain.decisions import DecisionRecord
from binfocheck.domain.storage import ArtifactPayload, IdRequest, ListRequest
from binfocheck.domain.text import ArtifactRef
from binfocheck.models import JevDecisionModel, OpenAIGenerationModel
from binfocheck.models.config import ModelAdapterConfig
from binfocheck.models.errors import ModelError, require
from binfocheck.models.json import canonical, object_value
from binfocheck.models.persistence import artifact_ref, prepare, save
from binfocheck.models.receipt import role_id
from binfocheck.models.replay import replay
from binfocheck.models.resources import ResourceRegistry
from binfocheck.models.transport import HttpResponse
from binfocheck.storage import MemoryStore

from .helpers import (
    Clock,
    FakeTransport,
    body,
    decision_request,
    generation_request,
    receipt,
    resources,
    response,
    seed,
)


class WriteFailureStore(MemoryStore):
    fail_role: str | None = None
    fail_decision = False

    def put_artifact(self, request: ArtifactPayload) -> Outcome[ArtifactRef]:
        if request.ref.storage_key == "models/v1/" + str(self.fail_role):
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="storage_io_error", message="storage error"),
            )
        return super().put_artifact(request)

    def append_decision(self, request: DecisionRecord) -> Outcome[DecisionRecord]:
        if self.fail_decision:
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="storage_io_error", message="storage error"),
            )
        return super().append_decision(request)


@pytest.mark.parametrize("role", ["prepared", "outbound", "intent"])
def test_failed_preflight_write_never_dispatches(role: str) -> None:
    with WriteFailureStore() as store:
        request = decision_request()
        seed(store, request, "jev")
        store.fail_role = role
        transport = FakeTransport(response("jev"))
        result = JevDecisionModel(
            store, store, resources(), ModelAdapterConfig(provider="jev"), transport
        ).decide(request)
        assert result.error is not None and result.error.code == "storage_failure"
        assert transport.calls == []


def test_failed_record_write_can_replay_without_resending() -> None:
    with WriteFailureStore() as store:
        request = decision_request()
        seed(store, request, "jev")
        store.fail_decision = True
        transport = FakeTransport(response("jev"))
        config = ModelAdapterConfig(provider="jev")
        adapter = JevDecisionModel(store, store, resources(), config, transport, Clock())
        assert adapter.decide(request).status == "failed"
        store.fail_decision = False
        assert adapter.decide(request).status == "succeeded"
        assert len(transport.calls) == 1


@pytest.mark.parametrize("role", ["raw", "receipt"])
def test_failed_post_dispatch_write_blocks_new_request(role: str) -> None:
    with WriteFailureStore() as store:
        request = decision_request()
        seed(store, request, "jev")
        store.fail_role = role
        transport = FakeTransport(response("jev"))
        config = ModelAdapterConfig(provider="jev")
        adapter = JevDecisionModel(store, store, resources(), config, transport, Clock())
        assert adapter.decide(request).status == "failed"
        store.fail_role = None
        retry = adapter.decide(request)
        assert retry.error is not None
        assert retry.error.code == (
            "raw_persistence_failed" if role == "raw" else "storage_failure"
        )
        assert len(transport.calls) == 1
        stored = require(
            store.get_record(IdRequest(id=prepare(request, config, resources(), store).record_id))
        )
        assert isinstance(stored, DecisionRecord) and stored.status == "failed"


def test_uncertain_transport_outcome_replays_failure_without_usage() -> None:
    with MemoryStore() as store:
        request = decision_request()
        seed(store, request, "jev")
        config = ModelAdapterConfig(provider="jev")
        transport = FakeTransport(
            HttpResponse(
                None,
                None,
                complete=False,
                outcome_uncertain=True,
                error=ModelError("dispatch_outcome_uncertain").detail,
            )
        )
        adapter = JevDecisionModel(store, store, resources(), config, transport, Clock())
        result = adapter.decide(request)
        id = prepare(request, config, resources(), store).record_id
        assert receipt(store, id).outcome_uncertain
        record = require(store.get_record(IdRequest(id=id)))
        assert isinstance(record, DecisionRecord) and record.usage.data is None
        assert replay(store, store, id) == result
        assert adapter.decide(request) == result and len(transport.calls) == 1


def test_no_receipt_intent_survives_new_adapter() -> None:
    with MemoryStore() as store:
        request = decision_request()
        seed(store, request, "jev")
        config = ModelAdapterConfig(provider="jev")
        prepared = prepare(request, config, resources(), store)
        for role, raw in [
            ("prepared", canonical(prepared.model_dump(mode="json"))),
            ("outbound", canonical(prepared.body)),
            (
                "intent",
                canonical({"work_key": prepared.work_key, "started_at": Clock().now().isoformat()}),
            ),
        ]:
            save(store, artifact_ref(prepared.record_id, role, raw), raw)
        transport = FakeTransport(response("jev"))
        result = JevDecisionModel(store, store, resources(), config, transport).decide(request)
        assert result.error is not None and result.error.code == "dispatch_outcome_uncertain"
        assert transport.calls == []
        assert receipt(store, prepared.record_id).elapsed_seconds is None


@pytest.mark.parametrize("case", ["labels", "resource", "model", "settings"])
def test_local_invalid_request_is_saved_failure(case: str) -> None:
    with MemoryStore() as store:
        request = decision_request()
        registry = resources()
        if case == "labels":
            request = request.model_copy(update={"allowed_labels": ("rot", "rot")})
        elif case == "resource":
            registry = ResourceRegistry({})
        elif case == "model":
            request = request.model_copy(update={"requested_model_id": "jev-latest"})
        else:
            request.settings.values["extra"] = 1
        seed(store, request, "jev")
        transport = FakeTransport(response("jev"))
        result = JevDecisionModel(
            store, store, registry, ModelAdapterConfig(provider="jev"), transport
        ).decide(request)
        assert result.status == "failed" and transport.calls == []
        records = require(store.list_records(ListRequest(record_kind="decision_record"))).records
        assert len(records) == 1 and isinstance(records[0], DecisionRecord)
        assert replay(store, store, records[0].id) == result


@pytest.mark.parametrize(
    "case", ["refusal", "incomplete", "missing", "tool", "multiple", "message_status"]
)
def test_generation_terminal_statuses(case: str) -> None:
    with MemoryStore() as store:
        request = generation_request()
        seed(store, request, "openai")
        raw = body("openai")
        output = raw["output"]
        assert isinstance(output, list)
        message = object_value(output[0])
        if case == "refusal":
            message["content"] = [{"type": "refusal", "refusal": "synthetic refusal"}]
        elif case == "incomplete":
            raw["status"] = "incomplete"
        elif case == "missing":
            raw["output"] = []
        elif case == "tool":
            message["type"] = "function_call"
        elif case == "multiple":
            output.append(message)
        else:
            message["status"] = "in_progress"
        result = OpenAIGenerationModel(
            store,
            store,
            resources(),
            ModelAdapterConfig(provider="openai"),
            FakeTransport(response("openai", raw)),
        ).generate(request)
        assert result.status == "failed"


@pytest.mark.parametrize("payload", [b'{"model":"a","model":"b"}', b'{"x":NaN}', b"", b"\xff"])
def test_malformed_raw_is_preserved(payload: bytes) -> None:
    with MemoryStore() as store:
        request = decision_request()
        seed(store, request, "jev")
        config = ModelAdapterConfig(provider="jev")
        result = JevDecisionModel(
            store, store, resources(), config, FakeTransport(HttpResponse(payload, 200))
        ).decide(request)
        assert result.status == "failed"
        id = prepare(request, config, resources(), store).record_id
        assert (
            require(store.get_artifact(IdRequest(id=role_id(id, "raw")))).ref.sha256
            == artifact_ref(id, "raw", payload).sha256
        )


def test_changed_run_creates_new_history() -> None:
    with MemoryStore() as store:
        transport = FakeTransport(response("jev"))
        adapter = JevDecisionModel(
            store, store, resources(), ModelAdapterConfig(provider="jev"), transport
        )
        ids: list[str] = []
        for run in ("run-first", "run-second"):
            request = decision_request(run)
            seed(store, request, "jev")
            ids.append(require(adapter.decide(request)).id)
        assert ids[0] != ids[1] and len(transport.calls) == 2


def test_nonfinite_raw_number_is_typed_failure() -> None:
    with MemoryStore() as store:
        request = decision_request()
        seed(store, request, "jev")
        raw = response("jev")
        assert raw.payload is not None
        raw = replace(raw, payload=raw.payload.replace(b"0.9", b"1e999"))
        assert (
            JevDecisionModel(
                store, store, resources(), ModelAdapterConfig(provider="jev"), FakeTransport(raw)
            )
            .decide(request)
            .status
            == "failed"
        )
