"""Exact-ID graph validation and immutable T11A completion artifacts."""

import base64
from collections.abc import Iterable
from typing import Literal

from binfocheck.domain.claims import CitationAssociation
from binfocheck.domain.common import Contract
from binfocheck.domain.interfaces import ClaimRequest
from binfocheck.domain.records import Record, RecordSet
from binfocheck.domain.storage import ArtifactPayload, ArtifactStore, IdRequest, RecordStore
from binfocheck.domain.text import ArtifactRef
from binfocheck.domain.validation import LinkedRecords

from .config import RULES, canonical, digest, identity
from .errors import check, require
from .scope import ReferenceAssessment


class Audit(Contract):
    version: Literal["1"] = "1"
    state: Literal["complete"] = "complete"
    work_key: str
    request: ClaimRequest
    input_hashes: dict[str, str]
    assessments: tuple[ReferenceAssessment, ...]
    result: CitationAssociation


class Store:
    def __init__(self, records: RecordStore, artifacts: ArtifactStore) -> None:
        self.records, self.artifacts = records, artifacts

    def record[T: Record](self, id: str, cls: type[T]) -> T:
        value = require(self.records.get_record(IdRequest(id=id)))
        check(isinstance(value, cls), "wrong_record_kind")
        assert isinstance(value, cls)
        return value

    def put(self, record: Record) -> None:
        require(self.records.put_record(record))

    def payload(self, role: str, value: object, id: str | None = None) -> ArtifactPayload:
        data = canonical(value)
        return ArtifactPayload(
            ref=ArtifactRef(
                id=id or identity(role, value),
                storage_key="citations/1/" + role,
                sha256=digest(data),
                media_type="application/json",
                access="restricted",
            ),
            content_base64=base64.b64encode(data).decode("ascii"),
        )

    def save(self, role: str, value: object) -> ArtifactRef:
        return require(self.artifacts.put_artifact(self.payload(role, value)))

    def bytes(self, id: str) -> bytes:
        payload = require(self.artifacts.get_artifact(IdRequest(id=id)))
        data = base64.b64decode(payload.content_base64, validate=True)
        check(
            payload.ref == self.record(id, ArtifactRef) and digest(data) == payload.ref.sha256,
            "artifact_mismatch",
        )
        return data

    def replay(
        self, id: str, request: ClaimRequest, hashes: dict[str, str], work: str
    ) -> CitationAssociation | None:
        response = self.artifacts.get_artifact(IdRequest(id=id))
        if response.error and response.error.code in {"not_found", "artifact_data_missing"}:
            return None
        require(response)
        audit = Audit.model_validate_json(self.bytes(id))
        check(
            audit.work_key == work and audit.request == request and audit.input_hashes == hashes,
            "audit_input_mismatch",
        )
        check(audit.result.id == identity("association", work), "audit_result_mismatch")
        saved = self.record(audit.result.id, CitationAssociation)
        check(
            saved == audit.result
            and saved.claim_id == request.claim_id
            and saved.analysis_run_id == request.analysis_run_id
            and saved.rule_version == request.settings.version,
            "audit_result_mismatch",
        )
        closure(self, (saved,))
        return saved

    def publish(self, audit: Audit) -> CitationAssociation:
        payload = self.payload(
            "audit", audit.model_dump(mode="json"), identity("audit", audit.work_key)
        )
        closure(self, (audit.result,))
        self.put(payload.ref)
        self.put(audit.result)
        require(self.artifacts.put_artifact(payload))  # Completion marker LAST.
        return audit.result


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
        check(len(links.records) <= RULES.max_linked_records, "graph_limit")
        for record in pending:
            links.validate_record(record)
            if isinstance(record, ArtifactRef):
                store.bytes(record.id)
            checked.add(record.id)
    links.validate_history()
    return {
        id: digest(canonical(record.model_dump(mode="json")))
        for id, record in sorted(links.records.items())
    }
