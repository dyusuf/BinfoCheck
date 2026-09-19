"""Output/cohort manifest over immutable units; no database-specific operations."""

import base64
from typing import Literal

from binfocheck.domain.common import Contract, Digest, Id, Settings
from binfocheck.domain.interfaces import IndexRequest
from binfocheck.domain.observations import Observation, TextUnit
from binfocheck.domain.records import RecordSet
from binfocheck.domain.runs import RunManifest
from binfocheck.domain.storage import ArtifactPayload, ArtifactStore, IdRequest, RecordStore
from binfocheck.domain.text import ArtifactRef, TextRecord
from binfocheck.domain.validation import LinkedRecords

from .config import INDEX_VERSION, SPACY_VERSION, canonical, digest, index_settings
from .errors import TextError, require


class UnitEntry(Contract):
    id: Id
    sha256: Digest


class HeadingEntry(Contract):
    id: Id
    level: int
    parent_heading_id: Id | None


class IndexManifest(Contract):
    version: Literal["1"] = "1"
    status: Literal["complete"] = "complete"
    spacy_version: Literal["3.8.16"] = "3.8.16"
    artifact_id: Id
    analysis_run_id: Id
    observation_id: Id
    answer_text_id: Id
    answer_sha256: Digest
    settings: Settings
    units: tuple[UnitEntry, ...]
    headings: tuple[HeadingEntry, ...]
    opaque_unit_ids: tuple[Id, ...]


def unit_hash(unit: TextUnit) -> str:
    return digest(canonical(unit.model_dump(mode="json")))


def index_reference_id(request: IndexRequest, answer: TextRecord) -> str:
    config = index_settings(request.settings)
    return "text-index-" + digest(
        canonical(
            {
                "run": request.analysis_run_id,
                "observation": request.observation_id,
                "answer": request.answer_text_id,
                "answer_sha256": digest(answer.text.encode()),
                "version": INDEX_VERSION.model_dump(mode="json"),
                "spacy": SPACY_VERSION,
                "settings": config.model_dump(mode="json"),
            }
        )
    )


def unit_id(cohort: str, kind: str, start: int, end: int) -> str:
    return "text-unit-" + digest(canonical([cohort, kind, start, end]))


def load_inputs(
    records: RecordStore, run_id: str, observation_id: str, answer_id: str | None = None
) -> tuple[RunManifest, Observation, TextRecord]:
    run = require(records.get_record(IdRequest(id=run_id)))
    observation = require(records.get_record(IdRequest(id=observation_id)))
    if not isinstance(run, RunManifest) or not isinstance(observation, Observation):
        raise TextError("invalid_index_inputs")
    if observation.id not in run.observation_ids:
        raise TextError("run_observation_mismatch")
    if observation.status != "succeeded" or observation.answer_text_id is None:
        raise TextError("observation_not_ready")
    if answer_id is not None and answer_id != observation.answer_text_id:
        raise TextError("answer_mismatch")
    answer = require(records.get_record(IdRequest(id=observation.answer_text_id)))
    if not isinstance(answer, TextRecord) or not answer.text.strip():
        raise TextError("answer_mismatch")
    return run, observation, answer


def check(condition: bool) -> None:
    if not condition:
        raise ValueError("invalid_unit_graph")


def validate_units(
    units: tuple[TextUnit, ...],
    manifest: IndexManifest,
    run: RunManifest,
    observation: Observation,
    answer: TextRecord,
) -> None:
    try:
        settings = index_settings(manifest.settings)
        request = IndexRequest(
            analysis_run_id=run.id,
            observation_id=observation.id,
            answer_text_id=answer.id,
            settings=manifest.settings,
        )
        check(manifest.artifact_id == index_reference_id(request, answer))
        check(
            (manifest.analysis_run_id, manifest.observation_id, manifest.answer_text_id)
            == (run.id, observation.id, answer.id)
        )
        check(manifest.answer_sha256 == digest(answer.text.encode()))
        check(len(units) <= settings.max_units and len(answer.text) <= settings.max_characters)
        check(len(units) > 0 and len({u.id for u in units}) == len(units))
        check(tuple(UnitEntry(id=u.id, sha256=unit_hash(u)) for u in units) == manifest.units)
        ranks = {"heading": 0, "paragraph": 1, "bullet": 2, "sentence": 3}
        check(
            list(units)
            == sorted(units, key=lambda u: (u.span.start, -u.span.end, ranks[u.unit_kind], u.id))
        )
        links = LinkedRecords(RecordSet(records=(run, observation, answer, *units)))
        by_id = {u.id: u for u in units}
        heading: str | None = None
        for order, unit in enumerate(units):
            check(unit.order == order and unit.created_at == run.created_at)
            check(unit.analysis_run_id == run.id and unit.observation_id == observation.id)
            check(unit.input_ids == (observation.id, answer.id))
            check(
                unit.id
                == unit_id(manifest.artifact_id, unit.unit_kind, unit.span.start, unit.span.end)
            )
            check(unit.span.source_unit_id is None)
            if unit.unit_kind == "heading":
                check(unit.heading_unit_id is None and unit.parent_unit_id is None)
                heading = unit.id
            else:
                check(unit.heading_unit_id == heading)
            links.validate_record(unit)
            seen = {unit.id}
            cursor = unit
            while cursor.parent_unit_id is not None:
                check(cursor.parent_unit_id not in seen)
                seen.add(cursor.parent_unit_id)
                cursor = by_id[cursor.parent_unit_id]
            if unit.unit_kind == "sentence":
                if unit.parent_unit_id is None:
                    raise ValueError("missing_parent")
                check(by_id[unit.parent_unit_id].unit_kind in {"paragraph", "bullet"})
                check(unit.span.exact_text == unit.span.exact_text.strip())
            else:
                check(unit.parent_unit_id is None)
        check(
            tuple(h.id for h in manifest.headings)
            == tuple(u.id for u in units if u.unit_kind == "heading")
        )
        stack: list[HeadingEntry] = []
        for entry in manifest.headings:
            check(1 <= entry.level <= 6)
            while stack and stack[-1].level >= entry.level:
                stack.pop()
            check(entry.parent_heading_id == (stack[-1].id if stack else None))
            stack.append(entry)
        check(len(set(manifest.opaque_unit_ids)) == len(manifest.opaque_unit_ids))
        for opaque in manifest.opaque_unit_ids:
            check(by_id[opaque].unit_kind == "paragraph")
            check(not any(u.parent_unit_id == opaque for u in units))
    except (KeyError, ValueError):
        raise TextError("invalid_unit_graph") from None


def publish(
    records: RecordStore,
    artifacts: ArtifactStore,
    manifest: IndexManifest,
    units: tuple[TextUnit, ...],
) -> None:
    content = canonical(manifest.model_dump(mode="json"))
    ref = ArtifactRef(
        id=manifest.artifact_id,
        storage_key="text/index-completion-v1",
        sha256=digest(content),
        media_type="application/json",
        access="restricted",
    )
    require(records.put_record(ref))
    for unit in units:
        require(records.put_record(unit))
    # Payload publication is the completion marker, never a provenance input.
    require(
        artifacts.put_artifact(
            ArtifactPayload(ref=ref, content_base64=base64.b64encode(content).decode())
        )
    )


def load_index(
    records: RecordStore,
    artifacts: ArtifactStore,
    artifact_id: str,
    run: RunManifest,
    observation: Observation,
    answer: TextRecord,
) -> tuple[IndexManifest, tuple[TextUnit, ...]]:
    result = artifacts.get_artifact(IdRequest(id=artifact_id))
    if result.error and result.error.code in {"not_found", "artifact_data_missing"}:
        raise TextError(
            "index_not_found" if result.error.code == "not_found" else "index_incomplete"
        )
    payload = require(result)
    try:
        content = base64.b64decode(payload.content_base64, validate=True)
        if digest(content) != payload.ref.sha256 or payload.ref.id != artifact_id:
            raise ValueError("hash")
        manifest = IndexManifest.model_validate_json(content)
        if manifest.artifact_id != artifact_id:
            raise ValueError("identity")
    except ValueError:
        raise TextError("invalid_index_manifest") from None
    if (manifest.analysis_run_id, manifest.observation_id, manifest.answer_text_id) != (
        run.id,
        observation.id,
        answer.id,
    ):
        raise TextError("context_target_mismatch")
    if len(manifest.units) > index_settings(manifest.settings).max_units:
        raise TextError("invalid_index_manifest")
    units: list[TextUnit] = []
    for entry in manifest.units:
        result = records.get_record(IdRequest(id=entry.id))
        if result.error and result.error.code == "not_found":
            raise TextError("index_incomplete")
        unit = require(result)
        if not isinstance(unit, TextUnit):
            raise TextError("invalid_unit_graph")
        units.append(unit)
    cohort = tuple(units)
    validate_units(cohort, manifest, run, observation, answer)
    return manifest, cohort
