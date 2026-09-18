from datetime import datetime
from typing import Literal, Self

from pydantic import field_validator, model_validator

from .common import Digest, Id, NonEmpty, NonNegative, UTCRecord, VersionRef, require_utc
from .text import SpanRef


class ArticleVersion(UTCRecord):
    kind: Literal["article_version"] = "article_version"
    url: NonEmpty
    raw_artifact_id: Id | None
    raw_text_id: Id | None
    cleaned_text_id: Id | None
    title: str | None
    heading_spans: tuple[SpanRef, ...]
    fetched_at: datetime | None
    content_sha256: Digest | None
    parser_version: VersionRef
    status: Literal["usable", "failed", "unusable"]
    reason: NonEmpty | None
    previous_version_id: Id | None = None

    @field_validator("fetched_at")
    @classmethod
    def utc_fetch(cls, value: datetime | None) -> datetime | None:
        return require_utc(value) if value is not None else None

    @model_validator(mode="after")
    def usable_content(self) -> Self:
        if self.status == "usable" and any(
            value is None
            for value in (
                self.raw_artifact_id,
                self.raw_text_id,
                self.cleaned_text_id,
                self.fetched_at,
                self.content_sha256,
            )
        ):
            raise ValueError("usable_article_requires_content_and_provenance")
        if self.status != "usable" and self.reason is None:
            raise ValueError("unusable_article_requires_reason")
        return self


class Passage(UTCRecord):
    kind: Literal["passage"] = "passage"
    article_version_id: Id
    order: NonNegative
    span: SpanRef
    heading_spans: tuple[SpanRef, ...]
    parent_passage_id: Id | None = None
    construction_version: VersionRef


class CorpusManifest(UTCRecord):
    kind: Literal["corpus_manifest"] = "corpus_manifest"
    article_version_ids: tuple[Id, ...]
    passage_ids: tuple[Id, ...]
    construction_version: VersionRef
    status: Literal["ready", "incomplete", "failed"]
    reason: NonEmpty | None

    @model_validator(mode="after")
    def manifest_state(self) -> Self:
        if self.status == "ready" and (not self.article_version_ids or not self.passage_ids):
            raise ValueError("ready_corpus_requires_articles_and_passages")
        if self.status != "ready" and self.reason is None:
            raise ValueError("incomplete_corpus_requires_reason")
        return self
