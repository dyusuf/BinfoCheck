import gzip
from collections.abc import Iterator
from pathlib import Path

import pytest

from binfocheck.corpus import StoredCorpusIngestor
from binfocheck.corpus.artifacts import Store
from binfocheck.corpus.config import URLS, ParserConfig, ReplaySettings, digest
from binfocheck.corpus.errors import require
from binfocheck.corpus.receipts import Receipt
from binfocheck.corpus.transport import Response
from binfocheck.domain.common import ErrorDetail, Outcome
from binfocheck.domain.corpus import ArticleVersion
from binfocheck.domain.interfaces import CorpusIngestor, IngestionRequest
from binfocheck.domain.records import Record
from binfocheck.domain.storage import ArtifactPayload, IdRequest
from binfocheck.domain.text import ArtifactRef, TextRecord
from binfocheck.storage import MemoryStore, SQLiteStore

from .helpers import HTML, Transport, capture, request


@pytest.fixture(params=["memory", "sqlite"])
def backend(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[MemoryStore | SQLiteStore]:
    store = MemoryStore() if request.param == "memory" else SQLiteStore(tmp_path / "private")
    with store:
        yield store


def test_full_roundtrip_and_idempotence(backend: MemoryStore | SQLiteStore) -> None:
    io = Store(backend, backend)
    batch = capture(io)
    ingestor = StoredCorpusIngestor(backend, backend)
    protocol: CorpusIngestor = ingestor
    result = require(protocol.ingest(request(batch)))
    assert result.manifest.status == "ready"
    assert len(result.articles) == 5 and len(result.passages) == 35
    assert require(ingestor.ingest(request(batch))) == result
    assert require(ingestor.load(result.manifest.id)) == result
    for article in result.articles:
        assert article.raw_artifact_id
        assert io.bytes(article.raw_artifact_id) == HTML
        assert article.content_sha256 == digest(HTML)
        assert article.raw_text_id and article.cleaned_text_id
        raw = io.record(article.raw_text_id, TextRecord)
        clean = io.record(article.cleaned_text_id, TextRecord)
        assert raw.text == HTML.decode()
        assert raw.artifact_id == article.raw_artifact_id and raw.source_text_id is None
        assert clean.source_text_id == raw.id and clean.transformation == article.parser_version
        assert io.bytes(clean.artifact_id) == clean.text.encode()
        assert all(
            clean.text[p.span.start : p.span.end] == p.span.exact_text
            for p in result.passages
            if p.article_version_id == article.id
        )


def test_sqlite_reopen(tmp_path: Path) -> None:
    root = tmp_path / "private"
    with SQLiteStore(root) as backend:
        batch = capture(Store(backend, backend))
        result = require(StoredCorpusIngestor(backend, backend).ingest(request(batch)))
    with SQLiteStore(root) as backend:
        ingestor = StoredCorpusIngestor(backend, backend)
        assert require(ingestor.load(result.manifest.id)) == result
        assert require(ingestor.ingest(request(batch))) == result


def test_compressed_html_hash_is_content_decoded(backend: MemoryStore | SQLiteStore) -> None:
    io = Store(backend, backend)
    compressed = gzip.compress(HTML, mtime=0)
    batch = capture(
        io,
        transport=Transport(
            {
                URLS[0]: Response(
                    200,
                    (
                        ("content-type", "text/html"),
                        ("content-encoding", "gzip"),
                        ("set-cookie", "SHOULD-NOT-BE-STORED"),
                    ),
                    compressed,
                )
            }
        ),
    )
    result = require(StoredCorpusIngestor(backend, backend).ingest(request(batch)))
    article = result.articles[0]
    receipt = io.load(batch.receipt_ids[0], Receipt)
    assert article.status == "usable"
    assert article.raw_artifact_id == receipt.body_artifact_id != receipt.encoded_artifact_id
    assert article.content_sha256 == digest(HTML) != digest(compressed)
    assert receipt.encoded_artifact_id and io.bytes(receipt.encoded_artifact_id) == compressed
    assert receipt.omitted_headers == ("set-cookie",)
    assert b"SHOULD-NOT-BE-STORED" not in io.bytes(receipt.id)


@pytest.mark.parametrize(
    ("response", "status", "reason"),
    [
        (Response(500, (), b"error"), "failed", "http_failure"),
        (
            Response(200, (("content-type", "text/html"),), b"<p>Consent only</p>"),
            "unusable",
            "ambiguous_article_root",
        ),
        (Response(200, (("content-type", "application/pdf"),), b"PDF"), "unusable", "not_html"),
        (
            Response(200, (("content-type", "text/html"),), b"\xff"),
            "unusable",
            "invalid_charset_bytes",
        ),
        (Response(None, (), None, False, "timeout"), "failed", "timeout"),
        (Response(200, (), b"partial", False, "truncated"), "failed", "truncated"),
    ],
)
def test_partial_corpus_and_failure_states(response: Response, status: str, reason: str) -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        batch = capture(io, transport=Transport({URLS[0]: response}))
        ingestor = StoredCorpusIngestor(backend, backend)
        result = require(ingestor.ingest(request(batch)))
        assert result.manifest.status == "incomplete"
        assert result.articles[0].status == status and result.articles[0].reason == reason
        if status == "unusable" and reason == "not_html":
            assert result.articles[0].raw_artifact_id is None
            assert result.articles[0].content_sha256 is None
            receipt = io.load(batch.receipt_ids[0], Receipt)
            assert receipt.body_artifact_id and io.bytes(receipt.body_artifact_id) == b"PDF"
        assert not any(p.article_version_id == result.articles[0].id for p in result.passages)
        assert require(ingestor.load(result.manifest.id)) == result
        if not response.complete:
            assert result.articles[0].raw_artifact_id is None
            receipt = io.load(batch.receipt_ids[0], Receipt)
            if response.body:
                assert receipt.partial_artifact_id
                assert io.bytes(receipt.partial_artifact_id) == response.body


def test_all_failed_is_not_ready() -> None:
    with MemoryStore() as backend:
        batch = capture(
            Store(backend, backend),
            transport=Transport({url: Response(404, (), b"not found") for url in URLS}),
        )
        result = require(StoredCorpusIngestor(backend, backend).ingest(request(batch)))
        assert result.manifest.status == "failed" and not result.passages


def test_versions_keep_history(backend: MemoryStore | SQLiteStore) -> None:
    io = Store(backend, backend)
    ingestor = StoredCorpusIngestor(backend, backend)
    batch = capture(io)
    first = require(ingestor.ingest(request(batch)))
    previous = tuple(a.id for a in first.articles)
    changed = capture(
        io,
        "batch-changed",
        Transport(
            {
                URLS[0]: Response(
                    200,
                    (("content-type", "text/html"),),
                    HTML.replace(b"Ein Beispiel", b"Neues Beispiel"),
                )
            }
        ),
    )
    second = require(ingestor.ingest(request(changed, previous_version_ids=previous)))
    assert second.manifest.id != first.manifest.id
    assert tuple(a.previous_version_id for a in second.articles) == previous
    assert first.articles[0].content_sha256 != second.articles[0].content_sha256
    assert first.articles[1].raw_artifact_id == second.articles[1].raw_artifact_id
    assert first.articles[1].id != second.articles[1].id  # fresh fetch, same bytes
    assert require(ingestor.load(first.manifest.id)) == first
    assert require(ingestor.ingest(request(changed, previous_version_ids=previous))) == second
    parser = ParserConfig(max_blocks=100)
    third = require(
        ingestor.ingest(
            request(
                changed, parser=parser, previous_version_ids=tuple(a.id for a in second.articles)
            )
        )
    )
    assert third.articles[0].id != second.articles[0].id
    assert third.articles[0].fetched_at == second.articles[0].fetched_at
    assert require(ingestor.load(first.manifest.id)) == first
    mutation = backend.put_record(first.articles[0].model_copy(update={"title": "Changed"}))
    assert mutation.error and mutation.error.code == "immutable_id_conflict"


@pytest.mark.parametrize("urls", [URLS[:4], URLS + (URLS[0],), (URLS[0],) * 5, URLS[::-1]])
def test_exact_url_allowlist(urls: tuple[str, ...]) -> None:
    with MemoryStore() as backend:
        settings = ReplaySettings(batch_artifact_id="missing").envelope()
        result = StoredCorpusIngestor(backend, backend).ingest(
            IngestionRequest(urls=urls, settings=settings)
        )
        assert result.error and result.error.code == "invalid_corpus_request"


def test_wrong_predecessor_url() -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        batch = capture(io)
        ingestor = StoredCorpusIngestor(backend, backend)
        first = require(ingestor.ingest(request(batch)))
        result = ingestor.ingest(
            request(batch, previous_version_ids=tuple(a.id for a in first.articles[::-1]))
        )
        assert result.error and result.error.code == "previous_article_url_mismatch"


class FailingStore(MemoryStore):
    fail: str | None = None

    def put_record(self, request: Record) -> Outcome[Record]:
        if self.fail == request.kind:
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="storage_io_error", message="test failure"),
            )
        return super().put_record(request)

    def put_artifact(self, request: ArtifactPayload) -> Outcome[ArtifactRef]:
        if self.fail and self.fail in request.ref.storage_key:
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="storage_io_error", message="test failure"),
            )
        return super().put_artifact(request)


@pytest.mark.parametrize(
    "stage", ["text", "article_version", "passage", "structure", "completion", "corpus_manifest"]
)
def test_partial_writes_never_publish_and_retry_offline(stage: str) -> None:
    with FailingStore() as backend:
        io = Store(backend, backend)
        batch = capture(io)
        ingestor = StoredCorpusIngestor(backend, backend)
        backend.fail = stage
        result = ingestor.ingest(request(batch))
        assert result.error and result.error.code == "storage_io_error"
        from binfocheck.domain.storage import ListRequest

        assert (
            require(backend.list_records(ListRequest(record_kind="corpus_manifest"))).records == ()
        )
        backend.fail = None
        result = require(ingestor.ingest(request(batch)))
        assert result.manifest.status == "ready"
        assert require(ingestor.load(result.manifest.id)) == result


@pytest.mark.parametrize("target", ["completion", "structure", "raw", "passage"])
def test_missing_dependency_never_loads_as_ready(
    target: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        result = require(StoredCorpusIngestor(backend, backend).ingest(request(capture(io))))
        id = {
            "completion": result.manifest.id + ".completion.v1",
            "structure": result.articles[0].id + ".structure.v1",
            "raw": result.articles[0].raw_artifact_id,
            "passage": result.passages[0].id,
        }[target]
        get = backend.get_record

        def missing(query: IdRequest) -> Outcome[Record]:
            if query.id == id:
                return Outcome(
                    status="failed",
                    value=None,
                    error=ErrorDetail(code="not_found", message="missing"),
                )
            return get(query)

        monkeypatch.setattr(backend, "get_record", missing)
        assert StoredCorpusIngestor(backend, backend).load(result.manifest.id).status == "failed"


def test_completion_cannot_hide_member_change(monkeypatch: pytest.MonkeyPatch) -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        result = require(StoredCorpusIngestor(backend, backend).ingest(request(capture(io))))
        get = backend.get_record

        def altered(query: IdRequest) -> Outcome[Record]:
            record = get(query)
            if isinstance(record.value, ArticleVersion):
                return Outcome(
                    status="succeeded",
                    error=None,
                    value=record.value.model_copy(update={"title": "changed"}),
                )
            return record

        monkeypatch.setattr(backend, "get_record", altered)
        outcome = StoredCorpusIngestor(backend, backend).load(result.manifest.id)
        assert outcome.error and outcome.error.code == "completion_record_mismatch"
