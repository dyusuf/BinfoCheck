"""Rank-only fusion and independently bounded path accounting."""

import math
from fractions import Fraction
from typing import Literal

from binfocheck.domain.common import Contract, Finite
from binfocheck.domain.retrieval import PathRank

from .errors import check


class Hit(Contract):
    passage_id: str
    rank: PathRank


class PathTrace(Contract):
    path: Literal["semantic", "lexical"]
    scored: int
    eligible: int
    requested_k: int = 50
    omitted: int
    tied_at_boundary: bool
    hits: tuple[Hit, ...]


class Fused(Contract):
    passage_id: str
    path_ranks: tuple[PathRank, ...]
    fused_score: Finite
    denominators: tuple[int, ...]


def top_path(
    ids: tuple[str, ...], scores: list[float], path: Literal["semantic", "lexical"]
) -> PathTrace:
    check(len(ids) == len(scores) and len(set(ids)) == len(ids), "path_membership_mismatch")
    check(all(math.isfinite(score) for score in scores), "invalid_path_scores")
    eligible = [
        (id, score)
        for id, score in zip(ids, scores, strict=True)
        if path == "semantic" or score > 0
    ]
    eligible.sort(key=lambda item: (-item[1], item[0]))
    chosen = eligible[:50]
    return PathTrace(
        path=path,
        scored=len(ids),
        eligible=len(eligible),
        omitted=max(0, len(eligible) - 50),
        tied_at_boundary=len(eligible) > 50 and eligible[49][1] == eligible[50][1],
        hits=tuple(
            Hit(passage_id=id, rank=PathRank(path=path, rank=i + 1, score=score))
            for i, (id, score) in enumerate(chosen)
        ),
    )


def fuse(paths: tuple[PathTrace, ...]) -> tuple[Fused, ...]:
    seen_paths: set[str] = set()
    ranks: dict[str, list[PathRank]] = {}
    for trace in paths:
        check(trace.path not in seen_paths, "duplicate_path")
        seen_paths.add(trace.path)
        seen: set[str] = set()
        for i, hit in enumerate(trace.hits):
            check(
                hit.passage_id not in seen
                and hit.rank.path == trace.path
                and hit.rank.rank == i + 1,
                "invalid_path_ranks",
            )
            seen.add(hit.passage_id)
            ranks.setdefault(hit.passage_id, []).append(hit.rank)
    exact = {
        id: sum((Fraction(1, 60 + r.rank) for r in rr), Fraction()) for id, rr in ranks.items()
    }
    return tuple(
        Fused(
            passage_id=id,
            path_ranks=tuple(sorted(ranks[id], key=lambda r: r.path != "semantic")),
            fused_score=float(exact[id]),
            denominators=tuple(60 + r.rank for r in ranks[id]),
        )
        for id in sorted(ranks, key=lambda id: (-exact[id], id))
    )
