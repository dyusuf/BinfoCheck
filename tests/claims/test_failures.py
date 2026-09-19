from unittest.mock import patch

import pytest
from pydantic import JsonValue

from binfocheck.claims.config import ExtractionSettings
from binfocheck.claims.context import prepare_inputs
from binfocheck.claims.persistence import canonical, identity
from binfocheck.domain.common import ErrorDetail, Outcome
from binfocheck.domain.decisions import DecisionRecord
from binfocheck.domain.interfaces import DecisionRequest
from binfocheck.domain.records import Record
from binfocheck.domain.storage import ArtifactPayload, IdRequest
from binfocheck.domain.text import ArtifactRef
from binfocheck.models.persistence import prepare
from binfocheck.storage import MemoryStore
from tests.claims.helpers import candidate, candidates, positive, seed_extraction
from tests.storage.helpers import success


@pytest.mark.parametrize(
    "corruption",
    [
        "wrong_run",
        "wrong_observation",
        "context_observation",
        "context_order",
        "missing_unit",
        "missing_index",
        "bad_index_hash",
        "foreign_unit",
        "wrong_run_config",
    ],
)
def test_preflight_rejects_before_models(corruption: str) -> None:
    store = MemoryStore()
    req, ext, double = seed_extraction(store, "Rot. Blau.", lambda _stage, _state: "factual")
    original_get = store.get_record
    original_artifact = store.get_artifact
    settings = ExtractionSettings.model_validate_json(canonical(req.settings.values))
    if corruption == "wrong_run":
        req = req.model_copy(update={"analysis_run_id": "absent"})
    if corruption == "wrong_observation":
        req = req.model_copy(update={"observation_id": "absent"})
    if corruption == "context_observation":
        req = req.model_copy(
            update={"context": req.context.model_copy(update={"observation_id": "foreign"})}
        )
    if corruption == "context_order":
        req = req.model_copy(
            update={
                "context": req.context.model_copy(
                    update={"ordered_unit_ids": tuple(reversed(req.context.ordered_unit_ids))}
                )
            }
        )

    def get(request: IdRequest) -> Outcome[Record]:
        result = original_get(request)
        if request.id == req.context.ordered_unit_ids[0]:
            if corruption == "missing_unit":
                return Outcome(
                    status="failed",
                    value=None,
                    error=ErrorDetail(code="not_found", message="missing"),
                )
            if corruption == "foreign_unit" and result.value:
                return Outcome(
                    status="succeeded",
                    value=result.value.model_copy(update={"analysis_run_id": "foreign"}),
                    error=None,
                )
        if corruption == "wrong_run_config" and request.id == req.analysis_run_id and result.value:
            return Outcome(
                status="succeeded",
                value=result.value.model_copy(update={"model_ids": ()}),
                error=None,
            )
        return result

    def artifact(request: IdRequest) -> Outcome[ArtifactPayload]:
        if request.id == settings.index_artifact_id and corruption in {
            "missing_index",
            "bad_index_hash",
        }:
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(
                    code="artifact_data_missing"
                    if corruption == "missing_index"
                    else "artifact_hash_mismatch",
                    message="synthetic corruption",
                ),
            )
        return original_artifact(request)

    with patch.object(store, "get_record", get), patch.object(store, "get_artifact", artifact):
        result = ext.extract_claims(req)
    assert result.status == "failed" and result.value is None
    assert not double.calls


@pytest.mark.parametrize("wrong", ["id", "kind"])
def test_exact_identity_rejects_wrong_record(wrong: str) -> None:
    store = MemoryStore()
    req, ext, double = seed_extraction(store, "Rot.", lambda _stage, _state: "factual")
    if wrong == "id":
        double.wrong_id = True
        assert ext.extract_claims(req).status == "failed"
    else:

        def broken(request: DecisionRequest) -> Outcome[DecisionRecord]:
            prepared = prepare(request, double.dc, double.resources, store)
            success(
                store.put_record(
                    ArtifactRef(
                        id=prepared.record_id,
                        storage_key="synthetic",
                        sha256="0" * 64,
                        media_type="application/json",
                        access="restricted",
                    )
                )
            )
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="synthetic_failure", message="failed"),
            )

        with patch.object(double, "decide", broken):
            assert ext.extract_claims(req).status == "failed"


@pytest.mark.parametrize(
    "role",
    [
        "extraction-state",
        "extraction-binding",
        "extraction-evidence",
        "extraction-final",
        "extraction-complete",
        "claim",
    ],
)
def test_storage_failure_retry_no_model_repeat(role: str) -> None:
    store = MemoryStore()

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        return candidates(candidate(store, state, "Rot.")) if stage == "F" else positive(stage)

    req, ext, double = seed_extraction(store, "Rot.", reply)
    original_artifact, original_record = store.put_artifact, store.put_record
    failed = False

    def artifact(payload: ArtifactPayload) -> Outcome[ArtifactRef]:
        nonlocal failed
        if not failed and payload.ref.id.startswith(role + "-"):
            failed = True
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="storage_io_error", message="write failed"),
            )
        return original_artifact(payload)

    def record(value: Record) -> Outcome[Record]:
        nonlocal failed
        if role == "claim" and value.kind == "claim" and not failed:
            failed = True
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="storage_io_error", message="write failed"),
            )
        return original_record(value)

    with patch.object(store, "put_artifact", artifact), patch.object(store, "put_record", record):
        outcome = ext.extract_claims(req)
    assert failed and outcome.status == "failed"
    result = success(ext.extract_claims(req))
    assert len(result.claims) == 1 and len(double.calls) == 6
    assert success(ext.extract_claims(req)) == result and len(double.calls) == 6


def test_partial_stage_failure_accounted() -> None:
    store = MemoryStore()

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "B":
            src = state["source"]
            assert isinstance(src, dict)
            double.failure = "synthetic_failure" if src["text"] == "Blau." else None
        if stage == "F":
            return candidates(candidate(store, state, "Rot."))
        return positive(stage)

    req, ext, double = seed_extraction(store, "Rot.\n\nBlau.", reply)
    # Fail second group's ambiguity after its selection was recorded.
    outcome = ext.extract_claims(req)
    result = success(outcome)
    assert len(result.claims) == 1 and any(i.issue == "failed" for i in result.issues)
    assert outcome.reason == "partial_extraction"


def test_budget_exhaustion_audits_all_targets() -> None:
    store = MemoryStore()
    req, ext, double = seed_extraction(store, "Rot.\n\nBlau.", lambda _stage, _state: "factual")
    settings = ExtractionSettings.model_validate_json(canonical(req.settings.values))
    settings = settings.model_copy(
        update={"limits": settings.limits.model_copy(update={"max_model_calls": 0})}
    )
    req = req.model_copy(update={"settings": settings.envelope(req.settings.version)})
    result = success(ext.extract_claims(req))
    assert len(result.issues) == 2 and not result.claims and not double.calls
    key = prepare_inputs(store, store, req).work_key
    assert (
        store.get_artifact(IdRequest(id=identity("extraction-complete", key))).status == "succeeded"
    )


def test_run_allowance_shared_across_distinct_scopes() -> None:
    from binfocheck.domain.interfaces import ContextRequest
    from binfocheck.text.context import IndexedContextBuilder

    store = MemoryStore()
    req, ext, double = seed_extraction(
        store, "Rot.\n\nBlau.", lambda _stage, _state: "nonfactual", request_limit=1
    )
    settings = ExtractionSettings.model_validate_json(canonical(req.settings.values))
    for index, target in enumerate(settings.target_unit_ids):
        scoped = settings.model_copy(update={"target_unit_ids": (target,)})
        context = success(
            IndexedContextBuilder(store, store).build_context(
                ContextRequest(
                    analysis_run_id=req.analysis_run_id,
                    observation_id=req.observation_id,
                    target_unit_ids=(target,),
                    settings=settings.context_settings.envelope(),
                )
            )
        )
        request = req.model_copy(
            update={"context": context, "settings": scoped.envelope(req.settings.version)}
        )
        result = success(ext.extract_claims(request))
        assert len(result.issues) == 1
        assert result.issues[0].issue == ("excluded" if index == 0 else "failed")
        assert success(ext.extract_claims(request)) == result
    assert len(double.calls) == 1
