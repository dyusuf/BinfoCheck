"""Strict T04 settings; theoretical bounds do not authorize live requests."""

from typing import Annotated, Self

from pydantic import Field, model_validator

from binfocheck.domain.common import Contract, Id, Settings, VersionRef
from binfocheck.text.config import ContextSettings


class Limits(Contract):
    max_groups: Annotated[int, Field(ge=1, le=20)] = 20
    max_candidates_per_group: Annotated[int, Field(ge=1, le=4)] = 4
    max_model_calls: Annotated[int, Field(ge=0, le=340)] = 340
    max_decision_calls: Annotated[int, Field(ge=0, le=280)] = 280
    max_generation_calls: Annotated[int, Field(ge=0, le=60)] = 60


class ExtractionSettings(Contract):
    index_artifact_id: Id
    target_unit_ids: Annotated[tuple[Id, ...], Field(min_length=1, max_length=20)]
    context_settings: ContextSettings
    policy_version: VersionRef
    resource_bundle_version: VersionRef
    limits: Limits = Limits()

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if (
            len(set(self.target_unit_ids)) != len(self.target_unit_ids)
            or self.index_artifact_id != self.context_settings.index_artifact_id
        ):
            raise ValueError("invalid_targets_or_index")
        return self

    def envelope(self, configuration: VersionRef) -> Settings:
        return Settings(version=configuration, values=self.model_dump(mode="json"))
