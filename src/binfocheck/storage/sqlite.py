"""SQLite metadata and local content-addressed bytes behind the T00 protocols."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from binfocheck.domain.records import Record
from binfocheck.domain.storage import ListRequest
from binfocheck.domain.text import ArtifactRef

from .base import BaseStore
from .blobs import ContentAddressedFiles
from .codec import SERIALIZATION_VERSION, decode, digest, run_id
from .errors import StorageError, StorageInitializationError, error_detail
from .migrations import initialize

# Column order used by every record read, including integrity checks of derived indexes.
COLUMNS = (
    "seq, id, kind, analysis_run_id, schema_version, serialization_version, canonical_json, sha256"
)
StoredRow = tuple[int, str, str, str | None, str, int, object, object]


def record_from_row(row: StoredRow) -> Record:
    _, record_id, kind, analysis_run_id, schema_version, version, data, expected_hash = row
    if not isinstance(data, bytes) or not isinstance(expected_hash, str):
        raise StorageError("storage_corrupt")
    if version != SERIALIZATION_VERSION:
        raise StorageError("storage_corrupt")
    record = decode(data, expected_hash)
    if (record.id, record.kind, run_id(record), record.schema_version) != (
        record_id,
        kind,
        analysis_run_id,
        schema_version,
    ):
        raise StorageError("storage_corrupt")
    return record


class SQLiteStore(BaseStore):
    def __init__(self, root: Path, *, busy_timeout_seconds: float = 1.0) -> None:
        connection: sqlite3.Connection | None = None
        blobs: ContentAddressedFiles | None = None
        try:
            if not 0 <= busy_timeout_seconds <= 60:
                raise StorageError("invalid_storage_configuration")
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Configuration is trusted, but managed children must never be symlinks.
            if root.is_symlink() or any(
                (root / name).is_symlink()
                for name in (
                    "store.sqlite3",
                    "store.sqlite3-journal",
                    "store.sqlite3-wal",
                    "store.sqlite3-shm",
                )
            ):
                raise StorageError("unsafe_storage_path")
            # mkdir's mode does not secure an existing directory. Reject before opening
            # SQLite (which holds record/text data), without changing operator permissions.
            if root.stat(follow_symlinks=False).st_mode & 0o077:
                raise StorageError("insecure_storage_permissions")
            blobs = ContentAddressedFiles(root)
            connection = sqlite3.connect(
                root / "store.sqlite3", timeout=busy_timeout_seconds, isolation_level=None
            )
            connection.execute("PRAGMA foreign_keys = ON")
            # Validate ownership/version before changing persistent journal settings.
            self.store_id = initialize(connection)
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA synchronous = FULL")
            self._connection = connection
            self._blobs = blobs
        except (StorageError, sqlite3.Error, OSError, ValueError) as error:
            if connection is not None:
                connection.close()
            if blobs is not None:
                blobs.close()
            detail = error_detail(error)
            raise StorageInitializationError(detail.code, retryable=detail.retryable) from None

    @contextmanager
    def _transaction(self) -> Generator[None]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def _insert(self, record: Record, data: bytes) -> None:
        row = cast(
            StoredRow | None,
            self._connection.execute(
                f"SELECT {COLUMNS} FROM records WHERE id = ?", (record.id,)
            ).fetchone(),
        )
        if row is not None:
            record_from_row(row)
            if row[6] != data or row[7] != digest(data):
                raise StorageError("immutable_id_conflict")
            return
        self._connection.execute(
            "INSERT INTO records (id, kind, analysis_run_id, schema_version, "
            "serialization_version, canonical_json, sha256) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.kind,
                run_id(record),
                record.schema_version,
                SERIALIZATION_VERSION,
                data,
                digest(data),
            ),
        )

    def _save(self, record: Record, data: bytes, payload: bytes | None = None) -> None:
        with self._transaction():
            self._insert(record, data)
            if payload is not None:
                if not isinstance(record, ArtifactRef):
                    raise StorageError("invalid_record")
                self._blobs.put(record, payload)
                existing = self._connection.execute(
                    "SELECT sha256, byte_length FROM artifact_payloads WHERE record_id = ?",
                    (record.id,),
                ).fetchone()
                if existing is not None:
                    if existing != (record.sha256, len(payload)):
                        raise StorageError("storage_corrupt")
                else:
                    self._connection.execute(
                        "INSERT INTO artifact_payloads VALUES (?, ?, ?)",
                        (record.id, record.sha256, len(payload)),
                    )

    def _load(self, record_id: str) -> Record:
        row = cast(
            StoredRow | None,
            self._connection.execute(
                f"SELECT {COLUMNS} FROM records WHERE id = ?", (record_id,)
            ).fetchone(),
        )
        if row is None:
            raise StorageError("not_found")
        return record_from_row(row)

    def _payload(self, ref: ArtifactRef) -> bytes:
        row = self._connection.execute(
            "SELECT sha256, byte_length FROM artifact_payloads WHERE record_id = ?", (ref.id,)
        ).fetchone()
        if row is None:
            raise StorageError("artifact_data_missing")
        content = self._blobs.read(ref)
        if row != (ref.sha256, len(content)):
            raise StorageError("storage_corrupt")
        return content

    def _maximum(self) -> int:
        return cast(
            int, self._connection.execute("SELECT COALESCE(MAX(seq), 0) FROM records").fetchone()[0]
        )

    def _page(self, request: ListRequest, after: int, through: int) -> list[tuple[int, Record]]:
        clauses = ["seq <= ?"]
        parameters: list[str | int] = [through]
        if request.record_kind is not None:
            clauses.append("kind = ?")
            parameters.append(request.record_kind)
        if request.analysis_run_id is not None:
            clauses.append("analysis_run_id = ?")
            parameters.append(request.analysis_run_id)
        where = " AND ".join(clauses)
        if (
            after
            and self._connection.execute(
                f"SELECT 1 FROM records WHERE {where} AND seq = ?", (*parameters, after)
            ).fetchone()
            is None
        ):
            raise StorageError("invalid_cursor")
        rows = cast(
            list[StoredRow],
            self._connection.execute(
                f"SELECT {COLUMNS} FROM records WHERE {where} AND seq > ? ORDER BY seq LIMIT ?",
                (*parameters, after, request.limit + 1),
            ).fetchall(),
        )
        return [(row[0], record_from_row(row)) for row in rows]

    def close(self) -> None:
        if not self._closed:
            try:
                self._connection.close()
            finally:
                self._blobs.close()
                super().close()
