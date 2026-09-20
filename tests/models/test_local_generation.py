"""Synthetic local-server envelopes. These tests make no model or network calls."""

from pathlib import Path

import pytest
from pydantic import JsonValue, ValidationError

from binfocheck.domain.common import Settings
from binfocheck.domain.decisions import GenerationResult
from binfocheck.domain.storage import IdRequest
from binfocheck.models import LocalVllmGenerationModel
from binfocheck.models.config import (
    LOCAL_CONFIG_VERSION,
    MODELS,
    LocalAuthorization,
    LocalGenerationConfig,
    ModelAdapterConfig,
)
from binfocheck.models.errors import ModelError, require
from binfocheck.models.generation import local_generation_output
from binfocheck.models.json import canonical, digest
from binfocheck.models.local_transport import LocalVllmTransport
from binfocheck.models.persistence import load, prepare
from binfocheck.models.receipt import PreparedRequest, role_id
from binfocheck.models.replay import replay
from binfocheck.models.transport import HttpResponse
from binfocheck.storage import MemoryStore, SQLiteStore

from .helpers import Clock, FakeTransport, generation_request, receipt, resources, seed

MANIFEST = canonical(
    {
        "origin": "synthetic runtime, no actual model",
        "model": MODELS["vllm"],
        "server_version": {"version": "0.10.2"},
        "environment": {
            "VLLM_USE_V1": "1",
            "VLLM_ATTENTION_BACKEND": "XFORMERS_VLLM_V1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        },
        "launch_arguments": [
            "vllm",
            "serve",
            "/synthetic/snapshot",
            "--guided-decoding-backend",
            "xgrammar",
            "--guided-decoding-disable-fallback",
            "--dtype",
            "float16",
            "--served-model-name",
            MODELS["vllm"],
            "--max-model-len",
            "4096",
        ],
    }
)
SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}


def envelope(content: str = '{"text":"Rot."}', finish: str = "stop") -> dict[str, JsonValue]:
    return {
        "id": "synthetic-local-response",
        "model": MODELS["vllm"],
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish,
                "message": {"role": "assistant", "content": content},
            }
        ],
        "usage": {"prompt_tokens": 42, "completion_tokens": 8, "total_tokens": 50},
    }


class LocalDouble(FakeTransport):
    runtime_manifest = MANIFEST


def setup(store: MemoryStore | SQLiteStore):
    request = generation_request().model_copy(
        update={
            "requested_model_id": MODELS["vllm"],
            "settings": Settings(
                version=LOCAL_CONFIG_VERSION, values={"state_artifact_id": "t03-state"}
            ),
        }
    )
    seed(store, request, "openai")
    config = LocalGenerationConfig(runtime_manifest_sha256=digest(MANIFEST))
    return request, config


def test_local_persistence_reopen_replay_and_exact_preparation(tmp_path: Path) -> None:
    root = tmp_path / "store"
    with SQLiteStore(root) as store:
        request, config = setup(store)
        transport = LocalDouble(HttpResponse(canonical(envelope()), 200))
        adapter = LocalVllmGenerationModel(store, store, resources(), config, transport, Clock())
        prepared = prepare(request, config, resources(), store)
        assert "input" not in prepared.body and "messages" in prepared.body
        assert prepared.body["max_tokens"] == 512
        assert prepared.body["temperature"] == 0
        assert prepared.body["tool_choice"] == "none"
        record = require(adapter.generate(request))
        assert isinstance(record.result, GenerationResult)
        assert record.result.structured_output == {"text": "Rot."}
        assert record.usage.data and record.usage.data.input_tokens == 42
        assert record.usage.data.output_tokens == 8 and record.usage.data.cost is None
        saved = receipt(store, record.id)
        assert saved.raw_response_artifact and saved.dispatched and saved.complete
        assert load(store, saved.raw_response_artifact) == canonical(envelope())
        stored_prepared = PreparedRequest.model_validate_json(load(store, saved.prepared_artifact))
        assert stored_prepared == prepared
        assert isinstance(stored_prepared.config, LocalGenerationConfig)
        assert prepared.record_id == stored_prepared.record_id
        runtime = require(store.get_artifact(IdRequest(id=role_id(record.id, "runtime"))))
        assert load(store, runtime.ref) == MANIFEST
    with SQLiteStore(root) as store:
        assert require(replay(store, store, record.id)) == record
        adapter = LocalVllmGenerationModel(store, store, resources(), config, transport, Clock())
        assert require(adapter.generate(request)) == record
        assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "content",
    [
        '```json\n{"text":"Rot."}\n```',
        '{"text":"a","text":"b"}',
        '{"text":7}',
        '{"text":"Rot.","invented":true}',
        '{"text":',
    ],
)
def test_no_repair_or_coercion(content: str) -> None:
    with pytest.raises(ModelError):
        local_generation_output(SCHEMA, envelope(content))


@pytest.mark.parametrize("finish", ["length", "tool_calls", "error", "abort"])
def test_truncation_never_passes(finish: str) -> None:
    with pytest.raises(ModelError, match="output_incomplete"):
        local_generation_output(SCHEMA, envelope(finish=finish))


def test_mismatched_model_persists_failure_and_never_retries() -> None:
    store = MemoryStore()
    request, config = setup(store)
    raw = envelope()
    raw["model"] = "another-model"
    transport = LocalDouble(HttpResponse(canonical(raw), 200))
    adapter = LocalVllmGenerationModel(store, store, resources(), config, transport, Clock())
    first = adapter.generate(request)
    assert first.error and first.error.code == "model_mismatch"
    assert adapter.generate(request) == first
    assert len(transport.calls) == 1


def test_local_requires_exact_authorization_and_manifest() -> None:
    store = MemoryStore()
    request, config = setup(store)
    prepared = prepare(request, config, resources(), store)
    body = canonical(prepared.body)
    authorization = LocalAuthorization(
        approval_reference="synthetic test",
        model=MODELS["vllm"],
        work_key=prepared.work_key,
        request_sha256=digest(body),
        runtime_manifest_sha256=digest(MANIFEST),
    )
    transport = LocalVllmTransport("synthetic-key", authorization, MANIFEST)
    assert transport.check(config, body, prepared.work_key) == authorization
    with pytest.raises(ModelError, match="live_request_not_authorized"):
        transport.check(config, body + b" ", prepared.work_key)
    with pytest.raises(ModelError, match="local_runtime_manifest_mismatch"):
        LocalVllmTransport("synthetic-key", authorization, b"wrong").check(
            config, body, prepared.work_key
        )
    with pytest.raises(ValidationError):
        ModelAdapterConfig(provider="vllm")
    with pytest.raises(ValidationError):
        LocalGenerationConfig(runtime_manifest_sha256=digest(MANIFEST), provider="openai")


def test_runtime_mismatch_blocks_before_dispatch() -> None:
    store = MemoryStore()
    request, config = setup(store)
    transport = LocalDouble(HttpResponse(canonical(envelope()), 200))
    transport.runtime_manifest = b"different"
    adapter = LocalVllmGenerationModel(store, store, resources(), config, transport, Clock())
    result = adapter.generate(request)
    assert result.error and result.error.code == "local_runtime_manifest_mismatch"
    assert transport.calls == []
