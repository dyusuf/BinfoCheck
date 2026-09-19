"""Parser metadata companion. All exact locations reuse the shared SpanRef."""

from typing import Literal

from binfocheck.domain.common import Contract, Id, VersionRef
from binfocheck.domain.text import SpanRef


class Block(Contract):
    kind: Literal["heading", "paragraph", "list", "pre"]
    span: SpanRef
    locator: str
    heading_indices: tuple[int, ...]


class Heading(Contract):
    span: SpanRef
    level: int
    parent_index: int | None
    section_end: int


class ListItem(Contract):
    span: SpanRef
    depth: int
    ordered: bool
    marker: str
    locator: str


class Link(Contract):
    span: SpanRef | None
    locator: str
    href: str
    resolved: str
    navigable: bool
    block_index: int


class Exclusion(Contract):
    locator: str
    rule: str


class Structure(Contract):
    format: Literal["t06-structure/1"] = "t06-structure/1"
    article_id: Id
    receipt_id: Id
    raw_text_id: Id
    cleaned_text_id: Id
    cleaned_sha256: str
    parser_version: VersionRef
    charset: str
    title: str
    roots: tuple[str, ...]
    blocks: tuple[Block, ...]
    headings: tuple[Heading, ...]
    list_items: tuple[ListItem, ...]
    links: tuple[Link, ...]
    exclusions: tuple[Exclusion, ...]
    language: str | None
    base_href: str | None
