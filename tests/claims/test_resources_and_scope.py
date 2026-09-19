import ast
from unittest.mock import patch

import pytest
from pydantic import JsonValue, TypeAdapter

from binfocheck.claims.config import ExtractionSettings
from binfocheck.claims.persistence import canonical
from binfocheck.claims.resources import ExtractionResources
from binfocheck.models.resources import schema_resource
from binfocheck.storage import MemoryStore
from tests.claims.helpers import ROOT, anchor, candidate, candidates, positive, seed_extraction
from tests.storage.helpers import success


def test_core_has_no_provider_dependencies() -> None:
    for path in (ROOT / "src/binfocheck/claims").glob("*.py"):
        if path.name == "integration.py":
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("binfocheck.models", "openai", "http"))
            if isinstance(node, ast.Import):
                assert all(
                    not n.name.startswith(("binfocheck.models", "openai", "http"))
                    for n in node.names
                )


def test_frozen_resources_schema_subset_and_hashes() -> None:
    resources = ExtractionResources(ROOT)
    assert len(resources.refs) == 11
    for name, ref in resources.refs.items():
        raw = resources.resolve(ref)
        assert raw
        if name.endswith("-output"):
            schema_resource(raw)
    # Altering a pinned byte fails, never silently updates a resource hash.
    resources.data["t04-mixed"] += b"changed"
    from binfocheck.claims.errors import ExtractionError

    with pytest.raises(ExtractionError):
        resources.resolve(resources.ref("mixed"))


def test_frozen_unicode_offsets() -> None:
    cases = TypeAdapter(list[dict[str, str | int]]).validate_json(
        (ROOT / "tests/fixtures/claims/v1/spans.json").read_bytes()
    )
    for case in cases:
        text, quote, start, end = case["answer"], case["quote"], case["start"], case["end"]
        assert (
            isinstance(text, str)
            and isinstance(quote, str)
            and isinstance(start, int)
            and isinstance(end, int)
        )
        assert text[start:end] == quote
        store = MemoryStore()

        def reply(
            stage: str,
            state: dict[str, JsonValue],
            quote: str = quote,
            start: int = start,
            store: MemoryStore = store,
        ) -> str | dict[str, JsonValue]:
            return (
                candidates(candidate(store, state, quote, start=start))
                if stage == "F"
                else positive(stage)
            )

        req, ext, _ = seed_extraction(store, text, reply)
        claim = success(ext.extract_claims(req)).claims[0]
        assert (claim.original_span.start, claim.original_span.end) == (start, end)


def test_governing_qualifier_context_rejects_short_quote() -> None:
    store = MemoryStore()

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "F":
            return candidates(
                candidate(
                    store, state, "bleibt die Tür geschlossen.", "Die Tür bleibt geschlossen."
                )
            )
        if stage == "H.faithfulness":
            context = state["context"]
            assert isinstance(context, list)
            assert any(
                isinstance(c, dict) and c["text"] == "Bei Frost bleibt die Tür geschlossen."
                for c in context
            )
            return "unfaithful"
        if stage in {"H.atomicity", "H.self_containment"}:
            assert "context" not in state
        return positive(stage)

    req, ext, _ = seed_extraction(store, "Bei Frost bleibt die Tür geschlossen.", reply)
    result = success(ext.extract_claims(req))
    assert not result.claims and result.issues[0].issue == "invalid"


def test_question_cannot_inject_fact() -> None:
    store = MemoryStore()

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "D":
            return "resolvable_from_context"
        if stage == "E":
            return {
                "status": "clarified",
                "clarified_text": "Der giftige Ball ist rot.",
                "anchors": [anchor(store, state, "Er ist rot.")],
                "bindings": [
                    {
                        "reference": "Er",
                        "resolved_reference": "Der giftige Ball",
                        "answer_context_unit_ids": [],
                        "question_reference_used": True,
                    }
                ],
                "reason_code": "none",
            }
        if stage == "F":
            value = candidate(store, state, "Er ist rot.", "Der giftige Ball ist rot.")
            value["consumed_binding_indices"] = [0]
            return candidates(value)
        if stage == "H.faithfulness":
            assert "question" in state
            return "unfaithful"
        return positive(stage)

    req, ext, double = seed_extraction(
        store, "Er ist rot.", reply, question="Welche Farbe hat der giftige Ball?"
    )
    result = success(ext.extract_claims(req))
    assert not result.claims and result.issues[-1].issue == "invalid"
    for stage, state, request in double.calls:
        if stage in {"B", "F"}:
            assert "question" not in state and "a-request" not in request.input_ids
        assert not set(request.input_ids).intersection(
            i for i in request.input_artifact_ids if "output" in i
        )


def test_missing_or_unused_question_binding_rejected() -> None:
    store = MemoryStore()

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "D":
            return "resolvable_from_context"
        if stage == "E":
            return {
                "status": "clarified",
                "clarified_text": "Der Ball ist rot.",
                "anchors": [anchor(store, state, "Der Ball ist rot.")],
                "bindings": [
                    {
                        "reference": "Ball",
                        "resolved_reference": "Ball",
                        "answer_context_unit_ids": [],
                        "question_reference_used": True,
                    }
                ],
                "reason_code": "none",
            }
        return positive(stage)

    req, ext, double = seed_extraction(store, "Der Ball ist rot.", reply)
    result = success(ext.extract_claims(req))
    assert not result.claims and result.issues[-1].issue == "invalid"
    assert all("question" not in state for _, state, _ in double.calls)


def test_h_budget_reserved_before_first_property() -> None:
    store = MemoryStore()

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        return candidates(candidate(store, state, "Rot.")) if stage == "F" else positive(stage)

    req, ext, double = seed_extraction(store, "Rot.", reply)
    settings = ExtractionSettings.model_validate_json(canonical(req.settings.values))
    settings = settings.model_copy(
        update={"limits": settings.limits.model_copy(update={"max_model_calls": 5})}
    )
    req = req.model_copy(update={"settings": settings.envelope(req.settings.version)})
    result = success(ext.extract_claims(req))
    assert not result.claims and len(result.issues) == 3 and len(double.calls) == 3


def test_unsupported_resource_fails_before_model() -> None:
    store = MemoryStore()
    req, ext, double = seed_extraction(store, "Rot.", lambda _stage, _state: "factual")
    with patch(
        "binfocheck.claims.integration.schema_resource", side_effect=ValueError("unsupported")
    ):
        assert ext.extract_claims(req).status == "failed"
    assert not double.calls
