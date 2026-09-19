"""OpenAI Responses adapter. Validated JSON and raw provider bytes are separate outputs."""

from pydantic import JsonValue

from binfocheck.domain.common import Outcome
from binfocheck.domain.decisions import DecisionRecord
from binfocheck.domain.interfaces import GenerationRequest

from .errors import ModelError
from .json import object_value, parse, text_value
from .persistence import ModelAdapter
from .resources import validate_output


def generation_output(
    schema: dict[str, JsonValue], body: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    if body.get("status") != "completed" or body.get("error") is not None:
        raise ModelError("output_incomplete")
    output = body.get("output")
    if not isinstance(output, list) or len(output) != 1:
        raise ModelError("invalid_provider_response")
    message = object_value(output[0])
    if (
        message.get("type") != "message"
        or message.get("role") != "assistant"
        or message.get("status") != "completed"
    ):
        raise ModelError("invalid_provider_response")
    content = message.get("content")
    if not isinstance(content, list) or len(content) != 1:
        raise ModelError("invalid_provider_response")
    item = object_value(content[0])
    if item.get("type") == "refusal":
        raise ModelError("model_refusal")
    if item.get("type") != "output_text":
        raise ModelError("invalid_provider_response")
    value = object_value(parse(text_value(item.get("text")).encode("utf-8")))
    validate_output(schema, value)
    return value


class OpenAIGenerationModel(ModelAdapter):
    provider = "openai"

    def generate(self, request: GenerationRequest) -> Outcome[DecisionRecord]:
        return self.execute(request)
