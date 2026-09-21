"""Explicit extraction resource bytes; paths are trusted composition configuration."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from binfocheck.domain.common import Contract, VersionRef

from .errors import check
from .persistence import canonical, digest
from .policy import POLICY


class Entry(Contract):
    path: str
    name: str
    version: str
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ExtractionResources:
    def __init__(self, root: Path, version: Literal["1", "2", "3", "4"] = "4") -> None:
        check(version in ("1", "2", "3", "4"), "unsupported_resource_version")
        raw = (root / f"prompts/extraction/v{version}/manifest.json").read_bytes()
        entries = TypeAdapter(tuple[Entry, ...]).validate_json(raw)
        self.refs: dict[str, VersionRef] = {}
        self.data: dict[str, bytes] = {}
        for entry in entries:
            check(entry.name not in self.refs, "duplicate_resource")
            path = (root / entry.path).resolve()
            check(path.is_relative_to(root.resolve()), "invalid_resource_path")
            content = path.read_bytes()
            check(digest(content) == entry.sha256, "resource_hash_mismatch")
            self.refs[entry.name] = VersionRef(
                name=entry.name, version=entry.version, sha256=entry.sha256
            )
            self.data[entry.name] = content
        self.version = VersionRef(
            name="t04-extraction-resources", version=version, sha256=digest(raw)
        )
        self.policy = VersionRef(
            name="t04-extraction-policy", version="1", sha256=digest(canonical(POLICY))
        )

    def ref(self, name: str) -> VersionRef:
        return self.refs["t04-" + name]

    def resolve(self, reference: VersionRef) -> bytes:
        check(self.refs.get(reference.name) == reference, "resource_version_mismatch")
        data = self.data[reference.name]
        check(digest(data) == reference.sha256, "resource_hash_mismatch")
        return data
