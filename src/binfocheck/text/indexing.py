"""Deterministic units over the unchanged answer, persisted via shared protocols."""

from binfocheck.domain.interfaces import IndexRequest
from binfocheck.domain.observations import TextUnit
from binfocheck.domain.storage import ArtifactStore, RecordStore
from binfocheck.domain.text import SpanRef

from .config import digest, index_settings
from .errors import TextError, boundary
from .persistence import (
    HeadingEntry,
    IndexManifest,
    UnitEntry,
    index_reference_id,
    load_inputs,
    publish,
    unit_hash,
    unit_id,
    validate_units,
)
from .sentences import GermanSentenceSegmenter
from .structure import scan


class StoredAnswerIndexer:
    def __init__(self, records: RecordStore, artifacts: ArtifactStore) -> None:
        self.records = records
        self.artifacts = artifacts
        self.segmenter = GermanSentenceSegmenter()

    @boundary
    def index_answer(self, request: IndexRequest) -> tuple[TextUnit, ...]:
        request = IndexRequest.model_validate_json(request.model_dump_json())
        settings = index_settings(request.settings)
        run, observation, answer = load_inputs(
            self.records, request.analysis_run_id, request.observation_id, request.answer_text_id
        )
        if len(answer.text) > settings.max_characters:
            raise TextError("index_limit_exceeded")
        cohort = index_reference_id(request, answer)
        units: list[TextUnit] = []
        headings: list[HeadingEntry] = []
        stack: list[HeadingEntry] = []
        opaque: list[str] = []
        active_heading: str | None = None

        def make(kind: str, start: int, end: int, parent: str | None = None) -> TextUnit:
            return TextUnit.model_validate(
                {
                    "id": unit_id(cohort, kind, start, end),
                    "created_at": run.created_at,
                    "analysis_run_id": run.id,
                    "input_ids": (observation.id, answer.id),
                    "observation_id": observation.id,
                    "unit_kind": kind,
                    "order": 0,
                    "parent_unit_id": parent,
                    "heading_unit_id": None if kind == "heading" else active_heading,
                    "span": SpanRef(
                        text_id=answer.id, start=start, end=end, exact_text=answer.text[start:end]
                    ),
                }
            )

        for block in scan(answer.text):
            unit = make(block.kind, block.start, block.end)
            units.append(unit)
            if block.kind == "heading":
                assert block.level is not None
                while stack and stack[-1].level >= block.level:
                    stack.pop()
                entry = HeadingEntry(
                    id=unit.id, level=block.level, parent_heading_id=stack[-1].id if stack else None
                )
                headings.append(entry)
                stack.append(entry)
                active_heading = unit.id
            elif block.opaque:
                opaque.append(unit.id)
            else:
                for start, end in self.segmenter.spans(answer.text, block.content_start, block.end):
                    units.append(make("sentence", start, end, unit.id))
            if len(units) > settings.max_units:
                raise TextError("index_limit_exceeded")
        ranks = {"heading": 0, "paragraph": 1, "bullet": 2, "sentence": 3}
        units.sort(key=lambda u: (u.span.start, -u.span.end, ranks[u.unit_kind], u.id))
        ordered = tuple(u.model_copy(update={"order": i}) for i, u in enumerate(units))
        manifest = IndexManifest(
            artifact_id=cohort,
            analysis_run_id=run.id,
            observation_id=observation.id,
            answer_text_id=answer.id,
            answer_sha256=digest(answer.text.encode()),
            settings=settings.envelope(),
            units=tuple(UnitEntry(id=u.id, sha256=unit_hash(u)) for u in ordered),
            headings=tuple(headings),
            opaque_unit_ids=tuple(opaque),
        )
        validate_units(ordered, manifest, run, observation, answer)
        publish(self.records, self.artifacts, manifest, ordered)
        return ordered
