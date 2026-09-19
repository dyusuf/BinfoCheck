"""Sanitized adapter failures; never include provider text or exception reprs."""

from binfocheck.domain.common import ErrorDetail, Outcome
from binfocheck.domain.decisions import DecisionRecord


class ModelError(Exception):
    def __init__(self, code: str) -> None:
        self.detail = ErrorDetail(code=code, message="Model adapter operation failed: " + code)
        super().__init__(code)


def require[T](outcome: Outcome[T]) -> T:
    if outcome.status != "succeeded" or outcome.value is None:
        raise ModelError("storage_failure")
    return outcome.value


def failure(detail: ErrorDetail) -> Outcome[DecisionRecord]:
    return Outcome(status="failed", value=None, error=detail)
