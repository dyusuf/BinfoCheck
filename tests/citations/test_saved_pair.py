import socket
from pathlib import Path

import pytest

from binfocheck.citations.errors import CitationError
from binfocheck.citations.persistence import Store
from binfocheck.citations.verify_saved_pair import check_saved_claim, verify
from binfocheck.domain.claims import Claim
from binfocheck.storage import SQLiteStore
from binfocheck.text.verify_saved_capture import fingerprint

from .helpers import seed_pair


def test_missing_real_claim_is_blocked_and_source_unchanged(tmp_path: Path) -> None:
    root = tmp_path / "source"
    with SQLiteStore(root):
        pass
    before = fingerprint(root)
    with pytest.raises(CitationError, match="genuine t04 claim missing"):
        verify(root, "missing", "missing-index", "missing-audit")
    assert fingerprint(root) == before


def test_synthetic_claim_cannot_satisfy_saved_pair_gate(tmp_path: Path) -> None:
    root = tmp_path / "source"
    with SQLiteStore(root) as backend:
        request = seed_pair(backend)
        with pytest.raises(CitationError, match="completed t04 evidence missing"):
            check_saved_claim(Store(backend, backend), request.claim_id, "missing-audit")


def test_copy_reopen_scaffolding_only_with_mocked_provenance_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Synthetic diagnostic wiring only; deliberately NOT real integration acceptance."""
    source = tmp_path / "source"
    with SQLiteStore(source) as backend:
        request = seed_pair(backend)
    before = fingerprint(source)
    called: list[str] = []

    def synthetic_gate(store: Store, claim_id: str, audit_id: str) -> Claim:
        called.append(claim_id)
        with pytest.raises(CitationError, match="network forbidden"):
            socket.getaddrinfo("example.org", 443)
        return store.record(claim_id, Claim)

    monkeypatch.setattr("binfocheck.citations.verify_saved_pair.check_saved_claim", synthetic_gate)
    index_id = request.settings.values["index_artifact_id"]
    assert isinstance(index_id, str)
    result = verify(source, request.claim_id, index_id, "synthetic-gate-only")
    assert result["status"] == "passed" and result["citation_status"] == "yes"
    assert called == [request.claim_id]
    assert result["copied_store"] != str(source)
    assert fingerprint(source) == before
