from typing import Annotated

from pydantic import Field, TypeAdapter

from .claims import CitationAssociation, Claim, ExtractionIssue
from .common import Contract
from .corpus import ArticleVersion, CorpusManifest, Passage
from .decisions import DecisionRecord
from .evidence import AlternativeInspection, Finding
from .observations import CaptureRequest, Observation, SourceReference, TextUnit
from .retrieval import CandidatePair, RetrievalBatch
from .runs import Review, RunManifest, StepAttempt
from .text import ArtifactRef, TextRecord

Record = Annotated[
    ArtifactRef
    | TextRecord
    | CaptureRequest
    | Observation
    | SourceReference
    | TextUnit
    | Claim
    | ExtractionIssue
    | CitationAssociation
    | ArticleVersion
    | Passage
    | CorpusManifest
    | RetrievalBatch
    | CandidatePair
    | DecisionRecord
    | AlternativeInspection
    | Finding
    | RunManifest
    | StepAttempt
    | Review,
    Field(discriminator="kind"),
]

RECORD_ADAPTER: TypeAdapter[Record] = TypeAdapter(Record)


class RecordSet(Contract):
    """An exchange/test bundle, not a storage format or persistence backend."""

    records: tuple[Record, ...]
