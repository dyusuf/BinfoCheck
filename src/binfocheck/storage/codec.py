"""Version-one canonical JSON; exact text and array order are never normalized."""

import hashlib
import json

from binfocheck.domain.common import DerivedRecord
from binfocheck.domain.records import RECORD_ADAPTER, Record
from binfocheck.domain.runs import RunManifest

from .errors import StorageError

SERIALIZATION_VERSION = 1


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(record: Record) -> bytes:
    # A JSON round trip forces validation even for model_construct and mutable children.
    validated = RECORD_ADAPTER.validate_json(record.model_dump_json(warnings="error"))
    return json.dumps(
        validated.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def decode(data: bytes, expected_hash: str) -> Record:
    if digest(data) != expected_hash:
        raise StorageError("storage_corrupt")
    try:
        record = RECORD_ADAPTER.validate_json(data)
        if encode(record) != data:
            raise StorageError("storage_corrupt")
        return record
    except (ValueError, TypeError) as error:
        raise StorageError("storage_corrupt") from error


def run_id(record: Record) -> str | None:
    if isinstance(record, DerivedRecord):
        return record.analysis_run_id
    if isinstance(record, RunManifest):
        return record.id
    return None
