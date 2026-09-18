import json
from pathlib import Path
from typing import Literal

from pydantic import JsonValue, TypeAdapter

from binfocheck.domain.common import Contract
from binfocheck.domain.records import RecordSet

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "contracts" / "v1"
JSON_OBJECT: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])


class ExpectedError(Contract):
    type: str
    contains: str | None


class RecordCase(Contract):
    kind: str
    valid: str
    invalid: str
    error: ExpectedError
    unavailable: str | None
    unavailable_not_applicable: str | None


class BoundaryCase(Contract):
    name: str
    valid: str
    invalid: str
    unavailable: str


class InvalidExchange(Contract):
    request: dict[str, JsonValue]
    response: dict[str, JsonValue]
    request_error: ExpectedError
    response_error: ExpectedError


def read_object(path: Path) -> dict[str, JsonValue]:
    return JSON_OBJECT.validate_json(path.read_bytes())


def linked() -> RecordSet:
    return RecordSet.model_validate_json((FIXTURES / "linked.json").read_bytes())


def replace_record(bundle: RecordSet, id: str, **changes: JsonValue) -> RecordSet:
    records: list[dict[str, JsonValue]] = []
    for record in bundle.records:
        data = JSON_OBJECT.validate_json(record.model_dump_json())
        if record.id == id:
            data.update(changes)
        records.append(data)
    return RecordSet.model_validate_json(json.dumps({"records": records}))


Variant = Literal["valid", "unavailable"]
