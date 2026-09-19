"""Synthetic transport/storage only. No SVG GET or automatic interpretation."""

import socket
from pathlib import Path
from typing import NoReturn, cast

import pytest

from binfocheck.corpus import asset, asset_transport
from binfocheck.corpus.artifacts import Store
from binfocheck.corpus.config import digest
from binfocheck.corpus.errors import CorpusError
from binfocheck.corpus.transport import Response
from binfocheck.domain.common import Contract
from binfocheck.domain.storage import IdRequest
from binfocheck.storage import MemoryStore, SQLiteStore

SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><text>synthetic only</text></svg>'


def approval() -> asset.AssetApproval:
    reference = "synthetic-test-authorization-only"
    return asset.AssetApproval(
        approval_reference=reference,
        proposal=asset.PROPOSAL,
        policy_sha256=asset.PROPOSAL_SHA256,
        envelope_sha256=asset.approval_digest(reference),
    )


def offline_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    # A synthetic test cannot contain the exact private parent HTML hash. Test the
    # other boundaries independently; durable integration checks the real parent.
    def validated(store: Store) -> None:
        pass

    monkeypatch.setattr(asset, "_validate_parent", validated)


def test_inert_proposal_has_exact_scope() -> None:
    p = asset.PROPOSAL
    assert p.url == asset.SVG_URL and p.policy.method == "GET"
    assert p.policy.request_limit == 1 and p.policy.redirects == p.policy.retries == 0
    assert p.policy.max_bytes == 2097152 and p.policy.request_seconds == 30
    assert (
        asset.PROPOSAL_SHA256 != "78de13b54502cf2c8395d9be1301f66c74bbe0d8b8cf5a931f58e71c1aad5d18"
    )
    assert asset.approval_digest("a") != asset.approval_digest("b")


def test_missing_parent_fails_before_authorization_persistence() -> None:
    with MemoryStore() as backend:
        with pytest.raises(CorpusError):
            asset.capture_asset(Store(backend, backend), approval())
        assert backend.get_record(IdRequest(id=asset.ATTEMPT + ".start.v1")).error
        assert backend.get_record(IdRequest(id=asset.ATTEMPT + ".authorization.v1")).error


@pytest.mark.parametrize(
    "field,value",
    [
        ("approval_reference", ""),
        ("approval_reference", "different approval"),
        ("policy_sha256", "0" * 64),
        ("envelope_sha256", "0" * 64),
        ("proposal", asset.PROPOSAL.model_copy(update={"url": "https://example.org/other.svg"})),
        ("proposal", asset.PROPOSAL.model_copy(update={"attempt_id": "another-attempt"})),
        (
            "proposal",
            asset.PROPOSAL.model_copy(
                update={"policy": asset.AssetPolicy().model_copy(update={"request_limit": 2})}
            ),
        ),
    ],
)
def test_bad_authorization_cannot_write_intent_or_construct_connection(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("dispatch not allowed")

    monkeypatch.setattr(asset_transport.http.client, "HTTPSConnection", forbidden)
    with MemoryStore() as backend:
        with pytest.raises(CorpusError, match="invalid asset authorization"):
            asset.capture_asset(
                Store(backend, backend), approval().model_copy(update={field: value})
            )
        assert backend.get_record(IdRequest(id=asset.ATTEMPT + ".start.v1")).error


def test_persist_before_dispatch_reopen_and_socket_blocked_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    offline_parent(monkeypatch)
    calls: list[asset.AssetApproval] = []
    with SQLiteStore(tmp_path) as backend:
        store = Store(backend, backend)

        def dispatch(a: asset.AssetApproval) -> Response:
            a.validate_approval()
            assert store.load(asset.ATTEMPT + ".authorization.v1", asset.AssetApproval) == a
            start = store.load(asset.ATTEMPT + ".start.v1", asset.AssetStart)
            assert start.authorization_sha256 == digest(
                store.bytes(start.authorization_artifact_id)
            )
            calls.append(a)
            return Response(200, (("content-type", "image/svg+xml"),), SVG)

        monkeypatch.setattr(asset_transport, "dispatch", dispatch)
        result = asset.capture_asset(store, approval())
        assert result.usable_svg and result.body_sha256 == digest(SVG)
        assert result.receipt.body_artifact_id
        assert store.bytes(result.receipt.body_artifact_id) == SVG

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("socket/DNS forbidden")

    for name in ("socket", "getaddrinfo", "gethostbyname", "create_connection"):
        monkeypatch.setattr(socket, name, forbidden)
    with SQLiteStore(tmp_path) as backend:
        store = Store(backend, backend)
        assert asset.load_asset(store) == result
        with pytest.raises(CorpusError, match="asset already started"):
            asset.capture_asset(store, approval())
    assert len(calls) == 1


@pytest.mark.parametrize(
    "response",
    [
        Response(302, (("location", "https://other.invalid/"),), b""),
        Response(200, (("content-type", "text/html"),), b"not svg"),
        Response(None, (), None, False, "timeout"),
        Response(200, (("content-type", "image/svg+xml"),), b"partial", False, "incomplete"),
        Response(
            200, (("content-type", "image/svg+xml"), ("content-encoding", "gzip")), b"encoded"
        ),
        Response(200, (("content-type", "image/svg+xml"),), b"x" * (2097152 + 1)),
    ],
)
def test_failed_or_uncertain_dispatch_consumes_allowance(
    monkeypatch: pytest.MonkeyPatch,
    response: Response,
) -> None:
    offline_parent(monkeypatch)

    def dispatch(a: asset.AssetApproval) -> Response:
        return response

    monkeypatch.setattr(asset_transport, "dispatch", dispatch)
    with MemoryStore() as backend:
        store = Store(backend, backend)
        result = asset.capture_asset(store, approval())
        assert not result.usable_svg
        assert asset.load_asset(store) == result
        with pytest.raises(CorpusError, match="asset already started"):
            asset.capture_asset(store, approval())


def test_write_failure_dispatches_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    offline_parent(monkeypatch)

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("dispatch not allowed")

    monkeypatch.setattr(asset_transport, "dispatch", forbidden)
    with MemoryStore() as backend:
        store = Store(backend, backend)

        def failed(*args: object, **kwargs: object) -> NoReturn:
            raise CorpusError("synthetic_store_failure")

        monkeypatch.setattr(store, "json", failed)
        with pytest.raises(CorpusError, match="synthetic store failure"):
            asset.capture_asset(store, approval())


@pytest.mark.parametrize(
    "field,value",
    [
        ("url", "https://example.org/other.svg"),
        ("body_sha256", "0" * 64),
        ("parent_raw_artifact_id", "wrong"),
        ("policy_sha256", "0" * 64),
        ("usable_svg", False),
        ("media_type", "text/html"),
    ],
)
def test_load_rejects_changed_evidence(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    offline_parent(monkeypatch)

    def dispatch(a: asset.AssetApproval) -> Response:
        return Response(200, (("content-type", "image/svg+xml"),), SVG)

    monkeypatch.setattr(asset_transport, "dispatch", dispatch)
    with MemoryStore() as backend:
        store = Store(backend, backend)
        result = asset.capture_asset(store, approval())
        original = store.load

        def changed[T: Contract](id: str, cls: type[T]) -> T:
            return (
                cast(T, result.model_copy(update={field: value}))
                if cls is asset.AssetReceipt
                else original(id, cls)
            )

        monkeypatch.setattr(store, "load", changed)
        with pytest.raises(CorpusError):
            asset.load_asset(store)


@pytest.mark.parametrize("status", [200, 302, 503])
def test_direct_asset_transport_exact_get_no_redirect_or_retry(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
) -> None:
    import ssl

    from .test_transport import Connection, Reply

    reply = Reply(SVG, str(len(SVG)))
    reply.status = status
    connection = Connection(reply)

    def create(host: str, timeout: float, context: ssl.SSLContext) -> Connection:
        assert host == "www.diabinfo.de" and timeout == 10
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        return connection

    monkeypatch.setattr(asset_transport.http.client, "HTTPSConnection", create)
    result = asset_transport.dispatch(approval())
    assert result.complete and result.body == SVG and result.status == status
    assert connection.calls == [
        (
            "GET",
            "/fileadmin/diabinfo/Grafiken/0511_diabinfo_Ramadan_DE_ohne-Titel.svg",
            {
                "User-Agent": "BinfoCheck-T06/1.0",
                "Accept": "image/svg+xml",
                "Accept-Encoding": "identity",
            },
        )
    ]
    assert all(0 < t <= 20 for t in connection.sock.timeouts) and connection.closed


@pytest.mark.parametrize("mode", ["oversize", "incomplete", "timeout", "error"])
def test_direct_asset_transport_bounds(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    import ssl

    from .helpers import FakeClock
    from .test_transport import Connection, Reply

    clock = FakeClock()
    monkeypatch.setattr(asset_transport.time, "monotonic", clock.clock)
    body = b"x" * (2097152 + 1) if mode == "oversize" else b"abc"
    reply = Reply(body, str(len(body) + (1 if mode == "incomplete" else 0)))
    connection = Connection(reply)

    def create(host: str, timeout: float, context: ssl.SSLContext) -> Connection:
        return connection

    monkeypatch.setattr(asset_transport.http.client, "HTTPSConnection", create)
    if mode == "timeout":

        def slow(size: int) -> bytes:
            clock.sleep(16)
            return b"x"

        monkeypatch.setattr(reply, "read1", slow)
    if mode == "error":

        def broken() -> NoReturn:
            raise OSError("do not retain arbitrary exception strings")

        monkeypatch.setattr(connection, "connect", broken)
    result = asset_transport.dispatch(approval())
    assert (
        not result.complete
        and result.error
        == {
            "oversize": "asset_too_large",
            "incomplete": "asset_incomplete",
            "timeout": "asset_timeout",
            "error": "asset_transport_failed",
        }[mode]
    )
    assert len(connection.calls) <= 1 and connection.closed


def test_transport_rechecks_bad_approval_before_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("connection forbidden")

    monkeypatch.setattr(asset_transport.http.client, "HTTPSConnection", forbidden)
    with pytest.raises(CorpusError, match="invalid asset authorization"):
        asset_transport.dispatch(approval().model_copy(update={"policy_sha256": "0" * 64}))
