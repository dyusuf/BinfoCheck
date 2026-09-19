"""Opaque continuation state, deliberately not an authentication mechanism."""

import base64

from pydantic import Field, ValidationError

from binfocheck.domain.common import Contract
from binfocheck.domain.storage import ListRequest

from .errors import StorageError


class Cursor(Contract):
    version: int = Field(ge=1, le=1)
    store: str
    kind: str | None
    run: str | None
    after: int = Field(gt=0)
    through: int = Field(gt=0)

    def token(self) -> str:
        return base64.urlsafe_b64encode(self.model_dump_json().encode()).decode()


def read_cursor(request: ListRequest, store_id: str, maximum: int) -> tuple[int, int]:
    if request.cursor is None:
        return 0, maximum
    try:
        if len(request.cursor) > 8192:
            raise ValueError("oversized")
        data = base64.b64decode(request.cursor, altchars=b"-_", validate=True)
        cursor = Cursor.model_validate_json(data)
        if (
            cursor.store != store_id
            or cursor.kind != request.record_kind
            or cursor.run != request.analysis_run_id
            or not cursor.after <= cursor.through <= maximum
        ):
            raise ValueError("incompatible")
        return cursor.after, cursor.through
    except (ValueError, ValidationError) as error:
        raise StorageError("invalid_cursor") from error


def next_cursor(request: ListRequest, store_id: str, after: int, through: int) -> str:
    return Cursor(
        version=1,
        store=store_id,
        kind=request.record_kind,
        run=request.analysis_run_id,
        after=after,
        through=through,
    ).token()
