"""One fixed HTTPS POST, no redirects/retries. Bodies are content-decoded, not JSON-decoded."""

import base64
import hashlib
import http.client
import io
import zlib
from dataclasses import dataclass
from typing import Protocol

from .config import ENDPOINT, HOST, CapturePolicy, Credentials, LiveAuthorization
from .errors import AcquisitionError

ALLOWED_HEADERS = frozenset(
    {"content-type", "content-encoding", "date", "retry-after", "x-request-id"}
)


@dataclass(frozen=True)
class HttpResponse:
    payload: bytes
    status: int
    headers: tuple[tuple[str, str], ...] = ()


class Transport(Protocol):
    def post(self, body: bytes, policy: CapturePolicy) -> HttpResponse: ...


def allowed_headers(headers: tuple[tuple[str, str], ...]) -> dict[str, str]:
    return {name.lower(): value for name, value in headers if name.lower() in ALLOWED_HEADERS}


def decode_content(wire_body: bytes, encoding: str, limit: int) -> bytes:
    """http.client removes HTTP transfer framing; decode supported content codings here."""
    if encoding in ("", "identity"):
        decoded = wire_body
    elif encoding in ("gzip", "deflate"):
        decoder = zlib.decompressobj(31 if encoding == "gzip" else zlib.MAX_WBITS)
        decoded = decoder.decompress(wire_body, limit + 1)
        if len(decoded) > limit or decoder.unconsumed_tail:
            raise AcquisitionError("response_too_large")
        if not decoder.eof or decoder.unused_data:
            raise AcquisitionError("response_decode_failed")
    else:
        raise AcquisitionError("unsupported_content_encoding")
    if len(decoded) > limit:
        raise AcquisitionError("response_too_large")
    return decoded


class HttpsTransport:
    """Constructing this class does not authorize spending; an explicit approval is required."""

    def __init__(
        self, credentials: Credentials, authorization: LiveAuthorization | None = None
    ) -> None:
        self._credentials = credentials
        self._authorization = authorization
        self._used = False

    def post(self, body: bytes, policy: CapturePolicy) -> HttpResponse:
        policy = CapturePolicy.model_validate_json(policy.model_dump_json())
        if self._authorization is None:
            raise AcquisitionError("live_not_authorized")
        authorization = LiveAuthorization.model_validate_json(self._authorization.model_dump_json())
        if hashlib.sha256(body).hexdigest() != authorization.request_sha256:
            raise AcquisitionError("live_request_not_authorized")
        if self._used or policy.request_limit != 1:
            raise AcquisitionError("request_limit_exhausted")
        login = self._credentials.login.get_secret_value()
        password = self._credentials.password.get_secret_value()
        if not login or not password or ":" in login:
            raise AcquisitionError("credentials_missing")
        token = base64.b64encode(f"{login}:{password}".encode()).decode()
        self._used = True  # Every possible dispatch consumes the single attempt, even on failure.
        connection = http.client.HTTPSConnection(HOST, timeout=policy.timeout_seconds)
        try:
            connection.request(
                "POST",
                ENDPOINT,
                body=body,
                headers={
                    "Authorization": "Basic " + token,
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip, deflate",
                },
            )
            response = connection.getresponse()
            headers = tuple(response.getheaders())
            # Read through a bounded buffer, including when Content-Length is absent.
            wire = response.read(policy.max_payload_bytes + 1)
            if len(wire) > policy.max_payload_bytes:
                raise AcquisitionError("response_too_large")
            length = response.getheader("Content-Length")
            if length is not None and not response.chunked and len(wire) != int(length):
                raise AcquisitionError("response_incomplete")
            payload = decode_content(
                wire, response.getheader("Content-Encoding", "").lower(), policy.max_payload_bytes
            )
            return HttpResponse(payload=payload, status=response.status, headers=headers)
        except (OSError, http.client.HTTPException):
            raise AcquisitionError("capture_outcome_uncertain") from None
        except (ValueError, zlib.error, io.UnsupportedOperation):
            raise AcquisitionError("response_decode_failed") from None
        finally:
            connection.close()
