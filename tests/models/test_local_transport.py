from unittest.mock import patch

import pytest

from binfocheck.models.config import MODELS, LocalAuthorization, LocalGenerationConfig
from binfocheck.models.errors import ModelError
from binfocheck.models.json import digest
from binfocheck.models.local_transport import LocalVllmTransport

from .test_transport import mock_response

MANIFEST = b'{"synthetic":true}'
BODY = b'{"model":"synthetic-test-only"}'
KEY = digest(b"synthetic-local-work")
CONFIG = LocalGenerationConfig(runtime_manifest_sha256=digest(MANIFEST))


def transport() -> LocalVllmTransport:
    return LocalVllmTransport(
        "synthetic-key",
        LocalAuthorization(
            approval_reference="SYNTHETIC TEST ONLY",
            model=MODELS["vllm"],
            work_key=KEY,
            request_sha256=digest(BODY),
            runtime_manifest_sha256=digest(MANIFEST),
        ),
        MANIFEST,
    )


def test_loopback_only_no_redirect_or_retry_and_raw_preservation() -> None:
    with patch("http.client.HTTPConnection") as connection:
        connection.return_value.getresponse.return_value = mock_response([b" raw bytes ", b""], 301)
        adapter = transport()
        result = adapter.post(CONFIG, BODY, KEY)
        assert result.status == 301 and result.payload == b" raw bytes "
        assert result.headers == (("x-typesafe-request-id", "synthetic-id"),)
        connection.assert_called_once_with("127.0.0.1", 8004, timeout=60)
        assert connection.return_value.request.call_args.args == ("POST", "/v1/chat/completions")
        with pytest.raises(ModelError, match="request_limit_exhausted"):
            adapter.post(CONFIG, BODY, KEY)
        connection.return_value.close.assert_called_once()


@pytest.mark.parametrize(
    "phase,dispatched", [("connect", False), ("request", True), ("getresponse", True)]
)
def test_timeout_consumes_single_authorization(phase: str, dispatched: bool) -> None:
    with patch("http.client.HTTPConnection") as connection:
        getattr(connection.return_value, phase).side_effect = TimeoutError("secret details")
        adapter = transport()
        result = adapter.post(CONFIG, BODY, KEY)
        assert result.dispatched == dispatched and result.outcome_uncertain == dispatched
        assert result.error and "secret" not in result.error.message
        with pytest.raises(ModelError, match="request_limit_exhausted"):
            adapter.post(CONFIG, BODY, KEY)


def test_truncated_valid_json_is_not_complete() -> None:
    with patch("http.client.HTTPConnection") as connection:
        response = mock_response([b"{}", b""])
        response.getheader.side_effect = {
            "Content-Length": "10",
            "Content-Encoding": "identity",
        }.get
        connection.return_value.getresponse.return_value = response
        result = transport().post(CONFIG, BODY, KEY)
        assert result.payload == b"{}" and result.outcome_uncertain
        assert result.error and result.error.code == "response_incomplete"


def test_response_cap_preserves_failure_bytes() -> None:
    with patch("http.client.HTTPConnection") as connection:
        connection.return_value.getresponse.return_value = mock_response([b"0123456789", b""])
        config = CONFIG.model_copy(update={"max_response_bytes": 4})
        result = transport().post(config, BODY, KEY)
        assert result.error and result.error.code == "response_too_large"
        assert not result.complete and result.outcome_uncertain
