from datetime import UTC, datetime

from binfocheck.domain.common import Availability, Available, ProcessingStatus, Settings, VersionRef
from binfocheck.domain.interfaces import ContextRequest, IndexRequest
from binfocheck.domain.observations import CaptureRequest, Observation, TextUnit
from binfocheck.domain.runs import Budget, RunManifest
from binfocheck.domain.text import TextRecord
from binfocheck.text import ContextSettings, IndexSettings, index_reference_id
from tests.storage.helpers import Store, payload, success

AT = datetime(2026, 9, 19, tzinfo=UTC)


def seed(store: Store, content: str, prefix: str = "a") -> tuple[IndexRequest, TextRecord]:
    config = Settings(version=VersionRef(name="synthetic", version="1"), values={"language": "de"})
    capture = CaptureRequest(
        id=prefix + "-request",
        created_at=AT,
        query_id=prefix + "-query",
        query="synthetic",
        product="google_ai_mode",
        provider="dataforseo",
        requested_settings=config,
    )
    artifact = payload(prefix + "-raw", content.encode())
    answer = TextRecord(id=prefix + "-text", artifact_id=artifact.ref.id, text=content)
    observation = Observation(
        id=prefix + "-obs",
        created_at=AT,
        request_id=capture.id,
        query_id=capture.query_id,
        product=capture.product,
        provider=capture.provider,
        requested_settings=config,
        reported_settings=Available[Settings](
            availability=Availability.UNAVAILABLE, data=None, reason="synthetic"
        ),
        status=ProcessingStatus.SUCCEEDED,
        raw_artifact_id=artifact.ref.id,
        answer_text_id=answer.id,
        source_reference_ids=Available[tuple[str, ...]](
            availability=Availability.UNAVAILABLE, data=None, reason="synthetic"
        ),
        citation_reference_ids=Available[tuple[str, ...]](
            availability=Availability.UNAVAILABLE, data=None, reason="synthetic"
        ),
        fanout_queries=Available[tuple[str, ...]](
            availability=Availability.UNAVAILABLE, data=None, reason="synthetic"
        ),
        normalization_version=VersionRef(name="synthetic", version="1"),
    )
    run = RunManifest(
        id=prefix + "-run",
        created_at=AT,
        input_ids=(observation.id, answer.id),
        observation_ids=(observation.id,),
        corpus_manifest_id=None,
        purpose="diagnostic",
        mode="reanalysis",
        capture_settings=config,
        configuration=VersionRef(name="t02-verification", version="1"),
        model_ids=(),
        prompt_versions=(),
        rubric_versions=(),
        budget=Budget(
            request_limit=0,
            cost_limit=0.0,
            currency="USD",
            timeout_seconds=60.0,
            concurrency=1,
            retry_limit=0,
        ),
        status=ProcessingStatus.SUCCEEDED,
    )
    success(store.put_artifact(artifact))
    for record in (capture, answer, observation, run):
        success(store.put_record(record))
    return IndexRequest(
        analysis_run_id=run.id,
        observation_id=observation.id,
        answer_text_id=answer.id,
        settings=IndexSettings().envelope(),
    ), answer


def context(
    request: IndexRequest, answer: TextRecord, targets: tuple[TextUnit, ...], **settings: object
) -> ContextRequest:
    values: dict[str, object] = {
        "index_artifact_id": index_reference_id(request, answer),
        **settings,
    }
    return ContextRequest(
        analysis_run_id=request.analysis_run_id,
        observation_id=request.observation_id,
        target_unit_ids=tuple(u.id for u in targets),
        settings=ContextSettings.model_validate(values).envelope(),
    )
