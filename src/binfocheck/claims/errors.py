"""Sanitized extraction failures; no provider payloads in error messages."""

from binfocheck.domain.common import ErrorDetail, Outcome


class ExtractionError(Exception):
    def __init__(self, code: str) -> None:
        self.detail = ErrorDetail(code=code, message=f"Extraction: {code}")
        super().__init__(code)


def require[T](outcome: Outcome[T]) -> T:
    if outcome.status != "succeeded" or outcome.value is None:
        raise ExtractionError("storage_or_input_failure")
    return outcome.value


def check(condition: bool, code: str = "invalid_extraction_input") -> None:
    if not condition:
        raise ExtractionError(code)
