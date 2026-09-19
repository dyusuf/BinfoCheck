import base64
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from binfocheck.domain.common import Availability, Available
from binfocheck.domain.decisions import DecisionRecord, DecisionResult, GenerationResult, Usage
from binfocheck.domain.records import RECORD_ADAPTER, RecordSet
from binfocheck.domain.runs import Review, RunManifest
from binfocheck.domain.storage import ArtifactPayload, IdRequest, ListRequest
from binfocheck.domain.validation import validate_links
from binfocheck.storage import MemoryStore, SQLiteStore
from binfocheck.storage.codec import encode, run_id
from tests.contracts.helpers import FIXTURES, linked

from .helpers import Store, all_records, failure, fixture_payloads, payload, success, text


def test_linked_fixture_through_protocols(store: Store) -> None:
    bundle = linked()
    for record in bundle.records:
        assert success(store.put_record(record)) == record
    for artifact in fixture_payloads():
        assert success(store.put_artifact(artifact)) == artifact.ref
        assert success(store.get_artifact(IdRequest(id=artifact.ref.id))) == artifact
    assert all_records(store) == bundle.records
    validate_links(RecordSet(records=all_records(store)))
    for record in bundle.records:
        assert success(store.get_record(IdRequest(id=record.id))) == record


def test_immutable_writes_and_new_version(store: Store) -> None:
    original = text()
    assert success(store.put_record(original)) == original
    assert success(store.put_record(original)) == original
    assert len(all_records(store)) == 1
    changed = original.model_copy(update={"text": "Andere Aussage."})
    failure(store.put_record(changed), "immutable_id_conflict")
    assert success(store.get_record(IdRequest(id=original.id))) == original
    new_version = changed.model_copy(update={"id": "text-v2"})
    assert success(store.put_record(new_version)) == new_version
    failure(store.put_record(payload(original.id).ref), "immutable_id_conflict")
    assert all_records(store) == (original, new_version)


def test_canonical_key_order_and_mutation_isolation(store: Store) -> None:
    record = next(r for r in linked().records if isinstance(r, RunManifest))
    success(store.put_record(record))
    settings = record.capture_settings
    reordered = settings.model_copy(update={"values": dict(reversed(settings.values.items()))})
    success(store.put_record(record.model_copy(update={"capture_settings": reordered})))
    assert len(all_records(store)) == 1
    settings.values["synthetic-extra"] = "new value"
    restored = success(store.get_record(IdRequest(id=record.id)))
    assert isinstance(restored, RunManifest)
    assert "synthetic-extra" not in restored.capture_settings.values
    restored.capture_settings.values["read-mutation"] = True
    again = success(store.get_record(IdRequest(id=record.id)))
    assert again != restored
    failure(store.put_record(record), "immutable_id_conflict")


def test_revalidates_nested_models(store: Store) -> None:
    record = next(r for r in linked().records if isinstance(r, Review))
    invalid = record.model_copy(update={"id": "../../unsafe"})
    failure(store.put_record(invalid), "invalid_record")
    failure(store.append_review(invalid), "invalid_record")
    assert all_records(store) == ()


def test_lookup_empty_and_missing_payload(store: Store) -> None:
    failure(store.get_record(IdRequest(id="absent")), "not_found")
    failure(store.get_artifact(IdRequest(id="absent")), "not_found")
    assert all_records(store) == ()
    artifact = payload()
    success(store.put_record(artifact.ref))
    failure(store.get_artifact(IdRequest(id=artifact.ref.id)), "artifact_data_missing")
    success(store.put_artifact(artifact))
    assert success(store.get_artifact(IdRequest(id=artifact.ref.id))) == artifact
    success(store.put_record(text()))
    failure(store.get_artifact(IdRequest(id="text-new")), "not_found")
    assert all_records(store, record_kind="nonexistent") == ()


def test_artifact_idempotency_and_metadata_conflicts(store: Store) -> None:
    first = payload()
    success(store.put_artifact(first))
    success(store.put_artifact(first))
    failure(store.put_artifact(payload(content=b"changed")), "immutable_id_conflict")
    for updates in ({"storage_key": "different"}, {"access": "restricted"}):
        changed = first.model_copy(update={"ref": first.ref.model_copy(update=updates)})
        failure(store.put_artifact(changed), "immutable_id_conflict")
    second = first.model_copy(update={"ref": first.ref.model_copy(update={"id": "artifact-other"})})
    success(store.put_artifact(second))
    assert len(all_records(store)) == 2
    assert success(store.get_artifact(IdRequest(id=first.ref.id))) == first
    assert success(store.get_artifact(IdRequest(id=second.ref.id))) == second


@pytest.mark.parametrize(
    "content,code", [("!bad!", "invalid_artifact_base64"), ("eA==", "artifact_hash_mismatch")]
)
def test_invalid_artifact_payloads(store: Store, content: str, code: str) -> None:
    valid = payload()
    with pytest.raises(ValidationError, match=code):
        ArtifactPayload(ref=valid.ref, content_base64=content)
    forged = valid.model_copy(update={"content_base64": content})
    failure(store.put_artifact(forged), code)
    assert all_records(store) == ()


@pytest.mark.parametrize("storage_key", ["../../escape", "/tmp/secret", "a\\..\\secret"])
def test_storage_key_is_metadata(store: Store, storage_key: str) -> None:
    artifact = payload()
    artifact = artifact.model_copy(
        update={"ref": artifact.ref.model_copy(update={"storage_key": storage_key})}
    )
    success(store.put_artifact(artifact))
    assert success(store.get_artifact(IdRequest(id=artifact.ref.id))) == artifact


def test_deterministic_bounded_snapshot_listing(store: Store) -> None:
    records = [text(f"text-{i}") for i in range(7)]
    for record in records:
        success(store.put_record(record))
    first = success(store.list_records(ListRequest(limit=2)))
    assert first.records == tuple(records[:2])
    assert first.next_cursor is not None
    success(store.put_record(text("later")))
    seen = list(first.records)
    cursor = first.next_cursor
    while cursor is not None:
        page = success(store.list_records(ListRequest(limit=1, cursor=cursor)))
        assert len(page.records) <= 1
        seen.extend(page.records)
        cursor = page.next_cursor
    assert seen == records
    assert len(all_records(store)) == 8


def test_filters(store: Store) -> None:
    for record in linked().records:
        success(store.put_record(record))
    for kind, run in [("review", None), (None, "run-1"), ("review", "run-1")]:
        filters: dict[str, str] = {}
        if kind is not None:
            filters["record_kind"] = kind
        if run is not None:
            filters["analysis_run_id"] = run
        expected = tuple(
            r
            for r in linked().records
            if (kind is None or r.kind == kind) and (run is None or run_id(r) == run)
        )
        assert all_records(store, **filters) == expected


def test_invalid_foreign_and_filter_cursors(store: Store) -> None:
    for i in range(3):
        success(store.put_record(text(f"text-{i}")))
    token = success(store.list_records(ListRequest(limit=1))).next_cursor
    assert token is not None
    for bad in ("", "!", "e30=", "x" * 9000):
        failure(store.list_records(ListRequest(cursor=bad)), "invalid_cursor")
    failure(store.list_records(ListRequest(cursor=token, record_kind="text")), "invalid_cursor")
    failure(
        store.list_records(ListRequest(cursor=token, analysis_run_id="run-1")), "invalid_cursor"
    )
    with MemoryStore() as other:
        failure(other.list_records(ListRequest(cursor=token)), "invalid_cursor")
    for changes in (
        {"version": 2},
        {"after": 0},
        {"after": 4},
        {"through": 4},
        {"after": 2, "through": 1},
        {"store": "another"},
        {"extra": 1},
    ):
        data = json.loads(base64.urlsafe_b64decode(token))
        data.update(changes)
        bad = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
        failure(store.list_records(ListRequest(cursor=bad)), "invalid_cursor")


@pytest.mark.parametrize("limit", [0, 1001])
def test_revalidates_listing_limit(store: Store, limit: int) -> None:
    failure(store.list_records(ListRequest.model_construct(limit=limit)), "invalid_record")


def test_append_history(store: Store) -> None:
    for record in linked().records:
        if isinstance(record, DecisionRecord):
            assert success(store.append_decision(record)) == record
            success(store.append_decision(record))
            changed = record.model_copy(update={"task_type": "different"})
            failure(store.append_decision(changed), "immutable_id_conflict")
            failure(store.put_record(changed), "immutable_id_conflict")
            success(store.append_decision(changed.model_copy(update={"id": record.id + "-v2"})))
        elif isinstance(record, Review):
            assert success(store.append_review(record)) == record
            success(store.append_review(record))
            changed = record.model_copy(update={"note": "different"})
            failure(store.append_review(changed), "immutable_id_conflict")
            failure(store.put_record(changed), "immutable_id_conflict")
            success(store.append_review(changed.model_copy(update={"id": record.id + "-v2"})))
        else:
            continue
        assert success(store.get_record(IdRequest(id=record.id))) == record
    reviews = all_records(store, record_kind="review")
    assert len(reviews) == 4
    assert isinstance(reviews[2], Review)
    assert reviews[2].supersedes_review_id == reviews[0].id
    assert len(all_records(store, record_kind="decision_record")) == 4


def test_null_availability_usage_and_generation_roundtrips(store: Store) -> None:
    # Cover all existing valid and missing-data variants, not only the linked chain.
    for index, path in enumerate(sorted((FIXTURES / "records").glob("*.json"))):
        if ".invalid." in path.name:
            continue
        record = RECORD_ADAPTER.validate_json(path.read_bytes())
        record = record.model_copy(update={"id": f"roundtrip-{index}"})
        success(store.put_record(record))
        recovered = success(store.get_record(IdRequest(id=record.id)))
        assert recovered == record
        assert encode(recovered) == encode(record)


def test_integer_float_distinction_in_arbitrary_json(store: Store) -> None:
    record = next(
        r
        for r in linked().records
        if isinstance(r, DecisionRecord) and isinstance(r.result, GenerationResult)
    )
    assert isinstance(record.result, GenerationResult)
    first = record.model_copy(
        update={"result": record.result.model_copy(update={"structured_output": {"value": 1}})}
    )
    second = record.model_copy(
        update={"result": record.result.model_copy(update={"structured_output": {"value": 1.0}})}
    )
    success(store.put_record(first))
    failure(store.put_record(second), "immutable_id_conflict")


def test_closed_backend(store: Store) -> None:
    store.close()
    store.close()
    failure(store.put_record(text()), "store_closed")
    failure(store.get_record(IdRequest(id="x")), "store_closed")
    failure(store.list_records(ListRequest()), "store_closed")
    failure(store.put_artifact(payload()), "store_closed")
    failure(store.get_artifact(IdRequest(id="x")), "store_closed")


def test_empty_artifact_is_not_missing(store: Store) -> None:
    empty = payload(content=b"")
    success(store.put_artifact(empty))
    assert success(store.get_artifact(IdRequest(id=empty.ref.id))) == empty


def test_missing_usage_is_not_zero(store: Store) -> None:
    original = next(r for r in linked().records if isinstance(r, DecisionRecord))
    zero = original.model_copy(
        update={
            "id": "decision-zero",
            "usage": Available[Usage](
                availability=Availability.AVAILABLE,
                data=Usage(input_tokens=0, output_tokens=0, requests=0, cost=0.0, currency="EUR"),
            ),
        }
    )
    for record in (original, zero):
        success(store.append_decision(record))
        assert success(store.get_record(IdRequest(id=record.id))) == record
    assert original.usage.data is None
    assert zero.usage.data is not None and zero.usage.data.requests == 0


def test_invalid_mutated_probability_distribution(store: Store) -> None:
    record = next(r for r in linked().records if isinstance(r, DecisionRecord))
    assert isinstance(record.result, DecisionResult)
    probabilities = record.result.probabilities.data
    assert probabilities is not None
    probabilities[record.result.label] = 0.0
    failure(store.put_record(record), "invalid_record")
    failure(store.append_decision(record), "invalid_record")
    assert all_records(store) == ()


def test_exact_text_is_not_normalized(store: Store) -> None:
    original = text(content="Ä\r\n🍎\u00a0e\u0301 ")
    success(store.put_record(original))
    failure(store.put_record(text(content="Ä\n🍎 é")), "immutable_id_conflict")
    assert success(store.get_record(IdRequest(id=original.id))) == original


def test_protocol_types(tmp_path: Path) -> None:
    # The Store annotations make both T00 protocol implementations a Pyright check.
    memory: Store = MemoryStore()
    persistent: Store = SQLiteStore(tmp_path)
    memory.close()
    persistent.close()
