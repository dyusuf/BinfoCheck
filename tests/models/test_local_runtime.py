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
    assert config_version(old).version == "1" and config_version(current).version == "2"
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
        data["environment"]["VLLM_USE_V1"] = "0"
    elif change == "attention":
        data["environment"]["VLLM_ATTENTION_BACKEND"] = "XFORMERS"
    elif change == "fallback":
        data["launch_arguments"].remove("--guided-decoding-disable-fallback")
    elif change == "backend":
        data["launch_arguments"][data["launch_arguments"].index("xgrammar")] = "auto"
    else:
        data["launch_arguments"] += ["--guided-decoding-backend", "auto"]
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
    for update in ({"version": "1"}, {"engine": "V0"}, {"attention_backend": "XFORMERS"}):
        with pytest.raises(ValidationError):
            LocalGenerationConfig.model_validate(
                {"runtime_manifest_sha256": digest(MANIFEST), **update}
            )
    with pytest.raises(ValidationError):
        ModelAdapterConfig(provider="jev", version="2")
