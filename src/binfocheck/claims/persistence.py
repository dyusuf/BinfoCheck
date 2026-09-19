"""Immutable T11A artifacts and exact-ID graph closure, never record scanning."""

import base64
import hashlib
import json
from collections.abc import Iterable

from pydantic import JsonValue

from binfocheck.domain.records import Record, RecordSet
from binfocheck.domain.storage import ArtifactPayload, ArtifactStore, IdRequest, RecordStore
from binfocheck.domain.text import ArtifactRef
from binfocheck.domain.validation import LinkedRecords, LinkError

from .errors import ExtractionError, check, require


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(prefix: str, *parts: object) -> str:
    return prefix + "-" + digest(canonical(parts))


def save(artifacts: ArtifactStore, id: str, value: object) -> ArtifactRef:
    data = canonical(value)
    ref = ArtifactRef(
        id=id,
        storage_key="claims/v1/" + id.split("-")[0],
        sha256=digest(data),
        media_type="application/json",
        access="restricted",
    )
    require(
        artifacts.put_artifact(
            ArtifactPayload(ref=ref, content_base64=base64.b64encode(data).decode())
        )
    )
    return ref


def load(artifacts: ArtifactStore, id: str) -> bytes | None:
    outcome = artifacts.get_artifact(IdRequest(id=id))
    if outcome.error and outcome.error.code == "not_found":
        return None
    payload = require(outcome)
    data = base64.b64decode(payload.content_base64, validate=True)
    check(payload.ref.id == id and digest(data) == payload.ref.sha256, "artifact_corrupt")
    return data


class ResolvingLinks(LinkedRecords):
    """Resolve only references requested by the shared graph validator."""

    def __init__(self, store: RecordStore, seeds: Iterable[Record]) -> None:
        super().__init__(RecordSet(records=tuple(seeds)))
        self.store = store

    def any_id(self, id: str, owner: str) -> Record:
        if id not in self.records:
            self.records[id] = require(self.store.get_record(IdRequest(id=id)))
        return super().any_id(id, owner)

    def require[T: Record](self, id: str, expected: type[T], owner: str) -> T:
        self.any_id(id, owner)
        return super().require(id, expected, owner)


def closure(
    store: RecordStore, artifacts: ArtifactStore, seeds: Iterable[Record]
) -> tuple[Record, ...]:
    links = ResolvingLinks(store, seeds)
    checked: set[str] = set()
    try:
        while pending := [r for r in links.records.values() if r.id not in checked]:
            check(len(links.records) <= 100_000, "graph_limit")
            for record in pending:
                links.validate_record(record)
                if isinstance(record, ArtifactRef):
                    check(load(artifacts, record.id) is not None, "required_artifact_missing")
                checked.add(record.id)
        links.validate_history()
    except LinkError:
        raise ExtractionError("invalid_linked_lineage") from None
    return tuple(links.records.values())


def json_object(raw: bytes) -> dict[str, JsonValue]:
    from pydantic import TypeAdapter

    return TypeAdapter(dict[str, JsonValue]).validate_json(raw)
