from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr, ValidationError

from binfocheck.models.config import (
    HOSTS,
    MODELS,
    PATHS,
    LiveAuthorization,
    ModelAdapterConfig,
    ModelCredentials,
)
from binfocheck.models.errors import ModelError
from binfocheck.models.json import digest
from binfocheck.models.transport import FixedHttpsTransport

BODY = b'{"model":"jev-1.13.0"}'
KEY = digest(b"synthetic-work")
CONFIG = ModelAdapterConfig(provider="jev")


def transport() -> FixedHttpsTransport:
    return FixedHttpsTransport(
        ModelCredentials(api_key=SecretStr("synthetic-test-key")),
        LiveAuthorization(
            approval_reference="SYNTHETIC TEST ONLY; not live authorization",
            provider="jev",
            model=MODELS["jev"],
            endpoint="https://" + HOSTS["jev"] + PATHS["jev"],
            work_key=KEY,
            request_sha256=digest(BODY),
            cost_ceiling_usd=0.01,
            verified_upper_cost_usd=0.005,
            pricing_verification_reference="synthetic-test",
        ),
    )


def mock_response(chunks: list[bytes], status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.chunked = False
    response.read1.side_effect = chunks
    headers = {"Content-Length": str(sum(map(len, chunks))), "Content-Encoding": "identity"}
    response.getheader.side_effect = headers.get
    response.getheaders.return_value = [
        ("X-TypeSafe-Request-Id", "synthetic-id"),
        ("Set-Cookie", "secret-cookie"),
    ]
    return response


def test_direct_post_preserves_bytes_without_redirects_or_retries() -> None:
    with patch("http.client.HTTPSConnection") as connection:
        connection.return_value.getresponse.return_value = mock_response([b' {"a": 1}\n', b""], 301)
        adapter = transport()
        response = adapter.post(CONFIG, BODY, KEY)
        assert response.payload == b' {"a": 1}\n' and response.status == 301
        assert response.headers == (("x-typesafe-request-id", "synthetic-id"),)
        call = connection.return_value.request.call_args
        assert call.args == ("POST", "/v1/systemone")
        assert call.kwargs["body"] == BODY
        assert call.kwargs["headers"]["Accept-Encoding"] == "identity"
        connection.assert_called_once()
        connection.return_value.close.assert_called_once()
        with pytest.raises(ModelError, match="request_limit_exhausted"):
            adapter.post(CONFIG, BODY, KEY)


@pytest.mark.parametrize(
    "phase,dispatched", [("connect", False), ("request", True), ("getresponse", True)]
)
def test_timeout_consumes_authorization(phase: str, dispatched: bool) -> None:
    with patch("http.client.HTTPSConnection") as connection:
        getattr(connection.return_value, phase).side_effect = TimeoutError("secret details")
        adapter = transport()
        response = adapter.post(CONFIG, BODY, KEY)
        assert response.dispatched == dispatched
        assert response.outcome_uncertain == dispatched
        assert response.error is not None and "secret" not in response.error.message
        with pytest.raises(ModelError, match="request_limit_exhausted"):
            adapter.post(CONFIG, BODY, KEY)
        connection.assert_called_once()


def test_read_deadline_does_not_reset_and_preserves_prefix() -> None:
    with (
        patch("http.client.HTTPSConnection") as connection,
        patch("binfocheck.models.transport.time.monotonic", side_effect=[0, 1, 2, 3, 4, 61]),
    ):
        connection.return_value.getresponse.return_value = mock_response([b"partial", b"rest", b""])
        response = transport().post(CONFIG, BODY, KEY)
        assert response.payload == b"partial"
        assert response.complete is False and response.outcome_uncertain is True
        timeouts = [call.args[0] for call in connection.return_value.sock.settimeout.call_args_list]
        assert timeouts == sorted(timeouts, reverse=True)


@pytest.mark.parametrize("case", ["oversize", "encoding", "incomplete", "disconnect"])
def test_incomplete_and_unsupported_bytes_are_retained(case: str) -> None:
    with patch("http.client.HTTPSConnection") as connection:
        response = mock_response([b"raw bytes", b""])
        config = CONFIG
        if case == "oversize":
            config = CONFIG.model_copy(update={"max_response_bytes": 4})
        elif case == "encoding":
            response.getheader.side_effect = {"Content-Length": "9", "Content-Encoding": "gzip"}.get
        elif case == "incomplete":
            response.getheader.side_effect = {"Content-Length": "100"}.get
        elif case == "disconnect":
            response.read1.side_effect = [b"raw bytes", ConnectionError("private")]
        connection.return_value.getresponse.return_value = response
        result = transport().post(config, BODY, KEY)
        assert result.payload == b"raw bytes"
        assert result.error is not None and not result.complete


def test_guards_run_before_connection() -> None:
    with patch("http.client.HTTPSConnection") as connection:
        no_approval = FixedHttpsTransport(ModelCredentials(api_key=SecretStr("test-key")))
        with pytest.raises(ModelError, match="live_not_authorized"):
            no_approval.post(CONFIG, BODY, KEY)
        with pytest.raises(ModelError, match="live_request_not_authorized"):
            transport().post(CONFIG, b"different", KEY)
        with pytest.raises(ModelError, match="live_request_not_authorized"):
            transport().post(ModelAdapterConfig(provider="openai"), BODY, KEY)
        connection.assert_not_called()


@pytest.mark.parametrize(
    "field,value", [("retry_limit", 1), ("concurrency", 2), ("request_limit", 2)]
)
def test_nonzero_retries_and_parallel_budgets_rejected(field: str, value: int) -> None:
    raw = CONFIG.model_dump(mode="json")
    raw["budget"][field] = value
    with pytest.raises(ValidationError):
        ModelAdapterConfig.model_validate(raw)
