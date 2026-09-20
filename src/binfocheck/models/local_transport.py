"""One authenticated loopback request to the explicitly provisioned vLLM server."""

import http.client
import time

from .config import MODELS, LocalAuthorization, LocalGenerationConfig, ModelAdapterConfig
from .errors import ModelError
from .json import digest
from .transport import ALLOWED_HEADERS, HttpResponse


class LocalVllmTransport:
    """Request-bound local authorization; no redirects, proxies, fallback or retries."""

    def __init__(
        self, api_key: str, authorization: LocalAuthorization, runtime_manifest: bytes
    ) -> None:
        self._api_key = api_key
        self._authorization = LocalAuthorization.model_validate_json(
            authorization.model_dump_json()
        )
        self.runtime_manifest = runtime_manifest
        self._used = False

    def check(self, config: ModelAdapterConfig, body: bytes, work_key: str) -> LocalAuthorization:
        if not isinstance(config, LocalGenerationConfig):
            raise ModelError("provider_mismatch")
        config = LocalGenerationConfig.model_validate_json(config.model_dump_json())
        approval = self._authorization
        if (
            approval.model != MODELS["vllm"]
            or approval.work_key != work_key
            or approval.request_sha256 != digest(body)
            or approval.runtime_manifest_sha256 != config.runtime_manifest_sha256
            or digest(self.runtime_manifest) != config.runtime_manifest_sha256
        ):
            raise ModelError("live_request_not_authorized")
        if self._used or config.budget.request_limit != 1:
            raise ModelError("request_limit_exhausted")
        if (
            not self._api_key
            or not self._api_key.isascii()
            or any(c.isspace() or ord(c) < 32 for c in self._api_key)
        ):
            raise ModelError("credentials_missing")
        if len(body) > config.max_request_bytes:
            raise ModelError("request_too_large")
        return approval

    def post(self, config: ModelAdapterConfig, body: bytes, work_key: str) -> HttpResponse:
        self.check(config, body, work_key)
        self._used = True
        deadline = time.monotonic() + config.budget.timeout_seconds
        connection = http.client.HTTPConnection(
            "127.0.0.1", 8004, timeout=config.budget.timeout_seconds
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
            connection.connect()
            remaining()
            dispatched = True
            connection.request(
                "POST",
                "/v1/chat/completions",
                body=body,
                headers={
                    "Authorization": "Bearer " + self._api_key,
                    "Content-Type": "application/json",
                    "Accept-Encoding": "identity",
                },
            )
            remaining()
            response = connection.getresponse()
            status = response.status
            headers = tuple(
                (k.lower(), v) for k, v in response.getheaders() if k.lower() in ALLOWED_HEADERS
            )
            if response.getheader("Content-Encoding", "identity") != "identity":
                raise ModelError("unsupported_content_encoding")
            expected_length = response.getheader("Content-Length")
            if expected_length is not None and not expected_length.isdigit():
                raise ModelError("invalid_content_length")
            while True:
                remaining()
                chunk = response.read1(min(65536, config.max_response_bytes + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
                if len(chunks) > config.max_response_bytes:
                    raise ModelError("response_too_large")
            if expected_length is not None and len(chunks) != int(expected_length):
                raise ModelError("response_incomplete")
            return HttpResponse(bytes(chunks), status, headers)
        except (OSError, http.client.HTTPException, ModelError) as caught:
            code = (
                caught.detail.code if isinstance(caught, ModelError) else "local_transport_failed"
            )
            return HttpResponse(
                bytes(chunks) if chunks else None,
                status,
                headers,
                complete=False,
                dispatched=dispatched,
                outcome_uncertain=dispatched,
                error=ModelError(code).detail,
            )
        finally:
            connection.close()
