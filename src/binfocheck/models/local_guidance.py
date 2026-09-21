"""Provider-only schema compatibility for the pinned xgrammar runtime."""

from pydantic import JsonValue


def xgrammar_schema(schema: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Copy a canonical schema and relax only xgrammar's broken ``\\S`` handling.

    xgrammar 0.2.3 compiles an unanchored ``pattern: "\\S"`` as effectively a
    one-character string grammar. ``minLength: 1`` preserves the useful guided
    constraint that the string is nonempty while allowing normal text. The
    canonical schema remains authoritative after generation, so whitespace-only
    strings still fail its unchanged ``\\S`` validation.
    """

    def transform(value: JsonValue) -> JsonValue:
        if isinstance(value, dict):
            result = {key: transform(child) for key, child in value.items()}
            if result.get("type") == "string" and result.get("pattern") == r"\S":
                del result["pattern"]
                result["minLength"] = 1
            return result
        if isinstance(value, list):
            return [transform(child) for child in value]
        return value

    result = transform(schema)
    assert isinstance(result, dict)
    return result
