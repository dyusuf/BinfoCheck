"""Single export catalog for concrete record and boundary schemas."""

from dataclasses import dataclass
from typing import Protocol

from pydantic import TypeAdapter
from pydantic.json_schema import JsonSchemaValue

from . import interfaces as api
from . import storage
from .claims import CitationAssociation, Claim, ExtractionIssue
from .common import Contract, Outcome
from .corpus import ArticleVersion, CorpusManifest, Passage
from .decisions import DecisionRecord
from .evidence import AlternativeInspection, Finding
from .observations import CaptureRequest, Observation, SourceReference, TextUnit
from .records import RECORD_ADAPTER, Record, RecordSet
from .retrieval import CandidatePair, RetrievalBatch
from .runs import Review, RunManifest, StepAttempt
from .text import ArtifactRef, SpanRef, TextRecord

RECORD_MODELS: tuple[type[Contract], ...] = (
    ArtifactRef,
    TextRecord,
    CaptureRequest,
    Observation,
    SourceReference,
    TextUnit,
    Claim,
    ExtractionIssue,
    CitationAssociation,
    ArticleVersion,
    Passage,
    CorpusManifest,
    RetrievalBatch,
    CandidatePair,
    DecisionRecord,
    AlternativeInspection,
    Finding,
    RunManifest,
    StepAttempt,
    Review,
)


class Adapter(Protocol):
    def validate_json(self, data: str | bytes, /) -> Contract: ...
    def json_schema(self) -> JsonSchemaValue: ...


@dataclass(frozen=True)
class Boundary:
    request: Adapter
    response: Adapter


def boundary[Q: Contract, R: Contract](request: type[Q], response: type[R]) -> Boundary:
    return Boundary(TypeAdapter(request), TypeAdapter(response))


BOUNDARIES: dict[str, Boundary] = {
    "capture": boundary(CaptureRequest, Outcome[Observation]),
    "index_answer": boundary(api.IndexRequest, Outcome[tuple[TextUnit, ...]]),
    "build_context": boundary(api.ContextRequest, Outcome[api.ContextResult]),
    "extract_claims": boundary(api.ExtractionRequest, Outcome[api.ExtractionResult]),
    "map_citations": boundary(api.ClaimRequest, Outcome[CitationAssociation]),
    "ingest": boundary(api.IngestionRequest, Outcome[api.IngestionResult]),
    "retrieve": boundary(api.RetrievalRequest, Outcome[api.RetrievalResult]),
    "expand_context": boundary(api.PairRequest, Outcome[api.ExpandedContext]),
    "decide": boundary(api.DecisionRequest, Outcome[DecisionRecord]),
    "generate": boundary(api.GenerationRequest, Outcome[DecisionRecord]),
    "verify_candidate": boundary(api.PairRequest, Outcome[DecisionRecord]),
    "judge_correspondence": boundary(api.PairRequest, Outcome[DecisionRecord]),
    "inspect_alternatives": boundary(api.ClaimRequest, Outcome[tuple[AlternativeInspection, ...]]),
    "classify": boundary(api.ClassificationRequest, Outcome[Finding]),
    "put_artifact": boundary(storage.ArtifactPayload, Outcome[ArtifactRef]),
    "get_artifact": boundary(storage.IdRequest, Outcome[storage.ArtifactPayload]),
    "put_record": Boundary(RECORD_ADAPTER, TypeAdapter(Outcome[Record])),
    "get_record": boundary(storage.IdRequest, Outcome[Record]),
    "list_records": boundary(storage.ListRequest, Outcome[storage.RecordPage]),
    "append_decision": boundary(DecisionRecord, Outcome[DecisionRecord]),
    "append_review": boundary(Review, Outcome[Review]),
}


def schema_catalog() -> dict[str, JsonSchemaValue]:
    result = {model.__name__: model.model_json_schema() for model in RECORD_MODELS}
    result["SpanRef"] = SpanRef.model_json_schema()
    result["RecordSet"] = RecordSet.model_json_schema()
    for name, spec in BOUNDARIES.items():
        result[f"{name}.request"] = spec.request.json_schema()
        result[f"{name}.response"] = spec.response.json_schema()
    return result
