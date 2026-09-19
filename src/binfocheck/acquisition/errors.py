"""Sanitized acquisition failures; no provider text or credentials in messages."""

from collections.abc import Callable
from functools import wraps

from binfocheck.domain.common import ErrorDetail, Outcome


class AcquisitionError(Exception):
    def __init__(self, code: str, provider_request_id: str | None = None) -> None:
        self.detail = ErrorDetail(
            code=code, message=code.replace("_", " "), provider_request_id=provider_request_id
        )
        super().__init__(self.detail.message)


class PersistenceError(Exception):
    def __init__(self, detail: ErrorDetail) -> None:
        self.detail = detail
        super().__init__(detail.message)


def require[T](result: Outcome[T]) -> T:
    if result.status != "succeeded" or result.value is None:
        raise PersistenceError(
            result.error or ErrorDetail(code="storage_failed", message="storage failed")
        )
    return result.value


def boundary[**P, T](function: Callable[P, T]) -> Callable[P, Outcome[T]]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> Outcome[T]:
        try:
            return Outcome(status="succeeded", value=function(*args, **kwargs), error=None)
        except (AcquisitionError, PersistenceError) as error:
            return Outcome(status="failed", value=None, error=error.detail)
        except (ValueError, TypeError, RecursionError):
            return Outcome(
                status="failed", value=None, error=AcquisitionError("invalid_capture_input").detail
            )

    return wrapped


def status_error(code: int, *, http: bool = False) -> str | None:
    if code == (200 if http else 20000):
        return None
    if code in (401, 40100):
        return "authentication_failed"
    if code in (402, 403, 40104, 40200, 40201, 40203, 40204, 40207, 40208, 40210):
        return "provider_access_denied"
    if code in (429, 40202, 40205, 40206, 40209):
        return "rate_limited"
    if code == 40102:
        return "answer_absent"
    if code == 40106:
        return "response_incomplete"
    return "provider_failed"
