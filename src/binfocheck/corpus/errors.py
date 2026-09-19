"""Sanitized typed boundary failures."""

from collections.abc import Callable
from functools import wraps

from binfocheck.domain.common import ErrorDetail, Outcome


class CorpusError(Exception):
    def __init__(self, code: str, detail: ErrorDetail | None = None) -> None:
        self.detail = detail or ErrorDetail(code=code, message=code.replace("_", " "))
        super().__init__(self.detail.message)


def require[T](outcome: Outcome[T]) -> T:
    if outcome.status != "succeeded" or outcome.value is None:
        raise CorpusError("storage_failed", outcome.error)
    return outcome.value


def check(condition: bool, code: str) -> None:
    if not condition:
        raise CorpusError(code)


def boundary[**P, T](fn: Callable[P, T]) -> Callable[P, Outcome[T]]:
    @wraps(fn)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> Outcome[T]:
        try:
            return Outcome(status="succeeded", value=fn(*args, **kwargs), error=None)
        except CorpusError as error:
            return Outcome(status="failed", value=None, error=error.detail)
        except (ValueError, TypeError, RecursionError):
            return Outcome(
                status="failed", value=None, error=CorpusError("invalid_corpus_input").detail
            )

    return wrapped
