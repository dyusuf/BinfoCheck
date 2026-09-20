"""Approved D05/D06 values and canonical identity helpers."""

import hashlib
import json
from importlib.metadata import version
from typing import Literal

from binfocheck.domain.common import Contract, Settings, VersionRef

MODEL = "microsoft/harrier-oss-v1-0.6b"
REVISION = "f9b9dc8d367d443f2479d27aa5d8d2850c0774ee"
INSTRUCTION = "Given a German health claim, retrieve passages relevant to evaluating the claim."
PACKAGES = {
    "bm25s": "0.2.14",
    "numpy": "2.5.3",
    "scipy": "1.18.1",
    "spacy": "3.8.16",
    "llama-index-core": "0.14.24",
}
LOCAL_PACKAGES = {
    "sentence-transformers": "5.2.0",
    "transformers": "4.57.3",
    "torch": "2.9.1",
    "tokenizers": "0.22.2",
    "huggingface-hub": "0.36.2",
    "safetensors": "0.8.0",
}


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def identity(role: str, value: object) -> str:
    return "retrieval-" + role + "-" + digest(canonical(value))


def version_ref(name: str, values: object) -> VersionRef:
    return VersionRef(name=name, version="1", sha256=digest(canonical(values)))


LEXICAL = Settings(
    version=version_ref("t07-german-lexical", PACKAGES),
    values={
        "tokenizer": "spacy.blank.de+protected/1",
        "normalization": "NFC+lower",
        "stemming": False,
        "stopwords": False,
        "method": "lucene",
        "k1": 1.2,
        "b": 0.75,
        "dtype": "float32",
        "backend": "numpy",
    },
)
POLICY = Settings(
    version=version_ref(
        "t07-retrieval",
        {
            "k": 50,
            "rrf": 60,
            "context": 1,
            "representation": 1,
            "instruction": INSTRUCTION,
        },
    ),
    values={
        "semantic_k": 50,
        "lexical_k": 50,
        "rrf_c": 60,
        "weights": [1, 1],
        "ties": "passage_id",
        "fused_cutoff": None,
        "context": "immediate-same-section/1",
    },
)
INDEX_VERSION = version_ref(
    "t07-index", {"packages": PACKAGES, "lexical": LEXICAL.model_dump(mode="json")}
)


class EmbeddingSpec(Contract):
    model: str = MODEL
    revision: str = REVISION
    dimensions: int = 1024
    max_tokens: int = 32768
    implementation: Literal["sentence-transformers", "synthetic"] = "sentence-transformers"
    software: dict[str, str] = LOCAL_PACKAGES
    device: str = "cpu"
    dtype: str = "float32"
    representation: Literal["t07-representation/1"] = "t07-representation/1"

    def validate_supported(self) -> None:
        from .errors import check

        check(self.dimensions > 0 and self.max_tokens > 0, "invalid_embedding_spec")
        if self.implementation == "sentence-transformers":
            check(self == EmbeddingSpec(), "unsupported_embedding_spec")
        else:
            check(
                self.model.startswith("synthetic-") and bool(self.revision), "invalid_fixture_model"
            )


def verify_packages() -> None:
    from .errors import check

    for name, expected in PACKAGES.items():
        check(version(name) == expected, "package_version_mismatch")
