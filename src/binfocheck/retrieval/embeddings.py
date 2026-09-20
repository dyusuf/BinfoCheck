"""Explicit local preparation only. Importing this module never imports a model."""

import importlib
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np

from .config import LOCAL_PACKAGES, MODEL, REVISION, EmbeddingSpec
from .errors import RetrievalError, check


class Embedder(Protocol):
    @property
    def spec(self) -> EmbeddingSpec: ...
    def count_tokens(self, text: str) -> int: ...
    def encode(self, texts: Sequence[str]) -> list[list[float]]: ...


def validate_vectors(vectors: Sequence[Sequence[float]], count: int, dimensions: int) -> None:
    check(len(vectors) == count, "embedding_count_mismatch")
    for row in vectors:
        check(len(row) == dimensions, "embedding_dimension_mismatch")
        array = np.asarray(row, dtype=np.float64)
        check(bool(np.isfinite(array).all()), "embedding_nonfinite")
        norm = float(np.linalg.norm(array))
        check(np.isfinite(norm) and norm > 0, "embedding_zero_or_invalid_norm")


def preflight(embedder: Embedder, inputs: Sequence[tuple[str, str]]) -> tuple[int, ...]:
    embedder.spec.validate_supported()
    lengths: list[int] = []
    for id, text in inputs:
        check(bool(text.strip()), "empty_embedding_input", id)
        length = embedder.count_tokens(text)
        check(type(length) is int and length > 0, "invalid_token_count", id)
        check(length <= embedder.spec.max_tokens, "embedding_input_overflow", id)
        lengths.append(length)
    return tuple(lengths)


class LocalHarrier:
    """Explicitly opened from a pre-provisioned immutable HF snapshot directory."""

    spec = EmbeddingSpec()

    def __init__(self, model: Any) -> None:
        self._model = model

    @classmethod
    def open(cls, cache_root: Path) -> "LocalHarrier":
        snapshot = cache_root / ("models--" + MODEL.replace("/", "--")) / "snapshots" / REVISION
        required = (
            "model.safetensors",
            "modules.json",
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "config_sentence_transformers.json",
            "1_Pooling/config.json",
        )
        check(all((snapshot / name).is_file() for name in required), "local_model_unavailable")
        try:
            for name, expected in LOCAL_PACKAGES.items():
                check(version(name).split("+")[0] == expected, "local_package_version_mismatch")
        except PackageNotFoundError:
            raise RetrievalError("local_model_software_unavailable") from None
        # Imports/load occur only here, never during ordinary load/retrieve/replay.
        torch = importlib.import_module("torch")
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        factory = importlib.import_module("sentence_transformers").SentenceTransformer
        model = factory(
            str(snapshot),
            revision=REVISION,
            device="cpu",
            local_files_only=True,
            trust_remote_code=False,
            token=False,
            truncate_dim=None,
            model_kwargs={
                "torch_dtype": torch.float32,
                "attn_implementation": "eager",
                "local_files_only": True,
            },
            tokenizer_kwargs={"local_files_only": True},
            config_kwargs={"local_files_only": True},
        )
        check(
            model.get_sentence_embedding_dimension() == cls.spec.dimensions,
            "embedding_dimension_mismatch",
        )
        check(model.tokenizer.model_max_length >= cls.spec.max_tokens, "model_input_limit_mismatch")
        model.max_seq_length = cls.spec.max_tokens
        model.default_prompt_name = None
        model.eval()
        return cls(model)

    def count_tokens(self, text: str) -> int:
        encoded = self._model.tokenizer(
            text,
            add_special_tokens=True,
            truncation=False,
            padding=False,
            return_attention_mask=False,
        )
        return len(encoded["input_ids"])

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        preflight(self, [(str(i), text) for i, text in enumerate(texts)])
        check(self._model.max_seq_length == self.spec.max_tokens, "model_input_limit_mismatch")
        torch = importlib.import_module("torch")
        result: list[list[float]] = []
        # SentenceTransformer.encode tokenization strips source whitespace. Feed exact
        # tokenizer features to its forward/pooling pipeline instead, one input at a time.
        with torch.inference_mode():
            for text in texts:
                features = self._model.tokenizer(
                    text,
                    add_special_tokens=True,
                    truncation=False,
                    padding=False,
                    return_attention_mask=True,
                    return_tensors="pt",
                )
                check(
                    int(features["attention_mask"].sum()) == self.count_tokens(text),
                    "embedding_token_count_mismatch",
                )
                values = self._model.forward(features)["sentence_embedding"]
                values = torch.nn.functional.normalize(values, p=2, dim=1)
                result.extend(cast(list[list[float]], values.cpu().tolist()))
        validate_vectors(result, len(texts), self.spec.dimensions)
        return result
