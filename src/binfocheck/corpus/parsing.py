"""Bounded HTML structure extraction, never relevance extraction or rewriting."""

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Comment, Tag
from bs4.element import NavigableString

from binfocheck.domain.text import SpanRef

from .config import ParserConfig, digest, identity
from .errors import CorpusError, check
from .structure import Block, Exclusion, Heading, Link, ListItem, Structure

SPACE = " \t\r\n\f"
INLINE = {"a", "em", "strong", "b", "i", "u", "span", "sup", "sub", "small", "abbr", "br", "code"}
WRAPPERS = {"article", "div", "section", "header", "footer", "aside", "details", "figure"}


def locator(tag: Tag) -> str:
    parts: list[str] = []
    cursor: Tag | None = tag
    while cursor is not None and cursor.name != "[document]":
        siblings = list(cursor.previous_siblings)
        number = 1 + sum(isinstance(s, Tag) and s.name == cursor.name for s in siblings)
        parts.append(f"{cursor.name}[{number}]")
        cursor = cursor.parent
    return "/" + "/".join(reversed(parts))


@dataclass
class Rendered:
    text: str
    links: list[tuple[int, int, Tag]]
    items: list[tuple[int, int, int, bool, str, Tag]]


def inline(
    tag: Tag, pre: bool = False, children: list[Tag | NavigableString] | None = None
) -> Rendered:
    # Atoms retain link membership through whitespace processing, without quote searches.
    atoms: list[tuple[str, int | None, bool]] = []
    anchors: list[Tag] = []

    def visit(node: Tag | NavigableString, anchor: int | None = None) -> None:
        if isinstance(node, Comment):
            return
        if isinstance(node, NavigableString):
            atoms.extend((c, anchor, False) for c in str(node))
            return
        check(node is tag or node.name in INLINE, "unsupported_inline_structure")
        if node.name == "a":
            anchor = len(anchors)
            anchors.append(node)
        if node.name == "br":
            atoms.append(("\n", anchor, True))
        else:
            for child in node.children:
                if isinstance(child, (Tag, NavigableString)):
                    visit(child, anchor)

    if children is None:
        visit(tag)
    else:
        for child in children:
            visit(child)
    normalized: list[tuple[str, int | None]] = []
    for char, anchor, explicit_break in atoms:
        if explicit_break:
            if normalized and normalized[-1][0] == " ":
                normalized.pop()
            normalized.append(("\n", anchor))
        elif not pre and char in SPACE:
            if normalized and normalized[-1][0] not in SPACE:
                normalized.append((" ", anchor))
        else:
            normalized.append((char, anchor))
    if not pre and normalized and normalized[-1][0] == " ":
        normalized.pop()
    positions: dict[int, list[int]] = {}
    for index, (_, anchor) in enumerate(normalized):
        if anchor is not None:
            positions.setdefault(anchor, []).append(index)
    links: list[tuple[int, int, Tag]] = []
    for index, anchor in enumerate(anchors):
        indexes = positions.get(index, [])
        links.append((indexes[0] if indexes else 0, indexes[-1] + 1 if indexes else 0, anchor))
    return Rendered("".join(c for c, _ in normalized), links, [])


def render_list(tag: Tag, depth: int = 0) -> Rendered:
    result = Rendered("", [], [])
    ordered = tag.name == "ol"
    check(
        not tag.has_attr("reversed") and str(tag.get("type", "1")) == "1",
        "unsupported_list_numbering",
    )
    try:
        counter = int(str(tag.get("start", "1")))
    except ValueError:
        raise CorpusError("invalid_list_number") from None
    for child in tag.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            check(not str(child).strip(), "unsupported_list_content")
            continue
        if not isinstance(child, Tag):
            continue
        check(child.name == "li", "unsupported_list_content")
        if child.has_attr("value"):
            try:
                counter = int(str(child["value"]))
            except ValueError:
                raise CorpusError("invalid_list_number") from None
        marker = f"{counter}." if ordered else "-"
        counter += 1
        if result.text:
            result.text += "\n"
        start = len(result.text)
        result.text += "  " * depth + marker + " "
        # Keep direct inline runs together, with nested lists in original order.
        temporary: list[Tag | NavigableString] = []

        def flush(tag: Tag = child, pending: list[Tag | NavigableString] = temporary) -> None:
            rendered = inline(tag, children=pending)
            if rendered.text and result.text and not result.text.endswith((" ", "\n")):
                result.text += " "
            offset = len(result.text)
            result.text += rendered.text
            result.links.extend((a + offset, b + offset, t) for a, b, t in rendered.links)
            pending.clear()

        for node in child.contents:
            if isinstance(node, Tag) and node.name in {"ul", "ol"}:
                flush()
                nested = render_list(node, depth + 1)
                result.text += "\n"
                offset = len(result.text)
                result.text += nested.text
                result.links.extend((a + offset, b + offset, t) for a, b, t in nested.links)
                result.items.extend(
                    (a + offset, b + offset, d, o, m, t) for a, b, d, o, m, t in nested.items
                )
            elif isinstance(node, Tag) and node.name == "p":
                flush()
                if not result.text.endswith(" "):
                    result.text += " "
                piece = inline(node)
                offset = len(result.text)
                result.text += piece.text
                result.links.extend((a + offset, b + offset, t) for a, b, t in piece.links)
            elif isinstance(node, (Tag, NavigableString)):
                temporary.append(node)
        flush()
        result.items.append((start, len(result.text), depth, ordered, marker, child))
    return result


def parse_html(
    html: str,
    url: str,
    article_id: str,
    receipt_id: str,
    raw_text_id: str,
    charset: str,
    config: ParserConfig,
) -> tuple[str, Structure]:
    soup = BeautifulSoup(html, "html5lib")
    tags = list(soup.find_all(True))
    check(len(tags) <= config.max_nodes, "html_node_limit")
    for tag in tags:
        check(sum(1 for _ in tag.parents) <= config.max_depth, "html_depth_limit")
    locations = {id(tag): locator(tag) for tag in tags}

    def source_location(tag: Tag) -> str:
        return locations[id(tag)]

    language = str(soup.html.get("lang")) if soup.html and soup.html.get("lang") else None
    check(language is None or language.lower().split("-")[0] == "de", "non_german_page")
    roots: list[Tag] = []
    for selector in config.roots:
        matches = soup.select(selector)
        check(len(matches) == 1, "ambiguous_article_root")
        roots.append(matches[0])
    check(bool(roots), "missing_article_root")
    check(len({id(t) for t in roots}) == len(roots), "overlapping_article_roots")
    for root in roots:
        check(not any(p in roots for p in root.parents), "overlapping_article_roots")
    # Selected roots must retain document order, independent of selector order.
    roots.sort(key=lambda t: next(i for i, candidate in enumerate(tags) if candidate is t))
    root_locations = tuple(source_location(r) for r in roots)
    exclusions: list[Exclusion] = []
    for root in roots:
        for selector in config.chrome:
            for removed in list(root.select(selector)):
                if removed.parent is None:
                    continue
                check(
                    not removed.select(config.protected)
                    and not removed.css.match(config.protected),
                    "chrome_contains_article_reference",
                )
                exclusions.append(Exclusion(locator=source_location(removed), rule=selector))
                removed.decompose()
    gathered: list[tuple[str, Tag, int]] = []

    def walk(tag: Tag) -> None:
        if re.fullmatch(r"h[1-6]", tag.name):
            gathered.append(("heading", tag, int(tag.name[1])))
        elif tag.css.match(config.faq_heading) or tag.name == "summary":
            gathered.append(("heading", tag, 2))
        elif tag.name in {"p", "figcaption"}:
            gathered.append(("paragraph", tag, 0))
        elif tag.name in {"ul", "ol"}:
            gathered.append(("list", tag, 0))
        elif tag.name == "pre":
            gathered.append(("pre", tag, 0))
        elif tag.name in WRAPPERS:
            for child in tag.children:
                if isinstance(child, Comment):
                    continue
                if isinstance(child, Tag):
                    walk(child)
                elif isinstance(child, NavigableString):
                    check(not str(child).strip(), "unwrapped_article_text")
        else:
            # No silent text loss or generic fallback for unseen structures.
            raise CorpusError("unsupported_article_structure")
        check(len(gathered) <= config.max_blocks, "article_block_limit")

    for root in roots:
        walk(root)
    rendered: list[tuple[str, Tag, int, int, int, Rendered]] = []
    text = ""
    for kind, tag, level in gathered:
        part = render_list(tag) if kind == "list" else inline(tag, pre=kind == "pre")
        if not part.text.strip():
            check(not part.links, "empty_link_block")
            continue
        if text:
            text += "\n\n"
        start = len(text)
        text += part.text
        check(len(text) <= config.max_characters, "article_text_limit")
        rendered.append((kind, tag, level, start, len(text), part))
    check(bool(text) and any(k != "heading" for k, *_ in rendered), "empty_article")
    titles = [
        part.text for kind, _, level, _, _, part in rendered if kind == "heading" and level == 1
    ]
    check(len(titles) == 1, "missing_or_ambiguous_title")
    check(titles[0].strip() not in config.unusable_titles, "unusable_page_title")
    text_id = identity(
        "clean-text", [raw_text_id, config.version().model_dump(mode="json"), digest(text.encode())]
    )

    def span(start: int, end: int) -> SpanRef:
        return SpanRef(text_id=text_id, start=start, end=end, exact_text=text[start:end])

    blocks: list[Block] = []
    headings: list[Heading] = []
    links: list[Link] = []
    items: list[ListItem] = []
    stack: list[int] = []
    for kind, tag, level, start, end, part in rendered:
        if kind == "heading":
            while stack and headings[stack[-1]].level >= level:
                old = stack.pop()
                headings[old] = headings[old].model_copy(update={"section_end": start})
            headings.append(
                Heading(
                    span=span(start, end),
                    level=level,
                    parent_index=stack[-1] if stack else None,
                    section_end=len(text),
                )
            )
            stack.append(len(headings) - 1)
        block = Block.model_validate(
            dict(
                kind=kind,
                span=span(start, end),
                locator=source_location(tag),
                heading_indices=tuple(stack),
            )
        )
        for a, b, anchor in part.links:
            href = str(anchor.get("href", ""))
            try:
                resolved = urljoin(url, href)
                navigable = urlsplit(resolved).scheme in {"https", "http"}
            except ValueError:
                resolved, navigable = href, False
            links.append(
                Link(
                    span=span(start + a, start + b) if b > a else None,
                    locator=source_location(anchor),
                    href=href,
                    resolved=resolved,
                    navigable=navigable,
                    block_index=len(blocks),
                )
            )
        for a, b, depth, ordered, marker, item in part.items:
            items.append(
                ListItem(
                    span=span(start + a, start + b),
                    depth=depth,
                    ordered=ordered,
                    marker=marker,
                    locator=source_location(item),
                )
            )
        blocks.append(block)
    base = soup.find("base")
    return text, Structure(
        article_id=article_id,
        receipt_id=receipt_id,
        raw_text_id=raw_text_id,
        cleaned_text_id=text_id,
        cleaned_sha256=digest(text.encode()),
        parser_version=config.version(),
        charset=charset,
        title=titles[0],
        roots=root_locations,
        blocks=tuple(blocks),
        headings=tuple(headings),
        list_items=tuple(items),
        links=tuple(links),
        exclusions=tuple(exclusions),
        language=language,
        base_href=str(base.get("href")) if base else None,
    )
