"""T04 audit envelopes and untrusted generation proposals, not domain replacements."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from binfocheck.domain.common import Contract, ErrorDetail, Id
from binfocheck.domain.interfaces import ExtractionResult


class Anchor(Contract):
    quote: Annotated[str, Field(pattern=r"\S")]
    source_unit_ids: Annotated[tuple[Id, ...], Field(min_length=1)]
    start: Annotated[int, Field(ge=0)] | None
    end: Annotated[int, Field(ge=0)] | None

    @model_validator(mode="after")
    def paired(self) -> Self:
        if (self.start is None) != (self.end is None):
            raise ValueError("paired_offsets_required")
        return self


class Binding(Contract):
    reference: Annotated[str, Field(pattern=r"\S")]
    resolved_reference: Annotated[str, Field(pattern=r"\S")]
    answer_context_unit_ids: tuple[Id, ...]
    question_reference_used: bool


class Candidate(Contract):
    normalized_claim: Annotated[str, Field(pattern=r"\S")]
    anchor: Anchor
    required_support: Annotated[tuple[Anchor, ...], Field(max_length=8)]
    consumed_binding_indices: Annotated[tuple[int, ...], Field(max_length=8)]


class Mixed(Contract):
    status: Literal["derived", "unresolved"]
    factual_text: str | None
    anchors: Annotated[tuple[Anchor, ...], Field(max_length=4)]
    excluded_quotes: Annotated[tuple[Anchor, ...], Field(max_length=4)]
    reason_code: Literal["none", "cannot_separate"]

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.status == "derived":
            if (
                not self.factual_text
                or not self.factual_text.strip()
                or not self.anchors
                or self.reason_code != "none"
            ):
                raise ValueError("invalid_derived_output")
        elif self.factual_text is not None or self.reason_code != "cannot_separate":
            raise ValueError("invalid_unresolved_output")
        return self


class Clarified(Contract):
    status: Literal["clarified", "unresolved"]
    clarified_text: str | None
    anchors: Annotated[tuple[Anchor, ...], Field(max_length=4)]
    bindings: Annotated[tuple[Binding, ...], Field(max_length=8)]
    reason_code: Literal["none", "insufficient_context"]

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.status == "clarified":
            if (
                not self.clarified_text
                or not self.clarified_text.strip()
                or not self.anchors
                or not self.bindings
                or self.reason_code != "none"
            ):
                raise ValueError("invalid_clarified_output")
        elif self.clarified_text is not None or self.reason_code != "insufficient_context":
            raise ValueError("invalid_unresolved_output")
        return self


class Decomposed(Contract):
    status: Literal["candidates", "unresolved"]
    candidates: Annotated[tuple[Candidate, ...], Field(max_length=4)]
    reason_code: Literal["none", "cannot_extract", "candidate_limit"]

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.status == "candidates":
            if not self.candidates or self.reason_code != "none":
                raise ValueError("invalid_candidates")
        elif self.candidates or self.reason_code == "none":
            raise ValueError("invalid_unresolved_output")
        return self


class StageEvidence(Contract):
    version: Literal["1"] = "1"
    stage_key: Id
    stage: str
    state_artifact_id: Id
    prepared_record_id: Id | None
    model_work_key: str | None
    outbound_sha256: str | None
    decision_ids: tuple[Id, ...]
    error: ErrorDetail | None
    halt: bool = False
    reservation_id: Id | None = None


class Accounting(Contract):
    target_unit_id: Id
    group_ids: tuple[Id, ...]
    terminal_claim_ids: tuple[Id, ...]
    terminal_issue_ids: tuple[Id, ...]


class FinalAudit(Contract):
    version: Literal["1"] = "1"
    work_key: Id
    extraction_result: ExtractionResult
    target_accounting: tuple[Accounting, ...]
    stage_artifact_ids: tuple[Id, ...]
    assessment_state: Literal["complete", "partial_failure", "all_targets_failed"]
