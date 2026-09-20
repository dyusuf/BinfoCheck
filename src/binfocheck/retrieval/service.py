"""T07 preparation, immutable index publication and model-free component boundaries."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from pydantic import field_validator

from binfocheck.corpus.ingestion import StoredCorpusIngestor
from binfocheck.domain.claims import Claim
from binfocheck.domain.common import Contract, Outcome, Settings, require_utc
from binfocheck.domain.interfaces import (
    ExpandedContext,
    IngestionResult,
    PairRequest,
    RetrievalRequest,
    RetrievalResult,
)
from binfocheck.domain.retrieval import CandidatePair, IndexRef, RetrievalBatch
from binfocheck.domain.runs import RunManifest
from binfocheck.domain.storage import ArtifactStore, RecordStore
from binfocheck.domain.text import ArtifactRef

from .config import (
    INDEX_VERSION,
    LEXICAL,
    PACKAGES,
    POLICY,
    EmbeddingSpec,
    digest,
    identity,
    verify_packages,
)
from .embeddings import Embedder, preflight, validate_vectors
from .errors import RetrievalError, check, require
from .fusion import Fused, PathTrace, fuse, top_path
from .indexes import LexicalState, build_lexical, lexical_scores, restore_lexical, semantic_scores
from .persistence import Store, closure
from .representations import context_ids, document_text, query_text, tokens


class IndexData(Contract):
    format: Literal["t07-index/1"] = "t07-index/1"
    corpus_id: str
    source_hashes: dict[str, str]
    spec: EmbeddingSpec
    software: dict[str, str]
    passage_ids: tuple[str, ...]
    documents: tuple[str, ...]
    lexical_tokens: tuple[tuple[str, ...], ...]
    token_counts: tuple[int, ...]
    vectors: tuple[tuple[float, ...], ...]
    lexical: LexicalState


class IndexCompletion(Contract):
    format: Literal["t07-index-completion/1"] = "t07-index-completion/1"
    index: IndexRef
    data_sha256: str


class QueryData(Contract):
    format: Literal["t07-query/1"] = "t07-query/1"
    index: IndexRef
    spec: EmbeddingSpec
    claim_id: str
    run_id: str
    source_hashes: dict[str, str]
    semantic_text: str
    lexical_text: str
    lexical_tokens: tuple[str, ...]
    token_count: int
    vector: tuple[float, ...]


class Trace(Contract):
    format: Literal["t07-trace/1"] = "t07-trace/1"
    request: RetrievalRequest
    query_artifact_id: str
    paths: tuple[PathTrace, ...]
    fused: tuple[Fused, ...]
    contexts: dict[str, tuple[str, ...]]


class PathEvidence(Contract):
    format: Literal["t07-path/1"] = "t07-path/1"
    request: RetrievalRequest
    trace: PathTrace


class Publication(Contract):
    format: Literal["t07-publication/1"] = "t07-publication/1"
    request: RetrievalRequest
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return require_utc(value)


class Completion(Contract):
    format: Literal["t07-retrieval-completion/1"] = "t07-retrieval-completion/1"
    result: RetrievalResult
    trace_id: str
    trace_sha256: str
    source_hashes: dict[str, str]


def request_settings(query_id: str) -> Settings:
    return Settings(version=POLICY.version, values={**POLICY.values, "query_artifact_id": query_id})


class HybridClaimRetriever:
    def __init__(self, records: RecordStore, artifacts: ArtifactStore) -> None:
        self.store = Store(records, artifacts)
        self.corpus = StoredCorpusIngestor(records, artifacts)

    def _perform[T](
        self, operation: str, ids: tuple[str, ...], action: Callable[[], T]
    ) -> Outcome[T]:
        try:
            return Outcome(status="succeeded", value=action(), error=None)
        except Exception as exception:
            error = (
                exception
                if isinstance(exception, RetrievalError)
                else RetrievalError("retrieval_operation_failed")
            )
            try:
                self.store.failure(operation, ids, error.detail)
            except Exception:
                return Outcome(
                    status="failed",
                    value=None,
                    error=RetrievalError("failure_persistence_failed").detail,
                )
            return Outcome(status="failed", value=None, error=error.detail)

    def _corpus(self, id: str) -> tuple[IngestionResult, dict[str, str]]:
        result = require(self.corpus.load(id))
        check(result.manifest.status == "ready", "corpus_not_ready", id)
        check(
            len(set(result.manifest.passage_ids)) == len(result.passages), "corpus_passage_mismatch"
        )
        check(
            tuple(p.id for p in result.passages) == result.manifest.passage_ids,
            "corpus_passage_mismatch",
        )
        for article in result.articles:
            pp = [p for p in result.passages if p.article_version_id == article.id]
            check(sorted(p.order for p in pp) == list(range(len(pp))), "passage_order_mismatch")
        completion = self.store.record(id + ".completion.v1", ArtifactRef)
        hashes = closure(self.store, [result.manifest, completion])
        # T06 load additionally verifies its own completion's full artifact/media chain.
        return result, hashes

    def prepare_index(self, corpus_id: str, embedder: Embedder) -> Outcome[IndexRef]:
        return self._perform(
            "prepare_index", (corpus_id,), lambda: self._prepare_index(corpus_id, embedder)
        )

    def _prepare_index(self, corpus_id: str, embedder: Embedder) -> IndexRef:
        verify_packages()
        corpus, hashes = self._corpus(corpus_id)
        documents = tuple(document_text(p) for p in corpus.passages)
        counts = preflight(embedder, list(zip(corpus.manifest.passage_ids, documents, strict=True)))
        lexical = tuple(tokens(p.span.exact_text) for p in corpus.passages)
        # All input-length checks finish before the first encode invocation.
        rows = embedder.encode(documents)
        validate_vectors(rows, len(documents), embedder.spec.dimensions)
        data = IndexData(
            corpus_id=corpus_id,
            source_hashes=hashes,
            spec=embedder.spec,
            software=PACKAGES,
            passage_ids=corpus.manifest.passage_ids,
            documents=documents,
            lexical_tokens=lexical,
            token_counts=counts,
            vectors=tuple(tuple(row) for row in rows),
            lexical=build_lexical(lexical),
        )
        ref = self._index_ref(data)
        saved = self.store.save("index", data, ref.id)
        self._validate_index(self.store.load(ref.id, IndexData), ref)
        self.store.save(
            "index-completion",
            IndexCompletion(index=ref, data_sha256=saved.sha256),
            ref.id + ".complete",
        )
        self._load_index(ref)
        return ref

    @staticmethod
    def _index_ref(data: IndexData) -> IndexRef:
        return IndexRef(
            id=identity("index", data.model_dump(mode="json")),
            corpus_manifest_id=data.corpus_id,
            version=INDEX_VERSION,
            embedding_model=data.spec.model,
            embedding_dimensions=data.spec.dimensions,
            lexical_settings=LEXICAL,
        )

    def load_index(self, ref: IndexRef) -> Outcome[IndexData]:
        return self._perform("load_index", (ref.id,), lambda: self._load_index(ref)[0])

    def _load_index(self, ref: IndexRef) -> tuple[IndexData, IngestionResult]:
        verify_packages()
        ref = IndexRef.model_validate_json(ref.model_dump_json())
        completion = self.store.load(ref.id + ".complete", IndexCompletion)
        check(completion.index == ref, "index_reference_mismatch")
        raw = self.store.bytes(ref.id)
        check(digest(raw) == completion.data_sha256, "index_hash_mismatch")
        return self._validate_index(IndexData.model_validate_json(raw), ref)

    def _validate_index(self, data: IndexData, ref: IndexRef) -> tuple[IndexData, IngestionResult]:
        data.spec.validate_supported()
        check(self._index_ref(data) == ref and data.software == PACKAGES, "index_identity_mismatch")
        corpus, hashes = self._corpus(ref.corpus_manifest_id)
        check(data.source_hashes == hashes, "index_corpus_mismatch")
        check(data.passage_ids == corpus.manifest.passage_ids, "index_membership_mismatch")
        check(
            data.documents == tuple(document_text(p) for p in corpus.passages),
            "index_representation_mismatch",
        )
        check(
            len(data.lexical_tokens) == len(data.passage_ids) == len(data.token_counts)
            and data.lexical.num_docs == len(data.passage_ids),
            "index_membership_mismatch",
        )
        check(
            all(0 < n <= data.spec.max_tokens for n in data.token_counts), "invalid_index_lengths"
        )
        validate_vectors(data.vectors, len(data.passage_ids), data.spec.dimensions)
        restore_lexical(data.lexical)
        return data, corpus

    def _claim(
        self, run_id: str, claim_id: str, corpus_id: str
    ) -> tuple[Claim, RunManifest, dict[str, str]]:
        claim = self.store.record(claim_id, Claim)
        run = self.store.record(run_id, RunManifest)
        check(claim.analysis_run_id == run_id, "claim_run_mismatch")
        check(run.corpus_manifest_id in (None, corpus_id), "run_corpus_mismatch")
        return claim, run, closure(self.store, [claim, run])

    def prepare_query(
        self, ref: IndexRef, run_id: str, claim_id: str, embedder: Embedder
    ) -> Outcome[ArtifactRef]:
        return self._perform(
            "prepare_query",
            (ref.id, run_id, claim_id),
            lambda: self._prepare_query(ref, run_id, claim_id, embedder),
        )

    def _prepare_query(
        self, ref: IndexRef, run_id: str, claim_id: str, embedder: Embedder
    ) -> ArtifactRef:
        data, _ = self._load_index(ref)
        check(embedder.spec == data.spec, "query_model_mismatch")
        claim, _, hashes = self._claim(run_id, claim_id, data.corpus_id)
        text = query_text(claim)
        lengths = preflight(embedder, [(claim.id, text)])
        vectors = embedder.encode([text])
        validate_vectors(vectors, 1, data.spec.dimensions)
        query = QueryData(
            index=ref,
            spec=data.spec,
            claim_id=claim_id,
            run_id=run_id,
            source_hashes=hashes,
            semantic_text=text,
            lexical_text=claim.original_span.exact_text,
            lexical_tokens=tokens(claim.original_span.exact_text),
            token_count=lengths[0],
            vector=tuple(vectors[0]),
        )
        return self.store.save("query", query)

    def _inputs(
        self, request: RetrievalRequest
    ) -> tuple[IndexData, IngestionResult, QueryData, RunManifest, str]:
        request = RetrievalRequest.model_validate_json(request.model_dump_json())
        id = request.settings.values.get("query_artifact_id")
        check(isinstance(id, str), "missing_query_artifact")
        assert isinstance(id, str)
        check(request.settings == request_settings(id), "retrieval_settings_mismatch")
        index, corpus = self._load_index(request.index)
        query = self.store.load(id, QueryData)
        claim, run, hashes = self._claim(request.analysis_run_id, request.claim_id, index.corpus_id)
        check(query.index == request.index and query.spec == index.spec, "query_model_mismatch")
        check(
            query.claim_id == claim.id and query.run_id == run.id and query.source_hashes == hashes,
            "query_input_mismatch",
        )
        check(
            query.semantic_text == query_text(claim)
            and query.lexical_text == claim.original_span.exact_text,
            "query_representation_mismatch",
        )
        check(0 < query.token_count <= index.spec.max_tokens, "invalid_query_length")
        check(identity("query", query.model_dump(mode="json")) == id, "query_identity_mismatch")
        validate_vectors((query.vector,), 1, index.spec.dimensions)
        return index, corpus, query, run, id

    def rescore(self, request: RetrievalRequest) -> Outcome[Trace]:
        """Recompute scores from saved indexes/vectors, without consulting saved results."""

        def action() -> Trace:
            index, corpus, query, _, query_id = self._inputs(request)
            return self._trace(request, index, corpus, query, query_id)

        return self._perform("rescore", (request.index.id, request.claim_id), action)

    def _trace(
        self,
        request: RetrievalRequest,
        index: IndexData,
        corpus: IngestionResult,
        query: QueryData,
        query_id: str,
    ) -> Trace:
        batch_id = identity("batch", request.model_dump(mode="json"))
        semantic = top_path(
            index.passage_ids,
            semantic_scores(index.passage_ids, index.vectors, query.vector, index.spec.dimensions),
            "semantic",
        )
        self.store.save(
            "path", PathEvidence(request=request, trace=semantic), batch_id + ".semantic"
        )
        lexical = top_path(
            index.passage_ids, lexical_scores(index.lexical, query.lexical_tokens), "lexical"
        )
        self.store.save("path", PathEvidence(request=request, trace=lexical), batch_id + ".lexical")
        paths = (semantic, lexical)
        fused = fuse(paths)
        passages = {p.id: p for p in corpus.passages}
        contexts = {
            hit.passage_id: context_ids(passages[hit.passage_id], corpus.passages) for hit in fused
        }
        return Trace(
            request=request, query_artifact_id=query_id, paths=paths, fused=fused, contexts=contexts
        )

    def retrieve(self, request: RetrievalRequest) -> Outcome[RetrievalResult]:
        return self._perform(
            "retrieve", (request.index.id, request.claim_id), lambda: self._retrieve(request)
        )

    def _retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        index, corpus, query, run, query_id = self._inputs(request)
        batch_id = identity("batch", request.model_dump(mode="json"))
        if self.store.exists(batch_id + ".complete"):
            return self._replay(batch_id)
        publication_id = batch_id + ".publication"
        if not self.store.exists(publication_id):
            self.store.save(
                "publication",
                Publication(request=request, created_at=datetime.now(UTC)),
                publication_id,
            )
        publication = self.store.load(publication_id, Publication)
        check(publication.request == request, "publication_request_mismatch")
        trace = self._trace(request, index, corpus, query, query_id)
        fused, contexts = trace.fused, trace.contexts
        trace_ref = self.store.save("trace", trace)
        candidates = tuple(
            CandidatePair(
                id=identity("pair", [batch_id, hit.passage_id]),
                created_at=publication.created_at,
                analysis_run_id=run.id,
                input_ids=(query.claim_id, hit.passage_id, query_id),
                claim_id=query.claim_id,
                retrieval_batch_id=batch_id,
                corpus_manifest_id=index.corpus_id,
                index_id=request.index.id,
                passage_id=hit.passage_id,
                path_ranks=hit.path_ranks,
                fused_rank=i + 1,
                context_passage_ids=contexts[hit.passage_id],
                verification_decision_id=None,
                correspondence_decision_id=None,
            )
            for i, hit in enumerate(fused)
        )
        batch = RetrievalBatch(
            id=batch_id,
            created_at=publication.created_at,
            analysis_run_id=run.id,
            input_ids=(query.claim_id, index.corpus_id, request.index.id, query_id, publication_id),
            claim_id=query.claim_id,
            corpus_manifest_id=index.corpus_id,
            index=request.index,
            candidate_pair_ids=tuple(c.id for c in candidates),
            completion="complete",
            truncation_reason=None,
            settings=Settings(
                version=POLICY.version, values={**request.settings.values, "trace_id": trace_ref.id}
            ),
        )
        result = RetrievalResult(batch=batch, candidates=candidates)
        sources = closure(self.store, [batch, *candidates])
        for record in (*candidates, batch):
            self.store.put(record)
            check(
                self.store.record(record.id, type(record)) == record,
                "publication_readback_mismatch",
            )
        check(digest(self.store.bytes(trace_ref.id)) == trace_ref.sha256, "trace_hash_mismatch")
        self.store.save(
            "completion",
            Completion(
                result=result,
                trace_id=trace_ref.id,
                trace_sha256=trace_ref.sha256,
                source_hashes=sources,
            ),
            batch_id + ".complete",
        )
        return self._replay(batch_id)

    def replay(self, batch_id: str) -> Outcome[RetrievalResult]:
        return self._perform("replay", (batch_id,), lambda: self._replay(batch_id))

    def _replay(self, batch_id: str) -> RetrievalResult:
        complete = self.store.load(batch_id + ".complete", Completion)
        trace = self.store.load(complete.trace_id, Trace)
        check(
            digest(self.store.bytes(complete.trace_id)) == complete.trace_sha256,
            "trace_hash_mismatch",
        )
        _, corpus, _, _, _ = self._inputs(trace.request)
        check(
            identity("batch", trace.request.model_dump(mode="json")) == batch_id,
            "batch_identity_mismatch",
        )
        result = complete.result
        publication = self.store.load(batch_id + ".publication", Publication)
        check(
            publication.request == trace.request
            and publication.created_at == result.batch.created_at
            and all(p.created_at == publication.created_at for p in result.candidates),
            "publication_mismatch",
        )
        check(result.batch.id == batch_id, "batch_identity_mismatch")
        check(self.store.record(batch_id, RetrievalBatch) == result.batch, "batch_record_mismatch")
        for pair in result.candidates:
            check(self.store.record(pair.id, CandidatePair) == pair, "candidate_record_mismatch")
        check(
            closure(self.store, [result.batch, *result.candidates]) == complete.source_hashes,
            "retrieval_source_mismatch",
        )
        check(
            fuse(trace.paths) == trace.fused and len(result.candidates) == len(trace.fused),
            "fusion_trace_mismatch",
        )
        by_id = {p.id: p for p in corpus.passages}
        for i, (pair, hit) in enumerate(zip(result.candidates, trace.fused, strict=True)):
            check(
                pair.passage_id == hit.passage_id
                and pair.path_ranks == hit.path_ranks
                and pair.fused_rank == i + 1,
                "candidate_trace_mismatch",
            )
            check(
                pair.context_passage_ids
                == trace.contexts[pair.passage_id]
                == context_ids(by_id[pair.passage_id], corpus.passages),
                "context_trace_mismatch",
            )
        return result

    def expand_context(self, request: PairRequest) -> Outcome[ExpandedContext]:
        def action() -> ExpandedContext:
            check(request.settings == POLICY, "context_settings_mismatch")
            pair = self.store.record(request.candidate_pair_id, CandidatePair)
            check(pair.analysis_run_id == request.analysis_run_id, "context_run_mismatch")
            self._replay(pair.retrieval_batch_id)
            return ExpandedContext(
                candidate_pair_id=pair.id, ordered_passage_ids=pair.context_passage_ids
            )

        return self._perform("expand_context", (request.candidate_pair_id,), action)


class SavedContextExpander(HybridClaimRetriever):
    """Same saved-cohort implementation, exposed through the ContextExpander protocol."""
