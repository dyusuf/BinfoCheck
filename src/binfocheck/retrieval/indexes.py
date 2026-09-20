"""Pinned library adapters. JSON numeric state is stored through T11A, never pickle."""

from typing import Any, cast

import bm25s  # pyright: ignore[reportMissingTypeStubs]
import numpy as np
from llama_index.core.vector_stores.simple import SimpleVectorStore, SimpleVectorStoreData
from llama_index.core.vector_stores.types import VectorStoreQuery

from binfocheck.domain.common import Contract, Finite

from .embeddings import validate_vectors
from .errors import check


class LexicalState(Contract):
    format: str = "t07-bm25s/1"
    vocabulary: dict[str, int]
    data: tuple[Finite, ...]
    indices: tuple[int, ...]
    indptr: tuple[int, ...]
    num_docs: int


def build_lexical(rows: tuple[tuple[str, ...], ...]) -> LexicalState:
    vocab = {word: i for i, word in enumerate(sorted({t for row in rows for t in row} | {""}))}
    ids = [[vocab[token] for token in row] for row in rows]
    bm = cast(Any, bm25s).BM25(k1=1.2, b=0.75, method="lucene", backend="numpy", dtype="float32")
    # Explicit vocabulary avoids bm25s's set-dependent vocabulary assignment.
    bm.index((ids, vocab), show_progress=False)
    return LexicalState(
        vocabulary=vocab,
        data=tuple(float(v) for v in bm.scores["data"]),
        indices=tuple(int(v) for v in bm.scores["indices"]),
        indptr=tuple(int(v) for v in bm.scores["indptr"]),
        num_docs=len(rows),
    )


def restore_lexical(state: LexicalState) -> Any:
    check(state.format == "t07-bm25s/1" and state.num_docs > 0, "invalid_lexical_state")
    check(
        sorted(state.vocabulary.values()) == list(range(len(state.vocabulary))),
        "invalid_vocabulary",
    )
    check(
        len(state.indptr) == len(state.vocabulary) + 1
        and state.indptr[0] == 0
        and state.indptr[-1] == len(state.data) == len(state.indices)
        and all(a <= b for a, b in zip(state.indptr, state.indptr[1:], strict=False))
        and all(0 <= i < state.num_docs for i in state.indices)
        and all(value >= 0 for value in state.data),
        "invalid_lexical_state",
    )
    bm = cast(Any, bm25s).BM25(k1=1.2, b=0.75, method="lucene", backend="numpy", dtype="float32")
    bm.nonoccurrence_array = None
    bm.vocab_dict = dict(state.vocabulary)
    bm.unique_token_ids_set = set(state.vocabulary.values())
    bm.scores = {
        "data": np.asarray(state.data, dtype=np.float32),
        "indices": np.asarray(state.indices, dtype=np.int32),
        "indptr": np.asarray(state.indptr, dtype=np.int32),
        "num_docs": state.num_docs,
    }
    return bm


def lexical_scores(state: LexicalState, query: tuple[str, ...]) -> list[float]:
    bm = restore_lexical(state)
    if not query:
        return [0.0] * state.num_docs
    return [float(v) for v in bm.get_scores(list(query))]


def semantic_scores(
    ids: tuple[str, ...],
    rows: tuple[tuple[float, ...], ...],
    query: tuple[float, ...],
    dimensions: int,
) -> list[float]:
    validate_vectors(rows, len(ids), dimensions)
    validate_vectors((query,), 1, dimensions)
    store = SimpleVectorStore(
        data=SimpleVectorStoreData(
            embedding_dict={id: list(row) for id, row in zip(ids, rows, strict=True)}
        )
    )
    result = store.query(VectorStoreQuery(query_embedding=list(query), similarity_top_k=len(ids)))
    check(result.ids is not None and result.similarities is not None, "semantic_result_missing")
    assert result.ids is not None and result.similarities is not None
    check(
        set(result.ids) == set(ids) and len(result.ids) == len(ids), "semantic_membership_mismatch"
    )
    scores = dict(zip(result.ids, result.similarities, strict=True))
    return [float(scores[id]) for id in ids]
