"""Failures are distinct from uncertain citation evidence; messages omit raw input."""

from binfocheck.domain.common import ErrorDetail, Outcome


class CitationError(Exception):
    def __init__(self, code: str, detail: ErrorDetail | None = None) -> None:
        self.detail = detail or ErrorDetail(code=code, message=code.replace("_", " "))
        super().__init__(self.detail.message)


def check(condition: bool, code: str) -> None:
    if not condition:
        raise CitationError(code)


def require[T](result: Outcome[T]) -> T:
    if result.status != "succeeded" or result.value is None:
        raise CitationError("storage_failed", result.error)
    return result.value
