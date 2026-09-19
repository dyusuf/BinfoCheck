"""Context is an ordered set of references from exactly one completed cohort."""

from binfocheck.domain.interfaces import ContextRequest, ContextResult
from binfocheck.domain.observations import TextUnit
from binfocheck.domain.storage import ArtifactStore, RecordStore

from .config import context_settings
from .errors import TextError, boundary
from .persistence import load_index, load_inputs


class IndexedContextBuilder:
    def __init__(self, records: RecordStore, artifacts: ArtifactStore) -> None:
        self.records = records
        self.artifacts = artifacts

    @boundary
    def build_context(self, request: ContextRequest) -> ContextResult:
        request = ContextRequest.model_validate_json(request.model_dump_json())
        settings = context_settings(request.settings)
        if len(request.target_unit_ids) > 20:
            raise TextError("context_limit_exceeded")
        run, observation, answer = load_inputs(
            self.records, request.analysis_run_id, request.observation_id
        )
        manifest, units = load_index(
            self.records, self.artifacts, settings.index_artifact_id, run, observation, answer
        )
        by_id = {u.id: u for u in units}
        if any(id not in by_id for id in request.target_unit_ids):
            raise TextError("context_target_mismatch")
        sentences = [u for u in units if u.unit_kind == "sentence"]
        positions = {u.id: i for i, u in enumerate(sentences)}
        selected: set[str] = set()
        anchors: list[TextUnit] = []
        for id in request.target_unit_ids:
            target = by_id[id]
            if target.unit_kind == "sentence":
                anchors.append(target)
            elif target.unit_kind == "heading":
                selected.add(id)
                first = next((s for s in sentences if s.heading_unit_id == id), None)
                if first:
                    anchors.append(first)
            elif id in manifest.opaque_unit_ids:
                selected.add(id)
            else:
                anchors.extend(
                    s
                    for s in sentences
                    if target.span.start <= s.span.start and s.span.end <= target.span.end
                )
        for anchor in anchors:
            position = positions[anchor.id]
            selected.add(anchor.id)
            for direction, count in ((-1, settings.before), (1, settings.after)):
                for step in range(1, count + 1):
                    candidate = position + direction * step
                    if not 0 <= candidate < len(sentences):
                        break
                    neighbor = sentences[candidate]
                    if (
                        settings.clip_at_heading
                        and neighbor.heading_unit_id != anchor.heading_unit_id
                    ):
                        break
                    selected.add(neighbor.id)
        if settings.include_headings:
            for id in tuple(selected):
                if heading := by_id[id].heading_unit_id:
                    selected.add(heading)
        if len(selected) > settings.max_units:
            raise TextError("context_limit_exceeded")
        return ContextResult(
            observation_id=observation.id,
            ordered_unit_ids=tuple(u.id for u in units if u.id in selected),
        )
