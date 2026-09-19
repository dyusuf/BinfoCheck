"""Minimal stage states and provider-independent execution port."""

import re
from dataclasses import dataclass
from typing import Protocol

from pydantic import JsonValue

from binfocheck.domain.common import ErrorDetail, VersionRef
from binfocheck.domain.decisions import DecisionRecord
from binfocheck.domain.observations import TextUnit
from binfocheck.domain.runs import RunManifest
from binfocheck.domain.text import SpanRef

from .artifacts import Binding
from .context import Group, Inputs


@dataclass(frozen=True)
class StageResult:
    artifact_id: str
    record: DecisionRecord | None
    error: ErrorDetail | None
    halt: bool = False


class StageModels(Protocol):
    configuration: VersionRef
    resource_version: VersionRef
    policy_version: VersionRef

    def validate_run(self, run: RunManifest) -> None: ...
    def reservation(self, stage: str) -> float: ...
    def call(
        self,
        run: RunManifest,
        stage: str,
        state: dict[str, JsonValue],
        input_ids: tuple[str, ...],
        scope: str,
        upstream: tuple[DecisionRecord, ...],
    ) -> StageResult: ...


def source(inputs: Inputs, group: Group) -> dict[str, JsonValue]:
    return {
        "text_id": inputs.answer.id,
        "start": group.start,
        "end": group.end,
        "text": inputs.answer.text[group.start : group.end],
        "unit_ids": [u.id for u in group.units],
    }


def question(inputs: Inputs) -> dict[str, JsonValue]:
    return {
        "capture_request_id": inputs.capture.id,
        "text": inputs.capture.query,
        "use": "reference_only",
    }


def unit_context(units: tuple[TextUnit, ...]) -> list[JsonValue]:
    return [
        {"unit_id": u.id, "start": u.span.start, "end": u.span.end, "text": u.span.exact_text}
        for u in units
    ]


REFERENCE = re.compile(
    r"\b(?:er|sie|es|dies(?:e[rsnm]?|er|es)?|dabei|dadurch|dort|deren|dessen)\b", re.I
)


def reference_context(
    inputs: Inputs, group: Group, working: str
) -> tuple[tuple[TextUnit, ...], bool]:
    # A conservative, frozen cue rule, not a semantic resolver or retrieval service.
    if not REFERENCE.search(working):
        return (), False
    heading_id = group.units[0].heading_unit_id
    preceding = [
        u
        for u in inputs.context
        if u.unit_kind == "sentence"
        and u.span.end <= group.start
        and u.heading_unit_id == heading_id
    ]
    if preceding:
        return (max(preceding, key=lambda u: u.span.end),), False
    headings = [
        u
        for u in inputs.context
        if u.unit_kind == "heading" and u.id == heading_id and u.span.end <= group.start
    ]
    if headings:
        return (max(headings, key=lambda u: u.span.end),), False
    # Internal antecedents are supplied already; do not add the question for them.
    internal = [u for u in group.units if u.unit_kind == "sentence"]
    leading = re.match(r"^(?:Er|Sie|Es|Dies(?:e[rsnm]?|er|es)?|Das)\b", working)
    return (), bool(leading and len(internal) <= 1 and inputs.capture.query.strip())


def working_state(
    inputs: Inputs,
    group: Group,
    working: str,
    context: tuple[TextUnit, ...] = (),
    use_question: bool = False,
) -> dict[str, JsonValue]:
    state: dict[str, JsonValue] = {"source": source(inputs, group)}
    if working != inputs.answer.text[group.start : group.end]:
        state["working_text"] = working
    if context:
        state["context"] = unit_context(context)
    if use_question:
        state["question"] = question(inputs)
    return state


def validation_state(
    inputs: Inputs, stage: str, claim: str, span: SpanRef, bindings: tuple[Binding, ...]
) -> tuple[dict[str, JsonValue], tuple[TextUnit, ...]]:
    state: dict[str, JsonValue] = {
        "normalized_claim": claim,
        "original_span": span.model_dump(mode="json"),
    }
    selected: dict[str, TextUnit] = {}
    if stage == "H.faithfulness":
        # Boundary sentence/heading context tests missing governing qualifications.
        for u in (*inputs.context, *inputs.units):
            if u.unit_kind == "sentence" and u.span.start < span.end and span.start < u.span.end:
                if u.span.start < span.start or u.span.end > span.end:
                    selected[u.id] = u
        heading_ids = {
            u.heading_unit_id
            for u in inputs.units
            if u.unit_kind == "sentence" and u.span.start < span.end and span.start < u.span.end
        }
        for u in inputs.context:
            if u.id in heading_ids and re.search(
                r"\b(bei|wenn|nur|für|unter|ohne)\b", u.span.exact_text, re.I
            ):
                selected[u.id] = u
        for b in bindings:
            for u in inputs.context:
                if u.id in b.answer_context_unit_ids:
                    selected[u.id] = u
    context = tuple(sorted(selected.values(), key=lambda u: u.order))
    if context:
        state["context"] = unit_context(context)
    if bindings:
        state["clarification_bindings"] = [b.model_dump(mode="json") for b in bindings]
    if any(b.question_reference_used for b in bindings):
        state["question"] = question(inputs)
    return state, context
