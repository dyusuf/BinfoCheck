"""Exercise direct HTTPS wiring with no sockets; not live integration proof."""

import http.client

import pytest

from binfocheck.corpus import transport as module
from binfocheck.corpus.config import POLICY, URLS
from binfocheck.corpus.errors import CorpusError
from binfocheck.corpus.transport import HttpsTransport, LiveAuthorization

from .helpers import FakeClock


class Socket:
    def __init__(self) -> None:
        self.timeouts: list[float] = []

    def settimeout(self, timeout: float) -> None:
        self.timeouts.append(timeout)


class Reply:
    status = 200
    chunked = False

    def __init__(self, body: bytes = b"HTML", declared: str | None = "4") -> None:
        self.body = body
        self.declared = declared

    def getheaders(self) -> list[tuple[str, str]]:
        return [("content-type", "text/html")]

    def getheader(self, name: str) -> str | None:
        return self.declared

    def read1(self, size: int) -> bytes:
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk


class Connection:
    def __init__(self, reply: Reply | None = None) -> None:
        self.sock = Socket()
        self.reply = reply or Reply()
        self.calls: list[tuple[str, str, dict[str, str]]] = []
        self.closed = False

    def connect(self) -> None:
        pass

    def request(self, method: str, path: str, headers: dict[str, str]) -> None:
        self.calls.append((method, path, headers))

    def getresponse(self) -> Reply:
        return self.reply

    def close(self) -> None:
        self.closed = True


def wire(monkeypatch: pytest.MonkeyPatch, connection: Connection) -> HttpsTransport:
    def create(host: str, timeout: float) -> Connection:
        assert host == "www.diabinfo.de" and timeout == 10
        return connection

    monkeypatch.setattr(http.client, "HTTPSConnection", create)
    return HttpsTransport(LiveAuthorization("synthetic test, no live permission", "test"))


def test_direct_https_settings_and_request_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = Connection()
    transport = wire(monkeypatch, connection)
    response = transport.get(URLS[0], POLICY.max_page_bytes)
    assert response.body == b"HTML" and response.complete
    method, path, headers = connection.calls[0]
    assert method == "GET" and path == "/leben/diabetes-im-alltag/strassenverkehr.html"
    assert headers == {
        "User-Agent": "BinfoCheck-T06/1.0",
        "Accept": "text/html",
        "Accept-Language": "de",
        "Accept-Encoding": "identity",
    }
    assert all(0 < timeout <= 20 for timeout in connection.sock.timeouts)
    assert connection.closed
    transport.requests = 6
    with pytest.raises(CorpusError, match="request limit exhausted"):
        transport.get(URLS[0], POLICY.max_page_bytes)
    assert len(connection.calls) == 1


def test_incomplete_body_is_not_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = wire(monkeypatch, Connection(Reply(b"abc", "4")))
    response = transport.get(URLS[0], POLICY.max_page_bytes)
    assert (
        response.body == b"abc"
        and not response.complete
        and response.error == "response_incomplete"
    )


def test_read_failure_keeps_received_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    reply = Reply()
    calls = 0

    def broken(size: int) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            return b"prefix"
        raise OSError("private payload must not leak")

    monkeypatch.setattr(reply, "read1", broken)
    transport = wire(monkeypatch, Connection(reply))
    response = transport.get(URLS[0], POLICY.max_page_bytes)
    assert (
        not response.complete
        and response.error == "transport_failed"
        and response.body == b"prefix"
    )


def test_total_deadline_not_only_socket_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeClock()
    monkeypatch.setattr(module.time, "monotonic", clock.clock)
    reply = Reply()

    def slow(size: int) -> bytes:
        clock.sleep(15)
        return b"x"

    monkeypatch.setattr(reply, "read1", slow)
    connection = Connection(reply)
    response = wire(monkeypatch, connection).get(URLS[0], POLICY.max_page_bytes)
    assert not response.complete and response.error == "request_timeout"
    assert response.body == b"xx" and connection.closed
