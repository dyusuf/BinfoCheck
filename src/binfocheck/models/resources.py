"""Explicit trusted resource registry; no business selection or remote resolution."""

from collections.abc import Mapping
from typing import Protocol, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from jsonschema.protocols import Validator
from pydantic import JsonValue

from binfocheck.domain.common import VersionRef

from .errors import ModelError
from .json import canonical, digest, object_value, parse


class ModelResources(Protocol):
    def resolve(self, reference: VersionRef) -> bytes: ...


class ResourceRegistry:
    def __init__(self, resources: Mapping[tuple[str, str], bytes]) -> None:
        self._resources = dict(resources)

    def resolve(self, reference: VersionRef) -> bytes:
        value = self._resources.get((reference.name, reference.version))
        if value is None:
            raise ModelError("resource_missing")
        if reference.sha256 is not None and digest(value) != reference.sha256:
            raise ModelError("resource_hash_mismatch")
        return value


def resolve(resources: ModelResources, reference: VersionRef | None) -> bytes:
    if reference is None:
        raise ModelError("resource_missing")
    value = resources.resolve(reference)
    if reference.sha256 is not None and digest(value) != reference.sha256:
        raise ModelError("resource_hash_mismatch")
    return value


def check_schema(schema: dict[str, JsonValue]) -> None:
    """Conservative supported subset, rejected rather than silently rewritten.

    No $id/anchors or remote references; jsonschema can only resolve local $defs.
    Recursive schemas and complex composition are intentionally unsupported in v1.
    """
    allowed = {
        "$schema",
        "$defs",
        "$ref",
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "const",
        "anyOf",
        "description",
        "title",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minItems",
        "maxItems",
        "pattern",
    }
    if schema.get("type") != "object" or "anyOf" in schema:
        raise ModelError("unsupported_output_schema")
    if "$schema" in schema and schema["$schema"] != "https://json-schema.org/draft/2020-12/schema":
        raise ModelError("unsupported_output_schema")

    def visit(node: JsonValue, depth: int, refs: tuple[str, ...] = ()) -> None:
        if not isinstance(node, dict) or depth > 10 or not set(node).issubset(allowed):
            raise ModelError("unsupported_output_schema")
        if "$ref" in node:
            if not set(node).issubset({"$ref", "description", "title"}):
                raise ModelError("unsupported_output_schema")
            ref = node["$ref"]
            definitions = object_value(schema.get("$defs", {}))
            if (
                not isinstance(ref, str)
                or not ref.startswith("#/$defs/")
                or ref in refs
                or ref[8:] not in definitions
            ):
                raise ModelError("unsupported_output_schema")
            visit(definitions[ref[8:]], depth, (*refs, ref))
        kind = node.get("type")
        if kind is None and "$ref" not in node and "anyOf" not in node:
            raise ModelError("unsupported_output_schema")
        is_object = kind == "object" or isinstance(kind, list) and "object" in kind
        is_array = kind == "array" or isinstance(kind, list) and "array" in kind
        if (
            not is_object
            and set(node).intersection({"properties", "required", "additionalProperties"})
            or not is_array
            and "items" in node
        ):
            raise ModelError("unsupported_output_schema")
        if kind == "object" or isinstance(kind, list) and "object" in kind:
            properties = node.get("properties")
            required = node.get("required")
            if (
                not isinstance(properties, dict)
                or not isinstance(required, list)
                or not all(isinstance(k, str) for k in required)
                or set(required) != set(properties)
                or len(required) != len(properties)
                or node.get("additionalProperties") is not False
            ):
                raise ModelError("unsupported_output_schema")
            for child in properties.values():
                visit(child, depth + 1, refs)
        if kind == "array" or isinstance(kind, list) and "array" in kind:
            visit(node.get("items"), depth + 1, refs)
        if "anyOf" in node:
            choices = node["anyOf"]
            if not isinstance(choices, list) or not choices:
                raise ModelError("unsupported_output_schema")
            for child in choices:
                visit(child, depth, refs)
        if "$defs" in node:
            for child in object_value(node["$defs"]).values():
                visit(child, depth, refs)

    try:
        Draft202012Validator.check_schema(schema)
        visit(schema, 1)
    except (SchemaError, TypeError, RecursionError):
        raise ModelError("unsupported_output_schema") from None


def validate_output(schema: dict[str, JsonValue], value: dict[str, JsonValue]) -> None:
    check_schema(schema)
    try:
        validator = cast(Validator, Draft202012Validator(schema))
        error = next(validator.iter_errors(value), None)
        if error is not None:
            raise error
    except ValidationError:
        raise ModelError("schema_validation_failed") from None


def schema_resource(raw: bytes) -> dict[str, JsonValue]:
    schema = object_value(parse(raw))
    check_schema(schema)
    canonical(schema)
    return schema
