"""Structured generation adapters keep validated JSON separate from raw provider bytes."""

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


def local_generation_output(
    schema: dict[str, JsonValue], body: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    """Validate the actual vLLM chat envelope; never manufacture a Responses envelope."""
    if body.get("error") is not None:
        raise ModelError("invalid_provider_response")
    choices = body.get("choices")
    if (
        body.get("object") != "chat.completion"
        or not isinstance(choices, list)
        or len(choices) != 1
    ):
        raise ModelError("invalid_provider_response")
    choice = object_value(choices[0])
    if choice.get("finish_reason") != "stop":
        raise ModelError("output_incomplete")
    if choice.get("index") != 0:
        raise ModelError("invalid_provider_response")
    message = object_value(choice.get("message"))
    if message.get("role") != "assistant" or message.get("tool_calls"):
        raise ModelError("invalid_provider_response")
    if message.get("refusal") or message.get("reasoning_content"):
        raise ModelError("model_refusal")
    value = object_value(parse(text_value(message.get("content")).encode("utf-8")))
    validate_output(schema, value)
    return value


class LocalVllmGenerationModel(ModelAdapter):
    provider = "vllm"

    def generate(self, request: GenerationRequest) -> Outcome[DecisionRecord]:
        return self.execute(request)
