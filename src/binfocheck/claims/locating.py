"""Exact, uniquely located minimal envelopes of proposed original support."""

from binfocheck.domain.text import SpanRef

from .artifacts import Anchor, Candidate
from .context import Group, Inputs
from .errors import ExtractionError, check


def locate(anchor: Anchor, inputs: Inputs, group: Group) -> SpanRef:
    units = {u.id: u for u in group.units}
    check(
        len(set(anchor.source_unit_ids)) == len(anchor.source_unit_ids)
        and all(id in units for id in anchor.source_unit_ids),
        "invalid_source_units",
    )
    selected = [units[id] for id in anchor.source_unit_ids]
    check(selected == sorted(selected, key=lambda u: u.order), "invalid_source_order")
    low, high = min(u.span.start for u in selected), max(u.span.end for u in selected)
    text = inputs.answer.text
    if anchor.start is None:
        positions: list[int] = []
        cursor = max(group.start, low)
        while (at := text.find(anchor.quote, cursor, min(group.end, high))) >= 0:
            positions.append(at)
            cursor = at + 1
        if not positions:
            raise ExtractionError("quote_missing")
        if len(positions) != 1:
            raise ExtractionError("location_ambiguous")
        start = positions[0]
        end = start + len(anchor.quote)
    else:
        start, end = anchor.start, anchor.end
        check(end is not None, "invalid_offsets")
        assert end is not None
    check(group.start <= low <= start < end <= high <= group.end, "invalid_offsets")
    check(text[start:end] == anchor.quote, "quote_missing")
    check(all(u.span.start < end and start < u.span.end for u in selected), "invalid_source_units")
    # All source-bearing sentence/opaque units crossed by this quote must be named,
    # unless a supplied parent unit itself contains the complete quote.
    containers = [u for u in selected if u.span.start <= start and end <= u.span.end]
    if not containers:
        crossed = {
            u.id
            for u in group.units
            if u.unit_kind == "sentence" and u.span.start < end and start < u.span.end
        }
        check(crossed.issubset(anchor.source_unit_ids), "incomplete_source_units")
    source_id = (
        min(containers, key=lambda u: (u.span.end - u.span.start, u.order)).id
        if containers
        else None
    )
    return SpanRef(
        text_id=inputs.answer.id,
        start=start,
        end=end,
        exact_text=text[start:end],
        source_unit_id=source_id,
    )


def supporting_span(candidate: Candidate, inputs: Inputs, group: Group) -> SpanRef:
    parts = [locate(a, inputs, group) for a in (candidate.anchor, *candidate.required_support)]
    start, end = min(p.start for p in parts), max(p.end for p in parts)
    ids = {id for a in (candidate.anchor, *candidate.required_support) for id in a.source_unit_ids}
    containers = [
        u for u in group.units if u.id in ids and u.span.start <= start and end <= u.span.end
    ]
    source_id = (
        min(containers, key=lambda u: (u.span.end - u.span.start, u.order)).id
        if containers
        else None
    )
    return SpanRef(
        text_id=inputs.answer.id,
        start=start,
        end=end,
        exact_text=inputs.answer.text[start:end],
        source_unit_id=source_id,
    )
