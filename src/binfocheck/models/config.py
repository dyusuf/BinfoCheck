"""D04 implementation settings. Configuration is not live authorization."""

import os
from pathlib import Path
from typing import Annotated, Literal, Self

from dotenv import load_dotenv
from pydantic import Field, SecretStr, model_validator

from binfocheck.domain.common import Contract, Digest, NonEmpty, VersionRef
from binfocheck.domain.runs import Budget

Provider = Literal["jev", "openai"]
MODELS = {"jev": "jev-1.13.0", "openai": "gpt-4.1-mini-2025-04-14"}
HOSTS = {"jev": "api.typesafe.ai", "openai": "api.openai.com"}
PATHS = {"jev": "/v1/systemone", "openai": "/v1/responses"}
CONFIG_VERSION = VersionRef(name="t03-model-adapters", version="1")


class ModelAdapterConfig(Contract):
    version: Literal["1"] = "1"
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


class ModelCredentials(Contract):
    api_key: SecretStr

    @classmethod
    def from_environment(cls, provider: Provider, dotenv_path: Path = Path(".env")) -> Self:
        from .errors import ModelError

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
