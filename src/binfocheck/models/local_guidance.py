"""Provider-only schema guidance for the pinned xgrammar runtime."""

from pydantic import JsonValue

from .errors import ModelError


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


def decomposition_schema(schema: dict[str, JsonValue], state: JsonValue) -> dict[str, JsonValue]:
    """Expose canonical decomposition invariants to guided decoding.

    Pydantic model validators and source-location checks are intentionally still
    authoritative after generation. This schema copy prevents xgrammar from
    guiding the model into combinations those validators must reject. Offsets are
    omitted as ``null`` so code locates each verbatim quote in immutable source
    text; generated numeric offsets cannot disagree with the quote.
    """
    guided = xgrammar_schema(schema)
    if guided.get("title") != "Decomposed":
        return guided
    if not isinstance(state, dict):
        raise ModelError("local_guidance_unavailable")
    source = state.get("source")
    if not isinstance(source, dict):
        raise ModelError("local_guidance_unavailable")
    unit_ids = source.get("unit_ids")
    if (
        not isinstance(unit_ids, list)
        or not unit_ids
        or any(not isinstance(unit_id, str) or not unit_id for unit_id in unit_ids)
        or len(set(unit_ids)) != len(unit_ids)
    ):
        raise ModelError("local_guidance_unavailable")

    definitions = guided.get("$defs")
    if not isinstance(definitions, dict):
        raise ModelError("local_guidance_unavailable")
    anchor = definitions.get("Anchor")
    if not isinstance(anchor, dict):
        raise ModelError("local_guidance_unavailable")
    anchor_properties = anchor.get("properties")
    if not isinstance(anchor_properties, dict):
        raise ModelError("local_guidance_unavailable")
    anchor_properties["start"] = {"const": None, "type": "null"}
    anchor_properties["end"] = {"const": None, "type": "null"}
    source_ids = anchor_properties.get("source_unit_ids")
    if not isinstance(source_ids, dict):
        raise ModelError("local_guidance_unavailable")
    source_ids["items"] = {"enum": unit_ids, "type": "string"}

    root_properties = guided.get("properties")
    if not isinstance(root_properties, dict):
        raise ModelError("local_guidance_unavailable")
    candidates = root_properties.get("candidates")
    if not isinstance(candidates, dict):
        raise ModelError("local_guidance_unavailable")
    candidate_items = candidates.get("items")
    if not isinstance(candidate_items, dict):
        raise ModelError("local_guidance_unavailable")

    common: dict[str, JsonValue] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "candidates", "reason_code"],
    }
    guided.pop("properties", None)
    guided.pop("required", None)
    guided.pop("additionalProperties", None)
    resolved_branch: dict[str, JsonValue] = {
        **common,
        "properties": {
            "status": {"const": "candidates", "type": "string"},
            "candidates": {
                "type": "array",
                "items": candidate_items,
                "minItems": 1,
                "maxItems": 4,
            },
            "reason_code": {"const": "none", "type": "string"},
        },
    }
    unresolved_branch: dict[str, JsonValue] = {
        **common,
        "properties": {
            "status": {"const": "unresolved", "type": "string"},
            "candidates": {
                "type": "array",
                "items": candidate_items,
                "maxItems": 0,
            },
            "reason_code": {
                "enum": ["cannot_extract", "candidate_limit"],
                "type": "string",
            },
        },
    }
    guided["anyOf"] = [resolved_branch, unresolved_branch]
    return guided
