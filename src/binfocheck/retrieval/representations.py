"""Retrieval representations never replace source text or source offsets."""

import re
import unicodedata
from functools import lru_cache

import spacy
from spacy.language import Language

from binfocheck.domain.claims import Claim
from binfocheck.domain.corpus import Passage

from .config import INSTRUCTION

PROTECTED = re.compile(
    r"(?<!\w)(?:mmol/l|mg/dl)(?!\w)|(?<!\w)\d+(?:[.,]\d+)*(?!\w)|<=|>=|[<>≤≥%]", re.IGNORECASE
)


@lru_cache(maxsize=1)
def tokenizer() -> Language:
    return spacy.blank("de")


def tokens(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFC", text).lower()
    result: list[str] = []
    cursor = 0
    for match in PROTECTED.finditer(normalized):
        result.extend(
            t.text
            for t in tokenizer().make_doc(normalized[cursor : match.start()])
            if not t.is_space and not t.is_punct
        )
        result.append(match.group())
        cursor = match.end()
    result.extend(
        t.text
        for t in tokenizer().make_doc(normalized[cursor:])
        if not t.is_space and not t.is_punct
    )
    return tuple(result)


def query_text(claim: Claim) -> str:
    return f"Instruct: {INSTRUCTION}\nQuery: {claim.normalized_claim}"


def document_text(passage: Passage) -> str:
    headings = "\n".join(span.exact_text for span in passage.heading_spans)
    return headings + "\n\n" + passage.span.exact_text if headings else passage.span.exact_text


def context_ids(target: Passage, passages: tuple[Passage, ...]) -> tuple[str, ...]:
    article = sorted(
        (p for p in passages if p.article_version_id == target.article_version_id),
        key=lambda p: p.order,
    )
    position = next(i for i, p in enumerate(article) if p.id == target.id)
    chosen = [target]
    for i in (position - 1, position + 1):
        if 0 <= i < len(article) and article[i].heading_spans == target.heading_spans:
            chosen.append(article[i])
    return tuple(p.id for p in sorted(chosen, key=lambda p: p.order))
