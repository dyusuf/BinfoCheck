"""D04 implementation settings. Configuration is not live authorization."""

import os
from pathlib import Path
from typing import Annotated, Literal, Self

from dotenv import load_dotenv
from pydantic import Field, SecretStr, model_validator

from binfocheck.domain.common import Contract, Digest, NonEmpty, VersionRef
from binfocheck.domain.runs import Budget

Provider = Literal["jev", "openai", "vllm"]
QWEN_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
QWEN_MODEL = "Qwen/Qwen3-4B-Instruct-2507"
MODELS = {
    "jev": "jev-1.13.0",
    "openai": "gpt-4.1-mini-2025-04-14",
    "vllm": QWEN_MODEL + "@" + QWEN_REVISION,
}
HOSTS = {"jev": "api.typesafe.ai", "openai": "api.openai.com"}
PATHS = {"jev": "/v1/systemone", "openai": "/v1/responses"}
CONFIG_VERSION = VersionRef(name="t03-model-adapters", version="1")
LOCAL_CONFIG_VERSION = VersionRef(name="t04-vllm-generation", version="3")


class ModelAdapterConfig(Contract):
    version: Literal["1", "2", "3"] = "1"
    provider: Provider
    budget: Budget = Budget(
        request_limit=1,
        cost_limit=0.01,
        currency="USD",
        timeout_seconds=60.0,
        concurrency=1,
        retry_limit=0,
    )
    max_response_bytes: Annotated[int, Field(gt=0, le=2 * 1024 * 1024)] = 2 * 1024 * 1024
    max_request_bytes: Annotated[int, Field(gt=0, le=65536)] = 4096
    max_output_tokens: Annotated[int, Field(gt=0, le=512)] = 512

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if self.provider == "vllm" and type(self) is ModelAdapterConfig:
            raise ValueError("local_configuration_required")
        if self.provider != "vllm" and self.version != "1":
            raise ValueError("unsupported_model_config_version")
        b = self.budget
        if (
            b.request_limit not in (0, 1)
            or b.retry_limit != 0
            or b.concurrency != 1
            or b.currency != "USD"
            or b.timeout_seconds > 60
        ):
            raise ValueError("unsupported_model_budget")
        return self


class LocalGenerationConfig(ModelAdapterConfig):
    """Separate adapter format; legacy configuration bytes and work IDs stay unchanged."""

    version: Literal["1", "2", "3"] = "3"
    provider: Provider = "vllm"
    runtime_manifest_sha256: Digest
    server_version: Literal["0.10.2", "0.19.0"] = "0.19.0"
    model_revision: Literal["cdbee75f17c01a7cc42f958dc650907174af0554"] = QWEN_REVISION
    endpoint: Literal["http://127.0.0.1:8004/v1/chat/completions"] = (
        "http://127.0.0.1:8004/v1/chat/completions"
    )
    dtype: Literal["float16"] = "float16"
    engine: Literal["V0", "V1"] = "V1"
    attention_backend: Literal["XFORMERS", "XFORMERS_VLLM_V1", "TRITON_ATTN"] = "TRITON_ATTN"
    max_model_len: Literal[4096] = 4096
    budget: Budget = Budget(
        request_limit=1,
        cost_limit=0,
        currency="USD",
        timeout_seconds=60,
        concurrency=1,
        retry_limit=0,
    )

    @model_validator(mode="after")
    def local_budget(self) -> Self:
        expected = {
            "1": ("V0", "XFORMERS", "0.10.2"),
            "2": ("V1", "XFORMERS_VLLM_V1", "0.10.2"),
            "3": ("V1", "TRITON_ATTN", "0.19.0"),
        }
        if (self.engine, self.attention_backend, self.server_version) != expected[self.version]:
            raise ValueError("local_engine_version_mismatch")
        if self.provider != "vllm":
            raise ValueError("local_provider_required")
        if self.budget.cost_limit != 0:
            raise ValueError("local_provider_cost_must_be_zero")
        return self


AdapterConfig = LocalGenerationConfig | ModelAdapterConfig


def config_version(config: ModelAdapterConfig) -> VersionRef:
    if config.provider == "vllm":
        return VersionRef(name=LOCAL_CONFIG_VERSION.name, version=config.version)
    return CONFIG_VERSION


class LocalAuthorization(Contract):
    approval_reference: NonEmpty
    provider: Literal["vllm"] = "vllm"
    model: NonEmpty
    work_key: Digest
    request_sha256: Digest
    runtime_manifest_sha256: Digest
    cost_ceiling_usd: Literal[0] = 0


class ModelCredentials(Contract):
    api_key: SecretStr

    @classmethod
    def from_environment(cls, provider: Provider, dotenv_path: Path = Path(".env")) -> Self:
        from .errors import ModelError

        if provider == "vllm":
            raise ModelError("local_credentials_require_explicit_injection")
        load_dotenv(dotenv_path=dotenv_path, override=False, interpolate=False)
        key = os.environ.get("TYPESAFE_API_KEY" if provider == "jev" else "OPENAI_API_KEY", "")
        if not key.strip() or "\n" in key or "\r" in key:
            raise ModelError("credentials_missing")
        return cls(api_key=SecretStr(key))


class LiveAuthorization(Contract):
    """External approval must name this exact request. Never inferred from credentials."""

    approval_reference: NonEmpty
    provider: Provider
    model: NonEmpty
    endpoint: NonEmpty
    work_key: Digest
    request_sha256: Digest
    cost_ceiling_usd: Annotated[float, Field(gt=0, le=0.01)]
    verified_upper_cost_usd: Annotated[float, Field(ge=0)]
    pricing_verification_reference: NonEmpty

    @model_validator(mode="after")
    def price_fits(self) -> Self:
        if self.verified_upper_cost_usd > self.cost_ceiling_usd:
            raise ValueError("cost_ceiling_exceeded")
        return self
