"""Private direct-HTTPS dispatch for the sole fixed asset. No redirect handling."""

import http.client
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit

from .asset import PROPOSAL, AssetApproval
from .errors import CorpusError, check
from .transport import Response


def dispatch(approval: AssetApproval) -> Response:
    approval.validate_approval()
    policy = PROPOSAL.policy
    deadline = time.monotonic() + policy.request_seconds
    connection = http.client.HTTPSConnection(
        "www.diabinfo.de", timeout=policy.connect_seconds, context=ssl.create_default_context()
    )
    status: int | None = None
    headers: tuple[tuple[str, str], ...] = ()
    chunks: list[bytes] = []
    size = 0

    def timeout() -> None:
        remaining = deadline - time.monotonic()
        check(remaining > 0, "asset_timeout")
        if connection.sock:
            connection.sock.settimeout(min(policy.read_seconds, remaining))

    def expire() -> None:
        if connection.sock:
            try:
                connection.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    watchdog = threading.Timer(policy.request_seconds, expire)
    watchdog.daemon = True
    watchdog.start()
    try:
        connection.connect()
        timeout()
        approval.validate_approval()
        connection.request(
            "GET",
            urlsplit(PROPOSAL.url).path,
            headers={
                "User-Agent": policy.user_agent,
                "Accept": policy.accept,
                "Accept-Encoding": policy.accept_encoding,
            },
        )
        timeout()
        response = connection.getresponse()
        status, headers = response.status, tuple(response.getheaders())
        # No credentials/cookies, proxy handling, HEAD, retries, or redirect loop.
        while True:
            timeout()
            chunk = response.read1(min(65536, policy.max_bytes + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            check(size <= policy.max_bytes, "asset_too_large")
        declared = response.getheader("Content-Length")
        if declared is not None and not response.chunked:
            check(size == int(declared), "asset_incomplete")
        timeout()
        return Response(status, headers, b"".join(chunks))
    except (OSError, http.client.HTTPException, ValueError, CorpusError) as error:
        return Response(
            status,
            headers,
            b"".join(chunks) if chunks else None,
            False,
            error.detail.code if isinstance(error, CorpusError) else "asset_transport_failed",
        )
    finally:
        watchdog.cancel()
        connection.close()
