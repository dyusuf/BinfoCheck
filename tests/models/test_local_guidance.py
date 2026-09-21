"""The local guidance schema is weaker only where xgrammar needs compatibility."""

import base64
import json
from pathlib import Path

import pytest
from pydantic import JsonValue

from binfocheck.domain.common import Settings, VersionRef
from binfocheck.models import LocalVllmGenerationModel
from binfocheck.models.config import LocalGenerationConfig, config_version
from binfocheck.models.errors import ModelError
from binfocheck.models.generation import local_generation_output
from binfocheck.models.json import canonical, digest, object_value, parse
from binfocheck.models.local_guidance import xgrammar_schema
from binfocheck.models.persistence import prepare
from binfocheck.models.resources import ResourceRegistry
from binfocheck.models.transport import HttpResponse
from binfocheck.storage import MemoryStore

from .helpers import FIXTURES
from .test_local_generation import MANIFEST, LocalDouble, setup

SCHEMA_PATH = Path("prompts/extraction/v1/decompose.output.schema.json")


def canonical_schema() -> dict[str, JsonValue]:
    return object_value(parse(SCHEMA_PATH.read_bytes()))


def extraction_registry() -> ResourceRegistry:
    raw_schema = SCHEMA_PATH.read_bytes()
    return ResourceRegistry(
        {
            ("t03-smoke-prompt", "1"): (FIXTURES / "resources/prompt.txt").read_bytes(),
            ("t04-decompose-output", "1"): raw_schema,
        }
    )


def candidate(claim: str, quote: str) -> dict[str, JsonValue]:
    return {
        "status": "candidates",
        "candidates": [
            {
                "normalized_claim": claim,
                "anchor": {
                    "quote": quote,
                    "source_unit_ids": ["unit-1"],
                    "start": 0,
                    "end": len(quote),
                },
                "required_support": [],
                "consumed_binding_indices": [],
            }
        ],
        "reason_code": "none",
    }


def envelope(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    from binfocheck.models.config import MODELS

    return {
        "id": "synthetic-guidance-response",
        "model": MODELS["vllm"],
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(value)},
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def test_guidance_copy_replaces_only_nonblank_patterns() -> None:
    schema = canonical_schema()
    guidance = xgrammar_schema(schema)

    definitions = object_value(schema["$defs"])
    guided_definitions = object_value(guidance["$defs"])
    anchor = object_value(definitions["Anchor"])
    guided_anchor = object_value(guided_definitions["Anchor"])
    candidate_definition = object_value(definitions["Candidate"])
    guided_candidate = object_value(guided_definitions["Candidate"])
    anchor_properties = object_value(anchor["properties"])
    guided_anchor_properties = object_value(guided_anchor["properties"])
    candidate_properties = object_value(candidate_definition["properties"])
    guided_candidate_properties = object_value(guided_candidate["properties"])
    assert anchor_properties["quote"] == {
        "pattern": r"\S",
        "title": "Quote",
        "type": "string",
    }
    assert guided_anchor_properties["quote"] == {
        "minLength": 1,
        "title": "Quote",
        "type": "string",
    }
    assert object_value(candidate_properties["normalized_claim"])["pattern"] == r"\S"
    assert object_value(guided_candidate_properties["normalized_claim"])["minLength"] == 1
    assert guided_anchor_properties["source_unit_ids"] == anchor_properties["source_unit_ids"]


def test_v4_prepares_compatible_wire_schema_but_retains_canonical_resource() -> None:
    raw_schema = SCHEMA_PATH.read_bytes()
    registry = extraction_registry()
    with MemoryStore() as store:
        request, config = setup(store)
        request = request.model_copy(
            update={
                "output_schema": VersionRef(
                    name="t04-decompose-output", version="1", sha256=digest(raw_schema)
                )
            }
        )
        prepared = prepare(request, config, registry, store)
        response_format = object_value(prepared.body["response_format"])
        json_schema = object_value(response_format["json_schema"])
        assert json_schema["schema"] == xgrammar_schema(canonical_schema())
        assert base64.b64decode(prepared.resource_bytes_base64["schema"]) == raw_schema

        historical = LocalGenerationConfig(
            version="3",
            runtime_manifest_sha256=digest(MANIFEST),
        )
        historical_request = request.model_copy(
            update={
                "settings": Settings(
                    version=config_version(historical), values=request.settings.values
                )
            }
        )
        historical_prepared = prepare(historical_request, historical, registry, store)
        historical_format = object_value(historical_prepared.body["response_format"])
        historical_json_schema = object_value(historical_format["json_schema"])
        assert historical_json_schema["schema"] == canonical_schema()
        assert historical_prepared.work_key != prepared.work_key


def test_adapter_validates_guided_output_against_canonical_schema() -> None:
    raw_schema = SCHEMA_PATH.read_bytes()
    with MemoryStore() as store:
        request, config = setup(store)
        request = request.model_copy(
            update={
                "output_schema": VersionRef(
                    name="t04-decompose-output", version="1", sha256=digest(raw_schema)
                )
            }
        )
        value = candidate("   ", "Zitat")
        transport = LocalDouble(HttpResponse(canonical(envelope(value)), 200))
        result = LocalVllmGenerationModel(
            store, store, extraction_registry(), config, transport
        ).generate(request)
        assert result.error and result.error.code == "schema_validation_failed"
        sent = object_value(parse(transport.calls[0]))
        response_format = object_value(sent["response_format"])
        guided = object_value(response_format["json_schema"])
        assert guided["schema"] == xgrammar_schema(canonical_schema())


@pytest.mark.parametrize(
    "claim,quote",
    [
        ("S", "J"),
        ("Menschen mit Diabetes dürfen grundsätzlich Auto fahren.", "grundsätzlich"),
        ("Ja, grundsätzlich dürfen Sie mit Diabetes Auto fahren.", "Ja, grundsätzlich"),
    ],
)
def test_canonical_validation_accepts_realistic_guided_values(claim: str, quote: str) -> None:
    schema = canonical_schema()
    value = candidate(claim, quote)
    assert local_generation_output(schema, envelope(value)) == value


@pytest.mark.parametrize("field", ["normalized_claim", "quote"])
@pytest.mark.parametrize("text", ["", " ", "\t\n"])
def test_canonical_validation_still_rejects_blank_or_whitespace(field: str, text: str) -> None:
    schema = canonical_schema()
    value = candidate("Behauptung", "Zitat")
    candidates = value["candidates"]
    assert isinstance(candidates, list)
    first = object_value(candidates[0])
    if field == "normalized_claim":
        first[field] = text
    else:
        object_value(first["anchor"])[field] = text
    with pytest.raises(ModelError, match="schema_validation_failed"):
        local_generation_output(schema, envelope(value))


def test_canonical_validation_still_rejects_malformed_structure() -> None:
    schema = canonical_schema()
    value = candidate("Vollständige Behauptung.", "Zitat")
    del value["reason_code"]
    with pytest.raises(ModelError, match="schema_validation_failed"):
        local_generation_output(schema, envelope(value))
