from pathlib import Path

import pytest

from binfocheck.domain.claims import Claim
from binfocheck.domain.interfaces import PairRequest
from binfocheck.domain.storage import ListRequest
from binfocheck.retrieval.config import POLICY
from binfocheck.retrieval.representations import document_text, query_text
from binfocheck.retrieval.service import HybridClaimRetriever, QueryData, Trace
from binfocheck.storage import MemoryStore, SQLiteStore
from tests.storage.helpers import success

from .helpers import SyntheticEmbedder, prepared, setup


def test_input_routing_provenance_and_both_paths() -> None:
    store = MemoryStore()
    retriever, request, embedder = prepared(store)
    index = success(retriever.load_index(request.index))
    corpus = success(retriever.corpus.load(index.corpus_id))
    claim = retriever.store.record("claim-1", Claim)
    assert embedder.encoded[0] == [document_text(p) for p in corpus.passages]
    assert embedder.encoded[1] == [query_text(claim)]
    query_id = request.settings.values["query_artifact_id"]
    assert isinstance(query_id, str)
    query = retriever.store.load(query_id, QueryData)
    assert query.lexical_text == "sind rot."
    assert query.lexical_tokens == ("sind", "rot")
    assert "Die Äpfel" in query.semantic_text

    assert index.documents[0] != corpus.passages[0].span.exact_text
    assert index.lexical_tokens[0][0] == "äpfel"
    result = success(retriever.retrieve(request))
    trace_id = result.batch.settings.values["trace_id"]
    assert isinstance(trace_id, str)
    trace = retriever.store.load(trace_id, Trace)
    assert all(path.hits for path in trace.paths)
    assert len(result.candidates) == len({h.passage_id for p in trace.paths for h in p.hits})
    assert any(len(pair.path_ranks) == 2 for pair in result.candidates)
    assert all(pair.verification_decision_id is None for pair in result.candidates)
    for pair in result.candidates:
        expanded = success(
            retriever.expand_context(
                PairRequest(analysis_run_id="run-1", candidate_pair_id=pair.id, settings=POLICY)
            )
        )
        assert pair.passage_id in expanded.ordered_passage_ids
        assert expanded.ordered_passage_ids == pair.context_passage_ids
    assert [
        r.id for r in success(store.list_records(ListRequest(record_kind="step_attempt"))).records
    ] == ["attempt-1"]


def test_reopen_reload_and_replay_without_tokenizer_or_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "private"
    with SQLiteStore(root) as store:
        retriever, request, _ = prepared(store)
        original = success(retriever.retrieve(request))

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("unexpected tokenizer or embedding call")

    monkeypatch.setattr("binfocheck.retrieval.service.tokens", forbidden)
    monkeypatch.setattr(SyntheticEmbedder, "encode", forbidden)
    with SQLiteStore(root) as store:
        retriever = HybridClaimRetriever(store, store)
        success(retriever.load_index(request.index))
        assert success(retriever.replay(original.batch.id)) == original
        assert success(retriever.retrieve(request)) == original


def test_overflow_all_passages_checked_before_encode() -> None:
    store = MemoryStore()
    corpus = setup(store)
    retriever = HybridClaimRetriever(store, store)
    embedder = SyntheticEmbedder()
    embedder.spec = embedder.spec.model_copy(update={"max_tokens": 2})
    result = retriever.prepare_index(corpus.manifest.id, embedder)
    assert result.error and result.error.code == "embedding_input_overflow"
    assert corpus.passages[0].id in result.error.message
    assert not embedder.encoded
    refs = success(store.list_records(ListRequest(record_kind="artifact", limit=1000))).records
    assert any("failure" in r.id for r in refs)
    assert not any(r.id.startswith("retrieval-index-") for r in refs)


@pytest.mark.parametrize(
    "field,value",
    [
        ("embedding_dimensions", 1024),
        ("embedding_model", "other"),
        ("corpus_manifest_id", "corpus-wrong"),
    ],
)
def test_index_reference_mismatches_fail_closed(field: str, value: object) -> None:
    store = MemoryStore()
    retriever, request, _ = prepared(store)
    bad = request.index.model_copy(update={field: value})
    result = retriever.load_index(bad)
    assert result.error and result.error.code == "index_reference_mismatch"


def test_query_model_revision_mismatch() -> None:
    store = MemoryStore()
    retriever, request, embedder = prepared(store)
    embedder.spec = embedder.spec.model_copy(update={"revision": "other"})
    result = retriever.prepare_query(request.index, "run-1", "claim-1", embedder)
    assert result.error and result.error.code == "query_model_mismatch"
    assert len(embedder.encoded) == 2


def test_real_top50_library_paths_full_union() -> None:
    store = MemoryStore()
    retriever, request, _ = prepared(store, count=12)
    result = success(retriever.retrieve(request))
    trace_id = result.batch.settings.values["trace_id"]
    assert isinstance(trace_id, str)
    trace = retriever.store.load(trace_id, Trace)
    assert [len(p.hits) for p in trace.paths] == [50, 50]
    assert len(result.candidates) >= 50
    assert {c.passage_id for c in result.candidates} == {
        h.passage_id for p in trace.paths for h in p.hits
    }
    assert [c.fused_rank for c in result.candidates] == list(range(1, len(result.candidates) + 1))
