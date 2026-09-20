"""Mechanical scope inference over an already validated T02 cohort."""

from binfocheck.domain.common import Contract
from binfocheck.domain.observations import SourceReference, TextUnit
from binfocheck.domain.text import SpanRef, TextRecord
from binfocheck.text.persistence import IndexManifest

from .config import RULES
from .hosts import HostAssessment


class ReferenceAssessment(Contract):
    reference_id: str
    host: HostAssessment
    marker: SpanRef | None
    scope: SpanRef | None
    clear: bool
    reason: str


def intersects(a: SpanRef, b: SpanRef) -> bool:
    return a.text_id == b.text_id and a.start < b.end and b.start < a.end


def contains(outer: SpanRef, inner: SpanRef) -> bool:
    return outer.text_id == inner.text_id and outer.start <= inner.start < inner.end <= outer.end


def covers(target: SpanRef, scopes: tuple[SpanRef, ...], answer: TextRecord) -> bool:
    """Every non-whitespace original code point must be covered; no text rewriting."""
    cursor = target.start
    for span in sorted(scopes, key=lambda s: (s.start, s.end)):
        if span.text_id != target.text_id or span.end <= cursor or span.start >= target.end:
            continue
        if any(not c.isspace() for c in answer.text[cursor : min(span.start, target.end)]):
            return False
        cursor = max(cursor, min(span.end, target.end))
    return not any(not c.isspace() for c in answer.text[cursor : target.end])


def supported(unit: TextUnit, references: tuple[SourceReference, ...]) -> bool:
    """Only captured markers are exempt from conservative unsupported-markup checks."""
    cursor = unit.span.start
    fragments: list[str] = []
    for ref in references:
        span = ref.citation_span
        if span and contains(unit.span, span):
            if span.start < cursor:
                return False
            fragments.append(
                unit.span.exact_text[cursor - unit.span.start : span.start - unit.span.start]
            )
            cursor = span.end
    fragments.append(unit.span.exact_text[cursor - unit.span.start :])
    remainder = "".join(fragments)
    return not any(c in remainder for c in RULES.unsupported_characters)


def infer_scope(
    ref: SourceReference,
    references: tuple[SourceReference, ...],
    units: tuple[TextUnit, ...],
    manifest: IndexManifest,
    answer: TextRecord,
    host: HostAssessment,
    evidence_reason: str | None,
) -> ReferenceAssessment:
    marker = ref.citation_span
    blocks = [u for u in units if u.unit_kind in {"paragraph", "bullet"}]
    block = next((u for u in blocks if marker and contains(u.span, marker)), None)
    sentence = next(
        (u for u in units if u.unit_kind == "sentence" and marker and contains(u.span, marker)),
        None,
    )

    def result(clear: bool, reason: str, scope: SpanRef | None) -> ReferenceAssessment:
        return ReferenceAssessment(
            reference_id=ref.id, host=host, marker=marker, scope=scope, clear=clear, reason=reason
        )

    if evidence_reason:
        return result(False, evidence_reason, block.span if block else None)
    if block is None or sentence is None or block.id in manifest.opaque_unit_ids:
        return result(False, "unestablished_scope", block.span if block else None)
    if not supported(sentence, references):
        return result(False, "unsupported_sentence_markup", block.span)
    local = [
        r.citation_span
        for r in references
        if r.citation_span and contains(sentence.span, r.citation_span)
    ]
    groups: list[list[SpanRef]] = []
    for span in local:
        if groups and all(
            c in RULES.horizontal_whitespace for c in answer.text[groups[-1][-1].end : span.start]
        ):
            groups[-1].append(span)
        else:
            groups.append([span])
    if len(groups) != 1:
        return result(False, "multiple_citation_groups", sentence.span)
    group = groups[0]
    before = answer.text[sentence.span.start : group[0].start]
    after = answer.text[group[-1].end : sentence.span.end]
    if not any(c.isalnum() for c in before):
        return result(False, "leading_citation", block.span)
    if any(not c.isspace() and c not in RULES.terminal_characters for c in after):
        return result(False, "internal_citation", sentence.span)
    siblings = [u for u in units if u.unit_kind == "sentence" and u.parent_unit_id == block.id]
    if len(siblings) > 1 and sentence.id == siblings[-1].id:
        return result(False, "ambiguous_paragraph_end", block.span)
    return result(True, "terminal_sentence_group", sentence.span)
