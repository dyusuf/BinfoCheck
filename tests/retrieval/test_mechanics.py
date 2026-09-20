from fractions import Fraction

import pytest

from binfocheck.retrieval.errors import RetrievalError
from binfocheck.retrieval.fusion import fuse, top_path
from binfocheck.retrieval.indexes import build_lexical, lexical_scores, semantic_scores
from binfocheck.retrieval.representations import tokens


def test_german_tokens_preserve_qualifiers_and_numbers() -> None:
    assert tokens("Nicht nur 3,5 mmol/l, kein Wert < 70 mg/dl und ≥ 5 %!") == (
        "nicht",
        "nur",
        "3,5",
        "mmol/l",
        "kein",
        "wert",
        "<",
        "70",
        "mg/dl",
        "und",
        "≥",
        "5",
        "%",
    )
    assert tokens("ÄPFEL A\u0308pfel Straße 0 1 2 3,5 3.5 1.000 5–10 5 bis 10 <= >=") == (
        "äpfel",
        "äpfel",
        "straße",
        "0",
        "1",
        "2",
        "3,5",
        "3.5",
        "1.000",
        "5",
        "10",
        "5",
        "bis",
        "10",
        "<=",
        ">=",
    )
    assert tokens("!!!") == ()


def test_library_lexical_roundtrip_numeric_and_oov() -> None:
    state = build_lexical((tokens("nicht 3,5 mmol/l"), tokens("3.5 mg/dl"), tokens("nur 0")))
    for term, expected in [("3,5", 0), ("3.5", 1), ("0", 2), ("nicht", 0)]:
        scores = lexical_scores(state, tokens(term))
        assert scores[expected] > 0
        assert sum(v > 0 for v in scores) == 1
    assert lexical_scores(state, ("unknown",)) == [0.0] * 3
    assert lexical_scores(state, ()) == [0.0] * 3
    assert build_lexical((tokens("nur 0"),)) == build_lexical((tokens("nur 0"),))


def test_rrf_hand_calculation_and_scale_independence() -> None:
    semantic = top_path(("A", "B"), [0.9, 0.1], "semantic")
    lexical = top_path(("B", "C"), [100.0, 1.0], "lexical")
    fused = fuse((semantic, lexical))
    assert [h.passage_id for h in fused] == ["B", "A", "C"]
    assert fused[0].fused_score == float(Fraction(1, 61) + Fraction(1, 62))
    assert [r.rank for r in fused[0].path_ranks] == [2, 1]
    changed = fuse((top_path(("A", "B"), [1000.0, 999.0], "semantic"), lexical))
    assert [h.passage_id for h in changed] == [h.passage_id for h in fused]
    tie = fuse((top_path(("Z",), [1.0], "semantic"), top_path(("A",), [2.0], "lexical")))
    assert [h.passage_id for h in tie] == ["A", "Z"]


def test_independent_top50_full_union_and_ties() -> None:
    ids = tuple(f"p{i:03}" for i in range(120))
    a = top_path(ids, [float(120 - i) for i in range(120)], "semantic")
    b = top_path(ids, [float(i + 1) for i in range(120)], "lexical")
    union = fuse((a, b))
    assert len(a.hits) == len(b.hits) == 50
    assert a.omitted == b.omitted == 70
    assert len(union) == 100
    assert {h.passage_id for h in union} == {h.passage_id for h in (*a.hits, *b.hits)}
    tied = top_path(tuple(reversed(ids)), [1.0] * 120, "semantic")
    assert [h.passage_id for h in tied.hits] == list(ids[:50])
    assert tied.tied_at_boundary
    assert top_path(ids, [0.0] * 120, "lexical").hits == ()
    assert len(top_path(ids, [-1.0] * 120, "semantic").hits) == 50


def test_path_duplicates_and_nonfinite_rejected() -> None:
    with pytest.raises(RetrievalError, match="membership"):
        top_path(("a", "a"), [1.0, 2.0], "semantic")
    with pytest.raises(RetrievalError, match="scores"):
        top_path(("a",), [float("nan")], "lexical")
    path = top_path(("a",), [1.0], "lexical")
    with pytest.raises(RetrievalError, match="duplicate_path"):
        fuse((path, path))


def test_explicit_vector_search_has_no_embedding_model() -> None:
    scores = semantic_scores(("a", "b"), ((1.0, 0.0), (-1.0, 0.0)), (1.0, 0.0), 2)
    assert scores == [1.0, -1.0]
