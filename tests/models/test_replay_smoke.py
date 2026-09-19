from pathlib import Path
from typing import NoReturn

import pytest

from binfocheck.domain.common import ErrorDetail, Outcome
from binfocheck.domain.storage import ArtifactPayload, IdRequest
from binfocheck.models import OpenAIGenerationModel
from binfocheck.models.config import ModelAdapterConfig, Provider
from binfocheck.models.errors import require
from binfocheck.models.json import canonical, digest
from binfocheck.models.live_check import prepare_smoke
from binfocheck.models.persistence import prepare
from binfocheck.models.receipt import role_id
from binfocheck.models.replay import replay
from binfocheck.storage import MemoryStore

from .helpers import FIXTURES, Clock, FakeTransport, generation_request, resources, response, seed


class MissingArtifactStore(MemoryStore):
    hidden: str | None = None

    def get_artifact(self, request: IdRequest) -> Outcome[ArtifactPayload]:
        if request.id == self.hidden:
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="artifact_data_missing", message="missing artifact"),
            )
        return super().get_artifact(request)


@pytest.mark.parametrize("role", ["prepared", "outbound", "raw", "structured", "receipt", "input"])
def test_missing_replay_artifacts_never_trigger_model(role: str) -> None:
    with MissingArtifactStore() as store:
        request = generation_request()
        seed(store, request, "openai")
        transport = FakeTransport(response("openai"))
        adapter = OpenAIGenerationModel(
            store, store, resources(), ModelAdapterConfig(provider="openai"), transport, Clock()
        )
        record = require(adapter.generate(request))
        store.hidden = "t03-state" if role == "input" else role_id(record.id, role)
        assert replay(store, store, record.id).status == "failed"
        assert adapter.generate(request).status == "failed"
        assert len(transport.calls) == 1


@pytest.mark.parametrize("provider", ["jev", "openai"])
def test_frozen_smoke_requests_are_exact(provider: Provider) -> None:
    with MemoryStore() as store:
        prepared, _ = prepare_smoke(store, FIXTURES, provider)
        raw = (FIXTURES / provider / "smoke-request.json").read_bytes()
        assert canonical(prepared.body) == raw and len(raw) < 4096
        expected = {
            "jev": "5075288ed5570c9fb31cf4cc11faad43756a7c8939022317691b58bcb67202dd",
            "openai": "b339839d1641defee14f9ed486562795dafb6144bb9884c448a59f1602ded02c",
        }
        assert digest(raw) == expected[provider]


def test_work_key_changes_with_resources_but_not_registry_order() -> None:
    from binfocheck.models.resources import ResourceRegistry

    with MemoryStore() as store:
        request = generation_request()
        # Null digest is supported; the actual resource bytes still enter the work key.
        assert request.prompt_version is not None
        request = request.model_copy(
            update={
                "prompt_version": request.prompt_version.model_copy(update={"sha256": None}),
            }
        )
        seed(store, request, "openai")
        schema = (FIXTURES / "resources/output.schema.json").read_bytes()
        registry = {
            ("t03-smoke-prompt", "1"): b"Synthetic instruction",
            ("t03-smoke-output", "1"): schema,
        }
        config = ModelAdapterConfig(provider="openai")
        a = prepare(request, config, ResourceRegistry(registry), store)
        b = prepare(
            request, config, ResourceRegistry(dict(reversed(list(registry.items())))), store
        )
        assert a.work_key == b.work_key
        registry[("t03-smoke-prompt", "1")] = b"Different synthetic instruction"
        assert prepare(request, config, ResourceRegistry(registry), store).work_key != a.work_key


def test_smoke_preparation_needs_neither_credentials_nor_transport(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    from binfocheck.models.live_check import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["smoke", "--provider", "jev", "--fixtures", str(FIXTURES)])

    def blocked(**kwargs: object) -> NoReturn:
        pytest.fail("dotenv loaded")

    monkeypatch.setattr("binfocheck.models.config.load_dotenv", blocked)
    assert main() == 0
    assert '"live_authorized":false' in capsys.readouterr().out
    assert not list(tmp_path.iterdir())
