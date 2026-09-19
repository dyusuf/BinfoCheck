import gzip
import hashlib
import json
import zlib
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr, ValidationError

from binfocheck.acquisition.config import (
    ENDPOINT,
    HOST,
    CapturePolicy,
    Credentials,
    LiveAuthorization,
    request_body,
)
from binfocheck.acquisition.errors import AcquisitionError
from binfocheck.acquisition.transport import HttpsTransport, decode_content

from .helpers import FIXTURE, request


def transport(body: bytes) -> HttpsTransport:
    return HttpsTransport(
        Credentials(login=SecretStr("test-login"), password=SecretStr("test-password")),
        LiveAuthorization(
            approval_reference="synthetic-test-only",
            request_sha256=hashlib.sha256(body).hexdigest(),
            cost_ceiling_usd=0.01,
            verified_request_price_usd=0.004,
        ),
    )


@pytest.mark.parametrize("encoding", ["identity", "gzip", "deflate"])
@pytest.mark.parametrize("chunked", [False, True])
def test_transport_preserves_decoded_bytes(encoding: str, chunked: bool) -> None:
    payload = FIXTURE.read_bytes()
    wire = gzip.compress(payload) if encoding == "gzip" else payload
    if encoding == "deflate":
        wire = zlib.compress(payload)
    response = MagicMock()
    response.status = 200
    response.chunked = chunked
    response.read.return_value = wire
    headers = {"Content-Length": str(len(wire)), "Content-Encoding": encoding}
    response.getheader.side_effect = headers.get
    response.getheaders.return_value = list(headers.items())
    body = request_body(request())
    adapter = transport(body)
    with patch("http.client.HTTPSConnection") as connection:
        connection.return_value.getresponse.return_value = response
        actual = adapter.post(body, CapturePolicy())
        assert actual.payload == payload
        connection.assert_called_once_with(HOST, timeout=60.0)
        call = connection.return_value.request.call_args
        assert call.args == ("POST", ENDPOINT)
        assert call.kwargs["body"] == body
        assert call.kwargs["headers"]["Authorization"].startswith("Basic ")
        connection.return_value.close.assert_called_once()
        with pytest.raises(AcquisitionError, match="request limit exhausted"):
            adapter.post(body, CapturePolicy())
        assert connection.call_count == 1


def test_uncertain_dispatch_never_retried() -> None:
    body = request_body(request())
    adapter = transport(body)
    with patch("http.client.HTTPSConnection") as connection:
        connection.return_value.request.side_effect = TimeoutError("secret internal details")
        with pytest.raises(AcquisitionError) as failure:
            adapter.post(body, CapturePolicy())
        assert failure.value.detail.code == "capture_outcome_uncertain"
        assert "secret" not in str(failure.value)
        with pytest.raises(AcquisitionError, match="request limit exhausted"):
            adapter.post(body, CapturePolicy())
        assert connection.call_count == 1


def test_live_guards_prevent_connection() -> None:
    body = request_body(request())
    credentials = Credentials(login=SecretStr("x"), password=SecretStr("y"))
    with patch("http.client.HTTPSConnection") as connection:
        with pytest.raises(AcquisitionError, match="live not authorized"):
            HttpsTransport(credentials).post(body, CapturePolicy())
        with pytest.raises(AcquisitionError, match="live request not authorized"):
            transport(body).post(b"different", CapturePolicy())
        with pytest.raises(AcquisitionError, match="request limit exhausted"):
            transport(body).post(body, CapturePolicy(request_limit=0))
        connection.assert_not_called()


@pytest.mark.parametrize(
    ("wire", "encoding", "limit", "code"),
    [
        (b"abcd", "identity", 3, "response_too_large"),
        (gzip.compress(b"x" * 100), "gzip", 10, "response_too_large"),
        (gzip.compress(b"abc")[:-2], "gzip", 100, "response_decode_failed"),
        (b"abc", "br", 100, "unsupported_content_encoding"),
    ],
)
def test_content_decoding_limits(wire: bytes, encoding: str, limit: int, code: str) -> None:
    with pytest.raises(AcquisitionError) as failure:
        decode_content(wire, encoding, limit)
    assert failure.value.detail.code == code


def test_request_configuration_and_secret_redaction() -> None:
    capture = request().model_copy(update={"query": "Äpfel + 10%"})
    task = json.loads(request_body(capture))[0]
    assert task["keyword"] == "Äpfel %2B 10%25"
    assert task["language_code"] == "de"
    assert task["device"] == "desktop"
    assert "test-password" not in repr(
        Credentials(login=SecretStr("test-login"), password=SecretStr("test-password"))
    )
    with pytest.raises(ValidationError):
        CapturePolicy.model_validate({"retry_limit": 1})
    with pytest.raises(ValidationError):
        CapturePolicy(request_limit=2)
    with pytest.raises(ValidationError):
        LiveAuthorization(
            approval_reference="test",
            request_sha256="0" * 64,
            cost_ceiling_usd=0.001,
            verified_request_price_usd=0.004,
        )
