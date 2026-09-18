from typing import Literal, Self

from pydantic import model_validator

from .common import (
    Available,
    Category,
    CorrespondenceStatus,
    DerivedRecord,
    FindingStatus,
    Id,
    NonEmpty,
    Score,
)


class AlternativeInspection(DerivedRecord):
    kind: Literal["alternative_inspection"] = "alternative_inspection"
    observation_id: Id
    claim_id: Id
    source_reference_id: Id
    excerpt_text_id: Id | None
    state: Literal["inspected", "unassessed"]
    correspondence: CorrespondenceStatus
    decision_id: Id | None
    coverage: Literal["assessable", "insufficient"]
    coverage_reason: NonEmpty
    duplicate_group: Id | None

    @model_validator(mode="after")
    def inspection_state(self) -> Self:
        if self.state == "inspected":
            if self.excerpt_text_id is None or self.decision_id is None:
                raise ValueError("inspection_requires_excerpt_and_decision")
            if self.correspondence == CorrespondenceStatus.NOT_ASSESSED:
                raise ValueError("inspected_cannot_be_not_assessed")
        elif self.correspondence != CorrespondenceStatus.NOT_ASSESSED or self.decision_id:
            raise ValueError("unassessed_cannot_have_correspondence_decision")
        if self.state == "unassessed" and self.coverage == "assessable":
            raise ValueError("unassessed_coverage_is_insufficient")
        return self


class Finding(DerivedRecord):
    kind: Literal["finding"] = "finding"
    observation_id: Id
    claim_id: Id
    citation_association_id: Id
    status: FindingStatus
    category: Category | None
    candidate_pair_ids: tuple[Id, ...]
    decision_ids: tuple[Id, ...]
    alternative_inspection_ids: Available[tuple[Id, ...]]
    provisional_scores: Available[dict[str, Score]]
    reason_codes: tuple[NonEmpty, ...]
    supersedes_finding_id: Id | None = None

    @model_validator(mode="after")
    def category_state(self) -> Self:
        if (self.status == FindingStatus.CATEGORIZED) != (self.category is not None):
            raise ValueError("category_requires_categorized_status_and_vice_versa")
        if self.supersedes_finding_id == self.id:
            raise ValueError("finding_cannot_supersede_itself")
        return self
