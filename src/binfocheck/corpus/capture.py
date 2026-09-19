"""Bounded capture is separate from ingestion/replay. No automatic restart/refetch."""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal
from urllib.robotparser import RobotFileParser

from binfocheck.domain.common import Id, UTCRecord
from binfocheck.domain.storage import IdRequest
from binfocheck.domain.text import ArtifactRef

from .artifacts import Store
from .config import POLICY, ROBOTS, URLS, capture_policy_sha256, identity
from .errors import CorpusError, boundary, check
from .receipts import AuthorizationEvidence, Batch, Receipt
from .transport import SAFE_HEADERS, HttpsTransport, Response, Transport, content_decode


class CaptureStart(UTCRecord):
    format: Literal["t06-capture-start/1"] = "t06-capture-start/1"
    origin: Literal["synthetic", "live"]
    authorization_artifact_id: Id | None = None


def validate_authorization(evidence: AuthorizationEvidence, batch_id: str) -> None:
    check(
        evidence.batch_id == batch_id
        and bool(evidence.approval_reference.strip())
        and evidence.robots_url == ROBOTS
        and evidence.page_urls == URLS
        and evidence.fetch_policy == POLICY
        and evidence.policy_sha256
        == capture_policy_sha256(evidence.robots_url, evidence.page_urls, evidence.fetch_policy),
        "invalid_authorization_evidence",
    )


def load_capture_start(store: Store, batch: Batch) -> CaptureStart:
    start = store.load(batch.id + ".start.v1", CaptureStart)
    check(
        start.id == batch.id
        and start.created_at == batch.created_at
        and start.origin == batch.origin,
        "capture_start_mismatch",
    )
    if batch.origin == "live":
        id = batch.id + ".authorization.v1"
        check(start.authorization_artifact_id == id, "missing_authorization_evidence")
        evidence = store.load(id, AuthorizationEvidence)
        validate_authorization(evidence, batch.id)
        check(batch.policy == evidence.fetch_policy, "authorization_policy_mismatch")
        check(store.record(id, ArtifactRef).access == "restricted", "authorization_access_mismatch")
    else:
        check(start.authorization_artifact_id is None, "synthetic_authorization_evidence")
    return start


def save_response(
    store: Store,
    batch_id: str,
    url: str,
    ordinal: int,
    response: Response,
    started: datetime,
    finished: datetime,
    dispatched: bool = True,
) -> Receipt:
    values = {k.lower(): v for k, v in response.headers if k.lower() in SAFE_HEADERS}
    omitted = tuple(
        sorted({k.lower() for k, _ in response.headers if k.lower() not in SAFE_HEADERS})
    )
    raw_id: str | None = None
    encoded_id: str | None = None
    partial_id: str | None = None
    complete, error = response.complete and response.error is None, response.error
    limit = POLICY.max_robots_bytes if url == ROBOTS else POLICY.max_page_bytes
    body = response.body
    decoded_size: int | None = None
    if body is not None:
        if not complete or len(body) > limit:
            partial_id = store.blob(body, "partial-body", "application/octet-stream").id
            complete, error = False, error or "response_too_large"
        else:
            encoding = values.get("content-encoding", "").lower()
            if encoding not in {"", "identity"}:
                encoded_id = store.blob(body, "encoded-body", "application/octet-stream").id
            try:
                decoded = content_decode(body, encoding, limit)
                decoded_size = len(decoded)
                media = values.get("content-type", "").split(";", 1)[0].strip().lower()
                role = (
                    "robots-body"
                    if url == ROBOTS
                    else "raw-html"
                    if media == "text/html"
                    else "response-body"
                )
                raw_id = store.blob(decoded, role, media or "application/octet-stream").id
            except CorpusError as failure:
                complete, error = False, failure.detail.code
    else:
        complete, error = False, error or "missing_body"
    receipt = Receipt(
        id=identity("receipt", [batch_id, ordinal, url]),
        batch_id=batch_id,
        url=url,
        ordinal=ordinal,
        created_at=started,
        finished_at=finished,
        status=response.status,
        headers=values,
        omitted_headers=omitted,
        body_artifact_id=raw_id,
        encoded_artifact_id=encoded_id,
        partial_artifact_id=partial_id,
        complete=complete,
        dispatched=dispatched,
        received_bytes=len(body) if body is not None else None,
        decoded_bytes=decoded_size,
        error=error,
    )
    store.json(receipt, "transport", receipt.id)
    return receipt


class SnapshotCapture:
    def __init__(
        self,
        store: Store,
        transport: Transport,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.store, self.transport = store, transport
        self.clock, self.sleep, self.now = clock, sleep, now

    @boundary
    def capture(self, batch_id: str, origin: Literal["synthetic", "live"]) -> Batch:
        evidence: AuthorizationEvidence | None = None
        check(origin != "live" or isinstance(self.transport, HttpsTransport), "live_not_authorized")
        if isinstance(self.transport, HttpsTransport):
            approval = self.transport.authorization
            check(
                approval is not None and approval.batch_id == batch_id and origin == "live",
                "live_not_authorized",
            )
            assert approval is not None
            approval.validate_policy(ROBOTS, URLS, POLICY)
            evidence = AuthorizationEvidence(
                batch_id=batch_id,
                approval_reference=approval.reference,
                policy_sha256=approval.policy_sha256,
                robots_url=ROBOTS,
                page_urls=URLS,
                fetch_policy=POLICY,
            )
            validate_authorization(evidence, batch_id)
        authorization_id = batch_id + ".authorization.v1" if evidence else None
        start = CaptureStart(
            id=batch_id,
            created_at=self.now(),
            origin=origin,
            authorization_artifact_id=authorization_id,
        )
        start_id = batch_id + ".start.v1"
        existing = self.store.records.get_record(IdRequest(id=start_id))
        check(
            existing.error is not None and existing.error.code == "not_found",
            "capture_already_started",
        )
        if evidence is not None and authorization_id is not None:
            self.store.json(evidence, "authorization", authorization_id)
            check(
                self.store.load(authorization_id, AuthorizationEvidence) == evidence,
                "authorization_readback_mismatch",
            )
        self.store.json(start, "capture-start", start_id)
        deadline = self.clock() + POLICY.batch_seconds
        last_start: float | None = None
        count = 0
        delay: float = POLICY.spacing_seconds

        def get(url: str, ordinal: int, blocked: str | None = None) -> Receipt:
            nonlocal last_start, count
            if not blocked and last_start is not None:
                wait = max(0.0, last_start + delay - self.clock())
                if self.clock() + wait + POLICY.request_seconds > deadline:
                    blocked = "batch_deadline"
                else:
                    self.sleep(wait)
            started = self.now()
            if blocked:
                response = Response(None, (), None, False, blocked)
            else:
                check(count < POLICY.request_limit, "request_limit_exhausted")
                count += 1
                last_start = self.clock()
                try:
                    response = self.transport.get(
                        url, POLICY.max_robots_bytes if url == ROBOTS else POLICY.max_page_bytes
                    )
                except (OSError, CorpusError):
                    response = Response(None, (), None, False, "transport_failed")
            return save_response(
                self.store,
                batch_id,
                url,
                ordinal,
                response,
                started,
                self.now(),
                dispatched=not bool(blocked),
            )

        robots = get(ROBOTS, 0)
        robot_parser: RobotFileParser | None = None
        blocked: str | None = None
        if robots.complete and robots.status in {404, 410}:
            pass
        elif robots.complete and robots.status == 200 and robots.body_artifact_id:
            try:
                body = self.store.bytes(robots.body_artifact_id).decode("utf-8", "strict")
                lines = [line.split("#", 1)[0].strip() for line in body.splitlines()]
                check(not any(line and ":" not in line for line in lines), "robots_unassessable")
                check(not body.lstrip().startswith("<"), "robots_unassessable")
                for line in lines:
                    if not line or ":" not in line:
                        continue
                    key, value = (part.strip() for part in line.split(":", 1))
                    if key.lower() == "crawl-delay":
                        check(value.isdigit(), "robots_unassessable")
                    elif key.lower() == "request-rate":
                        parts = value.split("/")
                        check(
                            len(parts) == 2 and all(p.isdigit() and int(p) > 0 for p in parts),
                            "robots_unassessable",
                        )
                robot_parser = RobotFileParser()
                robot_parser.parse(lines)
                delay = max(delay, float(robot_parser.crawl_delay(POLICY.user_agent) or 0))
                rate = robot_parser.request_rate(POLICY.user_agent)
                if rate:
                    check(rate.requests > 0, "robots_unassessable")
                    delay = max(delay, rate.seconds / rate.requests)
            except (ValueError, CorpusError):
                blocked = "robots_unassessable"
        else:
            blocked = "robots_unavailable"
        receipts: list[str] = []
        for ordinal, url in enumerate(URLS, start=1):
            reason = blocked
            if not reason and robot_parser and not robot_parser.can_fetch(POLICY.user_agent, url):
                reason = "robots_disallowed"
            receipt = get(url, ordinal, reason)
            receipts.append(receipt.id)
            if receipt.status in {429, 503}:
                blocked = "host_rate_limited"
            if receipt.error == "batch_deadline":
                blocked = "batch_deadline"
        batch = Batch(
            id=batch_id,
            created_at=start.created_at,
            origin=origin,
            receipt_ids=tuple(receipts),
            robots_receipt_id=robots.id,
            requests_dispatched=count,
        )
        self.store.json(batch, "batch", batch.id)
        return batch
