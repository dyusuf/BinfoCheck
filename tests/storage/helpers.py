import base64
from typing import Protocol

from binfocheck.domain.common import Outcome
from binfocheck.domain.records import Record
from binfocheck.domain.storage import ArtifactPayload, ArtifactStore, ListRequest, RecordStore
from binfocheck.domain.text import ArtifactRef, TextRecord
from binfocheck.storage.codec import digest
from tests.contracts.helpers import linked


class Store(RecordStore, ArtifactStore, Protocol):
    def close(self) -> None: ...


def success[T](result: Outcome[T]) -> T:
    assert result.status == "succeeded", result.error
    assert result.error is None
    assert result.value is not None
    return result.value


def failure[T](result: Outcome[T], code: str) -> None:
    assert result.status == "failed"
    assert result.value is None
    assert result.error is not None
    assert result.error.code == code
    assert result.error.message == code.replace("_", " ")
    assert result.error.retryable == (code == "storage_busy")


def text(record_id: str = "text-new", content: str = "Äpfel 🍎 sind rot.") -> TextRecord:
    return TextRecord(id=record_id, text=content, artifact_id="artifact-1")


def payload(record_id: str = "artifact-new", content: bytes = b"synthetic") -> ArtifactPayload:
    return ArtifactPayload(
        ref=ArtifactRef(
            id=record_id,
            storage_key="metadata-not-a-path",
            sha256=digest(content),
            media_type="application/octet-stream",
            access="shareable_fixture",
        ),
        content_base64=base64.b64encode(content).decode(),
    )


def fixture_payloads() -> tuple[ArtifactPayload, ...]:
    contents = {
        "artifact-1": "Äpfel 🍎 sind rot. Äpfel 🍎 sind rot.".encode(),
        "artifact-generation": b"{}",
    }
    return tuple(
        ArtifactPayload(ref=record, content_base64=base64.b64encode(contents[record.id]).decode())
        for record in linked().records
        if isinstance(record, ArtifactRef)
    )


def all_records(store: RecordStore, **filters: str) -> tuple[Record, ...]:
    records: list[Record] = []
    cursor: str | None = None
    while True:
        page = success(store.list_records(ListRequest(limit=3, cursor=cursor, **filters)))
        assert len(page.records) <= 3
        records.extend(page.records)
        cursor = page.next_cursor
        if cursor is None:
            return tuple(records)
