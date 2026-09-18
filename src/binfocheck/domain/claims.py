from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .common import CitationStatus, DerivedRecord, Id, NonEmpty, VersionRef
from .text import SpanRef


class Claim(DerivedRecord):
    kind: Literal["claim"] = "claim"
    observation_id: Id
    normalized_claim: NonEmpty
    language: Literal["de"] = "de"
    original_span: SpanRef
    context_unit_ids: Annotated[tuple[Id, ...], Field(min_length=1)]
    decision_ids: tuple[Id, ...]
    claim_group_id: Id


class ExtractionIssue(DerivedRecord):
    kind: Literal["extraction_issue"] = "extraction_issue"
    observation_id: Id
    issue: Literal["invalid", "unlocatable", "ambiguous", "unresolved", "excluded", "failed"]
    reason: NonEmpty
    proposed_claim: str | None
    original_span: SpanRef | None
    context_unit_ids: tuple[Id, ...]
    decision_ids: tuple[Id, ...]


class CitationAssociation(DerivedRecord):
    kind: Literal["citation_association"] = "citation_association"
    observation_id: Id
    claim_id: Id
    reference_ids: tuple[Id, ...]
    status: CitationStatus
    scope_assessable: bool
    rule_version: VersionRef
    evidence_spans: tuple[SpanRef, ...]
    reason: NonEmpty

    @model_validator(mode="after")
    def citation_state(self) -> Self:
        if self.status == CitationStatus.YES and not self.reference_ids:
            raise ValueError("citation_yes_requires_references")
        if self.status != CitationStatus.UNCLEAR and not self.scope_assessable:
            raise ValueError("definite_citation_status_requires_assessable_scope")
        return self
