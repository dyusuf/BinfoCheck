"""Shared T11A I/O only; no private database or filesystem save format."""

import base64

from binfocheck.domain.common import Contract
from binfocheck.domain.records import Record
from binfocheck.domain.storage import ArtifactPayload, ArtifactStore, IdRequest, RecordStore
from binfocheck.domain.text import ArtifactRef

from .config import canonical, digest, identity
from .errors import check, require


class Store:
    def __init__(self, records: RecordStore, artifacts: ArtifactStore) -> None:
        self.records = records
        self.artifacts = artifacts

    def put(self, record: Record) -> None:
        require(self.records.put_record(record))

    def record[T: Record](self, id: str, cls: type[T]) -> T:
        result = require(self.records.get_record(IdRequest(id=id)))
        check(isinstance(result, cls), "wrong_record_kind")
        assert isinstance(result, cls)
        return result

    def blob(self, data: bytes, role: str, media: str, id: str | None = None) -> ArtifactRef:
        ref = ArtifactRef(
            id=id or identity(role, digest(data)),
            storage_key=f"corpus/{role}/1",
            sha256=digest(data),
            media_type=media,
            access="restricted",
        )
        require(
            self.artifacts.put_artifact(
                ArtifactPayload(ref=ref, content_base64=base64.b64encode(data).decode("ascii"))
            )
        )
        return ref

    def json(self, value: Contract, role: str, id: str) -> ArtifactRef:
        return self.blob(canonical(value.model_dump(mode="json")), role, "application/json", id)

    def bytes(self, id: str) -> bytes:
        payload = require(self.artifacts.get_artifact(IdRequest(id=id)))
        data = base64.b64decode(payload.content_base64, validate=True)
        check(payload.ref.id == id and digest(data) == payload.ref.sha256, "artifact_hash_mismatch")
        check(self.record(id, ArtifactRef) == payload.ref, "artifact_metadata_mismatch")
        return data

    def load[T: Contract](self, id: str, cls: type[T]) -> T:
        return cls.model_validate_json(self.bytes(id))
