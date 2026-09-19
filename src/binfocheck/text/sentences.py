"""Blank German tokenizer/Sentencizer plus version-one mechanical protections."""

import re
from importlib.metadata import version

import spacy
from spacy.language import Language

from .config import SPACY_VERSION
from .errors import TextError

ABBREVIATION = re.compile(
    r"\b(?:z\.\s*B\.|d\.\s*h\.|u\.\s*a\.|Dr\.|Prof\.|bzw\.|ggf\.|ca\.|Nr\.|vgl\.|Abb\.)",
    re.IGNORECASE,
)
CONDITIONAL = re.compile(r"\b(?:usw|etc)\.", re.IGNORECASE)
NUMBER = re.compile(r"\b\d+(?:[.,]\d+)+")
ORDINAL = re.compile(
    r"\b\d+\.(?=\s+(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|Tag|Woche|Monat|Jahr)\b)"
)
URL = re.compile(r"https?://[^\s<>]+")
CLOSERS = "\"'”’»“*_)]"


def markdown_regions(text: str) -> tuple[list[tuple[int, int]], bool]:
    """Balanced inline links/backticks only; uncertain markup stays one exact span."""
    regions: list[tuple[int, int]] = []
    i = 0
    while i < len(text):
        if text[i] == "\\":
            if i + 1 < len(text):
                regions.append((i, i + 2))
            i += 2
            continue
        if text[i] == "`":
            j = i
            while j < len(text) and text[j] == "`":
                j += 1
            end = text.find(text[i:j], j)
            if end == -1:
                return regions, False
            regions.append((i, end + j - i))
            i = end + j - i
            continue
        if text[i] == "[":
            start = i
            depth = 1
            i += 1
            while i < len(text) and depth:
                if text[i] == "\\":
                    i += 2
                    continue
                depth += (text[i] == "[") - (text[i] == "]")
                i += 1
            if depth or i >= len(text) or text[i] != "(":
                return regions, False
            depth = 1
            i += 1
            while i < len(text) and depth:
                if text[i] == "\\":
                    i += 2
                    continue
                depth += (text[i] == "(") - (text[i] == ")")
                i += 1
            if depth:
                return regions, False
            regions.append((start, i))
            continue
        i += 1
    return regions, True


def trimmed(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


class GermanSentenceSegmenter:
    def __init__(self) -> None:
        if version("spacy") != SPACY_VERSION:
            raise TextError("tokenizer_version_mismatch")
        self.nlp: Language = spacy.blank("de")
        self.nlp.add_pipe("sentencizer", config={"punct_chars": [".", "!", "?", "…", "..."]})

    def spans(self, text: str, start: int, end: int) -> tuple[tuple[int, int], ...]:
        segment = text[start:end]
        markup, supported = markdown_regions(segment)
        if not supported:
            left, right = trimmed(text, start, end)
            return ((left, right),) if left < right else ()
        doc = self.nlp(segment)
        if doc.text != segment:
            raise TextError("tokenizer_changed_text")
        starts = {sentence.start_char for sentence in doc.sents}
        protected = list(markup)
        for pattern in (ABBREVIATION, NUMBER, ORDINAL):
            protected.extend((m.start(), m.end()) for m in pattern.finditer(segment))
        protected.extend(
            (m.start(), m.end())
            for m in URL.finditer(segment)
            if not any(a <= m.start() < b for a, b in markup)
        )
        for match in CONDITIONAL.finditer(segment):
            following = segment[match.end() :].lstrip()
            if following and following[0].islower():
                protected.append((match.start(), match.end()))
        cuts: set[int] = {0, len(segment)}
        for punctuation in re.finditer(r"[.!?…]+", segment):
            if any(a <= punctuation.start() < b for a, b in protected):
                continue
            cursor = punctuation.end()
            while cursor < len(segment) and segment[cursor] in CLOSERS:
                cursor += 1
            if cursor < len(segment) and not segment[cursor].isspace() and segment[cursor] != "[":
                continue
            while cursor < len(segment) and segment[cursor].isspace():
                cursor += 1
            candidate = cursor
            # Attach complete trailing link/numbered-marker syntax, without citation routing.
            while (
                link_end := next((b for a, b in markup if a == cursor and segment[a] == "["), None)
            ) is not None:
                cursor = link_end
                while cursor < len(segment) and segment[cursor] in CLOSERS + ".!?…":
                    cursor += 1
                while cursor < len(segment) and segment[cursor].isspace():
                    cursor += 1
            # spaCy candidates plus explicit period-at-token-end rules (e.g. usw.).
            explicit = bool(
                re.search(r"(?:\b(?:usw|etc)|\d)\.$", segment[: punctuation.end()], re.IGNORECASE)
            )
            if (
                explicit
                or candidate in starts
                or cursor in starts
                or any(punctuation.end() <= point <= cursor for point in starts)
            ):
                cuts.add(cursor)
        ordered = sorted(cuts)
        spans = [
            trimmed(text, start + a, start + b) for a, b in zip(ordered, ordered[1:], strict=False)
        ]
        return tuple((a, b) for a, b in spans if a < b)
