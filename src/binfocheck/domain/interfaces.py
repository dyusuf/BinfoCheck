"""Typed component boundaries. Implementations belong to their assigned tasks.

Synchronous signatures describe one operation, not a worker/execution mechanism.
Inputs identify saved originals; results may be incomplete without being failures.
"""

from typing import Annotated, Protocol

from pydantic import Field

from .claims import CitationAssociation, Claim, ExtractionIssue
from .common import Contract, Id, NonEmpty, Outcome, Settings, VersionRef
from .corpus import ArticleVersion, CorpusManifest, Passage
from .decisions import DecisionRecord
from .evidence import AlternativeInspection, Finding
from .observations import CaptureRequest, Observation, TextUnit
from .retrieval import CandidatePair, IndexRef, RetrievalBatch


class IndexRequest(Contract):
    analysis_run_id: Id
    observation_id: Id
    answer_text_id: Id
    settings: Settings


class ContextRequest(Contract):
    analysis_run_id: Id
    observation_id: Id
    target_unit_ids: Annotated[tuple[Id, ...], Field(min_length=1)]
    settings: Settings


class ContextResult(Contract):
    observation_id: Id
    ordered_unit_ids: tuple[Id, ...]


class ExtractionRequest(Contract):
    analysis_run_id: Id
    observation_id: Id
    context: ContextResult
    settings: Settings


class ExtractionResult(Contract):
    claims: tuple[Claim, ...]
    issues: tuple[ExtractionIssue, ...]


class ClaimRequest(Contract):
    analysis_run_id: Id
    claim_id: Id
    settings: Settings


class IngestionRequest(Contract):
    urls: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    settings: Settings


class IngestionResult(Contract):
    articles: tuple[ArticleVersion, ...]
    passages: tuple[Passage, ...]
    manifest: CorpusManifest


class RetrievalRequest(ClaimRequest):
    index: IndexRef


class RetrievalResult(Contract):
    batch: RetrievalBatch
    candidates: tuple[CandidatePair, ...]


class PairRequest(Contract):
    analysis_run_id: Id
    candidate_pair_id: Id
    settings: Settings


class ExpandedContext(Contract):
    candidate_pair_id: Id
    ordered_passage_ids: tuple[Id, ...]


class ModelRequest(Contract):
    analysis_run_id: Id
    task_type: NonEmpty
    input_ids: Annotated[tuple[Id, ...], Field(min_length=1)]
    input_artifact_ids: tuple[Id, ...]
    requested_model_id: NonEmpty
    prompt_version: VersionRef | None
    rubric_version: VersionRef | None
    settings: Settings


class DecisionRequest(ModelRequest):
    allowed_labels: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    probabilities_required: bool


class GenerationRequest(ModelRequest):
    output_schema: VersionRef


class ClassificationRequest(ClaimRequest):
    citation_association_id: Id
    retrieval_batch_ids: tuple[Id, ...]
    alternative_inspection_ids: tuple[Id, ...]


class ObservationProvider(Protocol):
    def capture(self, request: CaptureRequest) -> Outcome[Observation]: ...


class AnswerIndexer(Protocol):
    def index_answer(self, request: IndexRequest) -> Outcome[tuple[TextUnit, ...]]: ...


class ContextBuilder(Protocol):
    def build_context(self, request: ContextRequest) -> Outcome[ContextResult]: ...


class ClaimExtractor(Protocol):
    def extract_claims(self, request: ExtractionRequest) -> Outcome[ExtractionResult]: ...


class CitationMapper(Protocol):
    def map_citations(self, request: ClaimRequest) -> Outcome[CitationAssociation]: ...


class CorpusIngestor(Protocol):
    def ingest(self, request: IngestionRequest) -> Outcome[IngestionResult]: ...


class ClaimRetriever(Protocol):
    def retrieve(self, request: RetrievalRequest) -> Outcome[RetrievalResult]: ...


class ContextExpander(Protocol):
    def expand_context(self, request: PairRequest) -> Outcome[ExpandedContext]: ...


class DecisionModel(Protocol):
    def decide(self, request: DecisionRequest) -> Outcome[DecisionRecord]: ...


class GenerationModel(Protocol):
    def generate(self, request: GenerationRequest) -> Outcome[DecisionRecord]: ...


class CandidateVerifier(Protocol):
    def verify_candidate(self, request: PairRequest) -> Outcome[DecisionRecord]: ...


class CorrespondenceJudge(Protocol):
    def judge_correspondence(self, request: PairRequest) -> Outcome[DecisionRecord]: ...


class AlternativeSourceAnalyzer(Protocol):
    def inspect_alternatives(
        self, request: ClaimRequest
    ) -> Outcome[tuple[AlternativeInspection, ...]]: ...


class EvidenceClassifier(Protocol):
    def classify(self, request: ClassificationRequest) -> Outcome[Finding]: ...
