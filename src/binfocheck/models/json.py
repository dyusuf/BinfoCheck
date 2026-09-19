"""Canonical JSON without text normalization, coercion, or duplicate keys."""

import hashlib
import json
from typing import NoReturn

from pydantic import JsonValue, TypeAdapter

from .errors import ModelError

JSON_VALUE: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def _constant(value: str) -> NoReturn:
    raise ValueError("nonfinite")


def parse(data: bytes) -> JsonValue:
    try:
        value = JSON_VALUE.validate_python(
            json.loads(data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
        )
        canonical(value)  # Also rejects overflow such as 1e999 and unpaired surrogates.
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise ModelError("invalid_json") from None


def object_value(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ModelError("invalid_provider_response")
    return value


def text_value(value: JsonValue) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelError("invalid_provider_response")
    return value
