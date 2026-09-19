"""Synthetic HTTPS doubles only: persistence ordering and offline audit verification."""

from pathlib import Path

import pytest

from binfocheck.corpus import StoredCorpusIngestor
from binfocheck.corpus.artifacts import Store
from binfocheck.corpus.capture import CaptureStart, SnapshotCapture
from binfocheck.corpus.config import POLICY, ROBOTS, URLS, canonical, capture_policy_sha256
from binfocheck.corpus.errors import CorpusError, require
from binfocheck.corpus.receipts import AuthorizationEvidence, Batch
from binfocheck.corpus.transport import HttpsTransport, LiveAuthorization, Response
from binfocheck.domain.storage import IdRequest
from binfocheck.domain.text import ArtifactRef
from binfocheck.storage import MemoryStore, SQLiteStore

from .helpers import NOW, FakeClock, Transport, request


class AuditedTransport(HttpsTransport):
    def __init__(
        self, store: Store, reference: str = "synthetic approval; no live permission"
    ) -> None:
        super().__init__(
            LiveAuthorization(reference, "audit", capture_policy_sha256(ROBOTS, URLS, POLICY))
        )
        self.store = store
        self.fake = Transport()

    def get(self, url: str, max_bytes: int) -> Response:
        evidence = self.store.load("audit.authorization.v1", AuthorizationEvidence)
        start = self.store.load("audit.start.v1", CaptureStart)
        assert start.authorization_artifact_id == "audit.authorization.v1"
        assert self.authorization and evidence.approval_reference == self.authorization.reference
        return self.fake.get(url, max_bytes)


def run_capture(store: Store, transport: AuditedTransport) -> Batch:
    clock = FakeClock()
    return require(
        SnapshotCapture(
            store, transport, clock=clock.clock, sleep=clock.sleep, now=lambda: NOW
        ).capture("audit", "live")
    )


def test_authorization_reopen_replay_and_immutability(tmp_path: Path) -> None:
    root = tmp_path / "private"
    with SQLiteStore(root) as backend:
        io = Store(backend, backend)
        transport = AuditedTransport(io)
        batch = run_capture(io, transport)
        assert transport.fake.calls == [ROBOTS, *URLS]
        evidence = io.load("audit.authorization.v1", AuthorizationEvidence)
        assert evidence.model_dump(mode="json") == {
            "format": "t06-live-authorization/1",
            "batch_id": "audit",
            "approval_reference": "synthetic approval; no live permission",
            "policy_sha256": capture_policy_sha256(ROBOTS, URLS, POLICY),
            "robots_url": ROBOTS,
            "page_urls": list(URLS),
            "fetch_policy": POLICY.model_dump(mode="json"),
        }
        assert io.record("audit.authorization.v1", ArtifactRef).access == "restricted"
        result = require(StoredCorpusIngestor(backend, backend).ingest(request(batch)))
        with pytest.raises(CorpusError):
            io.json(
                evidence.model_copy(update={"approval_reference": "replacement"}),
                "authorization",
                "audit.authorization.v1",
            )
    with SQLiteStore(root) as backend:
        io = Store(backend, backend)
        assert io.load("audit.authorization.v1", AuthorizationEvidence) == evidence
        ingestor = StoredCorpusIngestor(backend, backend)
        assert require(ingestor.load(result.manifest.id)) == result
        assert require(ingestor.ingest(request(batch))) == result
        assert b"audit.authorization.v1" in io.bytes(result.manifest.id + ".completion.v1")


@pytest.mark.parametrize("stage", ["authorization", "capture-start"])
def test_evidence_write_failure_never_dispatches(
    stage: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        original = io.blob

        def failing(data: bytes, role: str, media: str, id: str | None = None) -> ArtifactRef:
            if role == "capture-start":
                assert io.load("audit.authorization.v1", AuthorizationEvidence)
            if role == stage:
                raise CorpusError("synthetic_write_failure")
            return original(data, role, media, id)

        monkeypatch.setattr(io, "blob", failing)
        transport = AuditedTransport(io)
        with pytest.raises(CorpusError, match="synthetic write failure"):
            run_capture(io, transport)
        assert transport.fake.calls == []
        assert backend.get_record(IdRequest(id="audit.start.v1")).status == "failed"


@pytest.mark.parametrize(
    "change", ["missing", "batch", "reference", "digest", "robots", "pages", "policy", "link"]
)
def test_replay_and_load_reject_invalid_evidence(
    change: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        batch = run_capture(io, AuditedTransport(io))
        ingestor = StoredCorpusIngestor(backend, backend)
        result = require(ingestor.ingest(request(batch)))
        original = Store.bytes

        def altered(self: Store, id: str) -> bytes:
            data = original(self, id)
            if change == "link" and id == "audit.start.v1":
                return canonical(
                    CaptureStart.model_validate_json(data)
                    .model_copy(update={"authorization_artifact_id": None})
                    .model_dump(mode="json")
                )
            if id != "audit.authorization.v1" or change == "link":
                return data
            if change == "missing":
                raise CorpusError("not_found")
            # Simulate even a self-consistent replacement artifact, so policy semantics
            # must reject it independently of T11A's content-hash protection.
            values = AuthorizationEvidence.model_validate_json(data).model_dump(mode="json")
            key, value = {
                "batch": ("batch_id", "another-batch"),
                "reference": ("approval_reference", " "),
                "digest": ("policy_sha256", "0" * 64),
                "robots": ("robots_url", ROBOTS + "?x"),
                "pages": ("page_urls", list(reversed(URLS))),
                "policy": ("fetch_policy", {**POLICY.model_dump(mode="json"), "read_seconds": 21}),
            }[change]
            values[key] = value
            return canonical(values)

        monkeypatch.setattr(Store, "bytes", altered)
        assert ingestor.ingest(request(batch)).status == "failed"
        assert ingestor.load(result.manifest.id).status == "failed"


def test_live_origin_requires_authorized_transport() -> None:
    with MemoryStore() as backend:
        fake = Transport()
        result = SnapshotCapture(Store(backend, backend), fake).capture("audit", "live")
        assert result.error and result.error.code == "live_not_authorized"
        assert fake.calls == []


def test_orphan_authorization_cannot_be_replaced() -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        evidence = AuthorizationEvidence(
            batch_id="audit",
            approval_reference="earlier explicit approval",
            policy_sha256=capture_policy_sha256(ROBOTS, URLS, POLICY),
            robots_url=ROBOTS,
            page_urls=URLS,
            fetch_policy=POLICY,
        )
        io.json(evidence, "authorization", "audit.authorization.v1")
        transport = AuditedTransport(io)
        with pytest.raises(CorpusError):
            run_capture(io, transport)
        assert transport.fake.calls == []
        assert backend.get_record(IdRequest(id="audit.start.v1")).status == "failed"
        assert io.load("audit.authorization.v1", AuthorizationEvidence) == evidence
