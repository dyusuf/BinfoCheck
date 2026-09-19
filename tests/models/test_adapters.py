import base64
from pathlib import Path

import pytest
from pydantic import JsonValue

from binfocheck.domain.decisions import DecisionRecord, DecisionResult, GenerationResult
from binfocheck.domain.interfaces import DecisionModel, GenerationModel
from binfocheck.domain.records import RecordSet
from binfocheck.domain.storage import IdRequest, ListRequest
from binfocheck.domain.validation import validate_links
from binfocheck.models import JevDecisionModel, OpenAIGenerationModel
from binfocheck.models.config import ModelAdapterConfig, Provider
from binfocheck.models.errors import require
from binfocheck.models.json import canonical, object_value
from binfocheck.models.persistence import load, prepare
from binfocheck.models.replay import replay
from binfocheck.models.transport import HttpResponse
from binfocheck.storage import MemoryStore, SQLiteStore

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


@pytest.mark.parametrize("provider", ["jev", "openai"])
def test_persist_reopen_replay_and_lineage(provider: Provider, tmp_path: Path) -> None:
    request = decision_request() if provider == "jev" else generation_request()
    config = ModelAdapterConfig(provider=provider)
    transport = FakeTransport(response(provider))
    root = tmp_path / "store"
    with SQLiteStore(root) as store:
        seed(store, request, provider)
        if provider == "jev":
            model: DecisionModel = JevDecisionModel(
                store, store, resources(), config, transport, Clock()
            )
            result = model.decide(decision_request())
        else:
            generator: GenerationModel = OpenAIGenerationModel(
                store, store, resources(), config, transport, Clock()
            )
            result = generator.generate(generation_request())
        record = require(result)
        assert record.input_ids == request.input_ids
        assert record.input_artifact_ids == request.input_artifact_ids
        assert record.returned_model_id.data == request.requested_model_id
        assert record.provider_request_id == "synthetic-request"
        assert record.usage.data is not None and record.usage.data.cost is None
        captured = receipt(store, record.id)
        assert captured.raw_response_artifact is not None
        assert captured.raw_response_artifact.access == "restricted"
        assert load(store, captured.raw_response_artifact) == transport.response.payload
        assert captured.estimated_cost_usd is not None
        assert captured.estimate_basis.startswith("estimate:")
        if isinstance(record.result, GenerationResult):
            generated = require(store.get_artifact(IdRequest(id=record.result.output_artifact_id)))
            assert base64.b64decode(generated.content_base64) == canonical(
                record.result.structured_output
            )
            assert generated.ref == captured.structured_output_artifact
            assert generated.ref.id != captured.raw_response_artifact.id
        else:
            assert isinstance(record.result, DecisionResult)
        records = require(store.list_records(ListRequest(limit=1000))).records
        validate_links(RecordSet(records=records))
    with SQLiteStore(root) as store:
        assert require(replay(store, store, record.id)) == record
        adapter = (JevDecisionModel if provider == "jev" else OpenAIGenerationModel)(
            store, store, resources(), config, transport, Clock()
        )
        assert require(adapter.execute(request)) == record
        assert len(transport.calls) == 1
        assert require(store.list_records(ListRequest(record_kind="decision_record"))).records == (
            record,
        )


@pytest.mark.parametrize(
    "probabilities,code",
    [
        (None, "required_probabilities_missing"),
        ({"rot": 0.9}, "required_probabilities_missing"),
        ({"rot": 0.8, "andere": 0.3}, "invalid_probabilities"),
        ({"rot": True, "andere": 0.0}, "invalid_probabilities"),
        ({"rot": "0.9", "andere": 0.1}, "invalid_probabilities"),
        ({"rot": -0.1, "andere": 1.1}, "invalid_probabilities"),
        ({"invented": 0.9, "andere": 0.1}, "invalid_probabilities"),
        ({"rot": 0.1, "andere": 0.9}, "choice_probability_mismatch"),
    ],
)
def test_invalid_probabilities_are_persisted_failures(probabilities: JsonValue, code: str) -> None:
    with MemoryStore() as store:
        request = decision_request()
        seed(store, request, "jev")
        raw = body("jev")
        object_value(object_value(raw["answers"])["q0"])["probabilities"] = probabilities
        transport = FakeTransport(response("jev", raw))
        config = ModelAdapterConfig(provider="jev")
        adapter = JevDecisionModel(store, store, resources(), config, transport, Clock())
        result = adapter.decide(request)
        assert result.error is not None and result.error.code == code
        id = prepare(request, config, resources(), store).record_id
        record = require(store.get_record(IdRequest(id=id)))
        assert (
            isinstance(record, DecisionRecord)
            and record.result is None
            and record.status == "failed"
        )
        assert replay(store, store, id) == result
        assert adapter.decide(request) == result
        assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "value,availability",
    [
        (None, "unavailable"),
        ({"rot": 0.7}, "incomplete"),
        ({"rot": 0.5, "andere": 0.5}, "available"),
        ({"rot": 0.8, "andere": 0.2000005}, "available"),
    ],
)
def test_optional_and_rounding_probabilities(value: JsonValue, availability: str) -> None:
    from binfocheck.models.decision import decision_result

    raw = body("jev")
    object_value(object_value(raw["answers"])["q0"])["probabilities"] = value
    result = decision_result(decision_request(required=False), raw)
    assert result.probabilities.availability == availability
    assert result.probabilities.data == value


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        '{"text":',
        '{"text":1}',
        "{}",
        "[]",
        '{"text":"a","extra":0}',
        '{"text":"a","text":"b"}',
        "```json\n{}\n```",
        '{"text":NaN}',
        '{"text":1e999}',
    ],
)
def test_generation_invalid_output(text: str) -> None:
    with MemoryStore() as store:
        request = generation_request()
        seed(store, request, "openai")
        raw = body("openai")
        output = raw["output"]
        assert isinstance(output, list)
        content = object_value(output[0])["content"]
        assert isinstance(content, list)
        object_value(content[0])["text"] = text
        transport = FakeTransport(response("openai", raw))
        config = ModelAdapterConfig(provider="openai")
        result = OpenAIGenerationModel(
            store, store, resources(), config, transport, Clock()
        ).generate(request)
        assert result.status == "failed" and result.value is None
        id = prepare(request, config, resources(), store).record_id
        saved = receipt(store, id)
        assert saved.structured_output_artifact is None
        assert saved.raw_response_artifact is not None
        assert load(store, saved.raw_response_artifact) == canonical(raw)
        assert replay(store, store, id) == result


@pytest.mark.parametrize("provider", ["jev", "openai"])
@pytest.mark.parametrize("model", [None, "", "unexpected-model"])
def test_returned_identity_required(provider: Provider, model: JsonValue) -> None:
    with MemoryStore() as store:
        request = decision_request() if provider == "jev" else generation_request()
        seed(store, request, provider)
        raw = body(provider)
        raw["model"] = model
        config = ModelAdapterConfig(provider=provider)
        transport = FakeTransport(response(provider, raw))
        adapter = (JevDecisionModel if provider == "jev" else OpenAIGenerationModel)(
            store, store, resources(), config, transport, Clock()
        )
        result = adapter.execute(request)
        assert result.error is not None and result.error.code in (
            "model_identity_missing",
            "model_mismatch",
        )
        stored = require(
            store.get_record(IdRequest(id=prepare(request, config, resources(), store).record_id))
        )
        assert isinstance(stored, DecisionRecord)
        assert stored.returned_model_id.data == (model or None)


@pytest.mark.parametrize("provider", ["jev", "openai"])
@pytest.mark.parametrize(
    "usage",
    [
        None,
        {},
        {"input_tokens": 0, "output_tokens": 0},
        {"input_tokens": True, "output_tokens": "10"},
        {"input_tokens": 5},
    ],
)
def test_usage_unknown_is_not_zero(provider: Provider, usage: JsonValue) -> None:
    from binfocheck.models.persistence import usage_metadata

    raw = body(provider)
    raw["usage"] = usage
    value, _, _ = usage_metadata(provider, raw)
    if usage is None:
        assert value.data is None and value.availability == "unavailable"
    else:
        assert value.data is not None and value.data.cost is None and value.data.requests is None
        if usage == {"input_tokens": 0, "output_tokens": 0}:
            assert value.data.input_tokens == value.data.output_tokens == 0
        elif usage == {} or usage == {"input_tokens": True, "output_tokens": "10"}:
            assert value.data.input_tokens is value.data.output_tokens is None


@pytest.mark.parametrize("status", [301, 400, 401, 403, 404, 422, 429, 500, 529])
def test_provider_errors_never_retry(status: int) -> None:
    with MemoryStore() as store:
        request = decision_request()
        seed(store, request, "jev")
        transport = FakeTransport(HttpResponse(b'{"error":"sensitive provider text"}', status))
        config = ModelAdapterConfig(provider="jev")
        adapter = JevDecisionModel(store, store, resources(), config, transport, Clock())
        result = adapter.decide(request)
        assert result.error is not None and result.error.retryable is False
        assert "sensitive" not in result.error.message
        assert adapter.decide(request) == result and len(transport.calls) == 1
