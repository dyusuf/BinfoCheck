"""Synthetic evidence chains exercise production validators, never real payloads."""

import json
import socket
from pathlib import Path
from typing import NoReturn

import pytest

from binfocheck.corpus import StoredCorpusIngestor, asset, asset_transport, nontext
from binfocheck.corpus.artifacts import Store
from binfocheck.corpus.config import URLS, canonical, digest
from binfocheck.corpus.diabinfo import pilot_profile
from binfocheck.corpus.errors import CorpusError, require
from binfocheck.corpus.ingestion import Completion
from binfocheck.corpus.parsing import parse_html
from binfocheck.corpus.receipts import Batch, Receipt
from binfocheck.corpus.structure import Structure
from binfocheck.corpus.transport import Response
from binfocheck.domain.interfaces import IngestionResult
from binfocheck.domain.storage import ListRequest
from binfocheck.domain.text import ArtifactRef, TextRecord
from binfocheck.storage import MemoryStore, SQLiteStore

from .helpers import request
from .test_authorization_evidence import AuditedTransport, run_capture
from .test_diabinfo import FIXTURES, positive_html

GALLERY = (FIXTURES / "informational.html").read_text()
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0L1 1"/></svg>'


def test_frozen_parser_identities() -> None:
    assert pilot_profile("diabinfo-pilot/3").version().sha256 == (
        "a21b5e2f13e5108af14ed504feda09415e191755d6ffdcef2685c700f7fd7037"
    )
    assert pilot_profile().version().version == "5"
    assert pilot_profile().version().sha256 == (
        "db6903268a38e67a07699495f73402e1d8fe911ab2a9c702acff0c2efdec9870"
    )


def seed(store: Store, monkeypatch: pytest.MonkeyPatch) -> Batch:
    """Substitute only frozen capture identities with synthetic ones, not validators."""
    transport = AuditedTransport(store)
    for url in URLS:
        transport.fake.responses[url] = Response(
            200,
            (("content-type", "text/html; charset=utf-8"),),
            positive_html(GALLERY if url == URLS[1] else "", faq_page=url == URLS[3]).encode(),
        )
    batch = run_capture(store, transport)
    parent = store.load(batch.receipt_ids[1], Receipt)
    assert parent.body_artifact_id
    monkeypatch.setattr(asset, "PARENT_BATCH", batch.id)
    monkeypatch.setattr(asset, "PARENT_RAW", parent.body_artifact_id)
    monkeypatch.setattr(asset, "PARENT_SHA256", digest(store.bytes(parent.body_artifact_id)))
    proposal = asset.AssetProposal(
        parent_batch_id=batch.id,
        parent_raw_artifact_id=asset.PARENT_RAW,
        parent_raw_sha256=asset.PARENT_SHA256,
    )
    monkeypatch.setattr(asset, "PROPOSAL", proposal)
    monkeypatch.setattr(
        asset, "PROPOSAL_SHA256", digest(canonical(proposal.model_dump(mode="json")))
    )

    def synthetic_dispatch(approval: asset.AssetApproval) -> Response:
        approval.validate_approval()
        return Response(200, (("content-type", "image/svg+xml"),), SVG)

    monkeypatch.setattr(asset_transport, "dispatch", synthetic_dispatch)
    saved = asset.capture_asset(
        store,
        asset.AssetApproval(
            approval_reference="synthetic fixture, no live permission",
            proposal=proposal,
            policy_sha256=asset.PROPOSAL_SHA256,
            envelope_sha256=asset.approval_digest("synthetic fixture, no live permission"),
        ),
    )
    assert saved.receipt.body_artifact_id
    monkeypatch.setattr(nontext, "SVG_ID", saved.receipt.body_artifact_id)
    inspection: dict[str, object] = {
        "format": "t06-svg-inspection/1",
        "status": "no_deterministic_text_extractable",
        "asset_attempt_id": asset.ATTEMPT,
        "asset_receipt_artifact_id": asset.ATTEMPT + ".receipt.v1",
        "authorization_artifact_id": saved.authorization_artifact_id,
        "authorization_policy_sha256": saved.policy_sha256,
        "http_receipt_artifact_id": saved.receipt.id,
        "raw_svg_artifact_id": saved.receipt.body_artifact_id,
        "raw_svg_sha256": saved.body_sha256,
        "raw_svg_bytes": len(SVG),
        "http_status": 200,
        "media_type": "image/svg+xml",
        "xml_root": "svg",
        "machine_readable_text": [],
        "accessibility_metadata": [],
        "external_or_internal_href_references": [],
        "unsafe_or_unsupported_elements": [],
        "scripts_executed": False,
        "external_resources_loaded": False,
        "ocr_used": False,
        "vector_path_semantics_inferred": False,
        "network_requests_during_inspection": 0,
    }
    store.blob(canonical(inspection), "svg-inspection", "application/json", nontext.INSPECTION_ID)
    robots = store.load(batch.robots_receipt_id or "missing", Receipt)
    ids = [
        batch.id,
        batch.id + ".start.v1",
        batch.id + ".authorization.v1",
        parent.id,
        parent.body_artifact_id,
        robots.id,
        robots.body_artifact_id,
        saved.start_artifact_id,
        saved.authorization_artifact_id,
        saved.receipt.id,
        asset.ATTEMPT + ".receipt.v1",
        saved.receipt.body_artifact_id,
        nontext.INSPECTION_ID,
    ]
    monkeypatch.setattr(
        nontext, "PINS", {id: store.record(id, ArtifactRef).sha256 for id in ids if id is not None}
    )
    nontext.validate_evidence(store, batch)
    return batch


def count(store: Store) -> int:
    return len(require(store.records.list_records(ListRequest(limit=1000))).records)


def test_ready_exact_lineage_limitation_and_offline_reopen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with SQLiteStore(tmp_path) as backend:
        io = Store(backend, backend)
        batch = seed(io, monkeypatch)
        ingestor = StoredCorpusIngestor(backend, backend)
        history: list[IngestionResult] = []
        from binfocheck.corpus.config import ParserConfig

        for parser in [
            ParserConfig(),
            pilot_profile("diabinfo-pilot/1"),
            pilot_profile("diabinfo-pilot/2"),
            pilot_profile("diabinfo-pilot/3"),
        ]:
            history.append(require(ingestor.ingest(request(batch, parser=parser))))
        before = history[-1]
        new_request = request(
            batch, parser=pilot_profile(), previous_version_ids=before.manifest.article_version_ids
        )
        result = require(ingestor.ingest(new_request))
        assert result.manifest.status == "ready"
        assert all(
            a.status == "usable" and a.parser_version.version == "5" for a in result.articles
        )
        for old, new in zip(before.articles, result.articles, strict=True):
            assert new.previous_version_id == old.id
            assert (new.raw_artifact_id, new.raw_text_id, new.content_sha256) == (
                old.raw_artifact_id,
                old.raw_text_id,
                old.content_sha256,
            )
            passages = [p for p in result.passages if p.article_version_id == new.id]
            assert passages
            assert new.cleaned_text_id
            text = io.record(new.cleaned_text_id, TextRecord).text
            assert all(text[p.span.start : p.span.end] == p.span.exact_text for p in passages)
            if old.cleaned_text_id:
                assert text == io.record(old.cleaned_text_id, TextRecord).text
                assert [p.span.exact_text for p in passages] == [
                    p.span.exact_text for p in before.passages if p.article_version_id == old.id
                ]
        ramadan = result.articles[1]
        media_id = ramadan.id + ".media-evidence.v1"
        media = io.load(media_id, nontext.MediaEvidence)
        assert media.disposition == "captured_nontext_informational"
        assert (
            media.article_version_id == ramadan.id
            and media.evidence.svg_artifact_id == nontext.SVG_ID
        )
        assert "not represented by textual passages" in media.limitation
        structure = io.load(ramadan.id + ".structure.v1", Structure)
        assert any(
            e.rule == nontext.DISPOSITION and e.locator == media.html_gallery_locator
            for e in structure.exclusions
        )
        completion = io.load(result.manifest.id + ".completion.v1", Completion)
        assert set(nontext.PINS) | {media_id} <= set(completion.artifact_ids)
        assert set(nontext.PINS) | {media_id} <= {m.id for m in completion.records}
        for old in history:
            assert require(ingestor.load(old.manifest.id)) == old

    def blocked(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("socket/DNS forbidden")

    for name in ("socket", "getaddrinfo", "gethostbyname", "create_connection"):
        monkeypatch.setattr(socket, name, blocked)
    monkeypatch.setattr(asset, "capture_asset", blocked)
    monkeypatch.setattr(asset_transport, "dispatch", blocked)
    with SQLiteStore(tmp_path) as backend:
        ingestor = StoredCorpusIngestor(backend, backend)
        assert require(ingestor.load(result.manifest.id)) == result
        assert require(ingestor.ingest(new_request)) == result


@pytest.mark.parametrize(
    "part",
    [
        "parent",
        "svg",
        "authorization",
        "start",
        "http",
        "receipt",
        "inspection",
    ],
)
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_evidence_failure_before_writes_and_ready_load_fails(
    monkeypatch: pytest.MonkeyPatch,
    part: str,
    damage: str,
) -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        batch = seed(io, monkeypatch)
        ingestor = StoredCorpusIngestor(backend, backend)
        req = request(batch, parser=pilot_profile())
        ready = require(ingestor.ingest(req))
        target = {
            "parent": asset.PARENT_RAW,
            "svg": nontext.SVG_ID,
            "authorization": asset.ATTEMPT + ".authorization.v1",
            "start": asset.ATTEMPT + ".start.v1",
            "http": asset.ATTEMPT + ".http.v1",
            "receipt": asset.ATTEMPT + ".receipt.v1",
            "inspection": nontext.INSPECTION_ID,
        }[part]
        original = Store.bytes

        def damaged(self: Store, id: str) -> bytes:
            if id == target:
                if damage == "missing":
                    raise CorpusError("not_found")
                return original(self, id) + b"corrupt"
            return original(self, id)

        size = count(io)
        with monkeypatch.context() as context:
            context.setattr(Store, "bytes", damaged)
            assert ingestor.ingest(req).status == "failed"
            assert ingestor.load(ready.manifest.id).status == "failed"
            # A new derivation must fail before publishing any article/raw text.
            assert (
                ingestor.ingest(
                    request(
                        batch,
                        parser=pilot_profile(),
                        previous_version_ids=ready.manifest.article_version_ids,
                    )
                ).status
                == "failed"
            )
            assert count(io) == size
        assert require(ingestor.ingest(req)) == ready
        recovered = require(
            ingestor.ingest(
                request(
                    batch,
                    parser=pilot_profile(),
                    previous_version_ids=ready.manifest.article_version_ids,
                )
            )
        )
        assert recovered.manifest.status == "ready"


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "machine_readable_text_available"),
        ("machine_readable_text", ["Wichtige Information"]),
        ("accessibility_metadata", ["Description"]),
        ("raw_svg_artifact_id", "unrelated-svg"),
        ("raw_svg_sha256", "0" * 64),
        ("authorization_artifact_id", "unrelated-approval"),
        ("http_receipt_artifact_id", "unrelated-receipt"),
        ("ocr_used", True),
        ("vector_path_semantics_inferred", True),
    ],
)
def test_inspection_semantics_independent_of_pinned_hash(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        batch = seed(io, monkeypatch)
        changed = json.loads(io.bytes(nontext.INSPECTION_ID))
        changed[field] = value
        data = canonical(changed)
        original = Store.bytes
        monkeypatch.setattr(nontext, "PINS", {**nontext.PINS, nontext.INSPECTION_ID: digest(data)})

        def altered(self: Store, id: str) -> bytes:
            return data if id == nontext.INSPECTION_ID else original(self, id)

        monkeypatch.setattr(Store, "bytes", altered)
        size = count(io)
        result = StoredCorpusIngestor(backend, backend).ingest(
            request(batch, parser=pilot_profile())
        )
        assert result.error and result.error.code == "nontext_inspection_mismatch"
        assert count(io) == size


@pytest.mark.parametrize(
    "change", ["companion", "corrupt_companion", "omit_artifact", "omit_record"]
)
def test_completion_requires_valid_linked_media_companion(
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        batch = seed(io, monkeypatch)
        ingestor = StoredCorpusIngestor(backend, backend)
        result = require(ingestor.ingest(request(batch, parser=pilot_profile())))
        media_id = result.articles[1].id + ".media-evidence.v1"
        completion_id = result.manifest.id + ".completion.v1"
        original = Store.bytes

        def altered(self: Store, id: str) -> bytes:
            data = original(self, id)
            if id == media_id and change == "companion":
                raise CorpusError("not_found")
            if id == media_id and change == "corrupt_companion":
                return data + b"corrupt"
            if id == completion_id and change.startswith("omit_"):
                completion = json.loads(data)
                if change == "omit_artifact":
                    completion["artifact_ids"].remove(nontext.INSPECTION_ID)
                else:
                    completion["records"] = [
                        m for m in completion["records"] if m["id"] != media_id
                    ]
                return canonical(completion)
            return data

        monkeypatch.setattr(Store, "bytes", altered)
        assert ingestor.load(result.manifest.id).status == "failed"


def test_no_broad_image_exception_or_direct_parser_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        batch = seed(io, monkeypatch)
        html = positive_html(GALLERY)
        with pytest.raises(CorpusError, match="nontext evidence required"):
            parse_html(html, URLS[1], "a", "r", "t", "utf-8", pilot_profile())
        evidence = nontext.validate_evidence(io, batch)
        for changed in [
            html.replace("ohne-Titel.svg", "other.svg"),
            html.replace("beim Fasten beachten?", "Neue Information"),
        ]:
            with pytest.raises(CorpusError):
                parse_html(changed, URLS[1], "a", "r", "t", "utf-8", pilot_profile(), evidence)


@pytest.mark.parametrize(
    "part,field,value",
    [
        ("receipt", "url", "https://www.diabinfo.de/unrelated.svg"),
        ("receipt", "parent_raw_artifact_id", "wrong-parent"),
        ("receipt", "body_sha256", "0" * 64),
        ("receipt", "authorization_artifact_id", "wrong-approval"),
        ("authorization", "approval_reference", "changed approval"),
        ("authorization", "policy_sha256", "0" * 64),
        ("start", "authorization_sha256", "0" * 64),
        ("http", "url", "https://www.diabinfo.de/unrelated.svg"),
        ("http", "body_artifact_id", "unrelated-svg"),
    ],
)
def test_chain_semantics_independent_of_pins(
    monkeypatch: pytest.MonkeyPatch, part: str, field: str, value: str
) -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        batch = seed(io, monkeypatch)
        target = asset.ATTEMPT + "." + part + ".v1"
        changed = json.loads(io.bytes(target))
        changed[field] = value
        data = canonical(changed)
        original = Store.bytes
        monkeypatch.setattr(nontext, "PINS", {**nontext.PINS, target: digest(data)})

        def altered(self: Store, id: str) -> bytes:
            return data if id == target else original(self, id)

        monkeypatch.setattr(Store, "bytes", altered)
        size = count(io)
        result = StoredCorpusIngestor(backend, backend).ingest(
            request(batch, parser=pilot_profile())
        )
        assert result.status == "failed"
        assert count(io) == size
