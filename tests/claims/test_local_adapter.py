"""End-to-end synthetic T04 composition through the local generation adapter."""

from pydantic import JsonValue

from binfocheck.claims.integration import T03Models
from binfocheck.claims.persistence import canonical, json_object
from binfocheck.domain.runs import RunManifest
from binfocheck.domain.storage import IdRequest
from binfocheck.models import JevDecisionModel, LocalVllmGenerationModel
from binfocheck.models.config import MODELS, LocalGenerationConfig, ModelAdapterConfig
from binfocheck.models.json import digest
from binfocheck.models.transport import HttpResponse
from binfocheck.storage import MemoryStore
from tests.models.helpers import Clock
from tests.models.test_local_generation import MANIFEST, envelope
from tests.storage.helpers import success

from .helpers import candidate, candidates, seed_extraction
from .test_adapters import OfflineTransport


class LocalExtractionTransport(OfflineTransport):
    runtime_manifest = MANIFEST

    def post(self, config: ModelAdapterConfig, body: bytes, work_key: str) -> HttpResponse:
        if config.provider == "jev":
            return super().post(config, body, work_key)
        request = json_object(body)
        self.calls.append(request)
        messages = request["messages"]
        assert isinstance(messages, list) and isinstance(messages[1], dict)
        raw = messages[1]["content"]
        assert isinstance(raw, str)
        state = json_object(raw.encode())
        output: dict[str, JsonValue] = candidates(candidate(self.store, state, "Rot."))
        return HttpResponse(canonical(envelope(canonical(output).decode())), 200)


def test_local_generation_keeps_all_three_jev_validations_and_replays() -> None:
    store = MemoryStore()
    config = LocalGenerationConfig(
        runtime_manifest_sha256=digest(MANIFEST), max_request_bytes=16384
    )
    request, extractor, double = seed_extraction(
        store,
        "Rot.",
        lambda _stage, _state: "factual",
        generation_config=config,
    )
    transport = LocalExtractionTransport(store)
    decisions = JevDecisionModel(store, store, double.resources, double.dc, transport, Clock())
    generation = LocalVllmGenerationModel(
        store, store, double.resources, config, transport, Clock()
    )
    extractor.models = T03Models(
        store,
        store,
        decisions,
        generation,
        double.resources,
        double.dc,
        config,
    )
    run = success(store.get_record(IdRequest(id=request.analysis_run_id)))
    assert isinstance(run, RunManifest)
    assert set(run.model_ids) == {MODELS["jev"], MODELS["vllm"]}
    result = success(extractor.extract_claims(request))
    assert len(result.claims) == 1 and not result.issues
    assert len(transport.calls) == 6
    assert result.claims[0].original_span.exact_text == "Rot."
    assert success(extractor.extract_claims(request)) == result
    assert len(transport.calls) == 6
