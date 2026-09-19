"""Only T02 text settings; no lexical retrieval/passage configuration."""

import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field

from binfocheck.domain.common import Contract, Id, Settings, VersionRef

from .errors import TextError

SPACY_VERSION = "3.8.16"
INDEX_VERSION = VersionRef(name="t02-text-index", version="1")
CONTEXT_VERSION = VersionRef(name="t02-text-context", version="1")


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


class IndexSettings(Contract):
    language: Literal["de"] = "de"
    max_characters: Annotated[int, Field(ge=1, le=1_000_000)] = 100_000
    max_units: Annotated[int, Field(ge=1, le=50_000)] = 10_000

    def envelope(self) -> Settings:
        return Settings(version=INDEX_VERSION, values=self.model_dump(mode="json"))


class ContextSettings(Contract):
    index_artifact_id: Id
    before: Annotated[int, Field(ge=0, le=10)] = 1
    after: Annotated[int, Field(ge=0, le=10)] = 1
    include_headings: bool = True
    clip_at_heading: bool = True
    max_units: Annotated[int, Field(ge=1, le=1000)] = 200

    def envelope(self) -> Settings:
        return Settings(version=CONTEXT_VERSION, values=self.model_dump(mode="json"))


def index_settings(settings: Settings) -> IndexSettings:
    try:
        if settings.version != INDEX_VERSION:
            raise ValueError("version")
        return IndexSettings.model_validate(settings.values)
    except ValueError:
        raise TextError("invalid_index_settings") from None


def context_settings(settings: Settings) -> ContextSettings:
    try:
        if settings.version != CONTEXT_VERSION:
            raise ValueError("version")
        return ContextSettings.model_validate(settings.values)
    except ValueError:
        raise TextError("invalid_context_settings") from None
