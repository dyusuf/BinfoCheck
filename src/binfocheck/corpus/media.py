"""Positive signatures for inspected pilot media; no image inference or I/O.

Each digest covers tag names, all attributes, text and ordered children of the
entire gallery/audio subtree. Only whitespace-only nodes and text edge whitespace
are ignored. Human-readable metadata accompanies each frozen digest for review.
Changing this file requires a new site profile; versions 1–3 never use this policy.
"""

import json
from pathlib import Path

from bs4 import Tag
from bs4.element import NavigableString

from .config import canonical, digest
from .errors import check

SIGNATURES = json.loads(Path(__file__).with_name("decorative_media_v1.json").read_text())


def media_tree(tag: Tag | NavigableString) -> object:
    if isinstance(tag, Tag):
        return [
            tag.name,
            tag.attrs,
            [
                media_tree(child)
                for child in tag.children
                if isinstance(child, (Tag, NavigableString))
                and (isinstance(child, Tag) or str(child).strip())
            ],
        ]
    return str(tag).strip()


def validate_media(tag: Tag, url: str, kind: str) -> None:
    signature = digest(canonical(media_tree(tag)))
    check(
        any(
            entry["url"] == url and entry["kind"] == kind and entry["signature_sha256"] == signature
            for entry in SIGNATURES
        ),
        "unsupported_informational_media",
    )
