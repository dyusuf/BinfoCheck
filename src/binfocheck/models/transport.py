"""One direct HTTPS POST. No SDK, redirect, retry, proxy, or fallback machinery."""

import http.client
import ssl
import time
from dataclasses import dataclass
from typing import Protocol

from binfocheck.domain.common import ErrorDetail

from .config import HOSTS, MODELS, PATHS, LiveAuthorization, ModelAdapterConfig, ModelCredentials
from .errors import ModelError
from .json import digest

ALLOWED_HEADERS = frozenset(
    {
        "content-type",
        "content-encoding",
        "date",
        "retry-after",
        "retry-after-ms",
        "x-request-id",
        "x-typesafe-request-id",
        "openai-processing-ms",
    }
)


@dataclass(frozen=True)
class HttpResponse:
    payload: bytes | None
    status: int | None
    headers: tuple[tuple[str, str], ...] = ()
    complete: bool = True
    dispatched: bool = True
    outcome_uncertain: bool = False
    error: ErrorDetail | None = None


class ModelTransport(Protocol):
    def check(
        self, config: ModelAdapterConfig, body: bytes, work_key: str
    ) -> LiveAuthorization | None: ...
    def post(self, config: ModelAdapterConfig, body: bytes, work_key: str) -> HttpResponse: ...


class FixedHttpsTransport:
    def __init__(
        self, credentials: ModelCredentials, authorization: LiveAuthorization | None = None
    ) -> None:
        self._credentials = credentials
        self._authorization = authorization
        self._used = False

    def check(self, config: ModelAdapterConfig, body: bytes, work_key: str) -> LiveAuthorization:
        config = ModelAdapterConfig.model_validate_json(config.model_dump_json())
        approval = self._authorization
        if approval is None:
            raise ModelError("live_not_authorized")
        approval = LiveAuthorization.model_validate_json(approval.model_dump_json())
        provider = config.provider
        endpoint = "https://" + HOSTS[provider] + PATHS[provider]
        if (
            approval.provider != provider
            or approval.model != MODELS[provider]
            or approval.endpoint != endpoint
            or approval.work_key != work_key
            or approval.request_sha256 != digest(body)
        ):
            raise ModelError("live_request_not_authorized")
        if self._used or config.budget.request_limit != 1:
            raise ModelError("request_limit_exhausted")
        if (
            approval.cost_ceiling_usd > config.budget.cost_limit
            or approval.verified_upper_cost_usd > config.budget.cost_limit
        ):
            raise ModelError("cost_ceiling_exceeded")
        key = self._credentials.api_key.get_secret_value()
        if not key.strip() or not key.isascii() or "\r" in key or "\n" in key:
            raise ModelError("credentials_missing")
        if len(body) > config.max_request_bytes:
            raise ModelError("request_too_large")
        return approval

    def post(self, config: ModelAdapterConfig, body: bytes, work_key: str) -> HttpResponse:
        self.check(config, body, work_key)
        self._used = True  # A transport authorization is single-use even on connect failure.
        deadline = time.monotonic() + config.budget.timeout_seconds
        connection = http.client.HTTPSConnection(
            HOSTS[config.provider],
            timeout=config.budget.timeout_seconds,
            context=ssl.create_default_context(),
        )
        dispatched = False
        status: int | None = None
        headers: tuple[tuple[str, str], ...] = ()
        chunks = bytearray()

        def remaining() -> None:
            seconds = deadline - time.monotonic()
            if seconds <= 0:
                raise TimeoutError
            connection.timeout = seconds
            if connection.sock is not None:
                connection.sock.settimeout(seconds)

        try:
            remaining()
            connection.connect()
            remaining()
            dispatched = True  # Conservative before the first possible application write.
            connection.request(
                "POST",
                PATHS[config.provider],
                body=body,
                headers={
                    "Authorization": "Bearer " + self._credentials.api_key.get_secret_value(),
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                    **({"X-Client-Request-Id": work_key} if config.provider == "openai" else {}),
                },
            )
            remaining()
            response = connection.getresponse()
            status = response.status
            headers = tuple(
                (name.lower(), value)
                for name, value in response.getheaders()
                if name.lower() in ALLOWED_HEADERS
            )
            while True:
                remaining()
                chunk = response.read1(min(65536, config.max_response_bytes + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
                if len(chunks) > config.max_response_bytes:
                    raise ModelError("response_too_large")
            remaining()
            length = response.getheader("Content-Length")
            if length is not None and not response.chunked and len(chunks) != int(length):
                raise ModelError("response_incomplete")
            if response.getheader("Content-Encoding", "identity").lower() not in ("", "identity"):
                raise ModelError("unsupported_content_encoding")
            return HttpResponse(bytes(chunks), status, headers)
        except (OSError, http.client.HTTPException, ValueError, ModelError) as error:
            code = (
                error.detail.code
                if isinstance(error, ModelError)
                else ("dispatch_outcome_uncertain" if dispatched else "connection_failed")
            )
            return HttpResponse(
                bytes(chunks) if status is not None else None,
                status,
                headers,
                complete=False,
                dispatched=dispatched,
                outcome_uncertain=dispatched,
                error=ModelError(code).detail,
            )
        finally:
            connection.close()
