"""Exact captured non-text informational evidence, under the approved T06 rule.

No XML interpretation, OCR, asset dispatch or arbitrary media exemption. The frozen
inspection is evidence, including its historical blocked decision, never rewritten.
"""

import json
from pathlib import Path
from typing import Literal

from bs4 import Tag
from pydantic import TypeAdapter

from binfocheck.domain.common import Contract, Digest, Id
from binfocheck.domain.text import ArtifactRef

from . import asset
from .artifacts import Store
from .config import URLS, canonical, digest
from .decoding import decode_html
from .errors import check
from .media import media_tree
from .receipts import Batch, Receipt

PINS = TypeAdapter(dict[str, str]).validate_json(
    Path(__file__).with_name("nontext_evidence_v1.json").read_bytes()
)
SVG_ID = "corpus-raw-svg-1201b0c36772982079a76330da05f79bf236b6f30105dda898a30bbd38ac33ad"
INSPECTION_ID = "t06-ramadan-svg-1.inspection.v1"
GALLERY_SHA256 = "0974661a8ae98b133bc44c15e7a441a299134db45dffe53d9844b771f3da337c"
DISPOSITION = "captured_nontext_informational"
LIMITATION = (
    "Informational visual captured and preserved; no deterministic machine-readable "
    "text is extractable. Visual content is not represented by textual passages. "
    "No OCR, image interpretation, SVG path inference or fabricated text."
)


def policy_sha256() -> str:
    return digest(
        canonical(
            {
                "format": "t06-nontext-policy/1",
                "pins": PINS,
                "svg_id": SVG_ID,
                "inspection_id": INSPECTION_ID,
                "gallery_sha256": GALLERY_SHA256,
                "url": asset.SVG_URL,
                "disposition": DISPOSITION,
                "limitation": LIMITATION,
            }
        )
    )


class EvidenceMember(Contract):
    artifact_id: Id
    sha256: Digest


class VerifiedMedia(Contract):
    policy_sha256: Digest
    parent_raw_artifact_id: Id
    parent_html_text_sha256: Digest
    svg_artifact_id: Id
    inspection_artifact_id: Id
    members: tuple[EvidenceMember, ...]


class MediaEvidence(Contract):
    format: Literal["t06-media-evidence/1"] = "t06-media-evidence/1"
    article_version_id: Id
    parent_raw_artifact_id: Id
    html_gallery_locator: str
    svg_url: str
    disposition: Literal["captured_nontext_informational"] = "captured_nontext_informational"
    limitation: str = LIMITATION
    evidence: VerifiedMedia


def validate_evidence(store: Store, batch: Batch) -> VerifiedMedia:
    """Preflight before any derived record publication; repeated on every load."""
    check(batch.id == asset.PARENT_BATCH, "nontext_parent_batch_mismatch")
    for id, expected in PINS.items():
        check(digest(store.bytes(id)) == expected, "nontext_evidence_hash_mismatch")
        check(store.record(id, ArtifactRef).access == "restricted", "nontext_evidence_access")
    saved = asset.load_asset(store)
    check(
        saved.usable_svg
        and saved.receipt.complete
        and saved.receipt.status == 200
        and saved.url == asset.SVG_URL
        and saved.parent_raw_artifact_id == asset.PARENT_RAW
        and saved.receipt.body_artifact_id == SVG_ID
        and saved.body_sha256 == PINS[SVG_ID],
        "nontext_asset_mismatch",
    )
    inspection = json.loads(store.bytes(INSPECTION_ID))
    check(
        inspection.get("format") == "t06-svg-inspection/1"
        and inspection.get("status") == "no_deterministic_text_extractable"
        and inspection.get("asset_attempt_id") == asset.ATTEMPT
        and inspection.get("asset_receipt_artifact_id") == asset.ATTEMPT + ".receipt.v1"
        and inspection.get("authorization_artifact_id") == saved.authorization_artifact_id
        and inspection.get("authorization_policy_sha256") == saved.policy_sha256
        and inspection.get("http_receipt_artifact_id") == saved.receipt.id
        and inspection.get("raw_svg_artifact_id") == SVG_ID
        and inspection.get("raw_svg_sha256") == saved.body_sha256
        and inspection.get("raw_svg_bytes") == saved.receipt.decoded_bytes
        and inspection.get("http_status") == 200
        and inspection.get("media_type") == "image/svg+xml"
        and inspection.get("xml_root") == "svg"
        and all(
            inspection.get(field) == []
            for field in (
                "machine_readable_text",
                "accessibility_metadata",
                "external_or_internal_href_references",
                "unsafe_or_unsupported_elements",
            )
        )
        and all(
            inspection.get(field) is False
            for field in (
                "scripts_executed",
                "external_resources_loaded",
                "ocr_used",
                "vector_path_semantics_inferred",
            )
        )
        and inspection.get("network_requests_during_inspection") == 0,
        "nontext_inspection_mismatch",
    )
    parent = store.load(batch.receipt_ids[1], Receipt)
    check(parent.body_artifact_id == asset.PARENT_RAW, "nontext_parent_mismatch")
    html, _ = decode_html(store.bytes(asset.PARENT_RAW), parent.headers.get("content-type", ""))
    return VerifiedMedia(
        policy_sha256=policy_sha256(),
        parent_raw_artifact_id=asset.PARENT_RAW,
        parent_html_text_sha256=digest(html.encode()),
        svg_artifact_id=SVG_ID,
        inspection_artifact_id=INSPECTION_ID,
        members=tuple(
            EvidenceMember(artifact_id=id, sha256=sha) for id, sha in sorted(PINS.items())
        ),
    )


def matches_gallery(tag: Tag, url: str) -> bool:
    return url == URLS[1] and digest(canonical(media_tree(tag))) == GALLERY_SHA256


def companion(article_id: str, locator: str, evidence: VerifiedMedia) -> MediaEvidence:
    return MediaEvidence(
        article_version_id=article_id,
        parent_raw_artifact_id=evidence.parent_raw_artifact_id,
        html_gallery_locator=locator,
        svg_url=asset.SVG_URL,
        evidence=evidence,
    )
