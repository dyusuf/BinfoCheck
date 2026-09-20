from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from binfocheck.domain.common import ErrorDetail, Outcome
from binfocheck.domain.storage import ArtifactPayload, IdRequest, ListRequest
from binfocheck.domain.text import ArtifactRef
from binfocheck.retrieval.config import EmbeddingSpec
from binfocheck.retrieval.embeddings import LocalHarrier, preflight, validate_vectors
from binfocheck.retrieval.errors import RetrievalError
from binfocheck.retrieval.representations import context_ids
from binfocheck.retrieval.service import HybridClaimRetriever, Trace
from binfocheck.storage import MemoryStore
from tests.storage.helpers import success

from .helpers import SyntheticEmbedder, prepared, setup


@pytest.mark.parametrize(
    "rows,code",
    [
        ([], "embedding_count_mismatch"),
        ([[1.0]], "embedding_dimension_mismatch"),
        ([[float("nan"), 1.0]], "embedding_nonfinite"),
        ([[float("inf"), 1.0]], "embedding_nonfinite"),
        ([[0.0, 0.0]], "embedding_zero_or_invalid_norm"),
    ],
)
def test_invalid_vectors(rows: list[list[float]], code: str) -> None:
    with pytest.raises(RetrievalError, match=code):
        validate_vectors(rows, 1, 2)


def test_missing_local_model_never_imports_or_downloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("model import forbidden")

    monkeypatch.setattr("binfocheck.retrieval.embeddings.importlib.import_module", forbidden)
    with pytest.raises(RetrievalError, match="local_model_unavailable"):
        LocalHarrier.open(tmp_path)


def test_local_adapter_counts_special_tokens_disables_truncation_and_hidden_prompt() -> None:
    class FakeModel:
        max_seq_length = 32768
        calls: list[dict[str, Any]] = []

        def tokenizer(self, text: str, **kwargs: Any) -> dict[str, list[int]]:
            assert kwargs == dict(
                add_special_tokens=True,
                truncation=False,
                padding=False,
                return_attention_mask=False,
            )
            return {"input_ids": list(range(len(text) + 2))}

        def encode(self, texts: list[str], **kwargs: Any) -> Any:
            import numpy as np

            self.calls.append(kwargs)
            assert kwargs["prompt"] == "" and kwargs["normalize_embeddings"] is True
            return np.ones((len(texts), 1024))

    fake = FakeModel()
    adapter = LocalHarrier(fake)
    assert adapter.count_tokens("Äpfel") == 7
    assert preflight(adapter, [("p", "x" * 32766)]) == (32768,)
    with pytest.raises(RetrievalError, match="p"):
        preflight(adapter, [("p", "x" * 32767)])
    assert fake.calls == []
    assert len(adapter.encode(["hello"])[0]) == 1024


def test_last_passage_overflow_prevents_all_embedding() -> None:
    store = MemoryStore()
    corpus = setup(store)
    retriever = HybridClaimRetriever(store, store)

    class LastTooLong(SyntheticEmbedder):
        def count_tokens(self, text: str) -> int:
            super().count_tokens(text)
            return 32769 if len(self.counted) == len(corpus.passages) else 10

    embedder = LastTooLong()
    result = retriever.prepare_index(corpus.manifest.id, embedder)
    assert result.error and result.error.code == "embedding_input_overflow"
    assert corpus.passages[-1].id in result.error.message
    assert len(embedder.counted) == len(corpus.passages) and not embedder.encoded


def test_bad_encode_does_not_publish_index() -> None:
    store = MemoryStore()
    corpus = setup(store)

    class WrongDimensions(SyntheticEmbedder):
        def encode(self, texts: Sequence[str]) -> list[list[float]]:
            return [[1.0, 2.0] for _ in texts]

    result = HybridClaimRetriever(store, store).prepare_index(corpus.manifest.id, WrongDimensions())
    assert result.error and result.error.code == "embedding_dimension_mismatch"
    assert not any(
        r.id.startswith("retrieval-index-")
        for r in success(store.list_records(ListRequest(limit=1000))).records
    )


def test_context_clips_exact_section_and_article() -> None:
    store = MemoryStore()
    corpus = setup(store)
    first, middle, last_a, only_b = corpus.passages[:4]
    assert context_ids(first, corpus.passages) == (first.id, middle.id)
    assert context_ids(middle, corpus.passages) == (first.id, middle.id, last_a.id)
    assert context_ids(last_a, corpus.passages) == (middle.id, last_a.id)
    assert context_ids(only_b, corpus.passages) == (only_b.id,)


@pytest.mark.parametrize(
    "target", ["query", "index", "index-completion", "corpus-completion", "trace"]
)
def test_missing_artifacts_never_become_empty_success(
    target: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    retriever, request, _ = prepared(store)
    result = success(retriever.retrieve(request))
    ids = {
        "query": request.settings.values["query_artifact_id"],
        "index": request.index.id,
        "index-completion": request.index.id + ".complete",
        "corpus-completion": request.index.corpus_manifest_id + ".completion.v1",
        "trace": result.batch.settings.values["trace_id"],
    }
    get = store.get_artifact

    def missing(req: IdRequest) -> Outcome[ArtifactPayload]:
        if req.id == ids[target]:
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="artifact_data_missing", message="missing"),
            )
        return get(req)

    monkeypatch.setattr(store, "get_artifact", missing)
    replay = retriever.replay(result.batch.id)
    assert replay.status == "failed" and replay.value is None


def test_corrupt_payload_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MemoryStore()
    retriever, request, _ = prepared(store)
    get = store.get_artifact

    def corrupt(req: IdRequest) -> Outcome[ArtifactPayload]:
        response = get(req)
        if req.id == request.index.id:
            payload = success(response).model_copy(update={"content_base64": "e30="})
            return Outcome(status="succeeded", value=payload, error=None)
        return response

    monkeypatch.setattr(store, "get_artifact", corrupt)
    result = retriever.load_index(request.index)
    assert result.error and result.error.code == "artifact_mismatch"


def test_failed_lexical_path_preserves_semantic_trace_no_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    retriever, request, _ = prepared(store)

    def fail(*args: object) -> None:
        raise RuntimeError("synthetic secret must not be logged")

    monkeypatch.setattr("binfocheck.retrieval.service.lexical_scores", fail)
    result = retriever.retrieve(request)
    assert result.status == "failed" and result.error
    assert "secret" not in result.error.message
    refs = success(store.list_records(ListRequest(record_kind="artifact", limit=1000))).records
    assert any(r.id.endswith(".semantic") for r in refs)
    assert not any(r.id.startswith("retrieval-batch-") and r.id.endswith(".complete") for r in refs)


def test_rescore_after_reopen_matches_saved_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from binfocheck.storage import SQLiteStore

    with SQLiteStore(tmp_path / "store") as store:
        retriever, request, _ = prepared(store)
        result = success(retriever.retrieve(request))
        trace_id = result.batch.settings.values["trace_id"]
        assert isinstance(trace_id, str)
        trace = retriever.store.load(trace_id, Trace)

    def forbidden(*args: object) -> None:
        raise AssertionError("implicit model or tokenization")

    monkeypatch.setattr(SyntheticEmbedder, "encode", forbidden)
    monkeypatch.setattr("binfocheck.retrieval.service.tokens", forbidden)
    with SQLiteStore(tmp_path / "store") as store:
        retriever = HybridClaimRetriever(store, store)
        assert success(retriever.rescore(request)) == trace
        assert success(retriever.replay(result.batch.id)) == result


def test_real_spec_rejects_wrong_revision_and_dimension() -> None:
    for changes in ({"revision": "main"}, {"dimensions": 3}, {"model": "other"}):
        with pytest.raises(RetrievalError, match="unsupported_embedding_spec"):
            EmbeddingSpec().model_copy(update=changes).validate_supported()


def test_publication_retry_is_idempotent_after_storage_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from binfocheck.retrieval.config import identity
    from binfocheck.retrieval.service import Publication

    store = MemoryStore()
    retriever, request, _ = prepared(store)
    put = store.put_artifact

    def interrupted(artifact: ArtifactPayload) -> Outcome[ArtifactRef]:
        if artifact.ref.storage_key == "retrieval/1/completion":
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="storage_io_error", message="synthetic failure"),
            )
        return put(artifact)

    monkeypatch.setattr(store, "put_artifact", interrupted)
    failed = retriever.retrieve(request)
    assert failed.error and failed.error.code == "storage_io_error"
    batch_id = identity("batch", request.model_dump(mode="json"))
    publication = retriever.store.load(batch_id + ".publication", Publication)
    assert not retriever.store.exists(batch_id + ".complete")
    monkeypatch.setattr(store, "put_artifact", put)
    result = success(retriever.retrieve(request))
    assert result.batch.created_at == publication.created_at
    assert all(pair.created_at == publication.created_at for pair in result.candidates)
    assert success(retriever.retrieve(request)) == result


def test_query_preflight_and_wrong_run_fail_before_embedding() -> None:
    store = MemoryStore()
    retriever, request, embedder = prepared(store)

    class TooLong(SyntheticEmbedder):
        def count_tokens(self, text: str) -> int:
            return 32769

    too_long = TooLong()
    result = retriever.prepare_query(request.index, "run-1", "claim-1", too_long)
    assert result.error and result.error.code == "embedding_input_overflow"
    assert "claim-1" in result.error.message and not too_long.encoded
    from binfocheck.domain.runs import RunManifest

    run = retriever.store.record("run-1", RunManifest).model_copy(update={"id": "another-run"})
    success(store.put_record(run))
    result = retriever.prepare_query(request.index, run.id, "claim-1", embedder)
    assert result.error and result.error.code == "claim_run_mismatch"
    assert len(embedder.encoded) == 2


def test_local_loader_uses_exact_snapshot_and_offline_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from binfocheck.retrieval.config import LOCAL_PACKAGES, MODEL, REVISION

    snapshot = tmp_path / ("models--" + MODEL.replace("/", "--")) / "snapshots" / REVISION
    for file in (
        "model.safetensors",
        "modules.json",
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "config_sentence_transformers.json",
        "1_Pooling/config.json",
    ):
        path = snapshot / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic loader test only")
    calls: list[dict[str, Any]] = []

    def factory(path: str, **kwargs: Any) -> Any:
        assert path == str(snapshot)
        calls.append(kwargs)
        return SimpleNamespace(
            tokenizer=SimpleNamespace(model_max_length=32768),
            get_sentence_embedding_dimension=lambda: 1024,
            eval=lambda: None,
        )

    def ignore(value: object) -> None:
        pass

    def package_version(name: str) -> str:
        return LOCAL_PACKAGES[name]

    torch = SimpleNamespace(
        set_num_threads=ignore,
        use_deterministic_algorithms=ignore,
        float32="synthetic-float32",
    )

    def imported(name: str) -> Any:
        return torch if name == "torch" else SimpleNamespace(SentenceTransformer=factory)

    monkeypatch.setattr("binfocheck.retrieval.embeddings.importlib.import_module", imported)
    monkeypatch.setattr("binfocheck.retrieval.embeddings.version", package_version)
    adapter = LocalHarrier.open(tmp_path)
    assert adapter.spec.revision == REVISION
    assert calls[0]["local_files_only"] is True and calls[0]["trust_remote_code"] is False
    assert calls[0]["token"] is False and calls[0]["revision"] == REVISION
    assert calls[0]["truncate_dim"] is None and calls[0]["device"] == "cpu"
