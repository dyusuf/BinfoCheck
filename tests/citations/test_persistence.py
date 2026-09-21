from pathlib import Path

import pytest

from binfocheck.citations import VERSION, CitationSettings, StoredCitationMapper
from binfocheck.citations.config import canonical, digest, identity
from binfocheck.domain.claims import Claim
from binfocheck.domain.common import ErrorDetail, Outcome, VersionRef
from binfocheck.domain.records import Record
from binfocheck.domain.storage import ArtifactPayload, IdRequest
from binfocheck.domain.text import ArtifactRef
from binfocheck.storage import MemoryStore, SQLiteStore
from tests.storage.helpers import Store, all_records, success

from .helpers import seed_pair


def test_replay_is_identical_and_does_not_rescope(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = seed_pair(store)
    mapper = StoredCitationMapper(store, store)
    result = success(mapper.map_citations(request))
    records = all_records(store)

    def no_scope(*args: object, **kwargs: object) -> None:
        pytest.fail("replay scoped again")

    monkeypatch.setattr("binfocheck.citations.mapper.infer_scope", no_scope)
    assert success(mapper.map_citations(request)) == result
    assert all_records(store) == records
    assert VERSION.sha256
    assert result.rule_version == VERSION
    claim = success(store.get_record(IdRequest(id=request.claim_id)))
    assert isinstance(claim, Claim)
    assert result.created_at == claim.created_at


def test_close_reopen(tmp_path: Path) -> None:
    root = tmp_path / "saved"
    with SQLiteStore(root) as store:
        request = seed_pair(store)
        result = success(StoredCitationMapper(store, store).map_citations(request))
        originals = all_records(store)
    with SQLiteStore(root) as reopened:
        assert success(StoredCitationMapper(reopened, reopened).map_citations(request)) == result
        assert all_records(reopened) == originals


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("claim_id", "absent", "not_found"),
        ("claim_id", "a-text", "wrong_record_kind"),
        ("analysis_run_id", "foreign-run", "run_mismatch"),
    ],
)
def test_request_failures(store: Store, field: str, value: str, code: str) -> None:
    request = seed_pair(store).model_copy(update={field: value})
    result = StoredCitationMapper(store, store).map_citations(request)
    assert result.status == "failed" and result.value is None
    assert result.error and result.error.code == code


def test_missing_index_and_unknown_version(store: Store) -> None:
    request = seed_pair(store)
    for settings in (
        CitationSettings(index_artifact_id="absent").envelope(),
        request.settings.model_copy(
            update={"version": VersionRef(name="t05-citation-mapping", version="future")}
        ),
    ):
        result = StoredCitationMapper(store, store).map_citations(
            request.model_copy(update={"settings": settings})
        )
        assert result.status == "failed" and result.value is None


def test_foreign_context_is_failure(store: Store) -> None:
    request = seed_pair(store)
    original = success(store.get_record(IdRequest(id=request.claim_id)))
    assert isinstance(original, Claim)
    invalid = original.model_copy(
        update={"id": "bad-context", "context_unit_ids": ("missing-unit",)}
    )
    success(store.put_record(invalid))
    result = StoredCitationMapper(store, store).map_citations(
        request.model_copy(update={"claim_id": invalid.id})
    )
    assert result.error and result.error.code == "claim_cohort_mismatch"


class InterruptedStore(MemoryStore):
    fail_role: str | None = None

    def put_artifact(self, request: ArtifactPayload) -> Outcome[ArtifactRef]:
        if request.ref.storage_key == "citations/1/" + str(self.fail_role):
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="storage_io_error", message="synthetic"),
            )
        return super().put_artifact(request)

    def put_record(self, request: Record) -> Outcome[Record]:
        if self.fail_role == "association" and request.kind == "citation_association":
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="storage_io_error", message="synthetic"),
            )
        return super().put_record(request)


@pytest.mark.parametrize("role", ["configuration", "inputs", "association", "audit"])
def test_partial_publication_repairs_without_overwrite(role: str) -> None:
    with InterruptedStore() as store:
        request = seed_pair(store)
        originals = all_records(store)
        store.fail_role = role
        mapper = StoredCitationMapper(store, store)
        failure = mapper.map_citations(request)
        assert failure.status == "failed" and failure.value is None
        for artifact in all_records(store):
            if isinstance(artifact, ArtifactRef) and artifact.storage_key == "citations/1/audit":
                assert store.get_artifact(IdRequest(id=artifact.id)).status == "failed"
        store.fail_role = None
        result = success(mapper.map_citations(request))
        assert result.status == "yes"
        assert success(mapper.map_citations(request)) == result
        for record in originals:
            assert success(store.get_record(IdRequest(id=record.id))) == record


def test_conflicting_audit_cannot_be_overwritten(store: Store) -> None:
    request = seed_pair(store)
    mapper = StoredCitationMapper(store, store)
    result = success(mapper.map_citations(request))
    collision = result.model_copy(update={"reason": "changed"})
    failure = store.put_record(collision)
    assert failure.error and failure.error.code == "immutable_id_conflict"
    assert success(mapper.map_citations(request)) == result


def test_corrupt_saved_blob_fails(tmp_path: Path) -> None:
    root = tmp_path / "corrupt"
    with SQLiteStore(root) as store:
        request = seed_pair(store)
        success(StoredCitationMapper(store, store).map_citations(request))
        audit = next(
            r
            for r in all_records(store)
            if isinstance(r, ArtifactRef) and r.storage_key == "citations/1/audit"
        )
    blob = root / "artifacts" / audit.access / "sha256" / audit.sha256[:2] / audit.sha256
    blob.write_bytes(b"corrupt")
    with SQLiteStore(root) as store:
        result = StoredCitationMapper(store, store).map_citations(request)
        assert result.status == "failed" and result.value is None
        assert blob.read_bytes() == b"corrupt"


def test_identity_includes_version_and_inputs() -> None:
    assert identity("work", {"version": "1", "claim": "a"}) != identity(
        "work", {"version": "2", "claim": "a"}
    )
    assert digest(canonical({"b": 1, "a": 2})) == digest(canonical({"a": 2, "b": 1}))


class AlteredReads(MemoryStore):
    """Supply inconsistent stored records to exercise component preflight, not write APIs."""

    changed: Record | None = None

    def get_record(self, request: IdRequest) -> Outcome[Record]:
        if self.changed is not None and request.id == self.changed.id:
            return Outcome(status="succeeded", value=self.changed, error=None)
        return super().get_record(request)


@pytest.mark.parametrize("change", ["quote", "pointer", "url", "observation", "kind"])
def test_invalid_captured_evidence_fails_not_unclear(change: str) -> None:
    from binfocheck.domain.observations import SourceReference

    with AlteredReads() as store:
        request = seed_pair(store)
        ref = success(store.get_record(IdRequest(id="a-citation-0")))
        assert isinstance(ref, SourceReference) and ref.citation_span is not None
        if change == "quote":
            altered = ref.model_copy(
                update={
                    "citation_span": ref.citation_span.model_copy(
                        update={"exact_text": "x" * len(ref.citation_span.exact_text)}
                    )
                }
            )
        elif change == "pointer":
            altered = ref.model_copy(update={"metadata_location": "/missing"})
        elif change == "url":
            altered = ref.model_copy(update={"url": "https://example.org/"})
        elif change == "observation":
            altered = ref.model_copy(update={"observation_id": "foreign"})
        else:
            altered = ref.model_copy(update={"reference_kind": "reference"})
        store.changed = altered
        result = StoredCitationMapper(store, store).map_citations(request)
        assert result.status == "failed" and result.value is None
        assert not any(r.kind == "citation_association" for r in all_records(store))


def test_required_original_bytes_missing_is_failure(tmp_path: Path) -> None:
    root = tmp_path / "missing-raw"
    with SQLiteStore(root) as store:
        request = seed_pair(store)
        raw = success(store.get_record(IdRequest(id="a-raw")))
        assert isinstance(raw, ArtifactRef)
    blob = root / "artifacts" / raw.access / "sha256" / raw.sha256[:2] / raw.sha256
    blob.unlink()
    with SQLiteStore(root) as store:
        result = StoredCitationMapper(store, store).map_citations(request)
        assert result.status == "failed" and result.value is None


def test_replay_missing_association_is_failure_not_success(tmp_path: Path) -> None:
    import sqlite3

    root = tmp_path / "missing-result"
    with SQLiteStore(root) as store:
        request = seed_pair(store)
        result = success(StoredCitationMapper(store, store).map_citations(request))
    # Deliberate corruption, not a production deletion interface.
    with sqlite3.connect(root / "store.sqlite3") as connection:
        connection.execute("DELETE FROM records WHERE id = ?", (result.id,))
    with SQLiteStore(root) as store:
        replay = StoredCitationMapper(store, store).map_citations(request)
        assert replay.status == "failed" and replay.value is None
