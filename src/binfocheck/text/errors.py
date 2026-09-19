"""Typed, sanitized failures at text-component boundaries."""

from collections.abc import Callable
from functools import wraps

from binfocheck.domain.common import ErrorDetail, Outcome


class TextError(Exception):
    def __init__(self, code: str, detail: ErrorDetail | None = None) -> None:
        self.detail = detail or ErrorDetail(code=code, message=code.replace("_", " "))
        super().__init__(self.detail.message)


def require[T](result: Outcome[T]) -> T:
    if result.status != "succeeded" or result.value is None:
        raise TextError("storage_failed", result.error)
    return result.value


def boundary[**P, T](function: Callable[P, T]) -> Callable[P, Outcome[T]]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> Outcome[T]:
        try:
            return Outcome(status="succeeded", value=function(*args, **kwargs), error=None)
        except TextError as error:
            return Outcome(status="failed", value=None, error=error.detail)
        except (ValueError, TypeError, RecursionError):
            return Outcome(
                status="failed", value=None, error=TextError("invalid_text_input").detail
            )

    return wrapped
