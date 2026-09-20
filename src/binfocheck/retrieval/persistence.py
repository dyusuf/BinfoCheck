"""T11A-only artifacts and lazy resolution through the shared graph validator."""

import base64
from collections.abc import Iterable

from binfocheck.domain.common import Contract, ErrorDetail
from binfocheck.domain.records import Record, RecordSet
from binfocheck.domain.storage import ArtifactPayload, ArtifactStore, IdRequest, RecordStore
from binfocheck.domain.text import ArtifactRef
from binfocheck.domain.validation import LinkedRecords

from .config import canonical, digest, identity
from .errors import check, require


class Store:
    def __init__(self, records: RecordStore, artifacts: ArtifactStore) -> None:
        self.records, self.artifacts = records, artifacts

    def record[T: Record](self, id: str, cls: type[T]) -> T:
        value = require(self.records.get_record(IdRequest(id=id)))
        check(isinstance(value, cls), "wrong_record_kind", id)
        assert isinstance(value, cls)
        return value

    def put(self, record: Record) -> None:
        require(self.records.put_record(record))

    def save(self, role: str, value: Contract, id: str | None = None) -> ArtifactRef:
        data = canonical(value.model_dump(mode="json"))
        ref = ArtifactRef(
            id=id or identity(role, value.model_dump(mode="json")),
            storage_key="retrieval/1/" + role,
            sha256=digest(data),
            media_type="application/json",
            access="restricted",
        )
        require(
            self.artifacts.put_artifact(
                ArtifactPayload(ref=ref, content_base64=base64.b64encode(data).decode())
            )
        )
        return ref

    def bytes(self, id: str) -> bytes:
        payload = require(self.artifacts.get_artifact(IdRequest(id=id)))
        data = base64.b64decode(payload.content_base64, validate=True)
        check(
            payload.ref == self.record(id, ArtifactRef) and payload.ref.sha256 == digest(data),
            "artifact_mismatch",
            id,
        )
        check(payload.ref.access == "restricted", "artifact_access_mismatch", id)
        return data

    def load[T: Contract](self, id: str, cls: type[T]) -> T:
        return cls.model_validate_json(self.bytes(id))

    def exists(self, id: str) -> bool:
        result = self.records.get_record(IdRequest(id=id))
        if result.error and result.error.code == "not_found":
            return False
        require(result)
        return True

    def failure(self, operation: str, inputs: tuple[str, ...], error: ErrorDetail) -> None:
        self.save("failure", Failure(operation=operation, input_ids=inputs, error=error))


class Failure(Contract):
    format: str = "t07-failure/1"
    operation: str
    input_ids: tuple[str, ...]
    error: ErrorDetail


class ResolvingLinks(LinkedRecords):
    def __init__(self, store: Store, seeds: Iterable[Record]) -> None:
        super().__init__(RecordSet(records=tuple(seeds)))
        self.store = store

    def any_id(self, id: str, owner: str) -> Record:
        if id not in self.records:
            self.records[id] = require(self.store.records.get_record(IdRequest(id=id)))
        return super().any_id(id, owner)

    def require[T: Record](self, id: str, expected: type[T], owner: str) -> T:
        self.any_id(id, owner)
        return super().require(id, expected, owner)


def closure(store: Store, seeds: Iterable[Record]) -> dict[str, str]:
    links = ResolvingLinks(store, seeds)
    checked: set[str] = set()
    while pending := [r for r in links.records.values() if r.id not in checked]:
        check(len(links.records) < 100000, "graph_limit")
        for record in pending:
            links.validate_record(record)
            if isinstance(record, ArtifactRef):
                payload = require(store.artifacts.get_artifact(IdRequest(id=record.id)))
                check(payload.ref == record, "artifact_mismatch", record.id)
            checked.add(record.id)
    links.validate_history()
    return {
        id: digest(canonical(record.model_dump(mode="json")))
        for id, record in links.records.items()
    }
