"""Bounded Markdown recognition on original character ranges, not a renderer."""

import re
from dataclasses import dataclass
from typing import Literal

ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+|$)")
SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
LIST = re.compile(r"^( {0,3})(?:[-+*]|[0-9]{1,9}[.)])[ \t]+")
NESTED_LIST = re.compile(r"^\s+(?:[-+*]|[0-9]+[.)])[ \t]+")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
THEMATIC = re.compile(r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")


@dataclass(frozen=True)
class Line:
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Block:
    kind: Literal["heading", "paragraph", "bullet"]
    start: int
    end: int
    content_start: int
    level: int | None = None
    opaque: bool = False


def lines(text: str) -> list[Line]:
    return [
        Line(m.start(), m.start() + len(m.group().rstrip("\r\n")), m.group().rstrip("\r\n"))
        for m in re.finditer(r"[^\r\n]*(?:\r\n|\r|\n|$)", text)
        if m.end() > m.start()
    ]


def opaque_line(line: str) -> bool:
    return bool(
        FENCE.match(line)
        or THEMATIC.match(line)
        or "|" in line
        or line.lstrip().startswith(("<", ">"))
        or line.startswith(("    ", "\t"))
    )


def scan(text: str) -> tuple[Block, ...]:
    source = lines(text)
    blocks: list[Block] = []
    i = 0
    while i < len(source):
        first = source[i]
        if not first.text.strip():
            i += 1
            continue
        fence = FENCE.match(first.text)
        html = re.match(r"^ {0,3}<([A-Za-z][A-Za-z0-9-]*)(?:\s|>)", first.text)
        comment = first.text.lstrip().startswith("<!--")
        if html or comment:
            # No HTML parsing: keep an entire raw region opaque, including blank
            # lines. Unclosed or ambiguous raw regions conservatively consume EOF.
            closing_html = "-->" if comment else "</" + html.group(1).lower() + ">" if html else ""
            j = i
            while j < len(source) and closing_html not in source[j].text.lower():
                j += 1
            j = min(j + 1, len(source))
            blocks.append(
                Block("paragraph", first.start, source[j - 1].end, first.start, opaque=True)
            )
            i = j
            continue
        if fence:
            marker = fence.group(1)
            j = i + 1
            closing = re.compile(
                r"^ {0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}[ \t]*$"
            )
            while j < len(source) and not closing.fullmatch(source[j].text):
                j += 1
            j = min(j + 1, len(source))
            blocks.append(
                Block("paragraph", first.start, source[j - 1].end, first.start, opaque=True)
            )
            i = j
            continue
        heading = ATX.match(first.text)
        if heading:
            blocks.append(
                Block("heading", first.start, first.end, first.start, len(heading.group(1)))
            )
            i += 1
            continue
        if (
            i + 1 < len(source)
            and (underline := SETEXT.fullmatch(source[i + 1].text))
            and not LIST.match(first.text)
            and not opaque_line(first.text)
        ):
            level = 1 if underline.group(1).startswith("=") else 2
            blocks.append(Block("heading", first.start, source[i + 1].end, first.start, level))
            i += 2
            continue
        marker = LIST.match(first.text)
        if marker and not THEMATIC.fullmatch(first.text):
            # Flat items and indented continuations are supported. A nested list makes
            # this entire contiguous list opaque, rather than inventing a hierarchy.
            j = i + 1
            while j < len(source) and source[j].text.strip() and not ATX.match(source[j].text):
                if not LIST.match(source[j].text) and not source[j].text.startswith((" ", "\t")):
                    break
                j += 1
            group = source[i:j]
            nested = any(
                NESTED_LIST.match(line.text)
                and len(line.text) - len(line.text.lstrip()) > len(marker.group(1))
                for line in group[1:]
            )
            ambiguous = any(
                "\t" in line.text[: len(line.text) - len(line.text.lstrip())]
                or opaque_line(LIST.sub("", line.text).lstrip())
                for line in group
            )
            if nested or ambiguous:
                blocks.append(
                    Block("paragraph", first.start, group[-1].end, first.start, opaque=True)
                )
            else:
                k = 0
                while k < len(group):
                    item = LIST.match(group[k].text)
                    assert item is not None
                    end = k + 1
                    while end < len(group) and not LIST.match(group[end].text):
                        end += 1
                    blocks.append(
                        Block(
                            "bullet",
                            group[k].start,
                            group[end - 1].end,
                            group[k].start + item.end(),
                        )
                    )
                    k = end
            i = j
            continue
        opaque = opaque_line(first.text)
        j = i + 1
        while j < len(source) and source[j].text.strip():
            if not opaque and (
                ATX.match(source[j].text)
                or LIST.match(source[j].text)
                or opaque_line(source[j].text)
            ):
                break
            if not opaque and j + 1 < len(source) and SETEXT.fullmatch(source[j + 1].text):
                break
            j += 1
        blocks.append(
            Block("paragraph", first.start, source[j - 1].end, first.start, opaque=opaque)
        )
        i = j
    return tuple(blocks)
