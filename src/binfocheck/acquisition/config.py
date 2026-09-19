"""T01 settings only; proposed German defaults are not live authorization."""

import hashlib
import json
import os
from typing import Annotated, Literal, Self

from pydantic import Field, SecretStr, model_validator

from binfocheck.domain.common import Contract, Digest, NonEmpty
from binfocheck.domain.observations import CaptureRequest

from .errors import AcquisitionError

HOST = "api.dataforseo.com"
ENDPOINT = "/v3/serp/google/ai_mode/live/advanced"
NORMALIZATION_VERSION = "1"


class CaptureSettings(Contract):
    location_name: NonEmpty = "Germany"
    language_code: Literal["de"] = "de"
    device: Literal["desktop"] = "desktop"
    os: Literal["windows"] = "windows"
    calculate_rectangles: Literal[False] = False


class CapturePolicy(Contract):
    request_limit: Annotated[int, Field(ge=0, le=1)] = 1
    retry_limit: Literal[0] = 0
    timeout_seconds: Annotated[float, Field(gt=0, le=120)] = 60.0
    max_payload_bytes: Annotated[int, Field(gt=0, le=64 * 1024 * 1024)] = 16 * 1024 * 1024


class LiveAuthorization(Contract):
    """Explicit operator approval, bound to exact outbound bytes, not inferred from env."""

    approval_reference: NonEmpty
    request_sha256: Digest
    cost_ceiling_usd: Annotated[float, Field(gt=0)]
    verified_request_price_usd: Annotated[float, Field(gt=0)]

    @model_validator(mode="after")
    def price_fits(self) -> Self:
        if self.verified_request_price_usd > self.cost_ceiling_usd:
            raise ValueError("cost_ceiling_exceeded")
        return self


class Credentials(Contract):
    login: SecretStr
    password: SecretStr

    @classmethod
    def from_environment(cls) -> Self:
        login = os.environ.get("DATAFORSEO_LOGIN", "")
        password = os.environ.get("DATAFORSEO_PASSWORD", "")
        if not login or not password:
            raise AcquisitionError("credentials_missing")
        return cls(login=SecretStr(login), password=SecretStr(password))


def request_tag(request: CaptureRequest) -> str:
    return "capture-" + hashlib.sha256(request.id.encode()).hexdigest()


def request_body(request: CaptureRequest) -> bytes:
    request = CaptureRequest.model_validate_json(request.model_dump_json(warnings="error"))
    if not request.query.strip() or len(request.query) > 700:
        raise AcquisitionError("invalid_capture_query")
    # This allowlist rejects credentials, endpoints, and unapproved paid options.
    settings = CaptureSettings.model_validate(request.requested_settings.values)
    task = settings.model_dump(mode="json")
    task["keyword"] = request.query.replace("%", "%25").replace("+", "%2B")
    task["tag"] = request_tag(request)
    return json.dumps([task], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
