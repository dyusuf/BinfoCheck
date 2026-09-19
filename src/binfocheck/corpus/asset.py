"""One exact Ramadan SVG companion, never a page/asset crawler.

No approval is constructed here. Proposal is inert; capture requires a separately
supplied approval. One operator/store owner only (T11A has no dispatch lease).
"""

from datetime import UTC, datetime
from typing import Literal
from urllib.robotparser import RobotFileParser

from binfocheck.domain.common import Contract, Digest, Id, UTCRecord, VersionRef
from binfocheck.domain.storage import IdRequest
from binfocheck.domain.text import ArtifactRef

from .artifacts import Store
from .capture import load_capture_start
from .config import URLS, canonical, digest
from .errors import check
from .receipts import Batch, Receipt
from .transport import SAFE_HEADERS

SVG_URL = (
    "https://www.diabinfo.de/fileadmin/diabinfo/Grafiken/0511_diabinfo_Ramadan_DE_ohne-Titel.svg"
)
ATTEMPT = "t06-ramadan-svg-1"
PARENT_BATCH = "t06-live-20260919T114133Z"
PARENT_RAW = "corpus-raw-html-b20f8e3b1f9ab0f136d75089f503ec43eb717090a9b7e93a2652aa164cda39d2"
PARENT_SHA256 = "8730ea878ffba196a129c7feb6728ed92531b48a272ec01e9c98ffb37a331afd"


class AssetPolicy(Contract):
    method: Literal["GET"] = "GET"
    request_limit: Literal[1] = 1
    redirects: Literal[0] = 0
    retries: Literal[0] = 0
    concurrency: Literal[1] = 1
    connect_seconds: Literal[10] = 10
    read_seconds: Literal[20] = 20
    request_seconds: Literal[30] = 30
    max_bytes: Literal[2097152] = 2097152
    tls_verify: Literal[True] = True
    cookies: Literal[False] = False
    authentication: Literal[False] = False
    follow_links: Literal[False] = False
    browser: Literal[False] = False
    user_agent: Literal["BinfoCheck-T06/1.0"] = "BinfoCheck-T06/1.0"
    accept: Literal["image/svg+xml"] = "image/svg+xml"
    accept_encoding: Literal["identity"] = "identity"
    paid_request_limit: Literal[0] = 0
    cost_ceiling_usd: Literal[0] = 0
    uncertain_dispatch_consumes_allowance: Literal[True] = True


class AssetProposal(Contract):
    format: Literal["t06-ramadan-svg-proposal/1"] = "t06-ramadan-svg-proposal/1"
    attempt_id: Id = ATTEMPT
    url: str = SVG_URL
    parent_batch_id: Id = PARENT_BATCH
    parent_raw_artifact_id: Id = PARENT_RAW
    parent_raw_sha256: Digest = PARENT_SHA256
    policy: AssetPolicy = AssetPolicy()


PROPOSAL = AssetProposal()
PROPOSAL_SHA256 = digest(canonical(PROPOSAL.model_dump(mode="json")))


class AssetApproval(Contract):
    format: Literal["t06-ramadan-svg-authorization/1"] = "t06-ramadan-svg-authorization/1"
    approval_reference: str
    proposal: AssetProposal
    policy_sha256: Digest
    envelope_sha256: Digest

    def validate_approval(self) -> None:
        check(
            bool(self.approval_reference.strip())
            and self.proposal == PROPOSAL
            and self.policy_sha256 == PROPOSAL_SHA256
            and self.envelope_sha256 == approval_digest(self.approval_reference),
            "invalid_asset_authorization",
        )


def approval_digest(reference: str) -> str:
    """Pure calculation for a future explicit reference; not an approval factory."""
    return digest(
        canonical(
            {
                "format": "t06-ramadan-svg-authorization/1",
                "approval_reference": reference,
                "proposal": PROPOSAL.model_dump(mode="json"),
                "policy_sha256": PROPOSAL_SHA256,
            }
        )
    )


class AssetStart(UTCRecord):
    format: Literal["t06-ramadan-svg-start/1"] = "t06-ramadan-svg-start/1"
    authorization_artifact_id: Id
    authorization_sha256: Digest


class AssetReceipt(UTCRecord):
    format: Literal["t06-ramadan-svg-receipt/1"] = "t06-ramadan-svg-receipt/1"
    start_artifact_id: Id
    authorization_artifact_id: Id
    policy_sha256: Digest
    url: str
    parent_raw_artifact_id: Id
    receipt: Receipt
    body_sha256: Digest | None
    media_type: str | None
    usable_svg: bool


def _validate_parent(store: Store) -> None:
    batch = store.load(PARENT_BATCH, Batch)
    check(
        batch.origin == "live"
        and batch.id == PARENT_BATCH
        and batch.urls == URLS
        and len(batch.receipt_ids) == 5,
        "asset_parent_not_live",
    )
    load_capture_start(store, batch)
    receipt = store.load(batch.receipt_ids[1], Receipt)
    check(
        receipt.complete
        and receipt.status == 200
        and receipt.body_artifact_id == PARENT_RAW
        and receipt.url == URLS[1]
        and receipt.batch_id == PARENT_BATCH
        and receipt.ordinal == 2,
        "asset_parent_mismatch",
    )
    check(digest(store.bytes(PARENT_RAW)) == PARENT_SHA256, "asset_parent_hash_mismatch")
    check(batch.robots_receipt_id is not None, "asset_robots_missing")
    assert batch.robots_receipt_id is not None
    robots = store.load(batch.robots_receipt_id, Receipt)
    check(
        robots.complete and robots.status == 200 and robots.body_artifact_id is not None,
        "asset_robots_missing",
    )
    assert robots.body_artifact_id is not None
    rules = RobotFileParser()
    rules.parse(store.bytes(robots.body_artifact_id).decode("utf-8", "strict").splitlines())
    check(rules.can_fetch(PROPOSAL.policy.user_agent, SVG_URL), "asset_robots_disallowed")


def capture_asset(store: Store, approval: AssetApproval) -> AssetReceipt:
    """Dispatch at most once; do not call without new explicit user permission.

    A durable intent consumes the allowance even if the process dies before GET.
    Failed/uncertain attempts cannot resume. Reopen via load_asset, never capture.
    """
    from .asset_transport import dispatch

    approval.validate_approval()
    _validate_parent(store)
    start_id, authorization_id = ATTEMPT + ".start.v1", ATTEMPT + ".authorization.v1"
    existing = store.records.get_record(IdRequest(id=start_id))
    check(
        existing.error is not None and existing.error.code == "not_found", "asset_already_started"
    )
    authorization = store.json(approval, "asset-authorization", authorization_id)
    check(store.load(authorization_id, AssetApproval) == approval, "asset_authorization_readback")
    start = AssetStart(
        id=ATTEMPT,
        created_at=datetime.now(UTC),
        authorization_artifact_id=authorization_id,
        authorization_sha256=authorization.sha256,
    )
    store.json(start, "asset-start", start_id)
    check(store.load(start_id, AssetStart) == start, "asset_start_readback")
    approval.validate_approval()  # Bind again immediately before dispatch.
    response = dispatch(approval)
    finished = datetime.now(UTC)
    headers = {k.lower(): v for k, v in response.headers if k.lower() in SAFE_HEADERS}
    media = headers.get("content-type", "").split(";", 1)[0].strip().lower() or None
    complete = response.complete and response.error is None and response.body is not None
    complete = complete and len(response.body or b"") <= PROPOSAL.policy.max_bytes
    complete = complete and headers.get("content-encoding", "identity").lower() in {"", "identity"}
    error = None if complete else response.error or "invalid_asset_response"
    body = None
    partial = None
    if response.body is not None:
        ref = store.blob(
            response.body,
            "raw-svg" if complete else "partial-svg",
            media or "application/octet-stream",
        )
        if complete:
            body = ref
        else:
            partial = ref
    receipt = Receipt(
        id=ATTEMPT + ".http.v1",
        batch_id=ATTEMPT,
        url=SVG_URL,
        ordinal=0,
        created_at=start.created_at,
        finished_at=finished,
        status=response.status,
        headers=headers,
        omitted_headers=tuple(
            sorted({k.lower() for k, _ in response.headers if k.lower() not in SAFE_HEADERS})
        ),
        body_artifact_id=body.id if body else None,
        encoded_artifact_id=None,
        partial_artifact_id=partial.id if partial else None,
        complete=complete,
        dispatched=True,
        received_bytes=len(response.body) if response.body is not None else None,
        decoded_bytes=len(response.body) if complete and response.body is not None else None,
        error=error,
        fetch_version=VersionRef(name="t06-ramadan-svg-fetch", version="1", sha256=PROPOSAL_SHA256),
    )
    store.json(receipt, "asset-http", receipt.id)
    result = AssetReceipt(
        id=ATTEMPT,
        created_at=start.created_at,
        start_artifact_id=start_id,
        authorization_artifact_id=authorization_id,
        policy_sha256=PROPOSAL_SHA256,
        url=SVG_URL,
        parent_raw_artifact_id=PARENT_RAW,
        receipt=receipt,
        body_sha256=body.sha256 if body else None,
        media_type=media,
        usable_svg=complete and response.status == 200 and media == "image/svg+xml",
    )
    store.json(result, "asset-receipt", ATTEMPT + ".receipt.v1")
    return load_asset(store)


def load_asset(store: Store) -> AssetReceipt:
    """Validate saved evidence only; never requests or parses external resources."""
    _validate_parent(store)
    result = store.load(ATTEMPT + ".receipt.v1", AssetReceipt)
    check(
        result.id == ATTEMPT
        and result.start_artifact_id == ATTEMPT + ".start.v1"
        and result.authorization_artifact_id == ATTEMPT + ".authorization.v1"
        and result.policy_sha256 == PROPOSAL_SHA256
        and result.url == SVG_URL
        and result.parent_raw_artifact_id == PARENT_RAW,
        "asset_receipt_mismatch",
    )
    start = store.load(result.start_artifact_id, AssetStart)
    approval = store.load(result.authorization_artifact_id, AssetApproval)
    approval.validate_approval()
    check(
        start.id == ATTEMPT
        and start.created_at == result.created_at
        and start.authorization_artifact_id == result.authorization_artifact_id
        and digest(store.bytes(result.authorization_artifact_id)) == start.authorization_sha256,
        "asset_start_mismatch",
    )
    receipt = result.receipt
    check(
        receipt == store.load(ATTEMPT + ".http.v1", Receipt)
        and receipt.id == ATTEMPT + ".http.v1"
        and receipt.batch_id == ATTEMPT
        and receipt.url == SVG_URL
        and receipt.ordinal == 0
        and receipt.dispatched
        and receipt.created_at == start.created_at
        and receipt.encoded_artifact_id is None
        and receipt.fetch_version
        == VersionRef(name="t06-ramadan-svg-fetch", version="1", sha256=PROPOSAL_SHA256),
        "asset_http_mismatch",
    )
    media = receipt.headers.get("content-type", "").split(";", 1)[0].strip().lower() or None
    check(
        result.media_type == media
        and result.usable_svg
        == (receipt.complete and receipt.status == 200 and media == "image/svg+xml"),
        "asset_status_mismatch",
    )
    ids = [
        ATTEMPT + ".receipt.v1",
        result.start_artifact_id,
        result.authorization_artifact_id,
        receipt.id,
    ]
    if receipt.body_artifact_id:
        body = store.bytes(receipt.body_artifact_id)
        check(
            digest(body) == result.body_sha256
            and len(body) == receipt.decoded_bytes
            and len(body) == receipt.received_bytes
            and len(body) <= PROPOSAL.policy.max_bytes
            and receipt.headers.get("content-encoding", "identity").lower() in {"", "identity"},
            "asset_body_mismatch",
        )
        check(
            store.record(receipt.body_artifact_id, ArtifactRef).media_type
            == (media or "application/octet-stream"),
            "asset_media_mismatch",
        )
        ids.append(receipt.body_artifact_id)
    else:
        check(result.body_sha256 is None, "asset_body_mismatch")
    if receipt.partial_artifact_id:
        check(
            len(store.bytes(receipt.partial_artifact_id)) == receipt.received_bytes,
            "asset_partial_mismatch",
        )
        ids.append(receipt.partial_artifact_id)
    for id in ids:
        check(store.record(id, ArtifactRef).access == "restricted", "asset_access_mismatch")
    return result
