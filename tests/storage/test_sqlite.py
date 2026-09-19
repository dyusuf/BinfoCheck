import base64
import json
import os
import sqlite3
from pathlib import Path
from typing import NoReturn

import pytest

from binfocheck.domain.records import RecordSet
from binfocheck.domain.storage import IdRequest, ListRequest
from binfocheck.domain.text import ArtifactRef, TextRecord
from binfocheck.domain.validation import validate_links
from binfocheck.storage import SQLiteStore, StorageInitializationError, migrations
from binfocheck.storage.migrations import APPLICATION_ID
from tests.contracts.helpers import linked

from .helpers import all_records, failure, fixture_payloads, payload, success, text


def blob_path(root: Path, ref: ArtifactRef) -> Path:
    return root / "artifacts" / ref.access / "sha256" / ref.sha256[:2] / ref.sha256


def test_close_reopen_linked_fixture_and_cursor(tmp_path: Path) -> None:
    original = linked()
    with SQLiteStore(tmp_path) as store:
        for record in original.records:
            success(store.put_record(record))
        for artifact in fixture_payloads():
            success(store.put_artifact(artifact))
        first = success(store.list_records(ListRequest(limit=5)))
        assert first.next_cursor is not None
    with SQLiteStore(tmp_path) as reopened:
        recovered = RecordSet(records=all_records(reopened))
        assert recovered == original
        assert recovered.model_dump(mode="json") == original.model_dump(mode="json")
        validate_links(recovered)
        for record in original.records:
            assert success(reopened.get_record(IdRequest(id=record.id))) == record
            success(reopened.put_record(record))
        for artifact in fixture_payloads():
            assert success(reopened.get_artifact(IdRequest(id=artifact.ref.id))) == artifact
            success(reopened.put_artifact(artifact))
        second = success(reopened.list_records(ListRequest(limit=1000, cursor=first.next_cursor)))
        assert first.records + second.records == original.records
        assert second.next_cursor is None
        answer = next(r for r in recovered.records if isinstance(r, TextRecord))
        assert answer.text[8:17] == "sind rot."
        assert answer.text[26:35] == "sind rot."
    with sqlite3.connect(tmp_path / "store.sqlite3") as database:
        assert database.execute("SELECT count(*) FROM records").fetchone()[0] == 27
        assert database.execute("SELECT count(*) FROM artifact_payloads").fetchone()[0] == 2


def test_dedup_and_metadata_paths(tmp_path: Path) -> None:
    with SQLiteStore(tmp_path) as store:
        artifact = payload()
        artifact = artifact.model_copy(
            update={
                "ref": artifact.ref.model_copy(
                    update={"storage_key": str(tmp_path / "must-not-exist")}
                )
            }
        )
        second = artifact.model_copy(
            update={"ref": artifact.ref.model_copy(update={"id": "other"})}
        )
        success(store.put_artifact(artifact))
        first_stat = blob_path(tmp_path, artifact.ref).stat()
        success(store.put_artifact(second))
        success(store.put_artifact(artifact))
        assert blob_path(tmp_path, artifact.ref).stat().st_ino == first_stat.st_ino
        files = [p for p in (tmp_path / "artifacts").rglob("*") if p.is_file()]
        assert files == [blob_path(tmp_path, artifact.ref)]
        assert not (tmp_path / "must-not-exist").exists()
        assert blob_path(tmp_path, artifact.ref).read_bytes() == b"synthetic"


@pytest.mark.parametrize("corrupt", [False, True])
def test_missing_corrupt_blobs_and_verified_reuse(tmp_path: Path, corrupt: bool) -> None:
    artifact = payload()
    with SQLiteStore(tmp_path) as store:
        success(store.put_artifact(artifact))
    path = blob_path(tmp_path, artifact.ref)
    if corrupt:
        path.write_bytes(b"partial")
    else:
        path.unlink()
    with SQLiteStore(tmp_path) as store:
        failure(
            store.get_artifact(IdRequest(id=artifact.ref.id)),
            "artifact_hash_mismatch" if corrupt else "artifact_data_missing",
        )
        if corrupt:
            failure(store.put_artifact(artifact), "artifact_hash_mismatch")
            assert path.read_bytes() == b"partial"
        else:
            # An explicit identical retry may restore missing bytes from verified input.
            success(store.put_artifact(artifact))
            assert success(store.get_artifact(IdRequest(id=artifact.ref.id))) == artifact


@pytest.mark.parametrize("location", ["artifacts", "access", "hashes", "prefix", "blob"])
def test_symlink_escape_rejected(tmp_path: Path, location: str) -> None:
    root = tmp_path / "store"
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"synthetic")
    artifact = payload()
    path = blob_path(root, artifact.ref)
    candidates = {
        "artifacts": root / "artifacts",
        "access": root / "artifacts" / artifact.ref.access,
        "hashes": path.parent.parent,
        "prefix": path.parent,
        "blob": path,
    }
    with SQLiteStore(root) as store:
        target = candidates[location]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(
            sentinel if location == "blob" else outside, target_is_directory=location != "blob"
        )
        result = store.put_artifact(artifact)
        failure(result, "storage_io_error")
        assert str(outside) not in result.model_dump_json()
        failure(store.get_record(IdRequest(id=artifact.ref.id)), "not_found")
        assert list(outside.iterdir()) == [sentinel]
        assert sentinel.read_bytes() == b"synthetic"


def test_read_symlink_rejected(tmp_path: Path) -> None:
    artifact = payload()
    with SQLiteStore(tmp_path / "store") as store:
        success(store.put_artifact(artifact))
        path = blob_path(tmp_path / "store", artifact.ref)
        outside = tmp_path / "outside"
        outside.write_bytes(b"synthetic")
        path.unlink()
        path.symlink_to(outside)
        failure(store.get_artifact(IdRequest(id=artifact.ref.id)), "storage_io_error")


@pytest.mark.parametrize("stage", ["write", "publish"])
def test_handled_file_failure_rolls_back_and_cleans_temps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    artifact = payload()
    with SQLiteStore(tmp_path) as store:

        def fail(*args: object, **kwargs: object) -> NoReturn:
            raise OSError("SECRET /unrestricted/path payload SQL")

        with monkeypatch.context() as patch:
            patch.setattr(os, "fsync" if stage == "write" else "link", fail)
            result = store.put_artifact(artifact)
        failure(result, "storage_io_error")
        assert "SECRET" not in result.model_dump_json()
        assert not blob_path(tmp_path, artifact.ref).exists()
        assert list(tmp_path.rglob(".tmp-*")) == []
        failure(store.get_record(IdRequest(id=artifact.ref.id)), "not_found")
        success(store.put_artifact(artifact))


def test_atomic_publication_contains_complete_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = payload(content=b"complete synthetic payload" * 100)
    real_link = os.link
    observed: list[bytes] = []

    def inspect_link(
        src: str, dst: str, *, src_dir_fd: int, dst_dir_fd: int, follow_symlinks: bool
    ) -> None:
        handle = os.open(src, os.O_RDONLY, dir_fd=src_dir_fd)
        with os.fdopen(handle, "rb") as stream:
            observed.append(stream.read())
        assert not blob_path(tmp_path, artifact.ref).exists()
        real_link(
            src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd, follow_symlinks=follow_symlinks
        )

    with SQLiteStore(tmp_path) as store:
        monkeypatch.setattr(os, "link", inspect_link)
        success(store.put_artifact(artifact))
        assert observed == [base64.b64decode(artifact.content_base64)]
        assert success(store.get_artifact(IdRequest(id=artifact.ref.id))) == artifact
        assert list(tmp_path.rglob(".tmp-*")) == []


def test_metadata_failure_rolls_back_and_orphan_is_reusable(tmp_path: Path) -> None:
    artifact = payload()
    with SQLiteStore(tmp_path) as store:
        with sqlite3.connect(tmp_path / "store.sqlite3") as connection:
            connection.execute("""CREATE TRIGGER fail_payload BEFORE INSERT ON artifact_payloads
                                  BEGIN SELECT RAISE(ABORT, 'SECRET SQL payload'); END""")
        result = store.put_artifact(artifact)
        failure(result, "storage_io_error")
        assert "SECRET" not in result.model_dump_json()
        failure(store.get_record(IdRequest(id=artifact.ref.id)), "not_found")
        assert blob_path(tmp_path, artifact.ref).read_bytes() == b"synthetic"
        assert list(tmp_path.rglob(".tmp-*")) == []
        with sqlite3.connect(tmp_path / "store.sqlite3") as connection:
            connection.execute("DROP TRIGGER fail_payload")
        success(store.put_artifact(artifact))
        assert len(all_records(store)) == 1


def test_commit_failure_returns_typed_failure_and_can_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FaultConnection(sqlite3.Connection):
        fail_commit = False

        def commit(self) -> None:
            if self.fail_commit:
                raise sqlite3.OperationalError("SECRET commit SQL")
            super().commit()

    original_connect = sqlite3.connect
    connections: list[FaultConnection] = []

    def connect(database: Path, *, timeout: float, isolation_level: None) -> FaultConnection:
        result = original_connect(
            database, timeout=timeout, isolation_level=isolation_level, factory=FaultConnection
        )
        connections.append(result)
        return result

    monkeypatch.setattr(sqlite3, "connect", connect)
    with SQLiteStore(tmp_path) as store:
        connections[0].fail_commit = True
        result = store.put_artifact(payload())
        failure(result, "storage_io_error")
        assert "SECRET" not in result.model_dump_json()
        failure(store.get_record(IdRequest(id="artifact-new")), "not_found")
        connections[0].fail_commit = False
        success(store.put_artifact(payload()))


def test_two_writers_busy_and_identical_retry(tmp_path: Path) -> None:
    with (
        SQLiteStore(tmp_path, busy_timeout_seconds=0.01) as first,
        SQLiteStore(tmp_path, busy_timeout_seconds=0.01) as second,
        sqlite3.connect(tmp_path / "store.sqlite3", isolation_level=None) as locker,
    ):
        locker.execute("BEGIN IMMEDIATE")
        try:
            failure(second.put_record(text()), "storage_busy")
        finally:
            locker.rollback()
        success(first.put_record(text()))
        success(second.put_record(text()))
        failure(second.put_record(text(content="different")), "immutable_id_conflict")
        assert all_records(first) == all_records(second) == (text(),)


def test_schema_v1_initialization_and_reopen(tmp_path: Path) -> None:
    with SQLiteStore(tmp_path):
        pass
    with sqlite3.connect(tmp_path / "store.sqlite3") as connection:
        assert connection.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    with SQLiteStore(tmp_path) as reopened:
        assert all_records(reopened) == ()


@pytest.mark.parametrize("mode", [0o755, 0o750, 0o707, 0o777])
@pytest.mark.parametrize("existing_database", [False, True])
def test_insecure_root_rejected_before_sqlite_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: int, existing_database: bool
) -> None:
    root = tmp_path / "store"
    root.mkdir(mode=0o700)
    if existing_database:
        with SQLiteStore(root) as store:
            success(store.put_record(text()))
    database = root / "store.sqlite3"
    original_bytes = database.read_bytes() if existing_database else None
    original_files = set(root.iterdir())
    root.chmod(mode)

    def unexpected_connect(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("An insecure root must be rejected before opening SQLite")

    monkeypatch.setattr(sqlite3, "connect", unexpected_connect)
    with pytest.raises(StorageInitializationError) as caught:
        SQLiteStore(root)
    assert caught.value.detail.code == "insecure_storage_permissions"
    assert caught.value.detail.message == "insecure storage permissions"
    assert not caught.value.detail.retryable
    assert str(root) not in str(caught.value)
    assert root.stat().st_mode & 0o777 == mode
    assert set(root.iterdir()) == original_files
    if existing_database:
        assert database.read_bytes() == original_bytes
    else:
        assert not database.exists()


@pytest.mark.parametrize("existing_root", [False, True])
def test_private_root_creation_and_reopen(tmp_path: Path, existing_root: bool) -> None:
    root = tmp_path / "store"
    if existing_root:
        root.mkdir(mode=0o700)
        root.chmod(0o700)
    with SQLiteStore(root) as store:
        success(store.put_record(text()))
    assert root.stat().st_mode & 0o777 == 0o700
    with SQLiteStore(root) as reopened:
        assert success(reopened.get_record(IdRequest(id="text-new"))) == text()


@pytest.mark.parametrize("foreign", [True, False])
def test_reject_foreign_or_newer_schema(tmp_path: Path, foreign: bool) -> None:
    with SQLiteStore(tmp_path):
        pass
    with sqlite3.connect(tmp_path / "store.sqlite3") as connection:
        connection.execute("PRAGMA application_id = 42" if foreign else "PRAGMA user_version = 2")
    code = "foreign_storage_schema" if foreign else "unsupported_storage_version"
    with pytest.raises(StorageInitializationError) as caught:
        SQLiteStore(tmp_path)
    assert caught.value.detail.code == code
    with sqlite3.connect(tmp_path / "store.sqlite3") as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == (1 if foreign else 2)


def test_reject_unlabelled_nonempty_database(tmp_path: Path) -> None:
    with sqlite3.connect(tmp_path / "store.sqlite3") as connection:
        connection.execute("CREATE TABLE foreign_data (value TEXT)")
    with pytest.raises(StorageInitializationError, match="foreign storage schema"):
        SQLiteStore(tmp_path)


def test_initialization_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(migrations, "DDL", (*migrations.DDL, "INVALID SYNTHETIC SQL"))
        with pytest.raises(StorageInitializationError):
            SQLiteStore(tmp_path)
    with sqlite3.connect(tmp_path / "store.sqlite3") as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert connection.execute("SELECT name FROM sqlite_master").fetchall() == []
    with SQLiteStore(tmp_path) as store:
        success(store.put_record(text()))


def test_foreign_sqlite_file_is_typed_error(tmp_path: Path) -> None:
    (tmp_path / "store.sqlite3").write_bytes(b"not a SQLite database")
    with pytest.raises(StorageInitializationError, match="storage corrupt"):
        SQLiteStore(tmp_path)


def test_unsupported_codec_is_rejected(tmp_path: Path) -> None:
    with SQLiteStore(tmp_path):
        pass
    with sqlite3.connect(tmp_path / "store.sqlite3") as connection:
        connection.execute("UPDATE store_meta SET serialization_version = 2")
    with pytest.raises(StorageInitializationError, match="unsupported serialization version"):
        SQLiteStore(tmp_path)


def test_initialization_failure_is_sanitized(tmp_path: Path) -> None:
    root = tmp_path / "SECRET-file"
    root.write_bytes(b"SECRET")
    with pytest.raises(StorageInitializationError) as caught:
        SQLiteStore(root)
    assert caught.value.detail.code == "storage_io_error"
    assert "SECRET" not in str(caught.value)


@pytest.mark.parametrize("name", ["store.sqlite3", "store.sqlite3-journal"])
def test_database_symlink_rejected(tmp_path: Path, name: str) -> None:
    outside = tmp_path / "outside"
    outside.write_bytes(b"untouched")
    root = tmp_path / "store"
    root.mkdir()
    (root / name).symlink_to(outside)
    with pytest.raises(StorageInitializationError, match="unsafe storage path"):
        SQLiteStore(root)
    assert outside.read_bytes() == b"untouched"


@pytest.mark.parametrize(
    "column,value",
    [
        ("canonical_json", b"bad"),
        ("sha256", "wrong"),
        ("kind", "claim"),
        ("serialization_version", 99),
    ],
)
def test_corrupt_records_are_not_returned(
    tmp_path: Path, column: str, value: bytes | str | int
) -> None:
    with SQLiteStore(tmp_path) as store:
        success(store.put_record(text()))
        with sqlite3.connect(tmp_path / "store.sqlite3") as connection:
            # Column is a fixed test parameter, not storage input.
            connection.execute(f"UPDATE records SET {column} = ?", (value,))
        failure(store.get_record(IdRequest(id="text-new")), "storage_corrupt")
        failure(store.list_records(ListRequest()), "storage_corrupt")
        failure(store.put_record(text()), "storage_corrupt")


def test_cursor_position_must_match_filters(tmp_path: Path) -> None:
    with SQLiteStore(tmp_path) as store:
        success(store.put_record(payload().ref))
        success(store.put_record(text("text-1")))
        success(store.put_record(text("text-2")))
        page = success(store.list_records(ListRequest(record_kind="text", limit=1)))
        assert page.next_cursor is not None
        data = json.loads(base64.urlsafe_b64decode(page.next_cursor))
        data["after"] = 1  # Existing sequence, but it is an artifact, not text.
        token = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
        failure(store.list_records(ListRequest(record_kind="text", cursor=token)), "invalid_cursor")
