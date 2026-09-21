"""Live capability rejection is independent of request preparation and saved replay."""

import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from binfocheck.domain.common import Settings
from binfocheck.models import LocalVllmGenerationModel
from binfocheck.models.config import LocalGenerationConfig, ModelAdapterConfig, config_version
from binfocheck.models.errors import ModelError
from binfocheck.models.json import canonical, digest
from binfocheck.models.local_runtime import require_structured_runtime
from binfocheck.models.persistence import prepare
from binfocheck.models.receipt import PreparedRequest
from binfocheck.models.replay import replay
from binfocheck.models.transport import HttpResponse
from binfocheck.storage import MemoryStore
from tests.models.helpers import Clock, receipt, resources
from tests.models.test_local_generation import MANIFEST, LocalDouble, envelope, setup
from tests.models.test_local_transport import BODY, KEY, transport


def legacy_config() -> LocalGenerationConfig:
    return LocalGenerationConfig(
        version="1",
        server_version="0.10.2",
        engine="V0",
        attention_backend="XFORMERS",
        runtime_manifest_sha256=digest(MANIFEST),
    )


def test_legacy_prepares_identically_but_cannot_dispatch() -> None:
    store = MemoryStore()
    request, current = setup(store)
    old = legacy_config()
    request = request.model_copy(
        update={
            "settings": Settings(
                version=config_version(old),
                values=request.settings.values,
            )
        }
    )
    prepared = prepare(request, old, resources(), store)
    assert PreparedRequest.model_validate_json(prepared.model_dump_json()) == prepared
    assert config_version(old).version == "1" and config_version(current).version == "3"
    updated = request.model_copy(
        update={
            "settings": Settings(
                version=config_version(current),
                values=request.settings.values,
            )
        }
    )
    newer = prepare(updated, current, resources(), store)
    assert prepared.body == newer.body  # No prompt/schema/wire change.
    assert prepared.work_key != newer.work_key
    double = LocalDouble(HttpResponse(canonical(envelope()), 200))
    adapter = LocalVllmGenerationModel(store, store, resources(), old, double, Clock())
    result = adapter.generate(request)
    assert result.error and result.error.code == "local_structured_output_unavailable"
    assert double.calls == []
    saved = receipt(store, prepared.record_id)
    assert not saved.dispatched and not saved.outcome_uncertain
    assert replay(store, store, prepared.record_id) == result
    with patch("http.client.HTTPConnection") as connection:
        with pytest.raises(ModelError, match="local_structured_output_unavailable"):
            transport().post(old, BODY, KEY)
        connection.assert_not_called()


@pytest.mark.parametrize("change", ["engine", "attention", "fallback", "backend", "duplicate"])
def test_matching_hash_is_not_sufficient_for_runtime_capability(change: str) -> None:
    data = json.loads(MANIFEST)
    if change == "engine":
        data["engine"] = "V0"
    elif change == "attention":
        data["launch_arguments"][data["launch_arguments"].index("TRITON_ATTN")] = "XFORMERS"
    elif change == "fallback":
        data["launch_arguments"] += ["--structured-outputs-config", '{"backend":"auto"}']
    elif change == "backend":
        data["launch_arguments"][data["launch_arguments"].index("xgrammar")] = "auto"
    else:
        data["launch_arguments"] += ["--structured-outputs-config.backend", "auto"]
    manifest = canonical(data)
    store = MemoryStore()
    request, _ = setup(store)
    config = LocalGenerationConfig(runtime_manifest_sha256=digest(manifest))
    double = LocalDouble(HttpResponse(canonical(envelope()), 200))
    double.runtime_manifest = manifest
    result = LocalVllmGenerationModel(store, store, resources(), config, double, Clock()).generate(
        request
    )
    assert result.error and result.error.code == "local_runtime_settings_mismatch"
    assert double.calls == []


def test_version_and_engine_are_not_interchangeable() -> None:
    require_structured_runtime(
        LocalGenerationConfig(runtime_manifest_sha256=digest(MANIFEST)), MANIFEST
    )
    for update in (
        {"version": "1"},
        {"version": "2"},
        {"server_version": "0.10.2"},
        {"engine": "V0"},
        {"attention_backend": "XFORMERS"},
    ):
        with pytest.raises(ValidationError):
            LocalGenerationConfig.model_validate(
                {"runtime_manifest_sha256": digest(MANIFEST), **update}
            )
    with pytest.raises(ValidationError):
        ModelAdapterConfig(provider="jev", version="2")


@pytest.mark.parametrize(
    "version,engine,backend", [("1", "V0", "XFORMERS"), ("2", "V1", "XFORMERS_VLLM_V1")]
)
def test_historical_configs_keep_body_and_replay_but_block_new_dispatch(
    version: str,
    engine: str,
    backend: str,
) -> None:
    store = MemoryStore()
    request, current = setup(store)
    old = LocalGenerationConfig.model_validate(
        {
            **current.model_dump(),
            "version": version,
            "engine": engine,
            "attention_backend": backend,
            "server_version": "0.10.2",
        }
    )
    old_request = request.model_copy(
        update={
            "settings": Settings(
                version=config_version(old),
                values=request.settings.values,
            )
        }
    )
    prepared = prepare(old_request, old, resources(), store)
    assert PreparedRequest.model_validate_json(prepared.model_dump_json()) == prepared
    assert prepared.body == prepare(request, current, resources(), store).body
    double = LocalDouble(HttpResponse(canonical(envelope()), 200))
    adapter = LocalVllmGenerationModel(store, store, resources(), old, double, Clock())
    # Seed an archived synthetic success as if written before the live-only guard.
    with patch("binfocheck.models.persistence.require_structured_runtime"):
        historical = adapter.generate(old_request)
    assert historical.value is not None
    with patch("http.client.HTTPConnection", side_effect=AssertionError("network forbidden")):
        assert replay(store, store, prepared.record_id) == historical
        assert adapter.generate(old_request) == historical
    assert len(double.calls) == 1
    with pytest.raises(ModelError, match="local_structured_output_unavailable"):
        require_structured_runtime(old, MANIFEST)


@pytest.mark.parametrize(
    "args",
    [
        ["--structured-outputs-config.backend=auto"],
        ["--structured-outputs-config", '{"backend":"auto"}'],
        ["--attention-config.backend", "FLASH_ATTN"],
        ["--config", "unreviewed.yaml"],
        ["--guided-decoding-backend", "xgrammar"],
        ["--trust-remote-code"],
    ],
)
def test_v3_rejects_overrides_even_with_matching_manifest_hash(args: list[str]) -> None:
    data = json.loads(MANIFEST)
    data["launch_arguments"] += args
    manifest = canonical(data)
    with pytest.raises(ModelError, match="local_runtime_settings_mismatch"):
        require_structured_runtime(
            LocalGenerationConfig(runtime_manifest_sha256=digest(manifest)), manifest
        )
