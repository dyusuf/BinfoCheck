"""Synthetic extraction fixtures and exact-preparation model doubles. Never live."""

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import JsonValue

from binfocheck.claims import ExtractionSettings, StoredClaimExtractor
from binfocheck.claims.integration import T03Models
from binfocheck.claims.persistence import json_object, load, save
from binfocheck.claims.resources import ExtractionResources
from binfocheck.domain.common import Availability, Available, ErrorDetail, Outcome
from binfocheck.domain.decisions import DecisionRecord, DecisionResult, GenerationResult, Usage
from binfocheck.domain.interfaces import (
    ContextRequest,
    DecisionRequest,
    ExtractionRequest,
    GenerationRequest,
)
from binfocheck.domain.observations import CaptureRequest, TextUnit
from binfocheck.domain.runs import RunManifest
from binfocheck.domain.storage import IdRequest, ListRequest
from binfocheck.domain.text import ArtifactRef
from binfocheck.models.config import MODELS, ModelAdapterConfig
from binfocheck.models.persistence import prepare
from binfocheck.storage import MemoryStore
from binfocheck.text import ContextSettings, StoredAnswerIndexer, index_reference_id
from binfocheck.text.context import IndexedContextBuilder
from tests.storage.helpers import Store, success
from tests.text.helpers import AT, seed

ROOT = Path(__file__).parents[2]
Reply = Callable[[str, dict[str, JsonValue]], str | dict[str, JsonValue]]


class ScriptedModels:
    def __init__(self, store: Store, resources: ExtractionResources, reply: Reply) -> None:
        self.store, self.resources, self.reply = store, resources, reply
        self.dc = ModelAdapterConfig(provider="jev", max_request_bytes=16384)
        self.gc = ModelAdapterConfig(provider="openai", max_request_bytes=16384)
        self.calls: list[tuple[str, dict[str, JsonValue], DecisionRequest | GenerationRequest]] = []
        self.failure: str | None = None
        self.persist_failure = True
        self.wrong_id = False

    def decide(self, request: DecisionRequest) -> Outcome[DecisionRecord]:
        return self.execute(request)

    def generate(self, request: GenerationRequest) -> Outcome[DecisionRecord]:
        return self.execute(request)

    def execute(self, request: DecisionRequest | GenerationRequest) -> Outcome[DecisionRecord]:
        config = self.dc if isinstance(request, DecisionRequest) else self.gc
        prepared = prepare(request, config, self.resources, self.store)
        previous = self.store.get_record(IdRequest(id=prepared.record_id))
        if previous.status == "succeeded" and isinstance(previous.value, DecisionRecord):
            saved = previous.value
            return Outcome(
                status=saved.status,
                value=saved if saved.status == "succeeded" else None,
                error=saved.error,
            )
        state_id = request.settings.values["state_artifact_id"]
        assert isinstance(state_id, str)
        raw = load(self.store, state_id)
        assert raw is not None
        state = json_object(raw)
        stage = request.task_type.removeprefix("t04.")
        self.calls.append((stage, state, request))
        error = (
            ErrorDetail(code=self.failure, message="Synthetic model failure")
            if self.failure
            else None
        )
        result: DecisionResult | GenerationResult | None = None
        if error is None:
            reply = self.reply(stage, state)
            if isinstance(request, DecisionRequest):
                assert isinstance(reply, str)
                values = {label: float(label == reply) for label in request.allowed_labels}
                result = DecisionResult(
                    allowed_labels=request.allowed_labels,
                    label=reply,
                    probabilities=Available(availability=Availability.AVAILABLE, data=values),
                )
            else:
                assert isinstance(reply, dict)
                output = save(self.store, prepared.record_id + "-output", reply)
                result = GenerationResult(
                    output_schema=request.output_schema,
                    structured_output=reply,
                    output_artifact_id=output.id,
                )
        record = DecisionRecord(
            id=prepared.record_id + ("-wrong" if self.wrong_id else ""),
            created_at=AT,
            analysis_run_id=request.analysis_run_id,
            input_ids=request.input_ids,
            task_type=request.task_type,
            input_artifact_ids=request.input_artifact_ids,
            requested_model_id=request.requested_model_id,
            returned_model_id=Available(
                availability=Availability.AVAILABLE, data=request.requested_model_id
            ),
            prompt_version=request.prompt_version,
            rubric_version=request.rubric_version,
            config_version=request.settings.version,
            status="failed" if error else "succeeded",
            result=result,
            usage=Available[Usage](
                availability=Availability.UNAVAILABLE, data=None, reason="Synthetic"
            ),
            started_at=AT,
            finished_at=AT,
            error=error,
            provider_request_id=None,
        )
        if not error or self.persist_failure:
            success(self.store.append_decision(record))
        return Outcome(
            status="failed" if error else "succeeded", value=None if error else record, error=error
        )


def seed_extraction(
    store: Store,
    content: str,
    reply: Reply,
    question: str = "Welche Farbe hat der Ball?",
    target_kind: str = "paragraph",
    target_orders: tuple[int, ...] | None = None,
    request_limit: int = 340,
    generation_config: ModelAdapterConfig | None = None,
    resource_version: Literal["1", "2", "3"] = "3",
) -> tuple[ExtractionRequest, StoredClaimExtractor, ScriptedModels]:
    resources = ExtractionResources(ROOT, version=resource_version)
    double = ScriptedModels(store, resources, reply)
    if generation_config is not None:
        double.gc = generation_config
    models = T03Models(store, store, double, double, resources, double.dc, double.gc)
    temporary = MemoryStore()
    indexed, answer = seed(temporary, content)
    for record in success(temporary.list_records(ListRequest(limit=100))).records:
        if isinstance(record, ArtifactRef):
            success(store.put_artifact(success(temporary.get_artifact(IdRequest(id=record.id)))))
            continue
        if isinstance(record, CaptureRequest):
            record = record.model_copy(update={"query": question})
        if isinstance(record, RunManifest):
            record = record.model_copy(
                update={
                    "configuration": models.configuration,
                    "model_ids": (MODELS[double.dc.provider], MODELS[double.gc.provider]),
                    "prompt_versions": models.prompts,
                    "rubric_versions": models.rubrics,
                    "budget": record.budget.model_copy(
                        update={"request_limit": request_limit, "cost_limit": request_limit * 0.01}
                    ),
                }
            )
        success(store.put_record(record))
    units = success(StoredAnswerIndexer(store, store).index_answer(indexed))
    targets = tuple(
        u
        for u in units
        if u.unit_kind == target_kind and (target_orders is None or u.order in target_orders)
    )
    context_settings = ContextSettings(index_artifact_id=index_reference_id(indexed, answer))
    context = success(
        IndexedContextBuilder(store, store).build_context(
            ContextRequest(
                analysis_run_id=indexed.analysis_run_id,
                observation_id=indexed.observation_id,
                target_unit_ids=tuple(u.id for u in targets),
                settings=context_settings.envelope(),
            )
        )
    )
    settings = ExtractionSettings(
        index_artifact_id=context_settings.index_artifact_id,
        target_unit_ids=tuple(u.id for u in targets),
        context_settings=context_settings,
        policy_version=resources.policy,
        resource_bundle_version=resources.version,
    )
    request = ExtractionRequest(
        analysis_run_id=indexed.analysis_run_id,
        observation_id=indexed.observation_id,
        context=context,
        settings=settings.envelope(models.configuration),
    )
    return request, StoredClaimExtractor(store, store, models), double


def anchor(
    store: Store, state: dict[str, JsonValue], quote: str, start: int | None = None
) -> dict[str, JsonValue]:
    source = state["source"]
    assert isinstance(source, dict)
    text, offset = source["text"], source["start"]
    assert isinstance(text, str) and isinstance(offset, int)
    position = offset + text.index(quote) if start is None else start
    ids = source["unit_ids"]
    assert isinstance(ids, list)
    units: list[TextUnit] = []
    for id in ids:
        assert isinstance(id, str)
        unit = success(store.get_record(IdRequest(id=id)))
        assert isinstance(unit, TextUnit)
        if unit.span.start <= position and position + len(quote) <= unit.span.end:
            units.append(unit)
    selected = min(units, key=lambda u: u.span.end - u.span.start)
    return {
        "quote": quote,
        "source_unit_ids": [selected.id],
        "start": position,
        "end": position + len(quote),
    }


def candidate(
    store: Store,
    state: dict[str, JsonValue],
    quote: str,
    claim: str | None = None,
    start: int | None = None,
) -> dict[str, JsonValue]:
    return {
        "normalized_claim": claim or quote,
        "anchor": anchor(store, state, quote, start),
        "required_support": [],
        "consumed_binding_indices": [],
    }


def candidates(*items: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {"status": "candidates", "candidates": list(items), "reason_code": "none"}


def positive(stage: str) -> str:
    return {
        "B": "factual",
        "D": "clear",
        "H.faithfulness": "faithful",
        "H.atomicity": "atomic",
        "H.self_containment": "self_contained",
    }[stage]
