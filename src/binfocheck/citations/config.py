"""Pinned T05 rules and settings within the unchanged shared Settings envelope."""

import hashlib
import json
from importlib.resources import files
from typing import Literal

from binfocheck.domain.common import CONTRACT_VALIDATION_VERSION, Contract, Id, Settings, VersionRef


class Rules(Contract):
    name: Literal["t05-citation-mapping"]
    version: Literal["1"]
    scope_version: Literal["sentence-terminal-full-coverage/1"]
    host_version: Literal["ascii-exact-allowlist/1"]
    audit_version: Literal["1"]
    normalizer_name: Literal["dataforseo-ai-mode-normalizer"]
    normalizer_version: Literal["1"]
    allowed_hosts: tuple[str, ...]
    schemes: tuple[str, ...]
    horizontal_whitespace: str
    terminal_characters: str
    unsupported_characters: str
    max_references: int
    max_linked_records: int


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(role: str, value: object) -> str:
    return "citation-" + role + "-" + digest(canonical(value))


RULES = Rules.model_validate_json(files(__package__).joinpath("rules_v1.json").read_bytes())
CONFIGURATION = {
    "rules": RULES.model_dump(mode="json"),
    "contract_validation_version": CONTRACT_VALIDATION_VERSION,
    "wire_schema_version": "1",
}
VERSION = VersionRef(
    name=RULES.name, version=RULES.version, sha256=digest(canonical(CONFIGURATION))
)


class CitationSettings(Contract):
    index_artifact_id: Id

    def envelope(self) -> Settings:
        return Settings(version=VERSION, values=self.model_dump(mode="json"))
