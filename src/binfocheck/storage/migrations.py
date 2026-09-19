"""Initialize storage v1; no speculative migrations or record rewriting."""

import sqlite3
from uuid import uuid4

from .codec import SERIALIZATION_VERSION
from .errors import StorageError

APPLICATION_ID = 0x42494E46
SCHEMA_VERSION = 1

DDL = (
    """CREATE TABLE records (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        id TEXT UNIQUE NOT NULL,
        kind TEXT NOT NULL,
        analysis_run_id TEXT,
        schema_version TEXT NOT NULL,
        serialization_version INTEGER NOT NULL,
        canonical_json BLOB NOT NULL,
        sha256 TEXT NOT NULL
    )""",
    """CREATE TABLE artifact_payloads (
        record_id TEXT PRIMARY KEY REFERENCES records(id),
        sha256 TEXT NOT NULL,
        byte_length INTEGER NOT NULL CHECK (byte_length >= 0)
    )""",
    """CREATE TABLE store_meta (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
        store_id TEXT NOT NULL,
        serialization_version INTEGER NOT NULL
    )""",
    "CREATE INDEX records_kind_seq ON records(kind, seq)",
    "CREATE INDEX records_run_seq ON records(analysis_run_id, seq)",
    "CREATE INDEX records_run_kind_seq ON records(analysis_run_id, kind, seq)",
)


def initialize(connection: sqlite3.Connection) -> str:
    connection.execute("BEGIN IMMEDIATE")
    try:
        application_id = connection.execute("PRAGMA application_id").fetchone()[0]
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        tables = connection.execute("SELECT name FROM sqlite_master").fetchall()
        if application_id == 0 and version == 0 and not tables:
            for statement in DDL:
                connection.execute(statement)
            store_id = uuid4().hex
            connection.execute(
                "INSERT INTO store_meta VALUES (1, ?, ?)", (store_id, SERIALIZATION_VERSION)
            )
            connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        elif application_id != APPLICATION_ID:
            raise StorageError("foreign_storage_schema")
        elif version != SCHEMA_VERSION:
            raise StorageError("unsupported_storage_version")
        row = connection.execute(
            "SELECT store_id, serialization_version FROM store_meta WHERE singleton = 1"
        ).fetchone()
        if row is None or not isinstance(row[0], str) or not row[0]:
            raise StorageError("storage_corrupt")
        if row[1] != SERIALIZATION_VERSION:
            raise StorageError("unsupported_serialization_version")
        # Recognized version labels alone do not make missing tables usable.
        connection.execute(
            "SELECT seq, id, kind, analysis_run_id, schema_version, "
            "serialization_version, canonical_json, sha256 FROM records LIMIT 0"
        )
        connection.execute("SELECT record_id, sha256, byte_length FROM artifact_payloads LIMIT 0")
        connection.commit()
        return row[0]
    except Exception:
        connection.rollback()
        raise
