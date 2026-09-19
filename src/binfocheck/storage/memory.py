"""Stateful, isolated test backend; no persistent storage or model references."""

from uuid import uuid4

from binfocheck.domain.records import Record
from binfocheck.domain.storage import ListRequest
from binfocheck.domain.text import ArtifactRef

from .base import BaseStore
from .codec import decode, digest, run_id
from .errors import StorageError


class MemoryStore(BaseStore):
    def __init__(self) -> None:
        self.store_id = uuid4().hex
        self._records: dict[str, tuple[int, bytes, str]] = {}
        self._artifacts: set[str] = set()
        self._blobs: dict[tuple[str, str], bytes] = {}

    def _save(self, record: Record, data: bytes, payload: bytes | None = None) -> None:
        existing = self._records.get(record.id)
        if existing is not None and (existing[1] != data or existing[2] != digest(data)):
            raise StorageError("immutable_id_conflict")
        if payload is not None:
            if not isinstance(record, ArtifactRef):
                raise StorageError("invalid_record")
            key = (record.access, record.sha256)
            if key in self._blobs and self._blobs[key] != payload:
                raise StorageError("artifact_hash_mismatch")
            self._blobs[key] = payload
            self._artifacts.add(record.id)
        if existing is None:
            self._records[record.id] = (len(self._records) + 1, data, digest(data))

    def _load(self, record_id: str) -> Record:
        if record_id not in self._records:
            raise StorageError("not_found")
        _, data, expected_hash = self._records[record_id]
        return decode(data, expected_hash)

    def _payload(self, ref: ArtifactRef) -> bytes:
        if ref.id not in self._artifacts:
            raise StorageError("artifact_data_missing")
        content = self._blobs.get((ref.access, ref.sha256))
        if content is None:
            raise StorageError("artifact_data_missing")
        return content

    def _maximum(self) -> int:
        return len(self._records)

    def _page(self, request: ListRequest, after: int, through: int) -> list[tuple[int, Record]]:
        matches: list[tuple[int, Record]] = []
        position_found = after == 0
        for seq, data, expected_hash in self._records.values():
            record = decode(data, expected_hash)
            if request.record_kind is not None and record.kind != request.record_kind:
                continue
            if request.analysis_run_id is not None and run_id(record) != request.analysis_run_id:
                continue
            if seq == after:
                position_found = True
            if after < seq <= through:
                matches.append((seq, record))
                if len(matches) == request.limit + 1:
                    break
        if not position_found:
            raise StorageError("invalid_cursor")
        return matches
