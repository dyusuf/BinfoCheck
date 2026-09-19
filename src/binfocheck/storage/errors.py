"""Sanitized errors at the storage boundary; never include input or SQL text."""

import sqlite3
from collections.abc import Callable
from functools import wraps

from pydantic import ValidationError

from binfocheck.domain.common import ErrorDetail, Outcome


class StorageError(Exception):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        self.detail = ErrorDetail(code=code, message=code.replace("_", " "), retryable=retryable)
        super().__init__(self.detail.message)


class StorageInitializationError(StorageError):
    """Opening a backend failed before an Outcome-returning interface existed."""


def error_detail(error: Exception) -> ErrorDetail:
    if isinstance(error, StorageError):
        return error.detail
    if isinstance(error, sqlite3.Error):
        code = getattr(error, "sqlite_errorcode", 0) & 0xFF
        if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
            return StorageError("storage_busy", retryable=True).detail
        if code in (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB):
            return StorageError("storage_corrupt").detail
        return StorageError("storage_io_error").detail
    if isinstance(error, OSError):
        return StorageError("storage_io_error").detail
    return StorageError("invalid_record").detail


def outcome[**P, T](function: Callable[P, T]) -> Callable[P, Outcome[T]]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> Outcome[T]:
        try:
            return Outcome(status="succeeded", value=function(*args, **kwargs), error=None)
        except (StorageError, sqlite3.Error, OSError, ValueError, TypeError) as error:
            return Outcome(status="failed", value=None, error=error_detail(error))

    return wrapped


def payload_validation_error(error: ValidationError) -> StorageError:
    # Inspect only known validator tags; never expose Pydantic's input-bearing message.
    for item in error.errors(include_input=False, include_context=False):
        for code in ("invalid_artifact_base64", "artifact_hash_mismatch"):
            if code in item["msg"]:
                return StorageError(code)
    return StorageError("invalid_record")
