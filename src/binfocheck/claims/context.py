"""Strict T02 preflight and reference-only grouping; no provider dependencies."""

from dataclasses import dataclass

from binfocheck.domain.interfaces import ContextRequest, ExtractionRequest
from binfocheck.domain.observations import CaptureRequest, Observation, TextUnit
from binfocheck.domain.runs import RunManifest
from binfocheck.domain.storage import ArtifactStore, IdRequest, RecordStore
from binfocheck.domain.text import TextRecord
from binfocheck.text.context import IndexedContextBuilder
from binfocheck.text.persistence import load_index, load_inputs

from .config import ExtractionSettings
from .errors import check, require
from .persistence import canonical, closure, digest, identity


@dataclass(frozen=True)
class Group:
    id: str
    target_ids: tuple[str, ...]
    units: tuple[TextUnit, ...]
    start: int
    end: int


@dataclass(frozen=True)
class Inputs:
    request: ExtractionRequest
    settings: ExtractionSettings
    run: RunManifest
    observation: Observation
    answer: TextRecord
    capture: CaptureRequest
    units: tuple[TextUnit, ...]
    context: tuple[TextUnit, ...]
    groups: tuple[Group, ...]
    work_key: str


def prepare_inputs(
    records: RecordStore, artifacts: ArtifactStore, request: ExtractionRequest
) -> Inputs:
    request = ExtractionRequest.model_validate_json(request.model_dump_json())
    settings = ExtractionSettings.model_validate_json(canonical(request.settings.values))
    run, obs, answer = load_inputs(records, request.analysis_run_id, request.observation_id)
    check(run.status in {"running", "succeeded"}, "run_not_ready")
    check(run.configuration == request.settings.version, "run_configuration_mismatch")
    check(request.context.observation_id == obs.id, "context_observation_mismatch")
    manifest, units = load_index(records, artifacts, settings.index_artifact_id, run, obs, answer)
    result = require(
        IndexedContextBuilder(records, artifacts).build_context(
            ContextRequest(
                analysis_run_id=run.id,
                observation_id=obs.id,
                target_unit_ids=settings.target_unit_ids,
                settings=settings.context_settings.envelope(),
            )
        )
    )
    check(result == request.context and bool(result.ordered_unit_ids), "context_recipe_mismatch")
    by_id = {u.id: u for u in units}
    check(all(id in by_id for id in settings.target_unit_ids), "target_not_in_cohort")
    check(
        tuple(sorted(settings.target_unit_ids, key=lambda id: by_id[id].order))
        == settings.target_unit_ids,
        "target_order_mismatch",
    )
    capture = require(records.get_record(IdRequest(id=obs.request_id)))
    check(isinstance(capture, CaptureRequest), "capture_request_missing")
    assert isinstance(capture, CaptureRequest)
    graph = closure(records, artifacts, (run, obs, answer, capture, *units))
    work_key = identity(
        "extraction",
        request.model_dump(mode="json"),
        manifest.model_dump(mode="json"),
        [
            (r.id, digest(canonical(r.model_dump(mode="json"))))
            for r in sorted(graph, key=lambda r: r.id)
        ],
    )
    # Merge overlapping explicit regions and adjacent targeted siblings only.
    regions: list[tuple[int, int, list[str]]] = []
    for id in settings.target_unit_ids:
        unit = by_id[id]
        if regions:
            start, end, ids = regions[-1]
            previous = by_id[ids[-1]]
            adjacent = (
                unit.unit_kind == previous.unit_kind == "sentence"
                and unit.parent_unit_id == previous.parent_unit_id
                and not answer.text[end : unit.span.start].strip()
            )
            if unit.span.start < end or adjacent:
                regions[-1] = (start, max(end, unit.span.end), [*ids, id])
                continue
        regions.append((unit.span.start, unit.span.end, [id]))
    check(len(regions) <= settings.limits.max_groups, "group_limit")
    groups: list[Group] = []
    for start, end, ids in regions:
        covered = tuple(
            u
            for u in units
            if start <= u.span.start
            and u.span.end <= end
            and (
                u.unit_kind in {"sentence", "heading"}
                or u.id in manifest.opaque_unit_ids
                or u.id in ids
            )
        )
        check(bool(covered), "empty_target")
        groups.append(
            Group(
                identity("claim-group", work_key, start, end, ids), tuple(ids), covered, start, end
            )
        )
    return Inputs(
        request,
        settings,
        run,
        obs,
        answer,
        capture,
        units,
        tuple(by_id[id] for id in result.ordered_unit_ids),
        tuple(groups),
        work_key,
    )
