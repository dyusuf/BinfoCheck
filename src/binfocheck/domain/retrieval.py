from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .common import Contract, DerivedRecord, Finite, Id, NonEmpty, Positive, Settings, VersionRef


class IndexRef(Contract):
    id: Id
    corpus_manifest_id: Id
    version: VersionRef
    embedding_model: NonEmpty
    embedding_dimensions: Positive
    lexical_settings: Settings


class RetrievalBatch(DerivedRecord):
    kind: Literal["retrieval_batch"] = "retrieval_batch"
    claim_id: Id
    corpus_manifest_id: Id
    index: IndexRef
    candidate_pair_ids: tuple[Id, ...]
    completion: Literal["complete", "incomplete", "failed"]
    truncation_reason: NonEmpty | None
    settings: Settings

    @model_validator(mode="after")
    def retrieval_state(self) -> Self:
        if self.index.corpus_manifest_id != self.corpus_manifest_id:
            raise ValueError("index_corpus_mismatch")
        if (self.completion == "complete") != (self.truncation_reason is None):
            raise ValueError("retrieval_completion_reason_mismatch")
        return self


class PathRank(Contract):
    path: Literal["semantic", "lexical"]
    rank: Positive
    score: Finite


class CandidatePair(DerivedRecord):
    kind: Literal["candidate_pair"] = "candidate_pair"
    claim_id: Id
    retrieval_batch_id: Id
    corpus_manifest_id: Id
    index_id: Id
    passage_id: Id
    path_ranks: Annotated[tuple[PathRank, ...], Field(min_length=1)]
    fused_rank: Positive
    context_passage_ids: tuple[Id, ...]
    verification_decision_id: Id | None
    correspondence_decision_id: Id | None

    @model_validator(mode="after")
    def unique_paths(self) -> Self:
        if len({item.path for item in self.path_ranks}) != len(self.path_ranks):
            raise ValueError("duplicate_retrieval_path")
        return self
