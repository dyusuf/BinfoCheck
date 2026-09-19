"""Shared protocol implementation, with persistence primitives supplied by backends."""

import base64
from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self

from pydantic import ValidationError

from binfocheck.domain.decisions import DecisionRecord
from binfocheck.domain.records import Record
from binfocheck.domain.runs import Review
from binfocheck.domain.storage import ArtifactPayload, IdRequest, ListRequest, RecordPage
from binfocheck.domain.text import ArtifactRef

from .codec import decode, digest, encode
from .cursors import next_cursor, read_cursor
from .errors import StorageError, outcome, payload_validation_error


class BaseStore(ABC):
    store_id: str
    _closed: bool = False

    def _check_open(self) -> None:
        if self._closed:
            raise StorageError("store_closed")

    @abstractmethod
    def _save(self, record: Record, data: bytes, payload: bytes | None = None) -> None: ...

    @abstractmethod
    def _load(self, record_id: str) -> Record: ...

    @abstractmethod
    def _payload(self, ref: ArtifactRef) -> bytes: ...

    @abstractmethod
    def _maximum(self) -> int: ...

    @abstractmethod
    def _page(self, request: ListRequest, after: int, through: int) -> list[tuple[int, Record]]:
        """Check continuation position, return at most limit + 1 matching records."""

    @outcome
    def put_record(self, request: Record) -> Record:
        self._check_open()
        data = encode(request)
        record = decode(data, digest(data))
        self._save(record, data)
        return record

    @outcome
    def get_record(self, request: IdRequest) -> Record:
        self._check_open()
        request = IdRequest.model_validate_json(request.model_dump_json(warnings="error"))
        return self._load(request.id)

    @outcome
    def put_artifact(self, request: ArtifactPayload) -> ArtifactRef:
        self._check_open()
        try:
            request = ArtifactPayload.model_validate_json(request.model_dump_json(warnings="error"))
        except ValidationError as error:
            raise payload_validation_error(error) from error
        data = encode(request.ref)
        self._save(request.ref, data, base64.b64decode(request.content_base64, validate=True))
        return request.ref

    @outcome
    def get_artifact(self, request: IdRequest) -> ArtifactPayload:
        self._check_open()
        request = IdRequest.model_validate_json(request.model_dump_json(warnings="error"))
        record = self._load(request.id)
        if not isinstance(record, ArtifactRef):
            raise StorageError("not_found")
        content = self._payload(record)
        if digest(content) != record.sha256:
            raise StorageError("artifact_hash_mismatch")
        return ArtifactPayload(ref=record, content_base64=base64.b64encode(content).decode())

    @outcome
    def list_records(self, request: ListRequest) -> RecordPage:
        self._check_open()
        request = ListRequest.model_validate_json(request.model_dump_json(warnings="error"))
        after, through = read_cursor(request, self.store_id, self._maximum())
        rows = self._page(request, after, through)
        selected = rows[: request.limit]
        token = (
            next_cursor(request, self.store_id, selected[-1][0], through)
            if len(rows) > request.limit
            else None
        )
        return RecordPage(records=tuple(record for _, record in selected), next_cursor=token)

    @outcome
    def append_decision(self, request: DecisionRecord) -> DecisionRecord:
        self._check_open()
        record = DecisionRecord.model_validate_json(request.model_dump_json(warnings="error"))
        self._save(record, encode(record))
        return record

    @outcome
    def append_review(self, request: Review) -> Review:
        self._check_open()
        record = Review.model_validate_json(request.model_dump_json(warnings="error"))
        self._save(record, encode(record))
        return record

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> Self:
        self._check_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
