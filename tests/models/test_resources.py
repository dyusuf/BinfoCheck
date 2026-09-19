import os
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from binfocheck.models.config import ModelCredentials
from binfocheck.models.errors import ModelError
from binfocheck.models.json import canonical, object_value, parse
from binfocheck.models.resources import check_schema, validate_output

from .helpers import FIXTURES


class SmokeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str


def test_smoke_schema_has_one_definition() -> None:
    raw = (FIXTURES / "resources/output.schema.json").read_bytes()
    assert parse(raw) == SmokeOutput.model_json_schema()
    validate_output(object_value(parse(raw)), {"text": "Grüße 🍎"})


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "array"},
        {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
        {"type": "object", "properties": {}, "required": [], "additionalProperties": True},
        {
            "type": "object",
            "properties": {"a": {"$ref": "https://example.com/schema"}},
            "required": ["a"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {"a": {"properties": {"b": {"$ref": "https://example.com/schema"}}}},
            "required": ["a"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "$id": "https://example.com",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    ],
)
def test_unsupported_schemas_fail_without_resolution(schema: object) -> None:
    with pytest.raises(ModelError, match="unsupported_output_schema"):
        check_schema(object_value(parse(canonical(schema))))


def test_local_defs_validate_and_recursion_rejected() -> None:
    schema = object_value(
        parse(
            canonical(
                {
                    "type": "object",
                    "properties": {"a": {"$ref": "#/$defs/value"}},
                    "required": ["a"],
                    "additionalProperties": False,
                    "$defs": {"value": {"type": "string"}},
                }
            )
        )
    )
    validate_output(schema, {"a": "ä"})
    schema["$defs"] = {"value": {"$ref": "#/$defs/value"}}
    with pytest.raises(ModelError, match="unsupported_output_schema"):
        check_schema(schema)


def test_dotenv_is_explicit_without_interpolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY=from-file\nTYPESAFE_API_KEY=literal-${OTHER_SECRET}\n")
    monkeypatch.setenv("OPENAI_API_KEY", "from-environment")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    assert (
        ModelCredentials.from_environment("openai", path).api_key.get_secret_value()
        == "from-environment"
    )
    assert (
        ModelCredentials.from_environment("jev", path).api_key.get_secret_value()
        == "literal-${OTHER_SECRET}"
    )
    monkeypatch.setenv("OPENAI_API_KEY", "")
    with pytest.raises(ModelError, match="credentials_missing"):
        ModelCredentials.from_environment("openai", path)
    assert "from-file" not in repr(ModelCredentials.from_environment("jev", path))
    os.environ.pop("TYPESAFE_API_KEY", None)
