import gzip
import zlib

import pytest

from binfocheck.corpus.artifacts import Store
from binfocheck.corpus.capture import SnapshotCapture
from binfocheck.corpus.config import POLICY, ROBOTS, URLS, capture_policy_sha256
from binfocheck.corpus.errors import CorpusError, require
from binfocheck.corpus.receipts import Receipt
from binfocheck.corpus.transport import HttpsTransport, LiveAuthorization, Response, content_decode
from binfocheck.storage import MemoryStore

from .helpers import HTML, NOW, FakeClock, Transport, capture


def test_capture_exact_requests_spacing_and_no_restart() -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        transport, clock = Transport(), FakeClock()
        capturer = SnapshotCapture(
            io, transport, clock=clock.clock, sleep=clock.sleep, now=lambda: NOW
        )
        batch = require(capturer.capture("capture-once", "synthetic"))
        assert transport.calls == [ROBOTS, *URLS] and batch.requests_dispatched == 6
        assert clock.value == 10
        second = capturer.capture("capture-once", "synthetic")
        assert second.error and second.error.code == "capture_already_started"
        assert len(transport.calls) == 6


@pytest.mark.parametrize(
    "response",
    [
        Response(403, (), b"denied"),
        Response(500, (), b"error"),
        Response(301, (("location", "https://example.org"),), b""),
        Response(None, (), None, False, "timeout"),
        Response(200, (), b"<html>consent</html>"),
        Response(200, (), b"invalid robots text"),
        Response(200, (), b"\xff"),
    ],
)
def test_unassessable_robots_prevents_article_requests(response: Response) -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        transport = Transport({ROBOTS: response})
        batch = capture(io, transport=transport)
        assert transport.calls == [ROBOTS] and batch.requests_dispatched == 1
        assert all(not io.load(id, Receipt).complete for id in batch.receipt_ids)


@pytest.mark.parametrize("status", [404, 410])
def test_absent_robots_allows_bounded_batch(status: int) -> None:
    with MemoryStore() as backend:
        batch = capture(
            Store(backend, backend), transport=Transport({ROBOTS: Response(status, (), b"")})
        )
        assert batch.requests_dispatched == 6


def test_robot_rules_and_longer_delay() -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        transport = Transport(
            {
                ROBOTS: Response(
                    200,
                    (),
                    b"User-agent: *\nDisallow: /leben/diabetes-im-alltag/ramadan.html\n"
                    b"Crawl-delay: 5\n",
                )
            }
        )
        clock = FakeClock()
        batch = require(
            SnapshotCapture(
                io, transport, clock=clock.clock, sleep=clock.sleep, now=lambda: NOW
            ).capture("robots-test", "synthetic")
        )
        assert URLS[1] not in transport.calls and batch.requests_dispatched == 5
        assert io.load(batch.receipt_ids[1], Receipt).error == "robots_disallowed"
        assert clock.value == 20


def test_robot_rate_and_deadline() -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        transport = Transport({ROBOTS: Response(200, (), b"User-agent: *\nRequest-rate: 1/1000\n")})
        batch = capture(io, transport=transport)
        assert transport.calls == [ROBOTS]
        assert io.load(batch.receipt_ids[0], Receipt).error == "batch_deadline"


@pytest.mark.parametrize("status", [429, 503])
def test_host_stop_no_retry(status: int) -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        transport = Transport({URLS[0]: Response(status, (("retry-after", "60"),), b"limit")})
        batch = capture(io, transport=transport)
        assert transport.calls == [ROBOTS, URLS[0]]
        assert all(
            io.load(id, Receipt).error == "host_rate_limited" for id in batch.receipt_ids[1:]
        )


def test_redirect_retained_without_following() -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        transport = Transport(
            {URLS[0]: Response(302, (("location", "https://example.org/new"),), b"move")}
        )
        batch = capture(io, transport=transport)
        assert transport.calls == [ROBOTS, *URLS]
        assert (
            io.load(batch.receipt_ids[0], Receipt).headers["location"] == "https://example.org/new"
        )


def test_https_requires_authorization_before_any_network() -> None:
    with pytest.raises(CorpusError, match="live not authorized"):
        HttpsTransport().get(URLS[0], POLICY.max_page_bytes)
    with MemoryStore() as backend:
        result = SnapshotCapture(Store(backend, backend), HttpsTransport()).capture(
            "denied", "live"
        )
        assert result.error and result.error.code == "live_not_authorized"


@pytest.mark.parametrize(
    "url",
    [
        "http://www.diabinfo.de/robots.txt",
        "https://diabinfo.de/robots.txt",
        URLS[0] + "?extra=1",
        "https://www.diabinfo.de.evil.example/",
        URLS[0] + "#fragment",
    ],
)
def test_https_allowlist_before_dispatch(url: str) -> None:
    transport = HttpsTransport(
        LiveAuthorization(
            "synthetic test only", "fixture", capture_policy_sha256(ROBOTS, URLS, POLICY)
        )
    )
    with pytest.raises(CorpusError, match="url not allowed"):
        transport.get(url, POLICY.max_page_bytes)
    assert transport.requests == 0


@pytest.mark.parametrize("encoding", ["gzip", "deflate", "identity"])
def test_bounded_content_decoding(encoding: str) -> None:
    encoded = (
        gzip.compress(HTML)
        if encoding == "gzip"
        else zlib.compress(HTML)
        if encoding == "deflate"
        else HTML
    )
    assert content_decode(encoded, encoding, len(HTML)) == HTML
    with pytest.raises(CorpusError, match="response too large"):
        content_decode(encoded, encoding, len(HTML) - 1)


@pytest.mark.parametrize(
    ("body", "encoding"),
    [
        (b"bad", "gzip"),
        (b"bad", "br"),
        (gzip.compress(b"abc")[:-1], "gzip"),
        (gzip.compress(b"abc") + b"garbage", "gzip"),
    ],
)
def test_invalid_compressed_bodies(body: bytes, encoding: str) -> None:
    with pytest.raises(CorpusError):
        content_decode(body, encoding, 1000)


def test_decode_failure_preserves_encoded_bytes() -> None:
    with MemoryStore() as backend:
        io = Store(backend, backend)
        batch = capture(
            io,
            transport=Transport(
                {
                    URLS[0]: Response(
                        200,
                        (("content-encoding", "gzip"), ("content-type", "text/html")),
                        b"invalid",
                    )
                }
            ),
        )
        receipt = io.load(batch.receipt_ids[0], Receipt)
        assert receipt.body_artifact_id is None and not receipt.complete
        assert receipt.encoded_artifact_id and io.bytes(receipt.encoded_artifact_id) == b"invalid"


@pytest.mark.parametrize(
    "directive", [b"Crawl-delay: 0.5", b"Crawl-delay: nope", b"Request-rate: 0/1"]
)
def test_unparseable_robot_limits_fail_closed(directive: bytes) -> None:
    with MemoryStore() as backend:
        transport = Transport({ROBOTS: Response(200, (), b"User-agent: *\n" + directive)})
        batch = capture(Store(backend, backend), transport=transport)
        assert batch.requests_dispatched == 1


def test_uncertain_dispatch_is_consumed_without_retry() -> None:
    class Uncertain(Transport):
        def get(self, url: str, max_bytes: int) -> Response:
            self.calls.append(url)
            raise OSError("uncertain outcome")

    with MemoryStore() as backend:
        io = Store(backend, backend)
        transport = Uncertain()
        batch = capture(io, transport=transport)
        assert batch.requests_dispatched == 1 and transport.calls == [ROBOTS]
        assert batch.robots_receipt_id
        receipt = io.load(batch.robots_receipt_id, Receipt)
        assert receipt.dispatched and receipt.received_bytes is None
        assert receipt.error == "transport_failed"
