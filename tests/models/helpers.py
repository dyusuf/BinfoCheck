"""Synthetic T03 data and transport doubles. No real provider artifacts."""

import base64
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import JsonValue

from binfocheck.domain.common import ProcessingStatus, Settings, VersionRef
from binfocheck.domain.interfaces import DecisionRequest, GenerationRequest
from binfocheck.domain.runs import RunManifest
from binfocheck.domain.storage import ArtifactPayload, ArtifactStore, RecordStore
from binfocheck.domain.text import ArtifactRef
from binfocheck.models.config import CONFIG_VERSION, MODELS, ModelAdapterConfig, Provider
from binfocheck.models.errors import require
from binfocheck.models.json import canonical, digest, object_value, parse
from binfocheck.models.receipt import ModelReceipt, role_id
from binfocheck.models.resources import ResourceRegistry
from binfocheck.models.transport import HttpResponse

FIXTURES = Path(__file__).parents[1] / "fixtures/models"
TEXT = "Äpfel 🍎 sind rot."
NOW = datetime(2026, 9, 19, 12, tzinfo=UTC)


class Store(RecordStore, ArtifactStore, Protocol):
    def close(self) -> None: ...


class Clock:
    def now(self) -> datetime:
        return NOW

    def monotonic(self) -> float:
        return 1.0


class FakeTransport:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.calls: list[bytes] = []

    def check(self, config: ModelAdapterConfig, body: bytes, work_key: str) -> None:
        pass

    def post(self, config: ModelAdapterConfig, body: bytes, work_key: str) -> HttpResponse:
        self.calls.append(body)
        return self.response


def resources() -> ResourceRegistry:
    return ResourceRegistry(
        {
            ("t03-smoke-rubric", "1"): (FIXTURES / "resources/rubric.json").read_bytes(),
            ("t03-smoke-prompt", "1"): (FIXTURES / "resources/prompt.txt").read_bytes(),
            ("t03-smoke-output", "1"): (FIXTURES / "resources/output.schema.json").read_bytes(),
        }
    )


def ref(name: str, filename: str) -> VersionRef:
    return VersionRef(
        name=name, version="1", sha256=digest((FIXTURES / "resources" / filename).read_bytes())
    )


def decision_request(run: str = "t03-run-jev", required: bool = True) -> DecisionRequest:
    return DecisionRequest(
        analysis_run_id=run,
        task_type="t03_choice_smoke",
        input_ids=("t03-state",),
        input_artifact_ids=("t03-state",),
        requested_model_id=MODELS["jev"],
        prompt_version=None,
        rubric_version=ref("t03-smoke-rubric", "rubric.json"),
        settings=Settings(version=CONFIG_VERSION, values={"state_artifact_id": "t03-state"}),
        allowed_labels=("rot", "andere"),
        probabilities_required=required,
    )


def generation_request(run: str = "t03-run-openai") -> GenerationRequest:
    return GenerationRequest(
        analysis_run_id=run,
        task_type="t03_generation_smoke",
        input_ids=("t03-state",),
        input_artifact_ids=("t03-state",),
        requested_model_id=MODELS["openai"],
        prompt_version=ref("t03-smoke-prompt", "prompt.txt"),
        rubric_version=None,
        settings=Settings(version=CONFIG_VERSION, values={"state_artifact_id": "t03-state"}),
        output_schema=ref("t03-smoke-output", "output.schema.json"),
    )


def seed(store: Store, request: DecisionRequest | GenerationRequest, provider: Provider) -> None:
    raw = TEXT.encode()
    require(
        store.put_artifact(
            ArtifactPayload(
                ref=ArtifactRef(
                    id="t03-state",
                    storage_key="synthetic/t03/state",
                    sha256=digest(raw),
                    media_type="text/plain",
                    access="shareable_fixture",
                ),
                content_base64=base64.b64encode(raw).decode(),
            )
        )
    )
    require(
        store.put_record(
            RunManifest(
                id=request.analysis_run_id,
                created_at=NOW,
                input_ids=request.input_ids,
                observation_ids=(),
                corpus_manifest_id=None,
                purpose="diagnostic",
                mode="reanalysis",
                capture_settings=request.settings,
                configuration=CONFIG_VERSION,
                model_ids=(request.requested_model_id,),
                prompt_versions=(request.prompt_version,) if request.prompt_version else (),
                rubric_versions=(request.rubric_version,) if request.rubric_version else (),
                budget=ModelAdapterConfig(provider=provider).budget,
                status=ProcessingStatus.PENDING,
            )
        )
    )


def body(provider: Provider) -> dict[str, JsonValue]:
    return object_value(parse((FIXTURES / provider / "success.json").read_bytes()))


def response(provider: Provider, value: dict[str, JsonValue] | None = None) -> HttpResponse:
    return HttpResponse(
        canonical(body(provider) if value is None else value),
        200,
        (("x-typesafe-request-id" if provider == "jev" else "x-request-id", "synthetic-request"),),
    )


def receipt(store: ArtifactStore, record_id: str) -> ModelReceipt:
    from binfocheck.domain.storage import IdRequest

    payload = require(store.get_artifact(IdRequest(id=role_id(record_id, "receipt"))))
    return ModelReceipt.model_validate_json(base64.b64decode(payload.content_base64))
