"""Pre-live approval binding: no network or storage writes on stale authorization."""

from typing import NoReturn

import pytest

from binfocheck.corpus import capture as capture_module
from binfocheck.corpus import transport as transport_module
from binfocheck.corpus.artifacts import Store
from binfocheck.corpus.capture import SnapshotCapture
from binfocheck.corpus.config import POLICY, ROBOTS, URLS, FetchPolicy, capture_policy_sha256
from binfocheck.corpus.errors import CorpusError, require
from binfocheck.corpus.transport import HttpsTransport, LiveAuthorization
from binfocheck.domain.storage import ListRequest
from binfocheck.storage import MemoryStore

from .test_transport import Connection, wire


def no_connection(*args: object, **kwargs: object) -> NoReturn:
    raise AssertionError("authorization rejection must precede connection construction")


@pytest.mark.parametrize("field", tuple(FetchPolicy.model_fields))
def test_every_policy_field_is_bound(field: str) -> None:
    original = capture_policy_sha256(ROBOTS, URLS, POLICY)
    value = POLICY.model_dump()[field]
    changed = value + 1 if isinstance(value, int) else str(value) + "-changed"
    # Simulate a future policy revision, rather than relaxing the frozen policy's validation.
    future_policy = POLICY.model_copy(update={field: changed})
    assert capture_policy_sha256(ROBOTS, URLS, future_policy) != original


def test_url_membership_and_order_are_bound() -> None:
    original = capture_policy_sha256(ROBOTS, URLS, POLICY)
    assert capture_policy_sha256(ROBOTS + "?changed=1", URLS, POLICY) != original
    assert capture_policy_sha256(ROBOTS, URLS[::-1], POLICY) != original
    for index in range(len(URLS)):
        changed = tuple(url + "?changed=1" if i == index else url for i, url in enumerate(URLS))
        assert capture_policy_sha256(ROBOTS, changed, POLICY) != original
    assert capture_policy_sha256(ROBOTS, URLS[:-1], POLICY) != original


@pytest.mark.parametrize("entrypoint", ["capture", "transport"])
@pytest.mark.parametrize("change", ["robots", "pages", "policy", "empty", "malformed", "wrong"])
def test_stale_approval_rejected_before_side_effects(
    entrypoint: str, change: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    approved_digest = capture_policy_sha256(ROBOTS, URLS, POLICY)
    supplied_digest = {"empty": "", "malformed": "not-a-sha256", "wrong": "0" * 64}.get(
        change, approved_digest
    )
    authorization = LiveAuthorization("synthetic approval only", "test", supplied_digest)
    transport = HttpsTransport(authorization)
    target = capture_module if entrypoint == "capture" else transport_module
    if change == "robots":
        monkeypatch.setattr(target, "ROBOTS", ROBOTS + "?changed=1")
    elif change == "pages":
        monkeypatch.setattr(target, "URLS", URLS[::-1])
    elif change == "policy":
        monkeypatch.setattr(target, "POLICY", POLICY.model_copy(update={"request_limit": 7}))
    monkeypatch.setattr(transport_module.http.client, "HTTPSConnection", no_connection)
    with MemoryStore() as backend:
        if entrypoint == "capture":
            result = SnapshotCapture(Store(backend, backend), transport).capture("test", "live")
            assert result.error and result.error.code == "live_policy_not_authorized"
        else:
            with pytest.raises(CorpusError, match="live policy not authorized"):
                transport.get(URLS[0], POLICY.max_page_bytes)
        assert transport.requests == 0
        assert require(backend.list_records(ListRequest())).records == ()


def test_binding_checked_again_before_each_request(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = Connection()
    transport = wire(monkeypatch, connection)
    assert transport.get(URLS[0], POLICY.max_page_bytes).complete
    monkeypatch.setattr(transport_module, "POLICY", POLICY.model_copy(update={"read_seconds": 21}))
    with pytest.raises(CorpusError, match="live policy not authorized"):
        transport.get(URLS[1], POLICY.max_page_bytes)
    assert transport.requests == 1 and len(connection.calls) == 1
