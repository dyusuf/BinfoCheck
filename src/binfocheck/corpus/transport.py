"""Direct HTTPS transport, disabled without a separate explicit live authorization."""

import http.client
import socket
import threading
import time
import zlib
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from .config import POLICY, ROBOTS, URLS, FetchPolicy, capture_policy_sha256
from .errors import CorpusError, check

SAFE_HEADERS = frozenset(
    {
        "content-type",
        "content-encoding",
        "date",
        "etag",
        "last-modified",
        "location",
        "retry-after",
        "content-length",
    }
)


@dataclass(frozen=True)
class Response:
    status: int | None
    headers: tuple[tuple[str, str], ...]
    body: bytes | None
    complete: bool = True
    error: str | None = None


class Transport(Protocol):
    def get(self, url: str, max_bytes: int) -> Response: ...


@dataclass(frozen=True)
class LiveAuthorization:
    """Operator-supplied reference to later explicit approval, not a configuration default."""

    reference: str
    batch_id: str
    policy_sha256: str

    def validate_policy(
        self, robots_url: str, page_urls: tuple[str, ...], policy: FetchPolicy
    ) -> None:
        check(bool(self.reference.strip()), "live_not_authorized")
        check(
            self.policy_sha256 == capture_policy_sha256(robots_url, page_urls, policy),
            "live_policy_not_authorized",
        )


class HttpsTransport:
    def __init__(self, authorization: LiveAuthorization | None = None) -> None:
        self.authorization = authorization
        self.requests = 0

    def get(self, url: str, max_bytes: int) -> Response:
        check(
            self.authorization is not None and bool(self.authorization.reference),
            "live_not_authorized",
        )
        assert self.authorization is not None
        self.authorization.validate_policy(ROBOTS, URLS, POLICY)
        check(url in (*URLS, ROBOTS), "url_not_allowed")
        check(self.requests < POLICY.request_limit, "request_limit_exhausted")
        check(
            max_bytes == (POLICY.max_robots_bytes if url == ROBOTS else POLICY.max_page_bytes),
            "invalid_transport_limit",
        )
        self.requests += 1  # Uncertain dispatch consumes a request, never retried here.
        deadline = time.monotonic() + POLICY.request_seconds
        connection = http.client.HTTPSConnection("www.diabinfo.de", timeout=POLICY.connect_seconds)
        status: int | None = None
        headers: tuple[tuple[str, str], ...] = ()
        chunks: list[bytes] = []
        size = 0
        watchdog: threading.Timer | None = None
        try:
            connection.connect()
            self._timeout(connection, deadline)

            # Socket deadlines alone permit slow trickles during HTTP header parsing.
            # Close this connection at the overall deadline as well.
            def expire() -> None:
                if connection.sock is not None:
                    try:
                        connection.sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

            watchdog = threading.Timer(max(0, deadline - time.monotonic()), expire)
            watchdog.daemon = True
            watchdog.start()
            connection.request(
                "GET",
                urlsplit(url).path,
                headers={
                    "User-Agent": POLICY.user_agent,
                    "Accept": "text/plain" if url == ROBOTS else "text/html",
                    "Accept-Language": "de",
                    "Accept-Encoding": "identity",
                },
            )
            self._timeout(connection, deadline)
            response = connection.getresponse()
            status, headers = response.status, tuple(response.getheaders())
            while True:
                self._timeout(connection, deadline)
                chunk = response.read1(min(65536, max_bytes + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                check(size <= max_bytes, "response_too_large")
            declared = response.getheader("Content-Length")
            if declared is not None and not response.chunked:
                check(size == int(declared), "response_incomplete")
            check(time.monotonic() <= deadline, "request_timeout")
            return Response(status, headers, b"".join(chunks))
        except (OSError, http.client.HTTPException, ValueError, CorpusError) as error:
            code = error.detail.code if isinstance(error, CorpusError) else "transport_failed"
            return Response(status, headers, b"".join(chunks) if chunks else None, False, code)
        finally:
            if watchdog is not None:
                watchdog.cancel()
            connection.close()

    @staticmethod
    def _timeout(connection: http.client.HTTPSConnection, deadline: float) -> None:
        remaining = deadline - time.monotonic()
        check(remaining > 0, "request_timeout")
        if connection.sock:
            connection.sock.settimeout(min(POLICY.read_seconds, remaining))


def content_decode(body: bytes, encoding: str, limit: int) -> bytes:
    if encoding in {"", "identity"}:
        check(len(body) <= limit, "response_too_large")
        return body
    check(encoding in {"gzip", "deflate"}, "unsupported_content_encoding")
    decoder = zlib.decompressobj(31 if encoding == "gzip" else zlib.MAX_WBITS)
    try:
        result = decoder.decompress(body, limit + 1)
        check(len(result) <= limit and not decoder.unconsumed_tail, "response_too_large")
        check(decoder.eof and not decoder.unused_data, "invalid_content_encoding")
        return result
    except zlib.error:
        raise CorpusError("invalid_content_encoding") from None
