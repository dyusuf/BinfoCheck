from pathlib import Path

import pytest
from pydantic import JsonValue

from binfocheck.claims.artifacts import FinalAudit
from binfocheck.claims.context import prepare_inputs
from binfocheck.claims.persistence import closure, identity, load
from binfocheck.domain.interfaces import ExtractionResult
from binfocheck.storage import MemoryStore, SQLiteStore
from tests.claims.helpers import anchor, candidate, candidates, positive, seed_extraction
from tests.storage.helpers import success


@pytest.mark.parametrize("persistent", [False, True])
def test_factual_exact_minimal_and_idempotent(tmp_path: Path, persistent: bool) -> None:
    store = SQLiteStore(tmp_path / "store") if persistent else MemoryStore()
    text = "Der Ball ist rot. Die Kiste wiegt 4 kg. Das Tor ist offen."

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        return (
            candidates(candidate(store, state, "Die Kiste wiegt 4 kg."))
            if stage == "F"
            else positive(stage)
        )

    request, extractor, double = seed_extraction(store, text, reply)

    # Runtime must never discover evidence by scanning.
    def no_scan(*args: object, **kwargs: object) -> None:
        raise AssertionError("Evidence scanning forbidden")

    from unittest.mock import patch

    with patch.object(store, "list_records", no_scan):
        outcome = extractor.extract_claims(request)
        result = success(outcome)
        assert len(result.claims) == 1
        claim = result.claims[0]
        assert (claim.original_span.start, claim.original_span.end) == (18, 39)
        assert claim.original_span.exact_text == "Die Kiste wiegt 4 kg."
        assert len(claim.decision_ids) == 6
        assert [s for s, _, _ in double.calls] == [
            "B",
            "D",
            "F",
            "H.faithfulness",
            "H.atomicity",
            "H.self_containment",
        ]
        for _, state, req in double.calls:
            assert "question" not in state and "context" not in state
            assert "a-request" not in req.input_ids
        assert extractor.extract_claims(request) == outcome
        assert len(double.calls) == 6
        closure(store, store, result.claims)
    store.close()
    if persistent:
        with SQLiteStore(tmp_path / "store") as reopened:
            assert closure(reopened, reopened, result.claims)


@pytest.mark.parametrize("label,kind", [("nonfactual", "excluded"), ("uncertain", "unresolved")])
def test_selection_exclusion(label: str, kind: str) -> None:
    store = MemoryStore()
    request, extractor, double = seed_extraction(store, "Guten Tag!", lambda _stage, _state: label)
    result = success(extractor.extract_claims(request))
    assert not result.claims and result.issues[0].issue == kind
    assert len(double.calls) == 1


@pytest.mark.parametrize("persist", [False, True])
def test_all_failed_is_complete_audit(persist: bool) -> None:
    store = MemoryStore()
    request, extractor, double = seed_extraction(
        store, "Der Ball ist rot.\n\nDas Tor ist offen.", lambda _stage, _state: "factual"
    )
    double.failure, double.persist_failure = "synthetic_failure", persist
    outcome = extractor.extract_claims(request)
    result = success(outcome)
    assert outcome.reason == "all_targets_failed" and not result.claims
    assert len(result.issues) == 2 and all(i.issue == "failed" for i in result.issues)
    assert all(bool(i.decision_ids) == persist for i in result.issues)
    key = prepare_inputs(store, store, request).work_key
    raw = load(store, identity("extraction-final", key))
    assert raw
    audit = FinalAudit.model_validate_json(raw)
    assert audit.assessment_state == "all_targets_failed"
    assert len(audit.target_accounting) == 2
    assert extractor.extract_claims(request) == outcome
    assert len(double.calls) == 2


@pytest.mark.parametrize(
    "stage,label,kind",
    [
        ("D", "unresolved", "unresolved"),
        ("H.faithfulness", "unfaithful", "invalid"),
        ("H.atomicity", "nonatomic", "invalid"),
        ("H.self_containment", "context_dependent", "invalid"),
        ("H.faithfulness", "uncertain", "unresolved"),
        ("H.atomicity", "uncertain", "unresolved"),
        ("H.self_containment", "uncertain", "unresolved"),
    ],
)
def test_independent_validation_and_uncertainty(stage: str, label: str, kind: str) -> None:
    store = MemoryStore()

    def reply(current: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if current == "F":
            return candidates(
                candidate(store, state, "Der Ball kann rot sein.", "Der Ball ist rot.")
            )
        return label if current == stage else positive(current)

    request, extractor, double = seed_extraction(store, "Der Ball kann rot sein.", reply)
    result = success(extractor.extract_claims(request))
    assert not result.claims and result.issues[-1].issue == kind
    if stage.startswith("H"):
        assert len(double.calls) == 6
        assert len(result.issues[-1].decision_ids) == 6
        for name, state, _ in double.calls:
            if name.startswith("H"):
                assert "label" not in state and "probabilities" not in state


def test_mixed_preserves_exclusions() -> None:
    store = MemoryStore()

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "B":
            return "mixed"
        if stage == "C":
            return {
                "status": "derived",
                "factual_text": "Der Ball ist rot.",
                "anchors": [anchor(store, state, "Der Ball ist rot.")],
                "excluded_quotes": [anchor(store, state, "Guten Tag!")],
                "reason_code": "none",
            }
        if stage == "F":
            return candidates(candidate(store, state, "Der Ball ist rot."))
        return positive(stage)

    request, extractor, double = seed_extraction(store, "Guten Tag! Der Ball ist rot.", reply)
    result = success(extractor.extract_claims(request))
    assert len(result.claims) == 1 and result.issues[0].issue == "excluded"
    assert (
        result.issues[0].original_span and result.issues[0].original_span.exact_text == "Guten Tag!"
    )
    for stage, state, _ in double.calls:
        if stage in {"B", "C"}:
            assert set(state) == {"source"}


def test_qualifier_expands_only_required_envelope() -> None:
    store = MemoryStore()

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "F":
            c = candidate(
                store, state, "bleibt die Tür geschlossen.", "Bei Frost bleibt die Tür geschlossen."
            )
            c["required_support"] = [anchor(store, state, "Bei Frost")]
            return candidates(c)
        return positive(stage)

    request, extractor, double = seed_extraction(
        store, "Bei Frost bleibt die Tür geschlossen. Der Ball ist rot.", reply
    )
    result = success(extractor.extract_claims(request))
    assert result.claims[0].original_span.exact_text == "Bei Frost bleibt die Tür geschlossen."
    for stage, state, _ in double.calls:
        if stage.startswith("H"):
            span = state["original_span"]
            assert (
                isinstance(span, dict)
                and span["exact_text"] == result.claims[0].original_span.exact_text
            )


def test_minimal_multisentence_and_shared_span() -> None:
    store = MemoryStore()
    quote = "Die Prüfung beginnt um 9 Uhr. Sie dauert 30 Minuten."

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "F":
            return candidates(candidate(store, state, quote, "Die Prüfung dauert 30 Minuten."))
        return positive(stage)

    request, extractor, _ = seed_extraction(store, quote + " Danach spielt Musik.", reply)
    claim = success(extractor.extract_claims(request)).claims[0]
    assert claim.original_span.exact_text == quote
    other = MemoryStore()
    shared = "Beide Kugeln, A und B, sind rot."

    def shared_reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "F":
            return candidates(
                candidate(other, state, shared, "Kugel A ist rot."),
                candidate(other, state, shared, "Kugel B ist rot."),
            )
        return positive(stage)

    req, ext, _ = seed_extraction(other, shared, shared_reply)
    a, b = success(ext.extract_claims(req)).claims
    assert (
        a.id != b.id and a.original_span == b.original_span and a.claim_group_id == b.claim_group_id
    )
    assert len(a.decision_ids) == len(b.decision_ids) == 6


@pytest.mark.parametrize("from_question", [False, True])
def test_reference_context_and_question_minimized(from_question: bool) -> None:
    store = MemoryStore()
    content = "Er ist rot." if from_question else "Der Ball liegt hier.\n\nEr ist rot."
    # The final paragraph is the only target; the preceding sentence is context.
    target_orders = None if from_question else (2,)

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "D":
            return "resolvable_from_context"
        if stage == "E":
            context = state.get("context", [])
            assert isinstance(context, list)
            ids = [c["unit_id"] for c in context if isinstance(c, dict)]
            return {
                "status": "clarified",
                "clarified_text": "Der Ball ist rot.",
                "anchors": [anchor(store, state, "Er ist rot.")],
                "bindings": [
                    {
                        "reference": "Er",
                        "resolved_reference": "Der Ball",
                        "answer_context_unit_ids": ids,
                        "question_reference_used": from_question,
                    }
                ],
                "reason_code": "none",
            }
        if stage == "F":
            c = candidate(store, state, "Er ist rot.", "Der Ball ist rot.")
            c["consumed_binding_indices"] = [0]
            return candidates(c)
        return positive(stage)

    req, ext, double = seed_extraction(store, content, reply, target_orders=target_orders)
    result = success(ext.extract_claims(req))
    assert len(result.claims) == 1
    for stage, state, _ in double.calls:
        if stage in {"B", "F"}:
            assert "question" not in state and "context" not in state
        if stage == "E":
            assert ("question" in state) == from_question
        if stage.startswith("H"):
            assert ("question" in state) == from_question


@pytest.mark.parametrize("invented", [False, True])
def test_ambiguous_or_invented_quote(invented: bool) -> None:
    store = MemoryStore()

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "F":
            c = candidate(store, state, "Rot.")
            a = c["anchor"]
            assert isinstance(a, dict)
            if invented:
                a["quote"] = "Blau."
            else:
                src = state["source"]
                assert isinstance(src, dict) and isinstance(src["unit_ids"], list)
                a.update(start=None, end=None, source_unit_ids=[src["unit_ids"][0]])
            return candidates(c)
        return positive(stage)

    req, ext, double = seed_extraction(store, "Rot. Rot.", reply)
    result = success(ext.extract_claims(req))
    assert not result.claims
    assert result.issues[0].issue == ("unlocatable" if invented else "ambiguous")
    assert result.issues[0].original_span is None
    assert len(double.calls) == 3


def test_unicode_repeated_distinct_locations() -> None:
    store = MemoryStore()
    text = "Äpfel 🍎 sind rot. Äpfel 🍎 sind rot."

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "F":
            return candidates(
                candidate(store, state, "sind rot.", "Die Äpfel sind rot.", 8),
                candidate(store, state, "sind rot.", "Die Äpfel sind rot.", 26),
            )
        return positive(stage)

    req, ext, _ = seed_extraction(store, text, reply)
    result = success(ext.extract_claims(req))
    assert [(c.original_span.start, c.original_span.end) for c in result.claims] == [
        (8, 17),
        (26, 35),
    ]
    assert len({c.id for c in result.claims}) == 2


def test_missing_accounting_rejected() -> None:
    from binfocheck.claims.errors import ExtractionError
    from binfocheck.claims.extractor import validate_accounting

    store = MemoryStore()
    req, _, _ = seed_extraction(store, "Rot.", lambda _stage, _state: "nonfactual")
    with pytest.raises(ExtractionError, match="incomplete_target_accounting"):
        validate_accounting(
            prepare_inputs(store, store, req), ExtractionResult(claims=(), issues=()), (), {}
        )


def test_same_located_candidate_with_different_anchor_encoding_is_accounted() -> None:
    store = MemoryStore()

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "F":
            explicit = candidate(store, state, "Rot.")
            implicit = candidate(store, state, "Rot.")
            a = implicit["anchor"]
            assert isinstance(a, dict)
            a["start"], a["end"] = None, None
            return candidates(explicit, implicit)
        return positive(stage)

    req, ext, double = seed_extraction(store, "Rot.", reply)
    result = success(ext.extract_claims(req))
    assert len(result.claims) == 1 and len(double.calls) == 6
    assert result.issues[0].issue == "excluded"
    assert result.issues[0].reason == "G.duplicate_candidate"
