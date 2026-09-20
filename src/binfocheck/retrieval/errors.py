"""T07 failures carry codes and optional offending input IDs, never raw text."""

from binfocheck.domain.common import ErrorDetail, Outcome


class RetrievalError(Exception):
    def __init__(self, code: str, input_id: str | None = None) -> None:
        self.input_id = input_id
        self.detail = ErrorDetail(code=code, message=code + (": " + input_id if input_id else ""))
        super().__init__(self.detail.message)


def check(condition: bool, code: str, input_id: str | None = None) -> None:
    if not condition:
        raise RetrievalError(code, input_id)


def require[T](result: Outcome[T]) -> T:
    if result.status != "succeeded" or result.value is None:
        raise RetrievalError(result.error.code if result.error else "upstream_unavailable")
    return result.value
